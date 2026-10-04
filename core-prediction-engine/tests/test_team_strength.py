from datetime import datetime, timezone

from shared.models import Fixture
from shared.team_strength import estimate_match_lambdas
from uuid import uuid4


def _played(home: str, away: str, home_goals: int, away_goals: int, day: int) -> Fixture:
    return Fixture(
        id=uuid4(),
        home_team=home,
        away_team=away,
        league="Test League",
        kickoff_at=datetime(2026, 8, day, 15, 0, tzinfo=timezone.utc),
        home_goals=home_goals,
        away_goals=away_goals,
    )


def test_attack_and_defence_set_the_match_rates():
    history = []
    for day in range(1, 13):
        history.append(_played("Hosts", "Filler", 3, 0, day))
        history.append(_played("Marker", "Guests", 2, 0, day))
        history.append(_played("Alpha", "Beta", 1, 1, day))
    rates = estimate_match_lambdas(
        history,
        home_team="Hosts",
        away_team="Guests",
        league="Test League",
        today=datetime(2026, 9, 1, tzinfo=timezone.utc).date(),
    )
    assert rates is not None
    lambda_home, lambda_away = rates
    assert lambda_home > 1.5
    assert lambda_away < lambda_home


def test_thin_history_leaves_the_stored_rates_alone():
    history = [_played("Hosts", "Guests", 2, 0, day) for day in range(1, 4)]
    assert (
        estimate_match_lambdas(
            history,
            home_team="Hosts",
            away_team="Guests",
            league="Test League",
            today=datetime(2026, 9, 1, tzinfo=timezone.utc).date(),
        )
        is None
    )
