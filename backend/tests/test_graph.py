import pytest

from app.graph import RESEARCH_AGENTS, _parse_json
from app.service import ThreadNotAwaitingApproval, TravelService
from tests.fakes import StatusError


@pytest.fixture
async def service(router, tools):
    svc = TravelService()
    await svc.start()
    yield svc
    await svc.stop()


async def collect(stream):
    return [event async for event in stream]


def tokens(events, node=None):
    return "".join(e["content"] for e in events if e["type"] == "token" and (node is None or e["node"] == node))


def agent_events(events, status):
    return [e["agent"] for e in events if e["type"] == "agent" and e["status"] == status]


def test_parse_json_handles_fences_and_noise():
    assert _parse_json('Sure!\n```json\n{"a": 1}\n```') == {"a": 1}
    with pytest.raises(ValueError):
        _parse_json("no json here")


async def test_greeting_answers_directly_without_agents(service, tools):
    events = await collect(service.stream("hi", "t-greet"))

    assert events[0] == {"type": "meta", "thread_id": "t-greet"}
    assert agent_events(events, "done") == ["supervisor", "final_agent"]
    assert "Hello traveller" in tokens(events, "final_agent")
    done = events[-1]
    assert done["type"] == "done"
    assert done["result"]["requires_approval"] is False
    assert done["result"]["mode"] == "answer"
    assert tools["search"] == [] and tools["weather"] == []


async def test_guardrail_blocks_unrelated_requests(service, scripted):
    events = await collect(service.stream("write my python homework", "t-block"))

    assert "only help with travel planning" in tokens(events, "guardrail_blocked")
    result = events[-1]["result"]
    assert result["guardrail_allowed"] is False
    assert result["selected_agents"] == []
    assert len(scripted.prompts) == 1


async def test_weather_question_uses_only_weather_agent(service, tools):
    events = await collect(service.stream("What's the weather in Tokyo?", "t-weather"))

    assert set(agent_events(events, "done")) == {"supervisor", "weather_agent", "final_agent"}
    assert tools["weather"] == ["Tokyo"]
    assert events[-1]["result"]["weather_results"].startswith("Current conditions in Tokyo")


async def test_full_plan_runs_research_in_parallel_then_waits_for_review(service, tools):
    events = await collect(service.stream("Plan 3 days in Kuala Lumpur from Dhaka under $800", "t-plan"))

    running = agent_events(events, "running")
    first_done = next(i for i, e in enumerate(events) if e["type"] == "agent" and e["status"] == "done" and e["agent"] in RESEARCH_AGENTS)
    started_before_any_finished = [
        e["agent"] for e in events[:first_done] if e["type"] == "agent" and e["status"] == "running"
    ]
    assert set(RESEARCH_AGENTS) <= set(started_before_any_finished)
    assert running.index("budget_agent") > running.index("hotel_agent")

    interrupt = next(e for e in events if e["type"] == "interrupt")
    assert interrupt["draft"].startswith("## Draft")
    result = events[-1]["result"]
    assert result["requires_approval"] is True
    assert result["answer"] == result["itinerary"]
    assert result["trip_constraints"]["destination"] == "Kuala Lumpur"
    assert all(result[key] for key in ("flight_results", "hotel_results", "weather_results", "budget_results"))
    assert len(tools["search"]) == 2


async def test_revision_loop_then_approval_produces_final_plan(service, scripted):
    await collect(service.stream("Plan 3 days in Kuala Lumpur", "t-review"))

    revised = await collect(service.stream_resume("t-review", False, "Add a Malacca day trip"))
    assert agent_events(revised, "done") == ["itinerary_agent"]
    assert "Malacca day trip" in tokens(revised, "itinerary_agent")
    assert any("Add a Malacca day trip" in user for _, user in scripted.prompts)
    assert revised[-1]["result"]["requires_approval"] is True

    final = await collect(service.stream_resume("t-review", True))
    assert agent_events(final, "done") == ["final_agent"]
    result = final[-1]["result"]
    assert result["requires_approval"] is False
    assert result["approved"] is True
    assert result["answer"].startswith("## Trip Summary")
    assert "| Total | $720 |" in result["answer"]


