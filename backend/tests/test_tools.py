import asyncio
import json
import time

import httpx
import pytest

from app.tools import mcp_client, weather_server

CURRENT = {
    "name": "Kuala Lumpur",
    "sys": {"country": "MY"},
    "main": {"temp": 30.1, "feels_like": 35.0, "humidity": 80},
    "weather": [{"description": "light rain"}],
    "wind": {"speed": 2.5},
}

FORECAST = {
    "city": {"name": "Kuala Lumpur"},
    "list": [
        {"dt_txt": "2026-10-17 09:00:00", "main": {"temp_min": 26, "temp_max": 31}, "weather": [{"description": "rain"}], "pop": 0.8},
        {"dt_txt": "2026-10-17 12:00:00", "main": {"temp_min": 27, "temp_max": 33}, "weather": [{"description": "rain"}], "pop": 0.4},
        {"dt_txt": "2026-10-18 09:00:00", "main": {"temp_min": 25, "temp_max": 30}, "weather": [{"description": "clear sky"}], "pop": 0},
    ],
}

RealAsyncClient = httpx.AsyncClient


@pytest.fixture
def openweather(monkeypatch):
    monkeypatch.setenv("OPENWEATHER_API_KEY", "secret-key-123")
    state = {"handler": None, "requests": []}

    def handler(request: httpx.Request) -> httpx.Response:
        state["requests"].append(request)
        return state["handler"](request)

    monkeypatch.setattr(
        weather_server.httpx,
        "AsyncClient",
        lambda **kwargs: RealAsyncClient(transport=httpx.MockTransport(handler), **kwargs),
    )
    return state


async def test_current_weather(openweather):
    openweather["handler"] = lambda r: httpx.Response(200, json=CURRENT)
    data = await weather_server.get_current_weather("Kuala Lumpur")
    assert data == {
        "city": "Kuala Lumpur",
        "country": "MY",
        "temperature_c": 30.1,
        "feels_like_c": 35.0,
        "humidity": 80,
        "condition": "light rain",
        "wind_speed_ms": 2.5,
    }
    request = openweather["requests"][0]
    assert request.url.path.endswith("/weather")
    assert request.url.params["units"] == "metric"


async def test_forecast_is_summarised_per_day(openweather):
    openweather["handler"] = lambda r: httpx.Response(200, json=FORECAST)
    data = await weather_server.get_forecast("Kuala Lumpur")
    assert data["forecast"] == [
        {"date": "2026-10-17", "min_c": 26, "max_c": 33, "rain_chance": 80, "condition": "rain"},
        {"date": "2026-10-18", "min_c": 25, "max_c": 30, "rain_chance": 0, "condition": "clear sky"},
    ]


async def test_weather_errors_never_leak_the_api_key(openweather):
    def boom(request):
        raise httpx.ConnectError(f"cannot reach {request.url}")

    openweather["handler"] = boom
    with pytest.raises(RuntimeError) as error:
        await weather_server.get_current_weather("Paris")
    assert "secret-key-123" not in str(error.value)

    openweather["handler"] = lambda r: httpx.Response(404, json={})
    with pytest.raises(ValueError, match="not found"):
        await weather_server.get_forecast("Atlantis")

    openweather["handler"] = lambda r: httpx.Response(500, text="secret-key-123")
    with pytest.raises(RuntimeError) as error:
        await weather_server.get_forecast("Paris")
    assert "secret-key-123" not in str(error.value)

    with pytest.raises(ValueError):
        await weather_server.get_current_weather("  ")


def test_weather_tools_are_registered_on_the_mcp_server():
    names = {tool.name for tool in weather_server.mcp._tool_manager.list_tools()}
    assert names == {"get_current_weather", "get_forecast"}


def test_to_text_and_result_formatting():
    assert mcp_client.to_text([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]) == "a\nb"
    assert mcp_client.to_text(({"x": 1}, None)) == '{"x": 1}'
    formatted = mcp_client._format_results(
        [{"title": " Hotel A ", "content": "Great\n  rooms"}, "junk", {"title": "B", "content": "x" * 1000}], 2500
    )
    lines = formatted.splitlines()
    assert lines[0] == "- Hotel A: Great rooms"
    assert len(lines[1]) < 400


async def _value(value, delay=0.0):
    await asyncio.sleep(delay)
    return value


async def _fail(delay=0.0):
    await asyncio.sleep(delay)
    raise RuntimeError("down")


async def test_hedged_prefers_fast_primary():
    started = time.monotonic()
    assert await mcp_client.hedged(lambda: _value("mcp"), lambda: _value("rest"), 0.2, "t") == "mcp"
    assert time.monotonic() - started < 0.1


