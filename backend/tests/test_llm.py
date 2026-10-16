import dataclasses
import time

import pytest
from langchain_core.messages import HumanMessage

from app.config import get_settings
from app.llm import AllProvidersFailed, LLMRouter, _classify, _clean, _retry_after, chunk_text
from tests.fakes import ScriptedModel, StatusError, make_router

MESSAGES = [HumanMessage(content="hello")]


def ok_model(text="fine"):
    return ScriptedModel(responder=lambda s, u: text)


def failing(error):
    return ScriptedModel(responder=lambda s, u: "never", fail_with=error)


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (StatusError("Incorrect API key provided", 401), "auth"),
        (StatusError("Your credit balance is too low to access the Anthropic API", 400), "auth"),
        (StatusError("Rate limit reached. Upgrade at console/settings/billing", 429), "rate_limit"),
        (Exception("429 RESOURCE_EXHAUSTED quota exceeded"), "rate_limit"),
        (StatusError("model is no longer available", 404), "model"),
        (StatusError("503 UNAVAILABLE high demand", 503), "transient"),
        (TimeoutError("timed out"), "transient"),
    ],
)
def test_error_classification(error, kind):
    assert _classify(error) == kind


def test_retry_after_parsing():
    assert _retry_after(Exception("Please try again in 3m15.5s.")) == pytest.approx(195.5)
    assert _retry_after(Exception("try again in 420ms")) == pytest.approx(0.42)
    assert _retry_after(Exception("try again in 7.5s")) == pytest.approx(7.5)
    assert _retry_after(Exception("no hint")) is None


def test_text_helpers():
    assert _clean("<think>secret plan</think>\nAnswer") == "Answer"
    assert chunk_text([{"type": "text", "text": "a"}, {"type": "tool_use"}, "b"]) == "ab"
    assert chunk_text(None) == ""


async def test_falls_back_to_next_provider_on_auth_error():
    broken = failing(StatusError("Incorrect API key", 401))
    healthy = ok_model("from groq")
    router = make_router([("openai", "gpt", broken), ("groq", "oss", healthy)])

    text, provider = await router.ainvoke(MESSAGES)

    assert (text, provider) == ("from groq", "groq")
    assert not router.endpoints[("openai", "gpt")].available


async def test_failed_provider_is_skipped_during_cooldown():
    broken = failing(StatusError("Incorrect API key", 401))
    router = make_router([("openai", "gpt", broken), ("groq", "oss", ok_model())])

    await router.ainvoke(MESSAGES)
    await router.ainvoke(MESSAGES)

    assert len(broken.prompts) == 1


async def test_auth_failure_disables_every_model_of_that_provider():
    router = make_router(
        [
            ("anthropic", "big", failing(StatusError("credit balance is too low", 400))),
            ("anthropic", "small", ok_model()),
            ("groq", "oss", ok_model("groq")),
        ]
    )
    _, provider = await router.ainvoke(MESSAGES)
    assert provider == "groq"
    assert not router.endpoints[("anthropic", "small")].available


async def test_rate_limit_cools_only_that_model_using_retry_hint():
    router = make_router(
        [
            ("groq", "big", failing(StatusError("Rate limit reached, try again in 12s", 429))),
            ("groq", "small", ok_model("small")),
        ]
    )
    text, _ = await router.ainvoke(MESSAGES)
    big = router.endpoints[("groq", "big")]
    assert text == "small"
    assert 10 < big.disabled_until - time.monotonic() <= 12
    assert router.endpoints[("groq", "small")].available


async def test_all_providers_failing_raises():
    router = make_router(
        [
            ("openai", "a", failing(StatusError("Incorrect API key", 401))),
            ("groq", "b", failing(StatusError("boom", 500))),
        ]
    )
    with pytest.raises(AllProvidersFailed):
        await router.ainvoke(MESSAGES)


async def test_everything_in_cooldown_still_retries_all():
    healthy = ok_model("back")
    router = make_router([("groq", "oss", healthy)])
    router.endpoints[("groq", "oss")].disabled_until = time.monotonic() + 999
    text, _ = await router.ainvoke(MESSAGES)
    assert text == "back"


async def test_empty_response_triggers_fallback():
    router = make_router([("openai", "a", ok_model("   ")), ("groq", "b", ok_model("real"))])
    text, provider = await router.ainvoke(MESSAGES)
    assert (text, provider) == ("real", "groq")


async def test_stream_reports_provider_and_tokens():
    router = make_router([("groq", "oss", ok_model("one two three"))])
    events = [event async for event in router.astream(MESSAGES)]
    assert events[0] == ("provider", "groq")
    assert "".join(v for k, v in events if k == "token") == "one two three"


async def test_stream_failure_before_tokens_falls_back_silently():
    router = make_router(
        [
            ("openai", "a", failing(StatusError("Incorrect API key", 401))),
            ("groq", "b", ok_model("hello world")),
        ]
    )
    events = [event async for event in router.astream(MESSAGES)]
    kinds = [k for k, _ in events]
    assert "reset" not in kinds
    assert ("provider", "groq") in events


