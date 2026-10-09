"""Parse ESPN payloads and persist them into the bb_* tables."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.basketball.espn_client import ESPNClient
from shared.basketball.model import normalize_odds
from shared.models import BBGame, BBLineSnapshot, BBLineupSnapshot, BBPlayerGameStat

logger = logging.getLogger("casuya.basketball")


def season_year_for(day: date) -> int:
    """ESPN season year: the ending year of the season (Oct+ rolls forward)."""
    return day.year + 1 if day.month >= 10 else day.year


def _num(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return _num(value.get("value"))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _int(value: object) -> int | None:
    number = _num(value)
    return int(number) if number is not None else None


@dataclass
class ParsedEvent:
    event_id: str
    tipoff: datetime
    season_year: int
    season_type: int
    status: str  # scheduled / live / post
    home_team_id: str
    home_team: str
    home_score: int | None
    away_team_id: str
    away_team: str
    away_score: int | None


def _state_to_status(state: object) -> str:
    if state == "post":
        return "post"
    if state in ("in", "halftime"):
        return "live"
    return "scheduled"


def parse_event(ev: dict) -> ParsedEvent | None:
    """Parse a scoreboard OR schedule event (both shapes verified)."""
    event_id = str(ev.get("id") or "").strip()
    raw_date = ev.get("date")
    if not event_id or not raw_date:
        return None
    try:
        tipoff = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
    except ValueError:
        return None

    season = ev.get("season") or {}
    season_type_block = ev.get("seasonType") or {}
    season_year = _int(season.get("year")) or season_year_for(tipoff.date())
    season_type = (
        _int(season.get("type"))
        or _int(season_type_block.get("type"))
        or _int(season_type_block.get("id"))
        or 2
    )

    competitions = ev.get("competitions") or []
    if not competitions:
        return None
    comp = competitions[0]

    status_block = ev.get("status") or comp.get("status") or {}
    status_type = status_block.get("type") or {}
    status = _state_to_status(status_type.get("state"))

    home: dict | None = None
    away: dict | None = None
    for competitor in comp.get("competitors") or []:
        if competitor.get("homeAway") == "home":
            home = competitor
        elif competitor.get("homeAway") == "away":
            away = competitor
    if home is None or away is None:
        return None
    home_team = home.get("team") or {}
    away_team = away.get("team") or {}
    home_id = str(home_team.get("id") or "").strip()
    away_id = str(away_team.get("id") or "").strip()
    if not home_id or not away_id:
        return None

    return ParsedEvent(
        event_id=event_id,
        tipoff=tipoff,
        season_year=season_year,
        season_type=season_type,
        status=status,
        home_team_id=home_id,
        home_team=str(home_team.get("displayName") or home_team.get("name") or f"Team {home_id}"),
        home_score=_int(home.get("score")) if status == "post" else _int(home.get("score")),
        away_team_id=away_id,
        away_team=str(away_team.get("displayName") or away_team.get("name") or f"Team {away_id}"),
        away_score=_int(away.get("score")) if status == "post" else _int(away.get("score")),
    )


async def upsert_game(db: AsyncSession, parsed: ParsedEvent) -> BBGame:
    game = (
        await db.execute(select(BBGame).where(BBGame.espn_event_id == parsed.event_id))
    ).scalar_one_or_none()
    if game is None:
        game = BBGame(espn_event_id=parsed.event_id)
        db.add(game)
    game.season_year = parsed.season_year
    game.season_type = parsed.season_type
    game.tipoff_at = parsed.tipoff
    game.status = parsed.status
    game.home_team_id = parsed.home_team_id
    game.away_team_id = parsed.away_team_id
    game.home_team = parsed.home_team
    game.away_team = parsed.away_team
    if parsed.home_score is not None:
        game.home_score = parsed.home_score
    if parsed.away_score is not None:
        game.away_score = parsed.away_score
    return game


async def ingest_events(db: AsyncSession, events: list[dict]) -> list[BBGame]:
    games: list[BBGame] = []
    seen: set[str] = set()
    for ev in events:
        parsed = parse_event(ev)
        if parsed is None or parsed.event_id in seen:
            continue
        seen.add(parsed.event_id)
        games.append(await upsert_game(db, parsed))
    await db.commit()
    return games


# --- summary payloads -------------------------------------------------------


@dataclass
class ParsedSummary:
    event_id: str
    total: float | None = None
    over_odds: float | None = None
    under_odds: float | None = None
    provider: str | None = None
    injuries: dict[str, dict[str, str]] | None = None  # athlete_id -> {...}
    standings: dict[str, tuple[int, int]] | None = None  # team_id -> (wins, losses)
    player_rows: list[dict] = field(default_factory=list)  # box score lines (finished)


def parse_pickcenter(summary: dict) -> tuple[float | None, float | None, float | None, str | None]:
    entries = summary.get("pickcenter") or []
    usable = [e for e in entries if _num(e.get("overUnder")) is not None]
    if not usable:
        return None, None, None, None
    preferred = next((e for e in usable if (e.get("provider") or {}).get("name") == "DraftKings"), usable[0])
    provider = str((preferred.get("provider") or {}).get("name") or "unknown")
    return (
        _num(preferred.get("overUnder")),
        normalize_odds(_num(preferred.get("overOdds"))),
        normalize_odds(_num(preferred.get("underOdds"))),
        provider,
    )


def _same_line(
    snap: BBLineSnapshot, total: float, over_odds: float | None, under_odds: float | None
) -> bool:
    """True when a fresh line observation matches the stored one (no movement)."""
    return (
        snap.over_under == total
        and snap.over_odds == over_odds
        and snap.under_odds == under_odds
    )


def parse_injuries(summary: dict) -> dict[str, dict[str, str]] | None:
    block = summary.get("injuries")
    if block is None:
        return None
    result: dict[str, dict[str, str]] = {}
    for team_block in block or []:
        team = team_block.get("team") or {}
        team_id = str(team.get("id") or "").strip()
        for item in team_block.get("injuries") or []:
            athlete = item.get("athlete") or {}
            athlete_id = str(athlete.get("id") or "").strip()
            if not athlete_id:
                continue
            status_type = item.get("type") or {}
            fantasy = (item.get("details") or {}).get("fantasyStatus") or {}
            result[athlete_id] = {
                "name": str(athlete.get("displayName") or ""),
                "status": str(status_type.get("name") or item.get("status") or ""),
                "fantasy": str(fantasy.get("abbreviation") or ""),
                "team_id": team_id,
            }
    return result


def parse_standings(summary: dict) -> dict[str, tuple[int, int]] | None:
    standings = summary.get("standings")
    if not standings:
        return None
    result: dict[str, tuple[int, int]] = {}
    for group in standings.get("groups") or []:
        entries = (group.get("standings") or {}).get("entries") or []
        for entry in entries:
            team_id = str(entry.get("id") or "").strip()
            if not team_id:
                continue
            wins = losses = None
            for stat in entry.get("stats") or []:
                if stat.get("name") == "wins":
                    wins = _int(stat.get("value"))
                elif stat.get("name") == "losses":
                    losses = _int(stat.get("value"))
            if wins is None or losses is None:
                continue
            result[team_id] = (wins, losses)
    return result or None


def parse_player_rows(summary: dict) -> list[dict]:
    boxscore = summary.get("boxscore") or {}
    teams = boxscore.get("players") or []
    rows: list[dict] = []
    for team_block in teams:
        team = team_block.get("team") or {}
        team_id = str(team.get("id") or "").strip()
        if not team_id:
            continue
        for stat_block in team_block.get("statistics") or []:
            labels = [str(x) for x in stat_block.get("labels") or []]
            try:
                pts_idx = labels.index("PTS")
                blk_idx = labels.index("BLK")
            except ValueError:
                continue
            for athlete_entry in stat_block.get("athletes") or []:
                athlete = athlete_entry.get("athlete") or {}
                athlete_id = str(athlete.get("id") or "").strip()
                if not athlete_id:
                    continue
                stats = athlete_entry.get("stats") or []
                def value_at(idx: int) -> int:
                    if idx >= len(stats):
                        return 0
                    return _int(stats[idx]) or 0
                rows.append(
                    {
                        "team_id": team_id,
                        "athlete_id": athlete_id,
                        "name": str(athlete.get("displayName") or athlete.get("fullName") or ""),
                        "points": value_at(pts_idx),
                        "blocks": value_at(blk_idx),
                        "starter": bool(athlete_entry.get("starter")),
                        "did_not_play": bool(athlete_entry.get("didNotPlay")) or not athlete_entry.get("active", True),
                    }
                )
    return rows


async def ingest_summary(
    db: AsyncSession, client: ESPNClient, game: BBGame
) -> ParsedSummary:
    """Fetch a game summary; store line snapshot and finished box-score lines."""
    summary = await client.summary(game.espn_event_id)
    total, over_odds, under_odds, provider = parse_pickcenter(summary)
    parsed = ParsedSummary(
        event_id=game.espn_event_id,
        total=total,
        over_odds=over_odds,
        under_odds=under_odds,
        provider=provider,
        injuries=parse_injuries(summary),
        standings=parse_standings(summary),
        player_rows=parse_player_rows(summary) if game.status == "post" else [],
    )

    if total is not None:
        latest = (
            await db.execute(
                select(BBLineSnapshot)
                .where(BBLineSnapshot.game_id == game.id)
                .order_by(BBLineSnapshot.captured_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if latest is None or not _same_line(latest, total, over_odds, under_odds):
            db.add(
                BBLineSnapshot(
                    game_id=game.id,
                    source=f"espn:{provider or 'unknown'}",
                    over_under=total,
                    over_odds=over_odds,
                    under_odds=under_odds,
                )
            )

    # Keep the injury-report timeline (late-scratch / gate-5 analysis input).
    if parsed.injuries is not None:
        latest_lineup = (
            await db.execute(
                select(BBLineupSnapshot)
                .where(BBLineupSnapshot.game_id == game.id)
                .order_by(BBLineupSnapshot.captured_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if latest_lineup is None or latest_lineup.players != parsed.injuries:
            db.add(
                BBLineupSnapshot(
                    game_id=game.id,
                    source="espn",
                    players=parsed.injuries,
                )
            )

    if parsed.player_rows:
        existing = set(
            (
                await db.execute(
                    select(BBPlayerGameStat.athlete_id).where(
                        BBPlayerGameStat.game_id == game.id
                    )
                )
            ).scalars()
        )
        for row in parsed.player_rows:
            if row["athlete_id"] in existing or row["did_not_play"]:
                continue
            db.add(
                BBPlayerGameStat(
                    game_id=game.id,
                    team_id=row["team_id"],
                    athlete_id=row["athlete_id"],
                    athlete_name=row["name"],
                    points=row["points"],
                    blocks=row["blocks"],
                    starter=row["starter"],
                    did_not_play=False,
                )
            )

    await db.commit()
    return parsed


async def ingest_team_schedule(
    db: AsyncSession, client: ESPNClient, team_id: str, season_year: int
) -> int:
    events = await client.team_schedule(team_id, season_year)
    games = await ingest_events(db, events)
    return len(games)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