async def test_hedged_falls_back_immediately_when_primary_fails():
    started = time.monotonic()
    assert await mcp_client.hedged(lambda: _fail(), lambda: _value("rest"), 5, "t") == "rest"
    assert time.monotonic() - started < 0.5


async def test_hedged_races_backup_when_primary_is_slow():
    started = time.monotonic()
    result = await mcp_client.hedged(lambda: _value("mcp", 2), lambda: _value("rest", 0.05), 0.1, "t")
    assert result == "rest"
    assert time.monotonic() - started < 0.5


async def test_hedged_still_uses_slow_primary_if_backup_fails():
    result = await mcp_client.hedged(lambda: _value("mcp", 0.3), lambda: _fail(), 0.1, "t")
    assert result == "mcp"


async def test_hedged_raises_when_both_fail():
    with pytest.raises(RuntimeError):
        await mcp_client.hedged(lambda: _fail(0.2), lambda: _fail(), 0.1, "t")


def _settings(**values):
    defaults = {"tavily_api_key": "k", "tool_timeout": 5, "hedge_delay": 0.2}
    return type("S", (), {**defaults, **values})()


async def test_web_search_parses_mcp_json(monkeypatch):
    monkeypatch.setattr(mcp_client, "get_settings", lambda: _settings())

    class Hub:
        async def call(self, server, tool, args):
            assert (server, tool) == ("tavily", "tavily_search")
            return json.dumps({"results": [{"title": "KL Hotels", "content": "Top picks"}]})

    monkeypatch.setattr(mcp_client, "get_hub", lambda: Hub())
    assert await mcp_client.web_search("hotels") == "- KL Hotels: Top picks"


async def test_web_search_falls_back_to_rest_client(monkeypatch):
    monkeypatch.setattr(mcp_client, "get_settings", lambda: _settings())

    class Hub:
        async def call(self, *args):
            raise RuntimeError("mcp down")

    class Client:
        def __init__(self, api_key):
            pass

        async def search(self, **kwargs):
            return {"results": [{"title": "Fallback", "content": "REST works"}]}

    import tavily

    monkeypatch.setattr(mcp_client, "get_hub", lambda: Hub())
    monkeypatch.setattr(tavily, "AsyncTavilyClient", Client)
    assert await mcp_client.web_search("hotels") == "- Fallback: REST works"


async def test_web_search_without_key_returns_empty(monkeypatch):
    monkeypatch.setattr(mcp_client, "get_settings", lambda: _settings(tavily_api_key=""))
    assert await mcp_client.web_search("anything") == ""


async def test_weather_report_falls_back_to_direct_call(monkeypatch):
    class Hub:
        async def call(self, *args):
            raise RuntimeError("mcp down")

    async def current(city):
        return {"city": city, "temperature_c": 20}

    async def forecast(city):
        return {"city": city, "forecast": []}

    monkeypatch.setattr(mcp_client, "get_hub", lambda: Hub())
    monkeypatch.setattr(weather_server, "get_current_weather", current)
    monkeypatch.setattr(weather_server, "get_forecast", forecast)
    report = await mcp_client.weather_report("Paris")
    assert json.loads(report["current"]) == {"city": "Paris", "temperature_c": 20}
    assert json.loads(report["forecast"]) == {"city": "Paris", "forecast": []}


async def test_hub_rejects_unconfigured_server():
    hub = mcp_client.MCPHub()
    with pytest.raises(RuntimeError, match="not configured"):
        await hub.call("tavily", "tavily_search", {"query": "x"})
    assert hub.status() == {}


async def test_hub_caches_tool_list_and_drops_it_after_failure(monkeypatch):
    hub = mcp_client.MCPHub()
    hub.client.connections["fake"] = {"transport": "streamable_http", "url": "http://x"}
    loads = []

    class Tool:
        name = "echo"

        def __init__(self, fail):
            self.fail = fail

        async def ainvoke(self, args):
            if self.fail:
                raise RuntimeError("broken")
            return args["text"]

    async def get_tools(server_name):
        loads.append(server_name)
        return [Tool(fail=len(loads) == 2)]

    monkeypatch.setattr(hub.client, "get_tools", get_tools)
    assert await hub.call("fake", "echo", {"text": "a"}) == "a"
    assert await hub.call("fake", "echo", {"text": "b"}) == "b"
    assert loads == ["fake"]
    hub._tools.clear()
    with pytest.raises(RuntimeError):
        await hub.call("fake", "echo", {"text": "c"})
    assert hub.status() == {"fake": False}
    assert await hub.call("fake", "echo", {"text": "d"}) == "d"
