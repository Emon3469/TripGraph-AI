import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.config import get_settings
from app.graph import build_graph, new_turn
from app.llm import AllProvidersFailed

logger = logging.getLogger("tripgraph.service")


class ThreadNotAwaitingApproval(Exception):
    pass


class TravelService:
    def __init__(self):
        self.graph = None
        self.pool = None
        self.checkpointer_kind = "memory"
        self.slots = asyncio.Semaphore(get_settings().max_concurrent_runs)

    async def start(self) -> None:
        settings = get_settings()
        checkpointer = InMemorySaver()
        if settings.database_url:
            try:
                checkpointer = await self._postgres(settings.database_url)
                self.checkpointer_kind = "postgres"
            except Exception as error:
                logger.error("Postgres checkpointer unavailable, using memory: %s", error)
        self.graph = build_graph().compile(checkpointer=checkpointer)

    async def _postgres(self, url: str):
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg.rows import dict_row
        from psycopg_pool import AsyncConnectionPool

        if "sslmode=" not in url and "localhost" not in url and "127.0.0.1" not in url:
            url = f"{url}{'&' if '?' in url else '?'}sslmode=require"
        self.pool = AsyncConnectionPool(
            conninfo=url,
            min_size=1,
            max_size=5,
            open=False,
            check=AsyncConnectionPool.check_connection,
            kwargs={"autocommit": True, "prepare_threshold": None, "row_factory": dict_row},
        )
        await self.pool.open(wait=True, timeout=20)
        saver = AsyncPostgresSaver(self.pool)
        await saver.setup()
        return saver

    async def stop(self) -> None:
        if self.pool:
            await self.pool.close()

    @staticmethod
    def _config(thread_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": thread_id}, "recursion_limit": 40}

    async def result(self, thread_id: str) -> dict[str, Any]:
        snapshot = await self.graph.aget_state(self._config(thread_id))
        values = snapshot.values or {}
        pending = "human_approval" in (snapshot.next or ())
        answer = values.get("itinerary", "") if pending else values.get("final_response", "")
        if values.get("guardrail_allowed") is False:
            answer = values.get("final_response") or values.get("guardrail_reason", "")
        return {
            "thread_id": thread_id,
            "answer": answer,
            "requires_approval": pending,
            "approval_request": values.get("approval_request", "") if pending else "",
            "mode": values.get("mode"),
            "selected_agents": values.get("selected_agents", []),
            "trip_constraints": values.get("trip_constraints", {}),
            "supervisor_reasoning": values.get("supervisor_reasoning", ""),
            "guardrail_allowed": values.get("guardrail_allowed", True),
            "guardrail_reason": values.get("guardrail_reason", ""),
            "flight_results": values.get("flight_results", ""),
            "hotel_results": values.get("hotel_results", ""),
            "weather_results": values.get("weather_results", ""),
            "budget_results": values.get("budget_results", ""),
            "itinerary": values.get("itinerary", ""),
            "approved": values.get("approved"),
            "llm_calls": values.get("llm_calls", 0),
        }

    async def _resume_command(self, thread_id: str, approved: bool, feedback: str) -> Command | None:
        snapshot = await self.graph.aget_state(self._config(thread_id))
        pending = snapshot.next or ()
        if "human_approval" in pending:
            return Command(resume={"approved": approved, "feedback": feedback.strip()})
        if pending:
            return None
        raise ThreadNotAwaitingApproval(thread_id)

    async def run(self, message: str, thread_id: str | None = None) -> dict[str, Any]:
        thread_id = thread_id or uuid.uuid4().hex
        async with self.slots:
            await self.graph.ainvoke(new_turn(message), self._config(thread_id))
        return await self.result(thread_id)

    async def resume(self, thread_id: str, approved: bool, feedback: str = "") -> dict[str, Any]:
        command = await self._resume_command(thread_id, approved, feedback)
        async with self.slots:
            await self.graph.ainvoke(command, self._config(thread_id))
        return await self.result(thread_id)

    async def stream(self, message: str, thread_id: str | None = None) -> AsyncIterator[dict[str, Any]]:
        thread_id = thread_id or uuid.uuid4().hex
        async for event in self._stream(new_turn(message), thread_id):
            yield event

    async def stream_resume(
        self, thread_id: str, approved: bool, feedback: str = ""
    ) -> AsyncIterator[dict[str, Any]]:
        command = await self._resume_command(thread_id, approved, feedback)
        async for event in self._stream(command, thread_id):
            yield event

    async def _stream(self, payload: Any, thread_id: str) -> AsyncIterator[dict[str, Any]]:
        yield {"type": "meta", "thread_id": thread_id}
        try:
            if self.slots.locked():
                yield {"type": "status", "message": "High demand right now - your request is queued."}
            async with self.slots:
                async for chunk in self.graph.astream(
                    payload, self._config(thread_id), stream_mode="custom"
                ):
                    if isinstance(chunk, dict):
                        yield chunk
            result = await self.result(thread_id)
            if result["requires_approval"]:
                yield {
                    "type": "interrupt",
                    "thread_id": thread_id,
                    "approval_request": result["approval_request"],
                    "draft": result["itinerary"],
                }
            yield {"type": "done", "result": result}
        except AllProvidersFailed as error:
            logger.error("All LLM providers failed: %s", error)
            yield {
                "type": "error",
                "message": "All AI providers are unavailable right now. Please try again in a moment.",
            }
        except Exception as error:
            logger.exception("Graph run failed")
            yield {"type": "error", "message": f"Something went wrong: {type(error).__name__}"}


travel_service = TravelService()
