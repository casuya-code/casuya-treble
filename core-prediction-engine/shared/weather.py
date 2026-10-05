"""Leave a match off a treble when kickoff weather is likely to suppress goals."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx

from shared.venues import venue_for

logger = logging.getLogger("casuya.weather")

# Downpour, lying snow, or a gale at the ground. Light rain stays in.
HEAVY_RAIN_MM = 5.0
SNOW_CM = 0.5
GALE_GUST_KMH = 70.0
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_CACHE: dict[tuple[float, float], tuple[datetime, dict]] = {}
_CACHE_FOR = timedelta(hours=3)


def _number(values: list, index: int) -> float:
    if index >= len(values) or values[index] is None:
        return 0.0
    try:
        return float(values[index])
    except (TypeError, ValueError):
        return 0.0


def weather_reason(payload: dict, kickoff: datetime) -> str | None:
    """rain, snow, or wind when the kickoff hour or the next hour is extreme. None otherwise."""
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=timezone.utc)
    start = kickoff.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    wanted = {
        start.strftime("%Y-%m-%dT%H:%M"),
        (start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
    }
    rain = snow = gust = 0.0
    seen = False
    for index, stamp in enumerate(times):
        if stamp not in wanted:
            continue
        seen = True
        rain = max(rain, _number(hourly.get("precipitation") or [], index))
        snow = max(snow, _number(hourly.get("snowfall") or [], index))
        gust = max(gust, _number(hourly.get("wind_gusts_10m") or [], index))
    if not seen:
        return None
    if snow >= SNOW_CM:
        return "snow"
    if rain >= HEAVY_RAIN_MM:
        return "rain"
    if gust >= GALE_GUST_KMH:
        return "wind"
    return None


def holds_for_weather(fixtures: list, forecasts: dict[tuple[float, float], dict]) -> list[tuple[object, str]]:
    """Fixtures to drop, using forecasts already fetched. Unknown grounds are kept."""
    held: list[tuple[object, str]] = []
    for fixture in fixtures:
        point = venue_for(fixture.home_team)
        if point is None:
            continue
        key = (round(point[0], 2), round(point[1], 2))
        payload = forecasts.get(key)
        if not payload:
            continue
        reason = weather_reason(payload, fixture.kickoff_at)
        if reason:
            held.append((fixture, reason))
    return held


def _fresh(point: tuple[float, float], now: datetime) -> dict | None:
    cached = _CACHE.get(point)
    if cached is None:
        return None
    stored_at, payload = cached
    if now - stored_at > _CACHE_FOR:
        return None
    return payload


async def _fetch_one(client: httpx.AsyncClient, point: tuple[float, float]) -> None:
    try:
        response = await client.get(
            _FORECAST_URL,
            params={
                "latitude": point[0],
                "longitude": point[1],
                "hourly": "precipitation,snowfall,wind_gusts_10m",
                "forecast_days": 10,
                "timezone": "UTC",
            },
            timeout=12,
        )
    except httpx.HTTPError:
        logger.warning("weather forecast failed for %s", point)
        return
    if response.status_code != 200:
        return
    _CACHE[point] = (datetime.now(timezone.utc), response.json())


async def forecasts_for(points: list[tuple[float, float]]) -> dict[tuple[float, float], dict]:
    """Open-Meteo hourly forecasts. A failed call leaves that ground out, so the match stays available."""
    now = datetime.now(timezone.utc)
    unique: list[tuple[float, float]] = []
    seen: set[tuple[float, float]] = set()
    for lat, lon in points:
        key = (round(lat, 2), round(lon, 2))
        if key in seen:
            continue
        seen.add(key)
        unique.append(key)
    missing = [point for point in unique if _fresh(point, now) is None]
    if missing:
        async with httpx.AsyncClient(headers={"User-Agent": "casuya-treble"}) as client:
            try:
                await asyncio.wait_for(asyncio.gather(*[_fetch_one(client, point) for point in missing]), timeout=20)
            except TimeoutError:
                logger.warning("weather forecast timed out")
    found: dict[tuple[float, float], dict] = {}
    for point in unique:
        payload = _fresh(point, datetime.now(timezone.utc))
        if payload is not None:
            found[point] = payload
    return found


async def matches_held_for_weather(fixtures: list) -> list[tuple[object, str]]:
    points = []
    for fixture in fixtures:
        point = venue_for(fixture.home_team)
        if point is not None:
            points.append(point)
    if not points:
        return []
    try:
        forecasts = await forecasts_for(points)
    except Exception:
        logger.exception("weather forecast failed")
        return []
    return holds_for_weather(fixtures, forecasts)