async def test_stream_failure_mid_answer_resets_and_recovers():
    flaky = ScriptedModel(
        responder=lambda s, u: "partial answer that breaks",
        fail_with=StatusError("overloaded", 503),
        fail_after_chunks=2,
    )
    router = make_router([("openai", "a", flaky), ("groq", "b", ok_model("clean answer"))])
    events = [event async for event in router.astream(MESSAGES)]

    reset_at = events.index(("reset", "openai"))
    after = "".join(v for k, v in events[reset_at:] if k == "token")
    assert after == "clean answer"


async def test_stream_all_failing_raises():
    router = make_router([("groq", "b", failing(StatusError("down", 500)))])
    with pytest.raises(AllProvidersFailed):
        async for _ in router.astream(MESSAGES):
            pass


def test_router_builds_order_from_settings():
    settings = dataclasses.replace(
        get_settings(),
        llm_providers=["openai", "anthropic", "groq", "gemini", "unknown"],
        openai_api_key="",
        anthropic_api_key="sk-ant-test",
        groq_api_key="gsk-test",
        gemini_api_key="",
        groq_model="big",
        groq_fast_model="small",
        groq_backup_models=["backup"],
    )
    router = LLMRouter(settings)
    smart = [(e.provider, e.model_name) for e in router.order["smart"]]
    fast = [(e.provider, e.model_name) for e in router.order["fast"]]
    assert smart == [
        ("anthropic", settings.anthropic_model),
        ("groq", "big"),
        ("groq", "small"),
        ("groq", "backup"),
    ]
    assert fast[1:] == [("groq", "small"), ("groq", "big"), ("groq", "backup")]
    assert all(entry["available"] for entry in router.status())


async def test_waits_briefly_for_a_preferred_model_instead_of_slow_fallback():
    preferred = ok_model("fast groq")
    slow = ok_model("slow gemini")
    router = make_router([("groq", "oss", preferred), ("gemini", "flash", slow)])
    router.endpoints[("groq", "oss")].disabled_until = time.monotonic() + 0.3

    started = time.monotonic()
    text, _ = await router.ainvoke(MESSAGES)

    assert text == "fast groq"
    assert 0.25 <= time.monotonic() - started < 2
    assert slow.prompts == []


async def test_long_cooldowns_are_skipped_without_waiting():
    router = make_router([("groq", "oss", ok_model("groq")), ("gemini", "flash", ok_model("gemini"))])
    router.endpoints[("groq", "oss")].disabled_until = time.monotonic() + 120

    started = time.monotonic()
    text, _ = await router.ainvoke(MESSAGES)
    assert text == "gemini"
    assert time.monotonic() - started < 0.5


async def test_total_waiting_per_request_is_capped(monkeypatch):
    from app import llm

    monkeypatch.setattr(llm, "SHORT_WAIT_SECONDS", 0.4)
    first = failing(StatusError("Rate limit reached, try again in 0.3s", 429))
    second = failing(StatusError("Rate limit reached, try again in 0.3s", 429))
    router = make_router([("groq", "a", first), ("groq", "b", second), ("gemini", "c", ok_model("gemini"))])
    now = time.monotonic()
    for key in (("groq", "a"), ("groq", "b")):
        router.endpoints[key].disabled_until = now + 0.3

    started = time.monotonic()
    text, _ = await router.ainvoke(MESSAGES)
    assert text == "gemini"
    assert time.monotonic() - started < 0.55


async def test_retries_once_when_every_provider_is_briefly_rate_limited():
    calls = {"n": 0}

    def flaky(system, user):
        calls["n"] += 1
        if calls["n"] == 1:
            raise StatusError("Rate limit reached, try again in 0.2s", 429)
        return "recovered"

    router = make_router([("groq", "oss", ScriptedModel(responder=flaky))])
    started = time.monotonic()
    text, _ = await router.ainvoke(MESSAGES)
    assert text == "recovered"
    assert time.monotonic() - started >= 0.15


async def test_stream_announces_retry_round():
    calls = {"n": 0}

    def flaky(system, user):
        calls["n"] += 1
        if calls["n"] == 1:
            raise StatusError("Rate limit reached, try again in 0.1s", 429)
        return "ok now"

    router = make_router([("groq", "oss", ScriptedModel(responder=flaky))])
    events = [event async for event in router.astream(MESSAGES)]
    assert events[0][0] == "waiting"
    assert "".join(v for k, v in events if k == "token") == "ok now"


async def test_long_rate_limits_do_not_trigger_a_retry_round():
    router = make_router([("groq", "oss", failing(StatusError("Rate limit reached, try again in 3m0s", 429)))])
    started = time.monotonic()
    with pytest.raises(AllProvidersFailed):
        await router.ainvoke(MESSAGES)
    assert time.monotonic() - started < 0.5
