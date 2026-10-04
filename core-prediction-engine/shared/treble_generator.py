import itertools
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from shared.models import Fixture, TimeCategory
from shared.poisson import prob_over_15
from shared.time_buckets import local_day

# A leg must clear both bars before it can sit on a treble.
MIN_LEG_PROBABILITY = 0.85
MIN_LEG_ODDS = 1.20


@dataclass
class CandidateLeg:
    fixture_id: UUID
    odds: float
    model_probability: float
    kickoff_day: date


@dataclass
class TrebleCandidate:
    legs: tuple[CandidateLeg, CandidateLeg, CandidateLeg]
    combined_odds: float
    model_probability: float
    time_category: TimeCategory
    forced: bool = False


def _leg_from_fixture(fixture: Fixture, *, priced_only: bool = False) -> CandidateLeg | None:
    odds = fixture.closing_odds_over_15 or fixture.opening_odds_over_15
    if not odds or odds <= 1.0:
        return None
    probability = prob_over_15(fixture.lambda_home, fixture.lambda_away)
    if not priced_only and (odds < MIN_LEG_ODDS or probability < MIN_LEG_PROBABILITY):
        return None
    return CandidateLeg(
        fixture_id=fixture.id,
        odds=odds,
        model_probability=probability,
        kickoff_day=local_day(fixture.kickoff_at),
    )


def find_best_trebles(
    fixtures: list[Fixture],
    *,
    min_combined_odds: float = 3.0,
    limit: int = 5,
) -> list[TrebleCandidate]:
    legs: list[CandidateLeg] = []
    for fixture in fixtures:
        leg = _leg_from_fixture(fixture)
        if leg is None:
            continue
        legs.append(leg)

    qualifying: list[TrebleCandidate] = []
    short: list[TrebleCandidate] = []
    for combo in itertools.combinations(legs, 3):
        days = {leg.kickoff_day for leg in combo}
        if len(days) != 1:
            continue
        combined_odds = combo[0].odds * combo[1].odds * combo[2].odds
        model_p = combo[0].model_probability * combo[1].model_probability * combo[2].model_probability
        candidate = TrebleCandidate(
            legs=combo,
            combined_odds=combined_odds,
            model_probability=model_p,
            time_category=TimeCategory.ALL_DAY,
            forced=combined_odds < min_combined_odds,
        )
        if candidate.forced:
            short.append(candidate)
        else:
            qualifying.append(candidate)

    if qualifying:
        qualifying.sort(key=lambda c: (c.model_probability, c.combined_odds), reverse=True)
        return qualifying[:limit]
    short.sort(key=lambda c: (c.combined_odds, c.model_probability), reverse=True)
    return short[:limit]


def count_priced_legs(fixtures: list[Fixture]) -> int:
    return sum(1 for fixture in fixtures if _leg_from_fixture(fixture, priced_only=True) is not None)


def count_eligible_legs(fixtures: list[Fixture]) -> int:
    return sum(1 for fixture in fixtures if _leg_from_fixture(fixture) is not None)


def busiest_day_count(fixtures: list[Fixture]) -> int:
    counts: dict[date, int] = {}
    for fixture in fixtures:
        leg = _leg_from_fixture(fixture, priced_only=True)
        if leg is None:
            continue
        counts[leg.kickoff_day] = counts.get(leg.kickoff_day, 0) + 1
    return max(counts.values(), default=0)


def empty_treble_reason(*, stored: int, upcoming: int, priced: int, same_day: int, eligible: int = 0) -> str:
    """Why generate found no treble. The desk turns the code into a sentence."""
    if stored == 0:
        return "none_loaded"
    if upcoming == 0:
        return "all_started"
    if priced == 0:
        return "no_price"
    if priced < 3 or same_day < 3:
        return "spread_days" if priced >= 3 else "too_few"
    if eligible < 3:
        return "below_floor"
    return "below_min"
