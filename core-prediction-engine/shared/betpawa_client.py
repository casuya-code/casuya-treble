"""Fetch upcoming football fixtures and Over 1.5 odds from BetPawa Kenya sportsbook API."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote

import httpx

from shared.config import settings

OVER_UNDER_FT_MARKET = "5000"
TOTAL_GOALS_LINE = "1.5"


@dataclass
class BetPawaOver15:
    external_id: str
    betpawa_event_id: str
    home_team: str
    away_team: str
    league: str
    kickoff_at: datetime
    decimal_odds: float


@dataclass
class BetPawaScore:
    home_goals: int
    away_goals: int
    live: bool


class BetPawaError(Exception):
    pass


def _headers() -> dict[str, str]:
    return {
        "X-Pawa-Brand": settings.betpawa_brand,
        "X-Pawa-Language": settings.betpawa_language,
        "deviceType": "mobile",
        "traceId": str(uuid.uuid4()),
        "Accept": "application/json",
    }


def _parse_start(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _iter_event_nodes(payload: dict | list):
    stack = [payload]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            parts = node.get("participants")
            if (
                isinstance(parts, list)
                and len(parts) >= 2
                and node.get("startTime")
                and node.get("id")
            ):
                yield node
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)


def _league_from_event(event: dict) -> str:
    competition = (event.get("competition") or {}).get("name")
    region = (event.get("region") or {}).get("name")
    category = (event.get("category") or {}).get("name")
    if competition and region:
        label = f"{category or 'Football'} / {region} / {competition}"
    else:
        label = competition or region or category or "Football"
    return label[:120]


def _participant_name(participants: list[dict], position: int) -> str | None:
    for part in participants:
        if part.get("position") == position:
            return part.get("name")
    return None


def _extract_over_15_odds(event: dict) -> float | None:
    for market in event.get("markets") or []:
        market_type = market.get("marketType") or {}
        if str(market_type.get("id")) != OVER_UNDER_FT_MARKET:
            continue
        for row in market.get("row") or []:
            specifier = row.get("specifier") or {}
            total = specifier.get("total")
            if total is None:
                for price in row.get("prices") or []:
                    if price.get("handicap") == TOTAL_GOALS_LINE:
                        total = TOTAL_GOALS_LINE
                        break
            if str(total) != TOTAL_GOALS_LINE:
                continue
            for price in row.get("prices") or []:
                if price.get("name") == "Over":
                    odds = float(price["odds"])
                    if odds > 1.0:
                        return round(odds, 3)
    return None


def parse_events_payload(payload: dict | list) -> list[BetPawaOver15]:
    """Parse nested BetPawa by-queries JSON into flat fixture rows."""
    seen: set[str] = set()
    rows: list[BetPawaOver15] = []

    for event in _iter_event_nodes(payload):
        event_id = str(event["id"])
        if event_id in seen:
            continue
        seen.add(event_id)

        odds = _extract_over_15_odds(event)
        if odds is None:
            continue

        participants = event["participants"]
        home = _participant_name(participants, 1)
        away = _participant_name(participants, 2)
        if not home or not away:
            continue

        rows.append(
            BetPawaOver15(
                external_id=f"betpawa:{event_id}",
                betpawa_event_id=event_id,
                home_team=home,
                away_team=away,
                league=_league_from_event(event),
                kickoff_at=_parse_start(str(event["startTime"])),
                decimal_odds=odds,
            )
        )

    return rows


def _build_list_query(*, take: int, skip: int, popular_only: bool) -> str:
    body = {
        "queries": [
            {
                "query": {
                    "eventType": "UPCOMING",
                    "categories": [settings.betpawa_football_category],
                    "zones": {},
                    "popular": popular_only,
                    "hasOdds": True,
                },
                "view": {"marketTypes": [OVER_UNDER_FT_MARKET]},
                "skip": skip,
                "take": take,
                "sort": {"startTime": "ASC"},
            }
        ]
    }
    return quote(json.dumps(body, separators=(",", ":")))


async def fetch_football_over_15(
    *,
    take: int | None = None,
    skip: int = 0,
    popular_only: bool = False,
) -> list[BetPawaOver15]:
    take_n = take if take is not None else settings.betpawa_fetch_take
    q = _build_list_query(take=take_n, skip=skip, popular_only=popular_only)
    url = f"{settings.betpawa_base_url.rstrip('/')}/api/sportsbook/v4/events/lists/by-queries?q={q}"

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.get(url, headers=_headers())
        if response.status_code != 200:
            raise BetPawaError(f"BetPawa HTTP {response.status_code}: {response.text[:240]}")
        payload = response.json()

    if isinstance(payload, dict) and payload.get("error"):
        raise BetPawaError(f"BetPawa API error: {payload.get('error')}")

    return parse_events_payload(payload)


def parse_event_score(payload: dict) -> BetPawaScore | None:
    """Full-time score from a BetPawa event. Live matches keep the current score."""
    info = payload.get("additionalInfo") or {}
    live = bool(info.get("live"))
    home: int | None = None
    away: int | None = None
    results = payload.get("results") or {}
    for part in results.get("participantPeriodResults") or []:
        side = (part.get("participant") or {}).get("type")
        for period in part.get("periodResults") or []:
            slug = (period.get("period") or {}).get("slug")
            if slug != "FULL_TIME_EXCLUDING_OVERTIME":
                continue
            raw = period.get("result")
            if raw is None or str(raw).strip() == "":
                continue
            try:
                goals = int(raw)
            except (TypeError, ValueError):
                continue
            if side == "HOME":
                home = goals
            elif side == "AWAY":
                away = goals
    if home is None or away is None:
        return None
    return BetPawaScore(home_goals=home, away_goals=away, live=live)


async def fetch_event_score(event_id: str) -> BetPawaScore | None:
    url = f"{settings.betpawa_base_url.rstrip('/')}/api/sportsbook/v4/events/{event_id}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url, headers=_headers())
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise BetPawaError(f"BetPawa HTTP {response.status_code}: {response.text[:240]}")
        payload = response.json()
    if not isinstance(payload, dict) or payload.get("error"):
        return None
    return parse_event_score(payload)
