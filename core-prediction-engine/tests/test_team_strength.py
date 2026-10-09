from datetime import datetime, timezone

from shared.models import Fixture
from shared.team_strength import apply_form_lambdas, estimate_match_lambdas
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


def _modelled_history() -> list[Fixture]:
    """Enough finished matches for the league and both teams to carry a rate."""
    rows: list[Fixture] = []
    for day in range(1, 13):
        rows.append(_played("Hosts", "Filler", 3, 1, day))
        rows.append(_played("Marker", "Guests", 2, 1, day))
        rows.append(_played("Alpha", "Beta", 1, 1, day))
    return rows


def _upcoming(league: str, *, lambda_home: float, lambda_away: float) -> Fixture:
    return Fixture(
        id=uuid4(),
        home_team="Hosts",
        away_team="Guests",
        league=league,
        kickoff_at=datetime(2026, 9, 1, 15, 0, tzinfo=timezone.utc),
        lambda_home=lambda_home,
        lambda_away=lambda_away,
    )


def test_apply_form_lambdas_reports_the_fixtures_it_estimated():
    fixture = _upcoming("Test League", lambda_home=1.4, lambda_away=1.1)

    modeled = apply_form_lambdas([fixture], _modelled_history())

    assert modeled == {fixture.id}
    assert (fixture.lambda_home, fixture.lambda_away) != (1.4, 1.1)


def test_a_fixture_with_no_history_is_reset_and_left_out():
    """An estimate left over from purged history must not survive to be priced."""
    fixture = _upcoming("No History League", lambda_home=4.0, lambda_away=0.2)

    modeled = apply_form_lambdas([fixture], _modelled_history())

    assert modeled == set()
    assert (fixture.lambda_home, fixture.lambda_away) == (1.4, 1.1)
