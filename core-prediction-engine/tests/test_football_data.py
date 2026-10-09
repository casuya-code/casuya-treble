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


def test_league_key_leaves_out_youth_women_cups_and_lower_tiers():
    # Women, youth, reserve, cup and play-off editions are never the senior league.
    assert league_key("Football / Spain / Primera Division Women") is None
    assert league_key("Football / Germany / Women Bundesliga") is None
    assert league_key("Football / Italy / Serie A, Women") is None
    assert league_key("Football / England / Premier League Cup") is None
    assert league_key("Football / England / Premier League 2") is None
    assert league_key("Football / England / Northern Premier League, Premier Division") is None
    assert league_key("Football / England / Championship, Play-offs") is None
    # Lower divisions and their trailing tier numbers stay out.
    assert league_key("Football / Portugal / Liga Portugal 2") is None
    assert league_key("Football / Portugal / Liga Portugal 3") is None
    assert league_key("Football / Spain / La Liga 2") is None
    assert league_key("Football / France / Ligue 2") is None
    assert league_key("Football / Germany / 2. Bundesliga") is None
    assert league_key("Football / Argentina / Primera B") is None
    # The real senior leagues still resolve.
    assert league_key("Football / Spain / La Liga") == "laliga"
    assert league_key("Football / Spain / LaLiga") == "laliga"
    assert league_key("Football / Germany / Bundesliga") == "bundesliga"
    assert league_key("Football / Italy / Serie A") == "seriea"
    assert league_key("Football / France / Ligue 1") == "ligue1"
    assert league_key("Football / Netherlands / Eredivisie") == "eredivisie"
    assert league_key("Football / Portugal / Liga Portugal") == "primeira"
    assert league_key("Football / Argentina / Primera Division") == "argentina"


def test_extra_senior_leagues_resolve_and_lower_tiers_stay_out():
    assert league_key("Football / Belgium / Pro League") == "belgium"
    assert league_key("Football / Belgium / U21 Pro League") is None
    assert league_key("Football / Belgium / Challenger Pro League") is None
    assert league_key("Football / Turkey / Super Lig") == "turkey"
    assert league_key("Football / Turkey / 1. Lig") is None
    assert league_key("Football / Greece / Super League") == "greece"
    assert league_key("Football / Scotland / Premiership") == "scotland"
    assert league_key("Football / Japan / J.League") == "japan"
    assert league_key("Football / Japan / J.League 2") is None
    assert league_key("Football / Sweden / Allsvenskan") == "sweden"
    assert league_key("Football / Norway / Eliteserien") == "norway"
    assert league_key("Football / Denmark / Superliga") == "denmark"
    assert league_key("Football / Poland / Ekstraklasa") == "poland"
    assert league_key("Football / Romania / Liga I") == "romania"
    assert league_key("Football / Romania / Liga II") is None
    assert league_key("Football / Austria / Bundesliga") == "austria"
    assert league_key("Football / Switzerland / Super League") == "switzerland"
    assert league_key("Football / Finland / Veikkausliiga") == "finland"
    assert league_key("Football / Ireland / Premier Division") == "ireland"
    assert league_key("Football / Ireland / First Division") is None
    assert league_key("Football / Northern Ireland / Premiership") is None
    assert league_key("Football / Mexico / Liga MX, Apertura") == "mexico"
    assert league_key("Football / Mexico / U21 Liga MX") is None
    assert league_key("Football / USA / MLS") == "usa"
    assert league_key("Football / USA / MLS Next Pro") is None
    assert league_key("Football / China / Chinese Super League") == "china"
    assert league_key("Football / Brazil / Serie A") == "brazil"
    # History labels must resolve to the same keys as the BetPawa labels.
    assert league_key("Belgium / Pro League") == "belgium"
    assert league_key("Turkey / Super Lig") == "turkey"
    assert league_key("China / Chinese Super League") == "china"


def test_every_seeded_league_file_resolves_to_a_key():
    from shared.football_data import DIVISIONS, EXTRA_FILES

    for division, league in DIVISIONS:
        assert league_key(league) is not None, f"{division} {league}"
    for _url, division, league, _tz in EXTRA_FILES:
        assert league_key(league) is not None, f"{division} {league}"


def test_extra_leagues_join_bookmaker_names_to_short_file_names():
    assert team_key("IFK Göteborg") == team_key("Goteborg")
    assert team_key("IK Sirius") == team_key("Sirius")
    assert team_key("IF Brommapojkarna") == team_key("Brommapojkarna")
    assert team_key("Västerås SK") == team_key("Vasteras SK")
    assert team_key("Odense Boldklub") == team_key("Odense")
    assert team_key("Seinäjoen JK") == team_key("SJK")
    assert team_key("RKS Raków Częstochowa") == team_key("Rakow")
    assert team_key("KS Cracovia Kraków") == team_key("Cracovia")
    assert team_key("Zagłębie Lubin") == team_key("Zaglebie")
    assert team_key("FC Corvinul Hunedoara 1921") == team_key("Corvinul")
    assert team_key("ACS Sepsi OSK Sfântu Gheorghe") == team_key("Sepsi Sf. Gheorghe")
    assert team_key("FC Dinamo Bucuresti 1948") == team_key("Dinamo Bucuresti")
    assert team_key("Deportivo Toluca FC") == team_key("Toluca")
    assert team_key("SK Beveren") == team_key("Beveren")
    assert team_key("Fagiano Okayama") == team_key("Okayama")
    assert team_key("Kyoto Sanga FC") == team_key("Kyoto")
    assert team_key("Machida Zelvia") == team_key("Machida")
    assert team_key("Urawa Red Diamonds") == team_key("Urawa Reds")
    assert team_key("Club Puebla") == team_key("Puebla")


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