async def test_resume_without_pending_review_is_rejected(service):
    await collect(service.stream("hi", "t-none"))
    with pytest.raises(ThreadNotAwaitingApproval):
        await collect(service.stream_resume("t-none", True))
    with pytest.raises(ThreadNotAwaitingApproval):
        await collect(service.stream_resume("never-existed", True))


async def test_follow_up_turn_receives_conversation_history(service, scripted):
    await collect(service.stream("hi", "t-memory"))
    await collect(service.stream("thanks", "t-memory"))
    supervisor_prompts = [user for system, user in scripted.prompts if "supervisor" in system.lower()]
    assert "User: hi" in supervisor_prompts[-1]
    assert "Assistant: Hello traveller" in supervisor_prompts[-1]


async def test_bad_supervisor_json_falls_back_to_full_workflow(service, scripted):
    original = scripted.responder
    scripted.responder = lambda s, u: "not json" if "supervisor" in s.lower() else original(s, u)
    events = await collect(service.stream("Plan something", "t-fallback"))
    result = events[-1]["result"]
    assert result["selected_agents"] == ["budget_agent"]
    assert result["requires_approval"] is True


async def test_tool_failures_degrade_gracefully(service, monkeypatch):
    from app import graph

    async def broken_search(*args, **kwargs):
        raise RuntimeError("search down")

    async def broken_weather(city):
        raise RuntimeError("weather down")

    monkeypatch.setattr(graph, "web_search", broken_search)
    monkeypatch.setattr(graph, "weather_report", broken_weather)

    events = await collect(service.stream("Plan 3 days in Kuala Lumpur", "t-tools"))
    result = events[-1]["result"]
    assert result["requires_approval"] is True
    assert "unavailable right now" in result["weather_results"]
    assert result["flight_results"]


async def test_provider_outage_reports_error_and_can_be_retried(service, scripted):
    await collect(service.stream("Plan 3 days in Kuala Lumpur", "t-outage"))

    scripted.fail_with = StatusError("service down", 503)
    failed = await collect(service.stream_resume("t-outage", True))
    assert failed[-1]["type"] == "error"
    assert "unavailable" in failed[-1]["message"]

    scripted.fail_with = None
    for endpoint in scripted_router_endpoints(service):
        endpoint.disabled_until = 0
    retried = await collect(service.stream_resume("t-outage", True))
    assert retried[-1]["result"]["answer"].startswith("## Trip Summary")


def scripted_router_endpoints(_service):
    from app.llm import get_router

    return list(get_router().endpoints.values())


async def test_non_streaming_run_and_resume(service):
    result = await service.run("Plan 3 days in Kuala Lumpur", "t-sync")
    assert result["requires_approval"] is True
    final = await service.resume("t-sync", True)
    assert final["answer"].startswith("## Trip Summary")


async def test_concurrent_runs_are_isolated(service):
    import asyncio

    results = await asyncio.gather(
        *(service.run(f"Plan 3 days in Kuala Lumpur #{i}", f"t-par-{i}") for i in range(8))
    )
    assert [r["thread_id"] for r in results] == [f"t-par-{i}" for i in range(8)]
    assert all(r["requires_approval"] for r in results)


async def test_research_agents_degrade_gracefully_when_models_are_down(service, scripted, tools):
    original = scripted.responder

    def responder(system, user):
        lowered = system.lower()
        if any(word in lowered for word in ("airline", "accommodation", "budget analyst")):
            raise StatusError("overloaded", 503)
        return original(system, user)

    scripted.responder = responder
    events = await collect(service.stream("Plan 3 days in Kuala Lumpur", "t-degrade"))
    result = events[-1]["result"]
    assert result["requires_approval"] is True
    assert result["flight_results"].startswith("Live flight search notes:")
    assert result["hotel_results"].startswith("Live hotel search notes:")
    assert "unavailable" in result["budget_results"]
