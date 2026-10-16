import os
import sys
from pathlib import Path

LIVE = os.getenv("RUN_LIVE") == "1"

if not LIVE:
    for key in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "ANTORPIC_API_KEY",
        "GROQ_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "TAVILY_API_KEY",
        "OPENWEATHER_API_KEY",
        "OPENWEATHERMAP_API_KEY",
        "DATABASE_URL",
        "LANGSMITH_API_KEY",
    ):
        os.environ[key] = ""
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["RATE_LIMIT_PER_MINUTE"] = "1000"
    os.environ["RATE_LIMIT_PER_HOUR"] = "10000"

os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000"
os.environ["ALLOWED_ORIGIN_REGEX"] = r"https://tripgraph[a-z0-9-]*\.vercel\.app"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from app import graph as graph_module  # noqa: E402
from app import llm as llm_module  # noqa: E402
from app.limits import limiter  # noqa: E402
from tests.fakes import ScriptedModel, make_router, travel_responder  # noqa: E402


def pytest_collection_modifyitems(config, items):
    skip = pytest.mark.skip(reason="set RUN_LIVE=1 to call real providers")
    for item in items:
        if "live" in item.keywords and not LIVE:
            item.add_marker(skip)
        if "live" not in item.keywords and LIVE:
            item.add_marker(pytest.mark.skip(reason="offline tests are skipped in live mode"))


@pytest.fixture
def scripted():
    return ScriptedModel(responder=travel_responder)


@pytest.fixture
def router(monkeypatch, scripted):
    router = make_router([("groq", "primary", scripted)])
    monkeypatch.setattr(llm_module, "_router", router)
    return router


@pytest.fixture
def tools(monkeypatch):
    calls = {"search": [], "weather": []}

    async def fake_search(query, max_results=5, limit=2500):
        calls["search"].append(query)
        return f"- Result for {query}: great options"

    async def fake_weather(city):
        calls["weather"].append(city)
        return {"current": f'{{"city":"{city}","temperature_c":30}}', "forecast": '{"forecast":[]}'}

    monkeypatch.setattr(graph_module, "web_search", fake_search)
    monkeypatch.setattr(graph_module, "weather_report", fake_weather)
    return calls


@pytest.fixture(autouse=True)
def reset_limiter():
    limiter.reset()
    yield
    limiter.reset()
