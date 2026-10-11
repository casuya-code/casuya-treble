"""Settle first-half corner bets from the public match timeline."""

from __future__ import annotations

import httpx

_TIMELINE = "https://stats.fn.sportradar.com/common/en/Etc:UTC/gismo/match_timeline/{match_id}"
_HALF_DONE = {
    "halftime",
    "2nd half",
    "awaiting extra time",
    "extra time",
    "penalties",
    "ended",
    "closed",
    "finished",
    "ap",
    "aet",
    "after extra time",
}
_ENDED = {"ended", "closed", "finished", "ap", "aet", "after extra time"}


def _timeline_data(payload: dict) -> dict | None:
    docs = payload.get("doc")
    if not isinstance(docs, list) or not docs or not isinstance(docs[0], dict):
        return None
    data = docs[0].get("data")
    if not isinstance(data, dict):
        return None
    return data


def corner_line(market: str) -> float | None:
    """The .5 line in a market such as Over 2.5 Corners 1H."""
    if "Corner" not in market and "corner" not in market.lower():
        return None
    for part in market.replace("—", " ").split():
        try:
            value = float(part)
        except ValueError:
            continue
        if value > 0:
            return value
    return None


def corner_leg_outcome(market: str, corners: int | None, complete: bool) -> str:
    """Won as soon as the count clears the line; lost once the period is closed.

    Covers the first-half Over markets and the full-time Over/Under markets; the
    side is read from the label and every quoted line is a .5 so a push cannot
    happen.
    """
    line = corner_line(market)
    if corners is None or line is None:
        return "pending"
    if "under" in market.lower():
        if corners < line:
            return "won"
    elif corners > line:
        return "won"
    if complete:
        return "lost"
    return "pending"


def parse_first_half_corners(payload: dict) -> tuple[int, bool] | None:
    """First-half corner count, and whether that half is closed. None before kickoff."""
    data = _timeline_data(payload)
    if data is None:
        return None
    events = [event for event in data.get("events") or [] if isinstance(event, dict)]
    match = data.get("match") if isinstance(data.get("match"), dict) else {}
    status_name = str((match.get("status") or {}).get("name") or "").lower()
    matchstatus = str(match.get("matchstatus") or "").lower()
    started = any(event.get("type") in ("match_started", "periodstart", "corner") for event in events)
    if not started and matchstatus not in ("live", "result"):
        return None

    count = 0
    half_done = status_name in _HALF_DONE or matchstatus == "result"
    try:
        if int(match.get("p") or 0) >= 2:
            half_done = True
    except (TypeError, ValueError):
        pass

    for event in events:
        if event.get("disabled"):
            continue
        kind = event.get("type")
        if kind == "corner":
            try:
                minute = int(event.get("time"))
            except (TypeError, ValueError):
                continue
            if 0 <= minute <= 45:
                count += 1
        elif kind == "periodscore" and event.get("period") == 1:
            half_done = True
        elif kind == "periodstart" and event.get("period") in (2, 31):
            half_done = True
    return count, half_done


def parse_total_corners(payload: dict) -> tuple[int, bool] | None:
    """Full-match corner count and whether the match has ended. None before kickoff."""
    data = _timeline_data(payload)
    if data is None:
        return None
    events = [event for event in data.get("events") or [] if isinstance(event, dict)]
    match = data.get("match") if isinstance(data.get("match"), dict) else {}
    status_name = str((match.get("status") or {}).get("name") or "").lower()
    matchstatus = str(match.get("matchstatus") or "").lower()
    started = any(event.get("type") in ("match_started", "periodstart", "corner") for event in events)
    if not started and matchstatus not in ("live", "result"):
        return None
    count = 0
    for event in events:
        if event.get("disabled"):
            continue
        if event.get("type") == "corner":
            count += 1
    finished = matchstatus == "result" or status_name in _ENDED
    return count, finished


async def fetch_corner_counts(match_id: str) -> tuple[tuple[int, bool], tuple[int, bool]] | None:
    """(first half (count, done), full match (count, finished)) from one timeline request."""
    url = _TIMELINE.format(match_id=match_id)
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        if response.status_code != 200:
            return None
        payload = response.json()
    if not isinstance(payload, dict):
        return None
    half = parse_first_half_corners(payload)
    total = parse_total_corners(payload)
    if half is None and total is None:
        return None
    return half, total


async def fetch_first_half_corners(match_id: str) -> tuple[int, bool] | None:
    url = _TIMELINE.format(match_id=match_id)
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        if response.status_code != 200:
            return None
        payload = response.json()
    if not isinstance(payload, dict):
        return None
    return parse_first_half_corners(payload)
