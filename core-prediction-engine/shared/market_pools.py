"""Over 1.5 Goals and first-half corners drawn from one pool so a treble can mix them."""

from shared.corners import MARKET, _priced_lines, collect_corner_legs
from shared.poisson import prob_over_15
from shared.time_buckets import local_day
from shared.treble_generator import (
    CandidateLeg,
    TrebleCandidate,
    busiest_day_from_legs,
    collect_goals_legs,
    slips_from_legs,
    trebles_from_legs,
)

GOALS = "goals"
CORNERS = "corners"
KNOWN_MARKETS = (GOALS, CORNERS)


def parse_markets(values: list[str]) -> set[str]:
    """Normalise the request into a known market set. Falls back to goals."""
    found: set[str] = set()
    for value in values:
        for part in str(value).split(","):
            name = part.strip().lower()
            if name in KNOWN_MARKETS:
                found.add(name)
    return found or {GOALS}


def _goals_priced_leg(fixture) -> CandidateLeg | None:
    """Over 1.5 price is on the board, whatever the model says."""
    odds = fixture.closing_odds_over_15 or fixture.opening_odds_over_15
    if not odds or odds <= 1.0:
        return None
    return CandidateLeg(
        fixture_id=fixture.id,
        odds=float(odds),
        model_probability=prob_over_15(fixture.lambda_home, fixture.lambda_away),
        kickoff_day=local_day(fixture.kickoff_at),
    )


def _corner_priced_leg(fixture) -> CandidateLeg | None:
    """Any quoted first-half corner line, with no edge test. Diagnostics only."""
    lines = _priced_lines(fixture)
    if not lines:
        return None
    line, odds = max(lines, key=lambda item: item[1])
    return CandidateLeg(
        fixture_id=fixture.id,
        odds=float(odds),
        model_probability=0.0,
        kickoff_day=local_day(fixture.kickoff_at),
        market=MARKET[line],
    )


def collect_priced_legs(
    fixtures: list,
    history: list,
    *,
    want_goals: bool,
    want_corners: bool,
    goals_fixtures: list | None = None,
) -> list[CandidateLeg]:
    """Legs with a live price in a requested market, ignoring the eligibility bars.

    ``goals_fixtures`` is the modeled subset for Over 1.5 and defaults to every
    fixture, so corners-only callers keep their behaviour.
    """
    del history  # pricing needs no model history
    goals = fixtures if goals_fixtures is None else goals_fixtures
    legs: list[CandidateLeg] = []
    if want_goals:
        for fixture in goals:
            leg = _goals_priced_leg(fixture)
            if leg is not None:
                legs.append(leg)
    if want_corners:
        for fixture in fixtures:
            leg = _corner_priced_leg(fixture)
            if leg is not None:
                legs.append(leg)
    return legs


def build_leg_pool(
    fixtures: list,
    history: list,
    *,
    want_goals: bool,
    want_corners: bool,
    goals_fixtures: list | None = None,
) -> list[CandidateLeg]:
    """Eligible legs from every requested market. One fixture can add two legs;
    the combiner drops any trio that repeats a fixture.

    Corners draw on ``fixtures``; goals draw on ``goals_fixtures``, the fixtures the
    model actually estimated. Nothing unmodeled can become a leg.
    """
    goals = fixtures if goals_fixtures is None else goals_fixtures
    legs: list[CandidateLeg] = []
    if want_goals:
        legs.extend(collect_goals_legs(goals))
    if want_corners:
        legs.extend(collect_corner_legs(fixtures, history))
    return legs


def find_mixed_trebles(
    fixtures: list,
    history: list,
    *,
    want_goals: bool,
    want_corners: bool,
    min_combined_odds: float = 3.0,
    max_combined_odds: float | None = None,
    max_legs: int = 3,
    limit: int = 5,
    goals_fixtures: list | None = None,
) -> list[TrebleCandidate]:
    """Best same-day slips drawn from the requested markets together.

    When an explicit ``max_combined_odds`` is given the modern combiner runs:
    slips of 1..max_legs teams inside ``[min, max]`` with no repeated teams
    across slips. Without it, the legacy 3-leg treble picker is kept for
    callers that still expect it.
    """
    legs = build_leg_pool(
        fixtures,
        history,
        want_goals=want_goals,
        want_corners=want_corners,
        goals_fixtures=goals_fixtures,
    )
    if max_combined_odds is None and max_legs == 3:
        return trebles_from_legs(
            legs,
            min_combined_odds=min_combined_odds,
            limit=limit,
            unique_fixtures=True,
        )
    return slips_from_legs(
        legs,
        min_combined_odds=min_combined_odds,
        max_combined_odds=max_combined_odds,
        max_legs=max_legs,
        limit=limit,
    )


__all__ = [
    "CORNERS",
    "GOALS",
    "KNOWN_MARKETS",
    "build_leg_pool",
    "busiest_day_from_legs",
    "collect_priced_legs",
    "find_mixed_trebles",
    "parse_markets",
]
