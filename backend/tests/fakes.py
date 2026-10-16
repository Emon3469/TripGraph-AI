import json
from collections.abc import Callable, Iterator
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from app.llm import Endpoint, LLMRouter


class ScriptedModel(BaseChatModel):
    responder: Callable[[str, str], str]
    prompts: list[tuple[str, str]] = []
    fail_with: Exception | None = None
    fail_after_chunks: int | None = None

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def _texts(self, messages: list[BaseMessage]) -> tuple[str, str]:
        system = next((str(m.content) for m in messages if m.type == "system"), "")
        user = next((str(m.content) for m in reversed(messages) if m.type == "human"), "")
        self.prompts.append((system, user))
        return system, user

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        system, user = self._texts(messages)
        if self.fail_with is not None:
            raise self.fail_with
        text = self.responder(system, user)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    def _stream(
        self,
        messages,
        stop=None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        system, user = self._texts(messages)
        if self.fail_with is not None and self.fail_after_chunks is None:
            raise self.fail_with
        text = self.responder(system, user)
        for index, word in enumerate(text.split(" ")):
            if self.fail_after_chunks is not None and index >= self.fail_after_chunks:
                raise self.fail_with or RuntimeError("stream broke")
            chunk = word if index == 0 else f" {word}"
            yield ChatGenerationChunk(message=AIMessageChunk(content=chunk))


class StatusError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def make_router(specs: list[tuple[str, str, BaseChatModel]]) -> LLMRouter:
    router = LLMRouter.__new__(LLMRouter)
    router.endpoints = {}
    router.order = {"smart": [], "fast": []}
    for provider, name, model in specs:
        endpoint = Endpoint(provider=provider, model_name=name, model=model)
        router.endpoints[(provider, name)] = endpoint
        router.order["smart"].append(endpoint)
        router.order["fast"].append(endpoint)
    return router


def supervisor_json(query: str) -> dict[str, Any]:
    q = query.lower()
    if "python" in q or "homework" in q:
        return {"allowed": False, "reason": "Not travel related", "mode": "answer", "selected_agents": []}
    if q.strip() in ("hi", "hello", "thanks"):
        return {"allowed": True, "mode": "answer", "selected_agents": [], "trip_constraints": {}, "reasoning": "greeting"}
    if "weather" in q:
        return {
            "allowed": True,
            "mode": "answer",
            "selected_agents": ["weather_agent"],
            "trip_constraints": {"destination": "Tokyo", "weather_city": "Tokyo"},
            "reasoning": "weather question",
        }
    return {
        "allowed": True,
        "mode": "plan",
        "selected_agents": ["flight_agent", "hotel_agent", "weather_agent", "budget_agent"],
        "trip_constraints": {
            "destination": "Kuala Lumpur",
            "weather_city": "Kuala Lumpur",
            "origin": "Dhaka",
            "duration_days": 3,
            "budget": "$800",
        },
        "reasoning": "full trip plan",
    }


def travel_responder(system: str, user: str) -> str:
    s = system.lower()
    if "supervisor" in s:
        query = user.split("Latest user message:")[-1].strip()
        return "```json\n" + json.dumps(supervisor_json(query)) + "\n```"
    if "airline" in s:
        return "- Fly AirAsia DAC to KUL, about 3h 45m, around $180 return (estimate)."
    if "accommodation" in s:
        return "- Hotel Stripes, Bukit Bintang, $90-120 per night."
    if "budget analyst" in s:
        return "Total estimate: $720. Feasible within $800."
    if "draft itinerary" in user.lower():
        revised = "Requested changes:" in user
        return "## Draft: KL Food Trip\n### Day 1 - Street food\n- Jalan Alor" + (
            "\n### Day 3 - Malacca day trip" if revised else ""
        )
    if "final travel plan" in user.lower():
        return "## Trip Summary\nA 3 day food trip.\n## Estimated Budget\n| Item | Cost |\n|---|---|\n| Total | $720 |"
    return "Hello traveller! Where would you like to go?"
