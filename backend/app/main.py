import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import AliasChoices, BaseModel, Field

from app.config import get_settings
from app.limits import rate_limit
from app.llm import AllProvidersFailed, get_router
from app.service import ThreadNotAwaitingApproval, travel_service
from app.tools.mcp_client import WEATHER_MOUNT, get_hub
from app.tools.weather_server import mcp as weather_mcp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
for noisy in ("httpx", "httpcore", "mcp", "google_genai"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

logger = logging.getLogger("tripgraph")
settings = get_settings()

HEARTBEAT_SECONDS = 15


LOOPBACK = {"127.0.0.1", "::1", "localhost"}


class InternalWeatherServer:
    def __init__(self):
        self.app = None

    async def __call__(self, scope, receive, send):
        client = (scope.get("client") or ("", 0))[0]
        forwarded = any(name == b"x-forwarded-for" for name, _ in scope.get("headers", []))
        if scope["type"] == "http" and (self.app is None or forwarded or client not in LOOPBACK):
            await send({"type": "http.response.start", "status": 404, "headers": [(b"content-type", b"text/plain")]})
            await send({"type": "http.response.body", "body": b"Not Found"})
            return
        await self.app(scope, receive, send)


weather_server = InternalWeatherServer()


async def _warmup() -> None:
    await asyncio.sleep(2)
    await get_hub().warmup()


@asynccontextmanager
async def lifespan(_: FastAPI):
    weather_mcp._session_manager = None
    weather_server.app = weather_mcp.streamable_http_app()
    async with weather_mcp.session_manager.run():
        await travel_service.start()
        get_router()
        warmup = asyncio.create_task(_warmup())
        yield
        warmup.cancel()
        await get_hub().close()
        await travel_service.stop()


app = FastAPI(
    title=settings.app_name,
    description="Multi-agent travel planner with a supervisor, guardrails, MCP tools and human review.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
)

app.mount(WEATHER_MOUNT, weather_server)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=settings.allowed_origin_regex or None,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    thread_id: str | None = Field(default=None, max_length=100)


class ApprovalRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=100)
    approved: bool = Field(validation_alias=AliasChoices("approved", "approval"))
    feedback: str = Field(default="", max_length=2000)


def _validate_message(message: str) -> str:
    message = message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    return message


def _validate_review(request: ApprovalRequest) -> None:
    if not request.approved and not request.feedback.strip():
        raise HTTPException(
            status_code=400, detail="Tell us what to change when requesting a revision."
        )


async def _sse(events: AsyncIterator[dict]) -> AsyncIterator[str]:
    queue: asyncio.Queue = asyncio.Queue()
    finished = object()

    async def produce() -> None:
        try:
            async for event in events:
                await queue.put(event)
        except Exception:
            logger.exception("Event stream failed")
            await queue.put({"type": "error", "message": "Something went wrong. Please try again."})
        finally:
            await queue.put(finished)

    producer = asyncio.create_task(produce())
    try:
        yield ": connected\n\n"
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), HEARTBEAT_SECONDS)
            except TimeoutError:
                yield ": ping\n\n"
                continue
            if item is finished:
                break
            yield f"data: {json.dumps(item, ensure_ascii=False, default=str)}\n\n"
    finally:
        producer.cancel()


def _streaming(events: AsyncIterator[dict]) -> StreamingResponse:
    return StreamingResponse(
        _sse(events),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/")
async def root():
    return {"name": settings.app_name, "status": "ok", "health": "/health"}


@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {
        "status": "ok",
        "checkpointer": travel_service.checkpointer_kind,
        "llm_providers": get_router().status(),
        "mcp_servers": get_hub().status(),
    }


@app.post("/api/travel", dependencies=[Depends(rate_limit)])
async def travel(request: ChatRequest):
    message = _validate_message(request.message)
    try:
        result = await travel_service.run(message, request.thread_id)
    except AllProvidersFailed:
        raise HTTPException(status_code=503, detail="All AI providers are unavailable right now.")
    return {"success": True, **result}


@app.post("/api/travel/approve", dependencies=[Depends(rate_limit)])
async def approve(request: ApprovalRequest):
    _validate_review(request)
    try:
        result = await travel_service.resume(request.thread_id, request.approved, request.feedback)
    except ThreadNotAwaitingApproval:
        raise HTTPException(status_code=409, detail="This conversation has no draft awaiting review.")
    except AllProvidersFailed:
        raise HTTPException(status_code=503, detail="All AI providers are unavailable right now.")
    return {"success": True, **result}


@app.post("/api/chat/stream", dependencies=[Depends(rate_limit)])
async def chat_stream(request: ChatRequest):
    message = _validate_message(request.message)
    return _streaming(travel_service.stream(message, request.thread_id))


@app.post("/api/chat/approve/stream", dependencies=[Depends(rate_limit)])
async def approve_stream(request: ApprovalRequest):
    _validate_review(request)
    try:
        events = travel_service.stream_resume(request.thread_id, request.approved, request.feedback)
        first = await anext(events)
    except ThreadNotAwaitingApproval:
        raise HTTPException(status_code=409, detail="This conversation has no draft awaiting review.")

    async def replay():
        yield first
        async for event in events:
            yield event

    return _streaming(replay())


@app.get("/api/threads/{thread_id}")
async def thread(thread_id: str):
    return await travel_service.result(thread_id)
