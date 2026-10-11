"""First-half corner chances from recent corner counts, kept only when the price is generous."""

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from shared.league_names import league_key
from shared.poisson import edge_vs_market, implied_probability, poisson_pmf
from shared.team_names import team_key
from shared.team_strength import (
    MIN_LEAGUE_GAMES,
    MIN_VENUE_GAMES,
    HistoryIndex,
    _avg,
    _weight,
)
from shared.time_buckets import local_day
from shared.treble_generator import CandidateLeg, TrebleCandidate, slips_from_legs, trebles_from_legs

# The score files record the full match. About 45% of corners arrive before half-time.
FIRST_HALF_SHARE = 0.45
MIN_CORNER_ODDS = 1.20
NAIROBI = ZoneInfo("Africa/Nairobi")

# BetPawa quotes whichever 1H lines it likes; 2.5 has since disappeared in
# favour of 4.5 and 5.5. Every line the book offers stays in play so the
# picker can take the one carrying the best edge.
CORNER_LINES = ("2.5", "3.5", "4.5", "5.5", "6.5")
LINE_FIELD = {line: f"fh_corner_over_{line.replace('.', '')}" for line in CORNER_LINES}
MARKET = {float(line): f"Over {line} Corners 1H" for line in CORNER_LINES}


def prob_over_line(lam: float, line: float) -> float:
    """Chance the corner count clears a .5 line. Over 2.5 means 3 or more."""
    need = int(line) + 1
    under = sum(poisson_pmf(k, lam) for k in range(need))
    return float(max(0.0, min(1.0, 1.0 - under)))


@dataclass(frozen=True, slots=True)
class CornerMatch:
    """A finished match reduced to plain corner values, for the same reason as
    HistoryMatch: the scoring walk reads these millions of times."""

    home_key: str
    away_key: str
    league_key: str | None
    league: str
    day: date
    day_iso: str
    home_corners: int
    away_corners: int


def project_corner_history(matches) -> list[CornerMatch]:
    """Reduce finished matches to plain corner rows, dropping any without both counts."""
    rows: list[CornerMatch] = []
    for match in matches:
        if match.home_corners is None or match.away_corners is None:
            continue
        day = local_day(match.kickoff_at)
        rows.append(
            CornerMatch(
                home_key=team_key(match.home_team),
                away_key=team_key(match.away_team),
                league_key=league_key(match.league),
                league=match.league,
                day=day,
                day_iso=day.isoformat(),
                home_corners=match.home_corners,
                away_corners=match.away_corners,
            )
        )
    return rows


def _corners_from_rows(
    candidates: list,
    *,
    home_key: str,
    away_key: str,
    today: date,
) -> float | None:
    """Expected first-half corners from rows already known to be in-league."""
    finished = []
    seen: set[tuple[str, str, str]] = set()
    for row in candidates:
        stamp = (row.home_key, row.away_key, row.day_iso)
        if stamp in seen:
            continue
        seen.add(stamp)
        finished.append(row)
    if len(finished) < MIN_LEAGUE_GAMES:
        return None

    finished.sort(key=lambda row: row.day, reverse=True)
    home_games = [row for row in finished if row.home_key == home_key][:10]
    away_games = [row for row in finished if row.away_key == away_key][:10]
    if len(home_games) < MIN_VENUE_GAMES or len(away_games) < MIN_VENUE_GAMES:
        return None

    def weighted(samples, value):
        return _avg([(_weight(row.day, today), value(row)) for row in samples])

    league_home = weighted(finished, lambda row: row.home_corners)
    league_away = weighted(finished, lambda row: row.away_corners)
    home_attack = weighted(home_games, lambda row: row.home_corners)
    home_defence = weighted(home_games, lambda row: row.away_corners)
    away_attack = weighted(away_games, lambda row: row.away_corners)
    away_defence = weighted(away_games, lambda row: row.home_corners)
    if None in (league_home, league_away, home_attack, home_defence, away_attack, away_defence):
        return None
    if league_home <= 0 or league_away <= 0:
        return None

    lambda_home = (home_attack / league_home) * (away_defence / league_away) * league_home
    lambda_away = (away_attack / league_away) * (home_defence / league_home) * league_away

    league_total = league_home + league_away
    raw_total = lambda_home + lambda_away
    if league_total <= 0:
        return None
    # Six to twelve games a side is a thin sample: pull extreme strength ratios
    # back toward the league mean so a lucky corner run cannot inflate a high
    # 1H line into a fake edge. A 1.41x corner rate becomes sqrt(1.41) = 1.19x.
    multiplier = (raw_total / league_total) ** 0.5 if raw_total > 0 else 1.0
    total = min(max(league_total * multiplier, 1.0), 14.0)
    return round(total * FIRST_HALF_SHARE, 3)


