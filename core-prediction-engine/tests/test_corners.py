from datetime import datetime, timezone
from uuid import uuid4

from shared.betpawa_client import extract_fh_corner_overs
from shared.corners import corner_leg, estimate_first_half_corners, prob_over_line
from shared.football_data import parse_football_data_csv
from shared.models import Fixture


def test_over_25_means_three_or_more_corners():
    assert prob_over_line(6.0, 2.5) > 0.9
    assert prob_over_line(1.2, 3.5) < 0.1


def test_corner_counts_are_kept_from_the_score_file():
    text = """Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,HC,AC
E0,15/08/2025,15:00,Arsenal,Chelsea,2,1,7,3
"""
    rows = parse_football_data_csv(text, "E0", "England / Premier League")
    assert rows[0].home_corners == 7
    assert rows[0].away_corners == 3


def test_first_half_price_is_read_from_the_25_and_35_lines():
    event = {
        "markets": [
            {
                "marketType": {"id": "1096784", "name": "Total Corners Over/Under - 1H"},
                "row": [
                    {"specifier": {"total": "3.5"}, "prices": [{"name": "Over", "odds": 1.54}, {"name": "Under", "odds": 2.05}]},
                    {"specifier": {"total": "4.5"}, "prices": [{"name": "Over", "odds": 2.16}]},
                    {"specifier": {"total": "2.5"}, "prices": [{"name": "Over"}]},
                ],
            }
        ]
    }
    assert extract_fh_corner_overs(event) == {"3.5": 1.54}


def test_a_short_price_is_left_out_and_a_generous_line_is_kept():
    history = []
    for day in range(1, 13):
        history.append(_corners("Hosts", "Filler", 8, 2, day))
        history.append(_corners("Marker", "Guests", 3, 7, day))
        history.append(_corners("Alpha", "Beta", 5, 4, day))
    expected = estimate_first_half_corners(
        history,
        home_team="Hosts",
        away_team="Guests",
        league="England / Premier League",
        today=datetime(2026, 9, 1, tzinfo=timezone.utc).date(),
    )
    assert expected is not None and expected > 2
    upcoming = _corners("Hosts", "Guests", None, None, 20)
    upcoming.home_corners = None
    upcoming.away_corners = None
    upcoming.league = "Football / England / Premier League"
    upcoming.fh_corner_over_25 = 1.05
    upcoming.fh_corner_over_35 = 2.4
    leg = corner_leg(upcoming, history)
    assert leg is not None
    assert leg.market == "Over 3.5 Corners 1H"
    assert leg.odds == 2.4


def _corners(home: str, away: str, home_corners: int | None, away_corners: int | None, day: int) -> Fixture:
    return Fixture(
        id=uuid4(),
        home_team=home,
        away_team=away,
        league="England / Premier League",
        kickoff_at=datetime(2026, 8, day, 15, 0, tzinfo=timezone.utc),
        home_corners=home_corners,
        away_corners=away_corners,
    )
