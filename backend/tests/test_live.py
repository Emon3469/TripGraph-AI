import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage

from app.config import get_settings
from app.llm import LLMRouter

pytestmark = pytest.mark.live


def configured_endpoints():
    return list(LLMRouter(get_settings()).endpoints.values())


@pytest.mark.parametrize("endpoint", configured_endpoints(), ids=lambda e: f"{e.provider}:{e.model_name}")
async def test_provider_endpoint_responds(endpoint):
    response = await endpoint.model.ainvoke([HumanMessage(content="Reply with the single word OK")])
    assert str(response.content).strip()


async def test_router_has_at_least_one_working_provider():
    text, provider = await LLMRouter(get_settings()).ainvoke([HumanMessage(content="Say hello")])
    assert text and provider


def _events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def test_live_api_answer_plan_and_approve():
    from app.main import app

    with TestClient(app) as client:
        health = client.get("/health").json()
        assert health["status"] == "ok"

        answer = _events(client.post("/api/chat/stream", json={"message": "What is the weather in Paris today?"}))
        assert answer[-1]["type"] == "done", answer[-1]
        assert answer[-1]["result"]["answer"]

        blocked = _events(client.post("/api/chat/stream", json={"message": "Write a python function to sort a list"}))
        assert blocked[-1]["result"]["guardrail_allowed"] is False

        plan = _events(client.post("/api/chat/stream", json={"message": "Plan a 2 day trip to Kuala Lumpur under $500"}))
        thread = plan[0]["thread_id"]
        assert plan[-1]["type"] == "done", plan[-1]
        assert plan[-1]["result"]["requires_approval"] is True
        assert plan[-1]["result"]["itinerary"]

        final = _events(client.post("/api/chat/approve/stream", json={"thread_id": thread, "approved": True}))
        assert final[-1]["type"] == "done", final[-1]
        assert final[-1]["result"]["requires_approval"] is False
        assert len(final[-1]["result"]["answer"]) > 300