def estimate_first_half_corners(
    matches: list,
    *,
    home_team: str,
    away_team: str,
    league: str,
    today: date | None = None,
) -> float | None:
    """Expected first-half corners. None when the corner sample is too thin.

    Projects `matches` on this call. Callers scoring many fixtures at once
    should build a CornerIndex once and use `estimate_corners_from_index`.
    """
    today = today or datetime.now(NAIROBI).date()
    index = HistoryIndex(project_corner_history(matches))
    return estimate_corners_from_index(index, home_team=home_team, away_team=away_team, league=league, today=today)


def estimate_corners_from_index(
    index: HistoryIndex,
    *,
    home_team: str,
    away_team: str,
    league: str,
    today: date,
) -> float | None:
    """Same estimate, against a prebuilt index. One projection serves the whole run."""
    return _corners_from_rows(
        index.for_league(league),
        home_key=team_key(home_team),
        away_key=team_key(away_team),
        today=today,
    )


def _priced_lines(fixture) -> list[tuple[float, float]]:
    """Every 1H corner line the book quoted, as (line, odds)."""
    lines = []
    for line in CORNER_LINES:
        odds = getattr(fixture, LINE_FIELD[line], None)
        if odds and odds > 1.0:
            lines.append((float(line), float(odds)))
    return lines


def corner_leg(fixture, history: list, index: HistoryIndex | None = None) -> CandidateLeg | None:
    """The corner line where the model chance is higher than the price implies.

    Every line the book quoted stays in play, so a quiet fixture priced at 5.5
    can beat a busy one priced at 3.5 whenever the edge is larger.
    """
    if index is None:
        index = HistoryIndex(project_corner_history(history))
    expected = estimate_corners_from_index(
        index,
        home_team=fixture.home_team,
        away_team=fixture.away_team,
        league=fixture.league,
        today=local_day(fixture.kickoff_at),
    )
    if expected is None:
        return None
    best: tuple[float, float, float, str] | None = None
    for line, odds in _priced_lines(fixture):
        if odds < MIN_CORNER_ODDS:
            continue
        probability = prob_over_line(expected, line)
        edge = edge_vs_market(probability, odds)
        if edge is None or edge <= 0 or probability <= implied_probability(odds):
            continue
        if best is None or edge > best[0]:
            best = (edge, odds, probability, MARKET[line])
    if best is None:
        return None
    _edge, odds, probability, market = best
    return CandidateLeg(
        fixture_id=fixture.id,
        odds=odds,
        model_probability=probability,
        kickoff_day=local_day(fixture.kickoff_at),
        market=market,
    )


def collect_corner_legs(fixtures: list, history: list) -> list[CandidateLeg]:
    """Every fixture where a corner line carries a positive edge.

    The history is projected once and shared across every fixture; projecting it
    per fixture was the bulk of the generate time.
    """
    index = HistoryIndex(project_corner_history(history))
    legs: list[CandidateLeg] = []
    for fixture in fixtures:
        leg = corner_leg(fixture, history, index)
        if leg is None:
            continue
        legs.append(leg)
    return legs


def find_best_corner_trebles(
    fixtures: list,
    history: list,
    *,
    min_combined_odds: float = 3.0,
    max_combined_odds: float | None = None,
    max_legs: int = 3,
    limit: int = 5,
) -> list[TrebleCandidate]:
    legs = collect_corner_legs(fixtures, history)
    if max_combined_odds is None and max_legs == 3:
        # Legacy path: same-day 3-leg trebles, kept for callers that want them.
        return trebles_from_legs(
            legs,
            min_combined_odds=min_combined_odds,
            limit=limit,
            unique_fixtures=True,
        )
    # Modern path: slips of 1..max_legs teams inside [min, max], no repeats.
    return slips_from_legs(
        legs,
        min_combined_odds=min_combined_odds,
        max_combined_odds=max_combined_odds,
        max_legs=max_legs,
        limit=limit,
    )


# Kept under the old name for anything still importing the private helper.
_trebles_from_legs = trebles_from_legs
