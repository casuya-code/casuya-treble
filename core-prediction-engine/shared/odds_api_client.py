"""Client for The Odds API (https://the-odds-api.com/)."""

from dataclasses import dataclass
from datetime import datetime

import httpx

from shared.config import settings


@dataclass
class OddsApiOver15:
    external_id: str
    sport_key: str
    home_team: str
    away_team: str
    commence_time: datetime
    decimal_odds: float
    bookmaker: str


class OddsApiError(Exception):
    pass


def _parse_commence(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _extract_over_15(event: dict) -> OddsApiOver15 | None:
    best_price: float | None = None
    best_book: str | None = None

    for bookmaker in event.get("bookmakers") or []:
        for market in bookmaker.get("markets") or []:
            if market.get("key") != "totals":
                continue
            for outcome in market.get("outcomes") or []:
                if outcome.get("name") != "Over":
                    continue
                point = outcome.get("point")
                if point is None or float(point) != 1.5:
                    continue
                price = float(outcome["price"])
                if price > 1.0 and (best_price is None or price > best_price):
                    best_price = price
                    best_book = bookmaker.get("title") or bookmaker.get("key") or "unknown"

    if best_price is None or best_book is None:
        return None

    return OddsApiOver15(
        external_id=f"oddsapi:{event['id']}",
        sport_key=event.get("sport_key", settings.odds_default_sport),
        home_team=event["home_team"],
        away_team=event["away_team"],
        commence_time=_parse_commence(event["commence_time"]),
        decimal_odds=round(best_price, 3),
        bookmaker=best_book,
    )


async def fetch_soccer_over_15(
    *,
    sport_key: str | None = None,
    region: str | None = None,
) -> tuple[list[OddsApiOver15], dict[str, str]]:
    if not settings.odds_api_configured:
        raise OddsApiError("ODDS_API_KEY is not set in environment")

    sport = sport_key or settings.odds_default_sport
    reg = region or settings.odds_default_region
    url = f"{settings.odds_api_base}/sports/{sport}/odds"
    params = {
        "apiKey": settings.odds_api_key,
        "regions": reg,
        "markets": "totals",
        "oddsFormat": "decimal",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        if response.status_code != 200:
            raise OddsApiError(f"Odds API HTTP {response.status_code}: {response.text[:200]}")
        payload = response.json()

    headers = {k.lower(): v for k, v in response.headers.items()}
    usage = {
        "requests_remaining": headers.get("x-requests-remaining", "?"),
        "requests_used": headers.get("x-requests-used", "?"),
    }

    rows: list[OddsApiOver15] = []
    for event in payload:
        row = _extract_over_15(event)
        if row:
            rows.append(row)
    return rows, usage
