"""Seed finished league scores from Football-Data.co.uk CSV files."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Fixture, MatchStatus

logger = logging.getLogger("casuya.history")

LONDON = ZoneInfo("Europe/London")
SOURCE = "https://www.football-data.co.uk/mmz4281"
# Current season plus the one before, so a team still has 20 results in August.
DIVISIONS = (
    ("E0", "England / Premier League"),
    ("E1", "England / Championship"),
    ("SP1", "Spain / La Liga"),
    ("I1", "Italy / Serie A"),
    ("D1", "Germany / Bundesliga"),
    ("F1", "France / Ligue 1"),
    ("N1", "Netherlands / Eredivisie"),
    ("P1", "Portugal / Liga Portugal"),
)

_fetched_at: datetime | None = None
_FRESH_FOR = timedelta(hours=12)
_RECENT_RESULT = timedelta(days=21)


@dataclass
class HistoricalMatch:
    external_id: str
    league: str
    home_team: str
    away_team: str
    kickoff_at: datetime
    home_goals: int
    away_goals: int


@dataclass
class HistoricalSeedResult:
    imported: int = 0
    updated: int = 0
    files: int = 0
    skipped: bool = False


def season_codes(today: date | None = None) -> list[str]:
    """Football-Data season folders, newest first. July starts the new code."""
    today = today or datetime.now(LONDON).date()
    start_year = today.year if today.month >= 7 else today.year - 1
    codes = []
    for year in (start_year, start_year - 1):
        codes.append(f"{str(year)[2:]}{str(year + 1)[2:]}")
    return codes


def historical_external_id(division: str, kickoff: datetime, home: str, away: str) -> str:
    raw = f"{division}|{kickoff.date().isoformat()}|{home}|{away}"
    return "fd:" + hashlib.sha1(raw.encode()).hexdigest()[:20]


def _kickoff(day_text: str, time_text: str | None) -> datetime | None:
    played = None
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            played = datetime.strptime(day_text.strip(), fmt).date()
            break
        except ValueError:
            continue
    if played is None:
        return None
    clock = time(15, 0)
    if time_text and time_text.strip():
        try:
            clock = datetime.strptime(time_text.strip(), "%H:%M").time()
        except ValueError:
            clock = time(15, 0)
    return datetime.combine(played, clock, tzinfo=LONDON).astimezone(timezone.utc)


def parse_football_data_csv(text: str, division: str, league: str) -> list[HistoricalMatch]:
    """Full-time scores only. Blank rows and other divisions in the file are skipped."""
    reader = csv.DictReader(io.StringIO(text))
    matches: list[HistoricalMatch] = []
    for row in reader:
        div = (row.get("Div") or "").strip()
        if div and div != division:
            continue
        home = (row.get("HomeTeam") or "").strip()
        away = (row.get("AwayTeam") or "").strip()
        home_goals = (row.get("FTHG") or "").strip()
        away_goals = (row.get("FTAG") or "").strip()
        if not home or not away or home_goals == "" or away_goals == "":
            continue
        kickoff = _kickoff(row.get("Date") or "", row.get("Time"))
        if kickoff is None:
            continue
        try:
            scored = int(home_goals)
            conceded = int(away_goals)
        except ValueError:
            continue
        matches.append(
            HistoricalMatch(
                external_id=historical_external_id(division, kickoff, home, away),
                league=league,
                home_team=home,
                away_team=away,
                kickoff_at=kickoff,
                home_goals=scored,
                away_goals=conceded,
            )
        )
    return matches


async def _download(client: httpx.AsyncClient, season: str, division: str) -> str | None:
    url = f"{SOURCE}/{season}/{division}.csv"
    try:
        response = await client.get(url, timeout=25, follow_redirects=True)
    except httpx.HTTPError:
        logger.warning("historical file unavailable: %s", url)
        return None
    if response.status_code != 200 or b"HomeTeam" not in response.content[:400]:
        return None
    return response.content.decode("latin-1")


async def _history_is_fresh(db: AsyncSession) -> bool:
    count = await db.scalar(select(func.count()).select_from(Fixture).where(Fixture.external_id.like("fd:%")))
    if not count or count < 800:
        return False
    newest = await db.scalar(select(func.max(Fixture.kickoff_at)).where(Fixture.external_id.like("fd:%")))
    if newest is None:
        return False
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=timezone.utc)
    return newest >= datetime.now(timezone.utc) - _RECENT_RESULT


async def import_football_data(db: AsyncSession, *, today: date | None = None) -> HistoricalSeedResult:
    """Download the seeded leagues and upsert finished matches. One commit."""
    seasons = season_codes(today)
    files: list[tuple[str, str, str]] = []
    async with httpx.AsyncClient(headers={"User-Agent": "casuya-treble"}) as client:
        jobs = [_download(client, season, division) for season in seasons for division, _league in DIVISIONS]
        payloads = await asyncio.gather(*jobs)
    index = 0
    for _season in seasons:
        for division, league in DIVISIONS:
            payload = payloads[index]
            index += 1
            if payload:
                files.append((division, league, payload))

    parsed_by_id: dict[str, HistoricalMatch] = {}
    for division, league, payload in files:
        for match in parse_football_data_csv(payload, division, league):
            parsed_by_id[match.external_id] = match
    parsed = list(parsed_by_id.values())
    if not parsed:
        return HistoricalSeedResult(files=0)

    ids = [match.external_id for match in parsed]
    existing = await db.execute(select(Fixture).where(Fixture.external_id.in_(ids)))
    by_id = {row.external_id: row for row in existing.scalars()}
    imported = 0
    updated = 0
    for match in parsed:
        row = by_id.get(match.external_id)
        if row:
            row.home_team = match.home_team
            row.away_team = match.away_team
            row.league = match.league
            row.kickoff_at = match.kickoff_at
            row.home_goals = match.home_goals
            row.away_goals = match.away_goals
            row.status = MatchStatus.FINISHED
            updated += 1
            continue
        db.add(
            Fixture(
                external_id=match.external_id,
                home_team=match.home_team,
                away_team=match.away_team,
                league=match.league,
                kickoff_at=match.kickoff_at,
                home_goals=match.home_goals,
                away_goals=match.away_goals,
                status=MatchStatus.FINISHED,
                lambda_home=1.4,
                lambda_away=1.1,
            )
        )
        imported += 1
    await db.commit()
    return HistoricalSeedResult(imported=imported, updated=updated, files=len(files))


async def ensure_historical_scores(db: AsyncSession) -> HistoricalSeedResult:
    """Refresh league history at most every 12 hours, and skip when last week is already stored."""
    global _fetched_at
    now = datetime.now(timezone.utc)
    if _fetched_at and now - _fetched_at < _FRESH_FOR:
        return HistoricalSeedResult(skipped=True)
    if await _history_is_fresh(db):
        _fetched_at = now
        return HistoricalSeedResult(skipped=True)
    result = await import_football_data(db)
    if result.files:
        _fetched_at = now
    return result
