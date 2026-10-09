"""Keyless ESPN data client for the basketball filter.

Only endpoints verified to be publicly reachable are used:
  - scoreboard?dates=YYYYMMDD        league slate for one US Eastern date
  - summary?event={id}               line (pickcenter), injuries, standings, box score
  - teams/{id}/schedule?season={Y}   full-season game list for one team
  - teams?limit=30                   league team directory
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date

import httpx

from shared.config import settings

logger = logging.getLogger("casuya.basketball")


class ESPNError(RuntimeError):
    """Raised when an ESPN endpoint cannot deliver usable data."""


class ESPNClient:
    """Thin async client with politeness delay and retry/backoff."""

    def __init__(
        self,
        *,
        base: str | None = None,
        delay: float | None = None,
        timeout: float | None = None,
        retries: int | None = None,
    ) -> None:
        self.base = (base or settings.bb_espn_base).rstrip("/")
        self.delay = settings.bb_http_delay if delay is None else delay
        self.timeout = settings.bb_http_timeout if timeout is None else timeout
        self.retries = settings.bb_http_retries if retries is None else retries
        self._client: httpx.AsyncClient | None = None
        self._throttle = asyncio.Lock()
        self._last_call = 0.0

    async def __aenter__(self) -> "ESPNClient":
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            headers={"User-Agent": "CasuyaBasketballFilter/1.0", "Accept": "application/json"},
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get(self, url: str, params: dict[str, object] | None = None) -> dict:
        if self._client is None:
            raise ESPNError("client not started (use 'async with ESPNClient()')")
        last_error: Exception | None = None
        for attempt in range(self.retries):
            async with self._throttle:
                wait = self.delay - (asyncio.get_event_loop().time() - self._last_call)
                if wait > 0:
                    await asyncio.sleep(wait)
                self._last_call = asyncio.get_event_loop().time()
            try:
                response = await self._client.get(url, params=params)
                if response.status_code == 429 or response.status_code >= 500:
                    raise ESPNError(f"HTTP {response.status_code} from {url}")
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise ESPNError(f"unexpected payload from {url}")
                return data
            except (httpx.HTTPError, ESPNError, ValueError) as exc:
                last_error = exc
                backoff = 1.0 * (2**attempt)
                logger.debug("espn call failed (%s), retry in %.1fs", exc, backoff)
                await asyncio.sleep(backoff)
        raise ESPNError(f"failed after {self.retries} attempts: {url} ({last_error})")

    async def scoreboard(self, day: date) -> list[dict]:
        data = await self._get(
            f"{self.base}/scoreboard", {"dates": day.strftime("%Y%m%d")}
        )
        events = data.get("events")
        return list(events) if isinstance(events, list) else []

    async def summary(self, event_id: str) -> dict:
        return await self._get(f"{self.base}/summary", {"event": event_id})

    async def team_schedule(self, team_id: str, season_year: int) -> list[dict]:
        data = await self._get(
            f"{self.base}/teams/{team_id}/schedule", {"season": season_year}
        )
        events = data.get("events")
        return list(events) if isinstance(events, list) else []

    async def teams(self) -> list[dict]:
        data = await self._get(f"{self.base}/teams", {"limit": 30})
        sports = data.get("sports") or []
        leagues = sports[0].get("leagues") if sports else None
        if not leagues:
            raise ESPNError("league directory missing from teams payload")
        teams = leagues[0].get("teams")
        return list(teams) if isinstance(teams, list) else []
