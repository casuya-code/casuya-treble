import itertools
from dataclasses import dataclass
from uuid import UUID

from shared.models import Fixture, TimeCategory
from shared.poisson import prob_over_15
from shared.time_buckets import classify_kickoff


@dataclass
class CandidateLeg:
    fixture_id: UUID
    odds: float
    model_probability: float
    kickoff_category: TimeCategory


@dataclass
class TrebleCandidate:
    legs: tuple[CandidateLeg, CandidateLeg, CandidateLeg]
    combined_odds: float
    model_probability: float
    time_category: TimeCategory


def _leg_from_fixture(fixture: Fixture) -> CandidateLeg | None:
    odds = fixture.closing_odds_over_15 or fixture.opening_odds_over_15
    if not odds or odds <= 1.0:
        return None
    return CandidateLeg(
        fixture_id=fixture.id,
        odds=odds,
        model_probability=prob_over_15(fixture.lambda_home, fixture.lambda_away),
        kickoff_category=classify_kickoff(fixture.kickoff_at),
    )


def find_best_trebles(
    fixtures: list[Fixture],
    *,
    min_combined_odds: float = 3.0,
    time_category: TimeCategory | None = None,
    limit: int = 5,
) -> list[TrebleCandidate]:
    legs: list[CandidateLeg] = []
    for fixture in fixtures:
        leg = _leg_from_fixture(fixture)
        if leg is None:
            continue
        if time_category and leg.kickoff_category != time_category:
            continue
        legs.append(leg)

    candidates: list[TrebleCandidate] = []
    for combo in itertools.combinations(legs, 3):
        combined_odds = combo[0].odds * combo[1].odds * combo[2].odds
        if combined_odds < min_combined_odds:
            continue
        model_p = combo[0].model_probability * combo[1].model_probability * combo[2].model_probability
        categories = {leg.kickoff_category for leg in combo}
        if len(categories) != 1:
            continue
        candidates.append(
            TrebleCandidate(
                legs=combo,
                combined_odds=combined_odds,
                model_probability=model_p,
                time_category=combo[0].kickoff_category,
            )
        )

    candidates.sort(key=lambda c: (c.model_probability, c.combined_odds), reverse=True)
    return candidates[:limit]
