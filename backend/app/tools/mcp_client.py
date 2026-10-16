import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from app.config import get_settings

logger = logging.getLogger("tripgraph.mcp")

T = TypeVar("T")

WEATHER_MOUNT = "/internal/weather"


def _connections() -> dict[str, dict[str, Any]]:
    settings = get_settings()
    connections: dict[str, dict[str, Any]] = {}
    if settings.tavily_api_key:
        connections["tavily"] = {
            "transport": "streamable_http",
            "url": f"https://mcp.tavily.com/mcp/?tavilyApiKey={settings.tavily_api_key}",
        }
    if settings.openweather_api_key:
        connections["weather"] = {
            "transport": "streamable_http",
            "url": f"http://127.0.0.1:{settings.port}{WEATHER_MOUNT}/mcp",
        }
    return connections


def to_text(result: Any, limit: int = 4000) -> str:
    if isinstance(result, tuple):
        result = result[0]
    if isinstance(result, list):
        parts = []
        for item in result:
            if isinstance(item, dict):
                parts.append(item.get("text") or json.dumps(item, default=str))
            else:
                parts.append(str(getattr(item, "text", item)))
        result = "\n".join(parts)
    elif isinstance(result, dict):
        result = json.dumps(result, default=str)
    text = str(result).strip()
    return text[:limit]


class MCPHub:
    def __init__(self):
        self.client = MultiServerMCPClient(_connections())
        self._tools: dict[str, dict[str, BaseTool]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    @property
    def servers(self) -> list[str]:
        return list(self.client.connections)

    async def _load(self, server: str) -> dict[str, BaseTool]:
        lock = self._locks.setdefault(server, asyncio.Lock())
        async with lock:
            if server not in self._tools:
                tools = await asyncio.wait_for(
                    self.client.get_tools(server_name=server), get_settings().tool_timeout
                )
                self._tools[server] = {tool.name: tool for tool in tools}
                logger.info("MCP server %s ready with tools: %s", server, ", ".join(self._tools[server]))
            return self._tools[server]

    async def call(self, server: str, tool_name: str, args: dict[str, Any]) -> Any:
        if server not in self.client.connections:
            raise RuntimeError(f"MCP server '{server}' is not configured")
        tools = await self._load(server)
        tool = tools.get(tool_name)
        if tool is None:
            raise RuntimeError(f"Tool '{tool_name}' not found on '{server}'")
        try:
            return await asyncio.wait_for(tool.ainvoke(args), get_settings().tool_timeout)
        except Exception:
            self._tools.pop(server, None)
            raise

    async def warmup(self) -> None:
        results = await asyncio.gather(*(self._load(name) for name in self.servers), return_exceptions=True)
        for name, result in zip(self.servers, results):
            if isinstance(result, BaseException):
                logger.warning("MCP server %s warmup failed: %s", name, result or type(result).__name__)

    async def close(self) -> None:
        self._tools.clear()

    def status(self) -> dict[str, bool]:
        return {name: name in self._tools for name in self.servers}


_hub: MCPHub | None = None


def get_hub() -> MCPHub:
    global _hub
    if _hub is None:
        _hub = MCPHub()
    return _hub


async def hedged(
    primary: Callable[[], Awaitable[T]],
    backup: Callable[[], Awaitable[T]],
    delay: float,
    label: str,
) -> T:
    first = asyncio.ensure_future(primary())
    try:
        return await asyncio.wait_for(asyncio.shield(first), delay)
    except TimeoutError:
        pass
    except Exception as error:
        logger.warning("%s via MCP failed, using direct API: %s", label, error or type(error).__name__)
        return await backup()

    second = asyncio.ensure_future(backup())
    pending = {first, second}
    error: BaseException | None = None
    try:
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                if task.exception() is None:
                    return task.result()
                error = task.exception()
        raise error or RuntimeError(f"{label} failed")
    finally:
        for task in pending:
            task.cancel()


def _format_results(results: list[Any], limit: int) -> str:
    lines = [
        f"- {str(item.get('title', '')).strip()}: {' '.join(str(item.get('content', '')).split())[:350]}"
        for item in results
        if isinstance(item, dict)
    ]
    return "\n".join(lines)[:limit]


def _compact(result: Any) -> str:
    text = to_text(result, limit=20000)
    try:
        return json.dumps(json.loads(text), separators=(",", ":"), ensure_ascii=False)[:2000]
    except ValueError:
        return text[:2000]


async def web_search(query: str, max_results: int = 5, limit: int = 2500) -> str:
    settings = get_settings()
    if not settings.tavily_api_key:
        return ""

    async def via_mcp() -> str:
        result = await get_hub().call("tavily", "tavily_search", {"query": query, "max_results": max_results})
        text = to_text(result, limit=50000)
        try:
            formatted = _format_results(json.loads(text).get("results", []), limit)
        except (ValueError, AttributeError):
            formatted = text[:limit]
        if not formatted:
            raise ValueError("empty search result")
        return formatted

    async def via_rest() -> str:
        from tavily import AsyncTavilyClient

        response = await asyncio.wait_for(
            AsyncTavilyClient(api_key=settings.tavily_api_key).search(
                query=query, max_results=max_results, search_depth="basic"
            ),
            settings.tool_timeout,
        )
        return _format_results(response.get("results", []), limit)

    return await hedged(via_mcp, via_rest, settings.hedge_delay, "Search")


async def weather_report(city: str) -> dict[str, str]:
    async def via_mcp() -> dict[str, str]:
        current, forecast = await asyncio.gather(
            get_hub().call("weather", "get_current_weather", {"city": city}),
            get_hub().call("weather", "get_forecast", {"city": city}),
        )
        return {"current": _compact(current), "forecast": _compact(forecast)}

    async def direct() -> dict[str, str]:
        from app.tools import weather_server

        current, forecast = await asyncio.gather(
            weather_server.get_current_weather(city), weather_server.get_forecast(city)
        )
        return {"current": _compact(current), "forecast": _compact(forecast)}

    return await hedged(via_mcp, direct, get_settings().hedge_delay, "Weather")
