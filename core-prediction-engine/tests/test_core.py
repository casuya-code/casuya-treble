from shared.fixture_source import is_demo_fixture, prefer_real_fixtures, upcoming_fixtures
from shared.poisson import prob_over_15
from shared.slip_format import combined_decimal_odds
from shared.treble_generator import find_best_trebles
from shared.models import Fixture, TimeCategory
from datetime import datetime, timezone
from uuid import uuid4


def test_prob_over_15_high_lambda():
    p = prob_over_15(2.0, 2.0)
    assert p > 0.85


def test_combined_odds_rounding():
    assert combined_decimal_odds([1.52, 1.46, 1.55]) == round(1.52 * 1.46 * 1.55, 2)


def test_find_trebles_respects_min_odds():
    kick = datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc)
    fixtures = []
    for i, odds in enumerate([1.55, 1.52, 1.48, 1.50]):
        fixtures.append(
            Fixture(
                id=uuid4(),
                home_team=f"H{i}",
                away_team=f"A{i}",
                kickoff_at=kick,
                lambda_home=2.2,
                lambda_away=1.8,
                closing_odds_over_15=odds,
            )
        )
    trebles = find_best_trebles(fixtures, min_combined_odds=3.0, limit=1)
    assert len(trebles) == 1
    assert trebles[0].combined_odds >= 3.0
    assert trebles[0].time_category == TimeCategory.ALL_DAY
    assert trebles[0].forced is False


def test_short_treble_is_offered_as_forced():
    kick = datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc)
    prices = [1.44, 1.44, 1.44, 1.22]
    fixtures = []
    for i, odds in enumerate(prices):
        fixtures.append(
            Fixture(
                id=uuid4(),
                home_team=f"H{i}",
                away_team=f"A{i}",
                kickoff_at=kick,
                lambda_home=2.2,
                lambda_away=1.8,
                closing_odds_over_15=odds,
            )
        )
    trebles = find_best_trebles(fixtures, min_combined_odds=3.0, limit=1)
    assert len(trebles) == 1
    assert trebles[0].forced is True
    assert abs(trebles[0].combined_odds - (1.44 * 1.44 * 1.44)) < 1e-9


def test_treble_uses_one_calendar_day():
    from shared.time_buckets import local_day
    from zoneinfo import ZoneInfo

    nairobi = ZoneInfo("Africa/Nairobi")

    def at(hour: int, day: int = 3):
        return datetime(2026, 10, day, hour, 0, tzinfo=nairobi)

    kicks = (at(13), at(15), at(20), at(15, 4))
    fixtures = []
    for i, kick in enumerate(kicks):
        fixtures.append(
            Fixture(
                id=uuid4(),
                home_team=f"H{i}",
                away_team=f"A{i}",
                kickoff_at=kick,
                lambda_home=2.2,
                lambda_away=1.8,
                closing_odds_over_15=1.5,
            )
        )
    trebles = find_best_trebles(fixtures, min_combined_odds=3.0, limit=5)
    assert len(trebles) == 1
    assert trebles[0].time_category == TimeCategory.ALL_DAY
    chosen = {leg.fixture_id for leg in trebles[0].legs}
    assert fixtures[3].id not in chosen
    assert {local_day(row.kickoff_at) for row in fixtures if row.id in chosen} == {local_day(kicks[0])}


def test_empty_treble_reason_names_the_gap():
    from shared.treble_generator import empty_treble_reason

    assert empty_treble_reason(stored=0, upcoming=0, priced=0, same_day=0) == "none_loaded"
    assert empty_treble_reason(stored=12, upcoming=0, priced=0, same_day=0) == "all_started"
    assert empty_treble_reason(stored=8, upcoming=8, priced=0, same_day=0) == "no_price"
    assert empty_treble_reason(stored=8, upcoming=8, priced=8, same_day=0) == "spread_days"
    assert empty_treble_reason(stored=8, upcoming=8, priced=8, same_day=8, eligible=0) == "below_floor"
    assert empty_treble_reason(stored=8, upcoming=8, priced=8, same_day=8, eligible=8) == "below_min"


def test_low_chance_or_short_price_is_left_out():
    kick = datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc)
    weak = Fixture(
        id=uuid4(),
        home_team="Quiet",
        away_team="Defence",
        kickoff_at=kick,
        lambda_home=0.8,
        lambda_away=0.6,
        closing_odds_over_15=1.40,
    )
    short_price = Fixture(
        id=uuid4(),
        home_team="Hot",
        away_team="Favourite",
        kickoff_at=kick,
        lambda_home=2.2,
        lambda_away=1.8,
        closing_odds_over_15=1.12,
    )
    from shared.treble_generator import count_eligible_legs, count_priced_legs

    assert count_priced_legs([weak, short_price]) == 2
    assert count_eligible_legs([weak, short_price]) == 0


def test_dixon_coles_raises_the_chance_of_a_goalless_draw():
    from shared.poisson import scoreline_probabilities

    adjusted = scoreline_probabilities(1.3, 1.0)
    independent = scoreline_probabilities(1.3, 1.0, rho=0.0)
    assert adjusted[(0, 0)] > independent[(0, 0)]
    assert adjusted[(1, 1)] > independent[(1, 1)]


def test_upcoming_fixtures_skip_started_matches():
    now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    started = Fixture(
        id=uuid4(),
        home_team="Started",
        away_team="Already",
        kickoff_at=datetime(2026, 10, 2, 10, 0, tzinfo=timezone.utc),
        closing_odds_over_15=1.5,
    )
    later = Fixture(
        id=uuid4(),
        home_team="Later",
        away_team="Kick",
        kickoff_at=datetime(2026, 10, 2, 16, 0, tzinfo=timezone.utc),
        closing_odds_over_15=1.5,
    )
    pool = upcoming_fixtures([started, later], now)
    assert len(pool) == 1
    assert pool[0].home_team == "Later"


def test_prefer_real_fixtures_over_demo():
    kick = datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc)
    demo = Fixture(
        id=uuid4(),
        external_id="demo-a-b",
        home_team="Demo A",
        away_team="Demo B",
        kickoff_at=kick,
        closing_odds_over_15=1.5,
    )
    real = [
        Fixture(
            id=uuid4(),
            external_id="oddsapi:1",
            home_team="Real H1",
            away_team="Real A1",
            kickoff_at=kick,
            closing_odds_over_15=1.5,
        ),
        Fixture(
            id=uuid4(),
            external_id="oddsapi:2",
            home_team="Real H2",
            away_team="Real A2",
            kickoff_at=kick,
            closing_odds_over_15=1.5,
        ),
        Fixture(
            id=uuid4(),
            external_id="oddsapi:3",
            home_team="Real H3",
            away_team="Real A3",
            kickoff_at=kick,
            closing_odds_over_15=1.5,
        ),
    ]
    pool = prefer_real_fixtures([demo, *real])
    assert len(pool) == 3
    assert all(not is_demo_fixture(f) for f in pool)
