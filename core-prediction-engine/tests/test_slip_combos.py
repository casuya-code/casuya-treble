"""The modern 1-3 team slip picker: odds range, same-day, no repeats, no forced."""

from datetime import date
from uuid import uuid4

from shared.treble_generator import CandidateLeg, slips_from_legs

DAY = date(2026, 10, 10)


def _legs(odds: list[float], day: date = DAY) -> list[CandidateLeg]:
    return [
        CandidateLeg(
            fixture_id=uuid4(),
            odds=value,
            model_probability=0.95,
            kickoff_day=day,
        )
        for value in odds
    ]


def test_doubles_only_when_singles_and_triples_are_out_of_range():
    legs = _legs([1.5, 1.5, 1.5, 1.5])
    slips = slips_from_legs(legs, min_combined_odds=2.1, max_combined_odds=2.5, limit=5)

    assert len(slips) == 2  # 4 legs -> two doubles of 2.25 each
    for slip in slips:
        assert len(slip.legs) == 2
        assert 2.1 <= slip.combined_odds <= 2.5
        assert slip.forced is False


def test_single_leg_slip_is_allowed():
    legs = _legs([2.2, 1.3])
    slips = slips_from_legs(legs, min_combined_odds=2.1, max_combined_odds=2.5, limit=5)

    assert len(slips) == 1
    assert len(slips[0].legs) == 1
    assert abs(slips[0].combined_odds - 2.2) < 1e-9


def test_triples_when_doubles_are_below_range():
    legs = _legs([1.3, 1.3, 1.3, 1.3, 1.3, 1.3])
    slips = slips_from_legs(legs, min_combined_odds=2.1, max_combined_odds=2.5, limit=5)

    assert len(slips) == 2  # 6 legs -> two trebles of ~2.197 each
    for slip in slips:
        assert len(slip.legs) == 3
        assert 2.1 <= slip.combined_odds <= 2.5


def test_teams_never_repeat_across_slips():
    legs = _legs([1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5])
    slips = slips_from_legs(legs, min_combined_odds=2.1, max_combined_odds=2.5, limit=5)

    used = {leg.fixture_id for slip in slips for leg in slip.legs}
    assert len(used) == len(legs)  # every team used at most once
    assert len(used) == 8


def test_mixed_day_cross_pairs_are_never_built():
    legs = _legs([1.5, 1.5], day=DAY) + _legs([1.5, 1.5], day=date(2026, 10, 11))
    slips = slips_from_legs(legs, min_combined_odds=2.1, max_combined_odds=2.5, limit=5)

    assert len(slips) == 2
    for slip in slips:
        assert len({leg.kickoff_day for leg in slip.legs}) == 1  # same day only


def test_out_of_range_combination_is_skipped():
    legs = _legs([1.3, 1.3])
    assert slips_from_legs(legs, min_combined_odds=2.1, max_combined_odds=2.5) == []
    assert slips_from_legs(legs, min_combined_odds=2.1, max_combined_odds=2.0) == []


def test_legacy_treble_picker_is_untouched():
    from shared.treble_generator import trebles_from_legs

    legs = _legs([1.5, 1.5, 1.5, 1.5])
    trebles = trebles_from_legs(legs, min_combined_odds=3.0, limit=5)
    assert trebles
    for treble in trebles:
        assert len(treble.legs) == 3
        assert abs(treble.combined_odds - 3.375) < 1e-9