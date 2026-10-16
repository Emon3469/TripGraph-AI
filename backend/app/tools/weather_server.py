import os
import sys
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.config import get_settings  # noqa: E402

mcp = FastMCP(
    "TripGraph Weather",
    stateless_http=True,
    json_response=True,
    streamable_http_path="/mcp",
    log_level="WARNING",
)

BASE_URL = "https://api.openweathermap.org/data/2.5"
TIMEOUT_SECONDS = 10


def _api_key() -> str:
    key = os.getenv("OPENWEATHER_API_KEY") or get_settings().openweather_api_key
    if not key:
        raise RuntimeError("OPENWEATHER_API_KEY is not configured")
    return key


async def _get(path: str, city: str) -> dict[str, Any]:
    city = city.strip()
    if not city:
        raise ValueError("City name cannot be empty")
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.get(
                f"{BASE_URL}/{path}",
                params={"q": city, "appid": _api_key(), "units": "metric"},
            )
    except httpx.HTTPError as error:
        raise RuntimeError(f"Weather service unreachable ({type(error).__name__})") from None
    if response.status_code == 404:
        raise ValueError(f"City '{city}' was not found")
    if response.is_error:
        raise RuntimeError(f"Weather service returned HTTP {response.status_code}")
    return response.json()


@mcp.tool()
async def get_current_weather(city: str) -> dict[str, Any]:
    """Current weather conditions for a city."""
    data = await _get("weather", city)
    return {
        "city": data["name"],
        "country": data.get("sys", {}).get("country"),
        "temperature_c": data["main"]["temp"],
        "feels_like_c": data["main"]["feels_like"],
        "humidity": data["main"]["humidity"],
        "condition": data["weather"][0]["description"],
        "wind_speed_ms": data["wind"]["speed"],
    }


@mcp.tool()
async def get_forecast(city: str) -> dict[str, Any]:
    """Five day forecast for a city, summarised per day."""
    data = await _get("forecast", city)
    days: dict[str, dict[str, Any]] = {}
    for item in data["list"]:
        day = item["dt_txt"][:10]
        entry = days.setdefault(day, {"date": day, "min_c": 99.0, "max_c": -99.0, "conditions": {}})
        entry["min_c"] = round(min(entry["min_c"], item["main"]["temp_min"]), 1)
        entry["max_c"] = round(max(entry["max_c"], item["main"]["temp_max"]), 1)
        condition = item["weather"][0]["description"]
        entry["conditions"][condition] = entry["conditions"].get(condition, 0) + 1
        entry["rain_chance"] = max(entry.get("rain_chance", 0), round(item.get("pop", 0) * 100))

    forecast = []
    for entry in days.values():
        conditions = entry.pop("conditions")
        entry["condition"] = max(conditions, key=conditions.get)
        forecast.append(entry)

    return {"city": data.get("city", {}).get("name", city), "forecast": forecast}


if __name__ == "__main__":
    mcp.run(transport="stdio")
