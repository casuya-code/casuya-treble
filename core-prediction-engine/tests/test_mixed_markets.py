from datetime import datetime, timezone
from uuid import uuid4

from shared.corners import find_best_corner_trebles
from shared.market_pools import (
    build_leg_pool,
    find_mixed_trebles,
    parse_markets,
)
from shared.models import Fixture
from shared.treble_generator import find_best_trebles

LEAGUE = "England / Premier League"
KICK = datetime(2026, 10, 5, 15, 0, tzinfo=timezone.utc)


def _corner_history() -> list[Fixture]:
    """Enough weighted corner samples for the first-half estimator to answer."""
    rows = []
    for day in range(1, 13):
        rows.append(_played("Hosts", "Filler", 8, 2, day))
        rows.append(_played("Marker", "Guests", 3, 7, day))
        rows.append(_played("Alpha", "Beta", 5, 4, day))
    return rows


def _played(home: str, away: str, hc: int, ac: int, day: int) -> Fixture:
    return Fixture(
        id=uuid4(),
        home_team=home,
        away_team=away,
        league=LEAGUE,
        kickoff_at=datetime(2026, 8, day, 15, 0, tzinfo=timezone.utc),
        home_corners=hc,
        away_corners=ac,
    )


def _goals(name: str) -> Fixture:
    """High-scoring fixture with an Over 1.5 price but no corner quote."""
    return Fixture(
        id=uuid4(),
        home_team=f"Goals H {name}",
        away_team=f"Goals A {name}",
        league=LEAGUE,
        kickoff_at=KICK,
        lambda_home=2.2,
        lambda_away=1.8,
        closing_odds_over_15=1.5,
    )


def _corner(name: str) -> Fixture:
    """First-half corner price with a positive edge, no Over 1.5 quote."""
    return Fixture(
        id=uuid4(),
        home_team="Hosts",
        away_team="Guests",
        league=LEAGUE,
        kickoff_at=KICK,
        lambda_home=1.1,
        lambda_away=0.9,
        fh_corner_over_35=2.4,
        external_id=f"corner-{name}",
    )


def _both(name: str) -> Fixture:
    """Qualifies in Over 1.5 Goals and in first-half corners at the same time."""
    return Fixture(
        id=uuid4(),
        home_team="Hosts",
        away_team="Guests",
        league=LEAGUE,
        kickoff_at=KICK,
        lambda_home=2.2,
        lambda_away=1.8,
        closing_odds_over_15=1.5,
        fh_corner_over_35=2.4,
        external_id=f"both-{name}",
    )


def test_mixed_request_pairs_goals_and_corners():
    history = _corner_history()
    fixtures = [_goals("1"), _goals("2"), _corner("1"), _corner("2")]

    trebles = find_mixed_trebles(
        fixtures,
        history,
        want_goals=True,
        want_corners=True,
        min_combined_odds=3.0,
        limit=5,
    )

    assert trebles, "the mixed pool should still find a treble"
    for treble in trebles:
        markets = {leg.market for leg in treble.legs}
        assert "Over 1.5 Goals" in markets
        assert any("Corner" in market for market in markets), markets


def test_a_fixture_never_repeats_inside_one_treble():
    history = _corner_history()
    fixtures = [_both("1"), _goals("2"), _goals("3"), _corner("1")]

    trebles = find_mixed_trebles(
        fixtures,
        history,
        want_goals=True,
        want_corners=True,
        min_combined_odds=3.0,
        limit=5,
    )

    assert trebles
    for treble in trebles:
        ids = [leg.fixture_id for leg in treble.legs]
        assert len(set(ids)) == 3, ids


def test_both_markets_are_drawn_from_the_pool():
    history = _corner_history()
    fixtures = [_goals("1"), _corner("1")]
    pool = build_leg_pool(fixtures, history, want_goals=True, want_corners=True)
    markets = [leg.market for leg in pool]
    assert markets.count("Over 1.5 Goals") == 1
    assert sum(1 for market in markets if "Corner" in market) == 1


def test_goals_only_matches_the_standalone_picker():
    fixtures = [_goals("1"), _goals("2"), _goals("3"), _goals("4")]
    history = _corner_history()
    mixed = find_mixed_trebles(
        fixtures, history, want_goals=True, want_corners=False, min_combined_odds=3.0, limit=5
    )
    plain = find_best_trebles(fixtures, min_combined_odds=3.0, limit=5)
    assert [tuple(leg.fixture_id for leg in t.legs) for t in mixed] == [
        tuple(leg.fixture_id for leg in t.legs) for t in plain
    ]


def test_corners_only_matches_the_standalone_picker():
    fixtures = [_corner("1"), _corner("2"), _corner("3"), _corner("4")]
    history = _corner_history()
    mixed = find_mixed_trebles(
        fixtures, history, want_goals=False, want_corners=True, min_combined_odds=3.0, limit=5
    )
    plain = find_best_corner_trebles(fixtures, history, min_combined_odds=3.0, limit=5)
    assert [tuple(leg.fixture_id for leg in t.legs) for t in mixed] == [
        tuple(leg.fixture_id for leg in t.legs) for t in plain
    ]


def test_market_request_parsing():
    assert parse_markets(["goals"]) == {"goals"}
    assert parse_markets(["corners"]) == {"corners"}
    assert parse_markets(["goals", "corners"]) == {"goals", "corners"}
    assert parse_markets(["Goals, Corners"]) == {"goals", "corners"}
    assert parse_markets(["betslip"]) == {"goals"}
    assert parse_markets([]) == {"goals"}


def test_corner_slips_in_the_new_range_are_singles_and_do_not_repeat():
    history = _corner_history()
    fixtures = [_corner("1"), _corner("2")]

    slips = find_best_corner_trebles(
        fixtures,
        history,
        min_combined_odds=1.9,
        max_combined_odds=2.5,
        max_legs=3,
        limit=5,
    )

    assert len(slips) == 2  # 2.4 sits in range on its own; 2.4 × 2.4 is too big
    for slip in slips:
        assert len(slip.legs) == 1
        assert abs(slip.combined_odds - 2.4) < 1e-9
        assert "Corner" in slip.legs[0].market
        assert slip.forced is False


def test_mixed_new_range_keeps_every_slip_inside_the_range_without_repeats():
    history = _corner_history()
    fixtures = [_goals("1"), _goals("2"), _goals("3"), _corner("1")]

    slips = find_mixed_trebles(
        fixtures,
        history,
        want_goals=True,
        want_corners=True,
        min_combined_odds=1.9,
        max_combined_odds=2.5,
        max_legs=3,
        limit=5,
    )

    assert slips
    used: set = set()
    total_legs = 0
    for slip in slips:
        assert 1.9 <= slip.combined_odds <= 2.5
        assert slip.forced is False
        ids = [leg.fixture_id for leg in slip.legs]
        assert len(set(ids)) == len(ids)  # no fixture twice inside a slip
        used.update(ids)
        total_legs += len(ids)
    assert total_legs == len(used)  # no fixture shared across slips

