from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from shared.football_data import historical_external_id, parse_football_data_csv, season_codes
from shared.league_names import league_key
from shared.models import Fixture
from shared.team_names import team_key
from shared.team_strength import estimate_match_lambdas
from uuid import uuid4


CSV = """Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR
E0,15/08/2025,20:00,Man City,Nott'm Forest,3,1,H
E0,16/08/2025,15:00,Liverpool,Bournemouth,,
E1,16/08/2025,15:00,Wolves,West Ham,1,0,H
"""


def test_season_folder_rolls_in_july():
    assert season_codes(date(2026, 10, 4)) == ["2627", "2526"]
    assert season_codes(date(2026, 6, 1)) == ["2526", "2425"]


def test_parse_keeps_full_time_scores_from_the_requested_division():
    rows = parse_football_data_csv(CSV, "E0", "England / Premier League")
    assert len(rows) == 1
    match = rows[0]
    assert match.home_team == "Man City"
    assert match.away_team == "Nott'm Forest"
    assert match.home_goals == 3
    assert match.away_goals == 1
    assert match.league == "England / Premier League"
    assert len(match.external_id) <= 64
    assert match.external_id == historical_external_id("E0", match.kickoff_at, "Man City", "Nott'm Forest")
    assert match.kickoff_at == datetime(2025, 8, 15, 19, 0, tzinfo=timezone.utc)


ARG = """Country,League,Season,Date,Time,Home,Away,HG,AG
Argentina,Liga Profesional,2012/2013,03/08/2012,23:00,Old Club,Other,1,0
Argentina,Liga Profesional,2026,05/10/2026,20:00,Boca Juniors,River Plate,2,1
"""


def test_argentina_file_keeps_the_recent_season_only():
    from shared.football_data import recent_season_labels

    rows = parse_football_data_csv(
        ARG,
        "ARG",
        "Argentina / Liga Profesional",
        seasons={"2026"},
        tz=ZoneInfo("America/Argentina/Buenos_Aires"),
    )
    assert len(rows) == 1
    assert rows[0].home_team == "Boca Juniors"
    assert rows[0].home_goals == 2
    assert rows[0].kickoff_at == datetime(2026, 10, 5, 23, 0, tzinfo=timezone.utc)
    assert "2026" in recent_season_labels(date(2026, 10, 5))
    assert league_key("Football / Argentina / Liga Profesional") == "argentina"
    assert league_key("Football / Argentina / Primera C") is None
    assert team_key("Argentinos Juniors") == team_key("Argentinos Jrs")
    assert team_key("Atletico Tucuman") == team_key("Atl. Tucuman")


def test_bookmaker_names_meet_the_short_names():
    assert team_key("Manchester City") == team_key("Man City")
    assert team_key("Nott'm Forest") == team_key("Nottingham Forest")
    assert team_key("Paris Saint-Germain") == team_key("Paris SG")
    assert team_key("Paris FC") != team_key("Paris SG")
    assert league_key("Football / England / Premier League") == "epl"
    assert league_key("England / Premier League") == "epl"
    assert league_key("Football / England / Championship") == "championship"
    assert league_key("Test League") is None


def test_form_uses_history_when_the_names_differ():
    history = []
    for day in range(1, 13):
        history.append(_played("Man City", "Filler", 3, 0, day, "England / Premier League"))
        history.append(_played("Marker", "Nott'm Forest", 2, 0, day, "England / Premier League"))
        history.append(_played("Alpha", "Beta", 1, 1, day, "England / Premier League"))
    rates = estimate_match_lambdas(
        history,
        home_team="Manchester City",
        away_team="Nottingham Forest",
        league="Football / England / Premier League",
        today=datetime(2026, 9, 1, tzinfo=timezone.utc).date(),
    )
    assert rates is not None
    lambda_home, lambda_away = rates
    assert lambda_home > 1.5
    assert lambda_away < lambda_home


def _played(home: str, away: str, home_goals: int, away_goals: int, day: int, league: str) -> Fixture:
    return Fixture(
        id=uuid4(),
        home_team=home,
        away_team=away,
        league=league,
        kickoff_at=datetime(2026, 8, day, 15, 0, tzinfo=timezone.utc),
        home_goals=home_goals,
        away_goals=away_goals,
    )
