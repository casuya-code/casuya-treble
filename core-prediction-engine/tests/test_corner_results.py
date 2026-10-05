from datetime import datetime, timezone

from shared.betpawa_client import sportradar_match_id
from shared.corner_results import corner_leg_outcome, parse_first_half_corners
from shared.models import Fixture, MatchStatus, SlipStatus
from shared.public_history import HistoryLeg, HistorySlip, build_public_history
from shared.tracker_logic import slip_status_from_fixtures


def _event(minute: int, disabled: int = 0) -> dict:
    return {"type": "corner", "time": minute, "disabled": disabled, "period": None}


def _payload(*events, period: int = 1, status: str = "1st half", matchstatus: str = "live") -> dict:
    return {
        "doc": [
            {
                "data": {
                    "match": {"p": period, "status": {"name": status}, "matchstatus": matchstatus},
                    "events": [{"type": "match_started", "time": -1}, *events],
                }
            }
        ]
    }


def test_inplay_sportradar_id_is_preferred():
    payload = {
        "widgets": [
            {"id": "111", "type": "SPORTRADAR", "retention": "PREMATCH"},
            {"id": "222", "type": "GENIUSSPORTS"},
            {"id": "333", "type": "SPORTRADAR", "retention": "INPLAY"},
        ]
    }
    assert sportradar_match_id(payload) == "333"


def test_first_half_corners_stop_at_minute_45():
    count, done = parse_first_half_corners(
        _payload(_event(13), _event(33), _event(33), _event(45), _event(76), period=2, status="2nd half")
    )
    assert count == 4
    assert done is True


def test_a_cancelled_corner_is_ignored_and_the_half_stays_open():
    count, done = parse_first_half_corners(_payload(_event(10), _event(20, disabled=1)))
    assert count == 1
    assert done is False


def test_corner_leg_wins_as_soon_as_the_line_is_cleared():
    assert corner_leg_outcome("Over 2.5 Corners 1H", 3, False) == "won"
    assert corner_leg_outcome("Over 3.5 Corners 1H", 3, False) == "pending"
    assert corner_leg_outcome("Over 3.5 Corners 1H", 3, True) == "lost"
    assert corner_leg_outcome("Over 3.5 Corners 1H", 4, True) == "won"


def test_goals_do_not_settle_a_corner_leg():
    kickoff = datetime(2026, 10, 5, 15, 0, tzinfo=timezone.utc)
    fixture = Fixture(
        home_team="Home",
        away_team="Away",
        kickoff_at=kickoff,
        status=MatchStatus.FINISHED,
        home_goals=3,
        away_goals=1,
    )

    class Leg:
        market = "Over 2.5 Corners 1H"

    assert slip_status_from_fixtures([fixture], [Leg()]) == SlipStatus.PENDING

    fixture.fh_corners = 4
    fixture.fh_half_complete = True
    assert slip_status_from_fixtures([fixture], [Leg()]) == SlipStatus.WON


def test_public_history_settles_the_corner_count():
    kickoff = datetime(2026, 10, 5, 15, 0, tzinfo=timezone.utc)
    won = HistoryLeg(
        fixture_id="c1",
        home_team="Hosts",
        away_team="Guests",
        kickoff_at=kickoff,
        odds=1.80,
        home_goals=0,
        away_goals=0,
        finished=False,
        practice=False,
        market="Over 2.5 Corners 1H",
        fh_corners=3,
        fh_half_complete=True,
    )
    lost = HistoryLeg(
        fixture_id="c2",
        home_team="Alpha",
        away_team="Beta",
        kickoff_at=kickoff,
        odds=2.10,
        home_goals=2,
        away_goals=2,
        finished=True,
        practice=False,
        market="Over 3.5 Corners 1H",
        fh_corners=2,
        fh_half_complete=True,
    )
    report = build_public_history(
        [HistorySlip("s", datetime(2026, 10, 5, 8, 0, tzinfo=timezone.utc), [won, lost, won])]
    )
    assert report["matches_won"] == 1
    assert report["matches_lost"] == 1
    assert report["slips"][0]["legs"][0]["fh_corners"] == 3
    assert report["treble_profit"] == -2000
