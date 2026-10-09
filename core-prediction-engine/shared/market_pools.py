"""Over 1.5 Goals and first-half corners drawn from one pool so a treble can mix them."""

from shared.corners import MARKET, _priced_lines, collect_corner_legs
from shared.poisson import prob_over_15
from shared.time_buckets import local_day
from shared.treble_generator import (
    CandidateLeg,
    TrebleCandidate,
    busiest_day_from_legs,
    collect_goals_legs,
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
) -> list[CandidateLeg]:
    """Legs with a live price in a requested market, ignoring the eligibility bars."""
    del history  # pricing needs no model history
    legs: list[CandidateLeg] = []
    if want_goals:
        for fixture in fixtures:
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
) -> list[CandidateLeg]:
    """Eligible legs from every requested market. One fixture can add two legs;
    the combiner drops any trio that repeats a fixture."""
    legs: list[CandidateLeg] = []
    if want_goals:
        legs.extend(collect_goals_legs(fixtures))
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
    limit: int = 5,
) -> list[TrebleCandidate]:
    """Best same-day trebles drawn from the requested markets together."""
    legs = build_leg_pool(
        fixtures,
        history,
        want_goals=want_goals,
        want_corners=want_corners,
    )
    return trebles_from_legs(
        legs,
        min_combined_odds=min_combined_odds,
        limit=limit,
        unique_fixtures=True,
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
