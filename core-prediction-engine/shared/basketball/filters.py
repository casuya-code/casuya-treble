"""Pure history helpers for the basketball filter: O/U rates, H2H pace, B2B, usage.

Every helper is strict: when there is not enough data it returns None (or an
empty selection) so the consuming gate fails instead of guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class FinishedGame:
    """One finished game with scores and (optionally) its market total."""

    tipoff: datetime
    home_team_id: str
    away_team_id: str
    home_score: int
    away_score: int
    line: float | None
    season_type: int = 2


@dataclass(frozen=True)
class PlayerLine:
    """Aggregated per-athlete season line."""

    athlete_id: str
    name: str
    games: int
    points: int
    blocks: int

    @property
    def ppg(self) -> float:
        return self.points / self.games if self.games else 0.0

    @property
    def bpg(self) -> float:
        return self.blocks / self.games if self.games else 0.0


def over_rate(games: list[FinishedGame], window: int) -> tuple[float | None, int]:
    """Hit rate of the closing total going OVER, newest `window` games with a line.

    Returns (rate, samples). (None, 0) when no game in the window has a line.
    """
    with_line = [g for g in games if g.line is not None]
    with_line.sort(key=lambda g: g.tipoff, reverse=True)
    sample = with_line[:window]
    if not sample:
        return None, 0
    hits = sum(1 for g in sample if (g.home_score + g.away_score) > float(g.line))  # type: ignore[arg-type]
    return hits / len(sample), len(sample)


def h2h_pace(
    games: list[FinishedGame],
    team_a_id: str,
    team_b_id: str,
    *,
    window: int,
    league_ppp: float,
) -> tuple[float | None, int]:
    """Head-to-head pace proxy in possessions per team.

    possessions ≈ combined final score / (2 * league points-per-possession).
    Uses the newest `window` regular-season meetings between the pair
    (either venue). Returns (pace, meetings).
    """
    if league_ppp <= 0:
        raise ValueError("league_ppp must be positive")
    meetings = [
        g
        for g in games
        if g.season_type == 2
        and {g.home_team_id, g.away_team_id} == {team_a_id, team_b_id}
    ]
    meetings.sort(key=lambda g: g.tipoff, reverse=True)
    sample = meetings[:window]
    if not sample:
        return None, 0
    paces = [(g.home_score + g.away_score) / (2.0 * league_ppp) for g in sample]
    return sum(paces) / len(paces), len(sample)


def back_to_back(
    finished_before: list[FinishedGame],
    tipoff: datetime,
) -> bool | None:
    """True when the team already played the previous day (US Eastern dates).

    `finished_before` must contain only that team's finished games with
    tipoff < the target game. None when the team has no prior game (unknown).
    """
    if not finished_before:
        return None
    latest = max(finished_before, key=lambda g: g.tipoff)
    prev_day: date = latest.tipoff.astimezone(ET).date()
    target_day: date = tipoff.astimezone(ET).date()
    return (target_day - prev_day).days == 1


def aggregate_players(rows: list[tuple[str, str, int, int]]) -> list[PlayerLine]:
    """Aggregate raw (athlete_id, name, points, blocks) lines into PlayerLine stats."""
    buckets: dict[str, dict[str, object]] = {}
    for athlete_id, name, points, blocks in rows:
        bucket = buckets.setdefault(
            athlete_id, {"name": name, "games": 0, "points": 0, "blocks": 0}
        )
        bucket["name"] = name or str(bucket["name"])
        bucket["games"] = int(bucket["games"]) + 1
        bucket["points"] = int(bucket["points"]) + points
        bucket["blocks"] = int(bucket["blocks"]) + blocks
    return [
        PlayerLine(
            athlete_id=athlete_id,
            name=str(bucket["name"]),
            games=int(bucket["games"]),
            points=int(bucket["points"]),
            blocks=int(bucket["blocks"]),
        )
        for athlete_id, bucket in buckets.items()
    ]


def top_usage_and_rim(
    players: list[PlayerLine], min_games: int
) -> tuple[list[PlayerLine], PlayerLine | None]:
    """Top-4 usage (scoring) players plus the team's leading shot blocker.

    Returns ([top4], rim_protector). The rim protector is None when nobody
    qualifies on games played; callers must treat that as unconfirmable.
    """
    qualified = [p for p in players if p.games >= min_games]
    if not qualified:
        return [], None
    by_scoring = sorted(qualified, key=lambda p: (p.ppg, p.points), reverse=True)
    top4 = by_scoring[:4]
    rim = max(qualified, key=lambda p: (p.bpg, p.blocks))
    return top4, rim
