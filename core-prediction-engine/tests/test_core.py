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
                lambda_home=1.6,
                lambda_away=1.0,
                closing_odds_over_15=odds,
            )
        )
    trebles = find_best_trebles(fixtures, min_combined_odds=3.0, limit=1)
    assert len(trebles) == 1
    assert trebles[0].combined_odds >= 3.0
    assert trebles[0].time_category == TimeCategory.DAY


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
