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
    market: str = "Over 1.5 Goals"


@dataclass
class TrebleCandidate:
    legs: tuple[CandidateLeg, ...]
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


def collect_goals_legs(fixtures: list[Fixture]) -> list[CandidateLeg]:
    """Every fixture that clears the Over 1.5 Goals bars."""
    legs: list[CandidateLeg] = []
    for fixture in fixtures:
        leg = _leg_from_fixture(fixture)
        if leg is None:
            continue
        legs.append(leg)
    return legs


def find_best_trebles(
    fixtures: list[Fixture],
    *,
    min_combined_odds: float = 3.0,
    max_combined_odds: float | None = None,
    max_legs: int = 3,
    limit: int = 5,
) -> list[TrebleCandidate]:
    legs = collect_goals_legs(fixtures)
    if max_combined_odds is None and max_legs == 3:
        # Legacy path: same-day 3-leg trebles, kept for callers that want them.
        return trebles_from_legs(legs, min_combined_odds=min_combined_odds, limit=limit)
    return slips_from_legs(
        legs,
        min_combined_odds=min_combined_odds,
        max_combined_odds=max_combined_odds,
        max_legs=max_legs,
        limit=limit,
    )


def trebles_from_legs(
    legs: list[CandidateLeg],
    *,
    min_combined_odds: float,
    limit: int,
    unique_fixtures: bool = False,
) -> list[TrebleCandidate]:
    """Same-day pairing for legs that already cleared their market bar.

    unique_fixtures keeps a fixture from appearing twice in one treble, which
    matters when a fixture qualified in more than one market.
    """
    qualifying: list[TrebleCandidate] = []
    short: list[TrebleCandidate] = []
    for combo in itertools.combinations(legs, 3):
        days = {leg.kickoff_day for leg in combo}
        if len(days) != 1:
            continue
        if unique_fixtures and len({leg.fixture_id for leg in combo}) != 3:
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


def slips_from_legs(
    legs: list[CandidateLeg],
    *,
    min_combined_odds: float = 2.1,
    max_combined_odds: float | None = None,
    max_legs: int = 3,
    limit: int = 5,
) -> list[TrebleCandidate]:
    """Same-day slips of 1..max_legs legs whose combined odds land in the range.

    This is the modern picker: a slip can be one, two, or three teams and every
    fixture is used in at most one returned slip, so a team never repeats across
    the slips of a single run. Nothing is marked forced — a slip only exists
    when its combined odds really sit inside ``[min_combined_odds,
    max_combined_odds]``.
    """
    if max_legs < 1 or max_combined_odds is None or max_combined_odds < min_combined_odds:
        return []

    by_day: dict[date, list[CandidateLeg]] = {}
    for leg in legs:
        by_day.setdefault(leg.kickoff_day, []).append(leg)

    candidates: list[TrebleCandidate] = []
    for day_legs in by_day.values():
        for width in range(1, max_legs + 1):
            for combo in itertools.combinations(day_legs, width):
                if len({leg.fixture_id for leg in combo}) != width:
                    continue  # the same match can never appear twice in one slip
                combined = 1.0
                model_p = 1.0
                for leg in combo:
                    combined *= leg.odds
                    model_p *= leg.model_probability
                if combined < min_combined_odds or combined > max_combined_odds:
                    continue
                candidates.append(
                    TrebleCandidate(
                        legs=combo,
                        combined_odds=combined,
                        model_probability=model_p,
                        time_category=TimeCategory.ALL_DAY,
                        forced=False,
                    )
                )

    candidates.sort(key=lambda c: (c.model_probability, c.combined_odds), reverse=True)

    chosen: list[TrebleCandidate] = []
    used: set[UUID] = set()
    for candidate in candidates:
        if any(leg.fixture_id in used for leg in candidate.legs):
            continue  # a team that already sits on a chosen slip is not repeated
        chosen.append(candidate)
        used.update(leg.fixture_id for leg in candidate.legs)
        if len(chosen) >= limit:
            break
    return chosen


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


def busiest_day_from_legs(legs: list[CandidateLeg]) -> int:
    """How many priced legs share the busiest single day, across any market."""
    counts: dict[date, int] = {}
    for leg in legs:
        counts[leg.kickoff_day] = counts.get(leg.kickoff_day, 0) + 1
    return max(counts.values(), default=0)


def empty_treble_reason(*, stored: int, upcoming: int, priced: int, same_day: int, eligible: int = 0) -> str:
    """Why generate found no slip. The desk turns the code into a sentence."""
    if stored == 0:
        return "none_loaded"
    if upcoming == 0:
        return "all_started"
    if priced == 0:
        return "no_price"
    if same_day < 1:
        return "spread_days"
    if eligible < 1:
        return "below_floor"
    return "below_min"
