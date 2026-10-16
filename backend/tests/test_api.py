import json

import pytest
from fastapi.testclient import TestClient

from app.limits import RateLimiter, client_ip, limiter
from app.main import app


@pytest.fixture
def client(router, tools):
    with TestClient(app) as test_client:
        yield test_client


def sse_events(response) -> list[dict]:
    assert response.headers["content-type"].startswith("text/event-stream")
    return [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]


def test_root_and_health(client):
    assert client.get("/").json()["status"] == "ok"
    health = client.get("/health").json()
    assert health["status"] == "ok"
    assert health["checkpointer"] == "memory"
    assert health["llm_providers"][0]["available"] is True
    assert client.head("/health").status_code == 200


def test_stream_chat_end_to_end(client):
    response = client.post("/api/chat/stream", json={"message": "hi"})
    assert response.status_code == 200
    assert response.headers["cache-control"].startswith("no-cache")
    assert response.headers["x-accel-buffering"] == "no"
    events = sse_events(response)
    assert events[0]["type"] == "meta"
    assert events[-1]["type"] == "done"
    assert "".join(e["content"] for e in events if e["type"] == "token").startswith("Hello")


def test_stream_plan_review_and_final(client):
    plan = sse_events(client.post("/api/chat/stream", json={"message": "Plan KL trip", "thread_id": "api-1"}))
    assert any(e["type"] == "interrupt" for e in plan)

    revise = client.post(
        "/api/chat/approve/stream",
        json={"thread_id": "api-1", "approved": False, "feedback": "Add Malacca"},
    )
    assert any(e["type"] == "interrupt" for e in sse_events(revise))

    final = sse_events(client.post("/api/chat/approve/stream", json={"thread_id": "api-1", "approval": True}))
    assert final[-1]["result"]["answer"].startswith("## Trip Summary")


def test_json_endpoints(client):
    first = client.post("/api/travel", json={"message": "Plan KL trip"}).json()
    assert first["success"] and first["requires_approval"]
    final = client.post("/api/travel/approve", json={"thread_id": first["thread_id"], "approved": True}).json()
    assert final["success"] and not final["requires_approval"]
    assert client.get(f"/api/threads/{first['thread_id']}").json()["answer"].startswith("## Trip Summary")


@pytest.mark.parametrize(
    ("path", "payload", "status"),
    [
        ("/api/chat/stream", {"message": "   "}, 400),
        ("/api/chat/stream", {}, 422),
        ("/api/chat/stream", {"message": "x" * 4001}, 422),
        ("/api/travel", {"message": ""}, 422),
        ("/api/chat/approve/stream", {"thread_id": "nope", "approved": True}, 409),
        ("/api/chat/approve/stream", {"thread_id": "nope", "approved": False}, 400),
        ("/api/chat/approve/stream", {"thread_id": "", "approved": True}, 422),
        ("/api/travel/approve", {"thread_id": "nope", "approved": True}, 409),
    ],
)
def test_validation_errors(client, path, payload, status):
    response = client.post(path, json=payload)
    assert response.status_code == status
    assert "detail" in response.json()


@pytest.mark.parametrize(
    ("origin", "allowed"),
    [
        ("http://localhost:3000", True),
        ("https://tripgraph-ai.vercel.app", True),
        ("https://tripgraph-git-main-me.vercel.app", True),
        ("https://evil.example.com", False),
        ("https://other-app.vercel.app", False),
    ],
)
def test_cors(client, origin, allowed):
    response = client.options(
        "/api/chat/stream",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"},
    )
    assert (response.headers.get("access-control-allow-origin") == origin) is allowed


def test_rate_limit_returns_429_with_retry_after(client, monkeypatch):
    monkeypatch.setattr(limiter, "windows", ((60.0, 2), (3600.0, 100)))
    headers = {"X-Forwarded-For": "203.0.113.9"}
    for _ in range(2):
        assert client.post("/api/chat/stream", json={"message": "hi"}, headers=headers).status_code == 200
    blocked = client.post("/api/chat/stream", json={"message": "hi"}, headers=headers)
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0
    other = client.post("/api/chat/stream", json={"message": "hi"}, headers={"X-Forwarded-For": "198.51.100.1"})
    assert other.status_code == 200


def test_rate_limiter_windows():
    rl = RateLimiter(per_minute=2, per_hour=3)
    assert rl.check("a") is None
    assert rl.check("a") is None
    assert rl.check("a") is not None
    rl.hits["a"][0] -= 120
    rl.hits["a"][1] -= 120
    assert rl.check("a") is None
    assert rl.check("a") is not None
    assert RateLimiter(0, 0).check("x") is None


def test_client_ip_prefers_forwarded_header():
    class Req:
        def __init__(self, headers, host):
            self.headers = headers
            self.client = type("C", (), {"host": host})()

    assert client_ip(Req({"x-forwarded-for": "1.2.3.4, 10.0.0.1"}, "10.0.0.1")) == "1.2.3.4"
    assert client_ip(Req({}, "127.0.0.1")) == "127.0.0.1"


def test_provider_outage_is_reported_in_stream(client, scripted, router):
    from tests.fakes import StatusError

    scripted.fail_with = StatusError("down", 503)
    events = sse_events(client.post("/api/chat/stream", json={"message": "hi"}))
    assert events[-1]["type"] == "error"
    assert client.post("/api/travel", json={"message": "hi"}).status_code == 503


async def test_stream_sends_keepalive_pings_during_slow_steps(monkeypatch):
    import asyncio

    from app import main

    monkeypatch.setattr(main, "HEARTBEAT_SECONDS", 0.05)

    async def slow():
        yield {"type": "meta"}
        await asyncio.sleep(0.2)
        yield {"type": "done"}

    chunks = [chunk async for chunk in main._sse(slow())]
    assert chunks[0] == ": connected\n\n"
    assert ": ping\n\n" in chunks
    assert chunks[-1] == 'data: {"type": "done"}\n\n'


async def test_stream_converts_unexpected_failures_to_error_event():
    from app import main

    async def broken():
        yield {"type": "meta"}
        raise RuntimeError("kaboom")

    chunks = [chunk async for chunk in main._sse(broken())]
    assert '"type": "error"' in chunks[-1]
    assert "kaboom" not in chunks[-1]


def test_internal_weather_mcp_server_is_not_publicly_reachable(client):
    public = client.post(
        "/internal/weather/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers={"X-Forwarded-For": "203.0.113.5"},
    )
    assert public.status_code == 404


async def test_internal_weather_mcp_server_serves_tools_to_the_backend():
    from langchain_mcp_adapters.tools import load_mcp_tools
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    import httpx
    from app.main import app, lifespan, weather_server

    async with lifespan(app):
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 5000))

        def factory(headers=None, timeout=None, auth=None):
            return httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000", headers=headers, timeout=timeout, auth=auth)

        async with streamablehttp_client(
            "http://127.0.0.1:8000/internal/weather/mcp", httpx_client_factory=factory
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await load_mcp_tools(session)
    assert {tool.name for tool in tools} == {"get_current_weather", "get_forecast"}
    assert weather_server.app is not None
