from datetime import datetime, timezone
from uuid import uuid4

from shared.models import Fixture, MatchStatus, SlipStatus
from shared.public_history import HistoryLeg, HistorySlip, build_public_history
from shared.tracker_logic import slip_status_from_fixtures


def _leg(name: str, hour: int, odds: float, goals: tuple[int, int] | None, fixture_id: str | None = None) -> HistoryLeg:
    return HistoryLeg(
        fixture_id=fixture_id or str(uuid4()),
        home_team=name,
        away_team="Away",
        kickoff_at=datetime(2026, 10, 2, hour, 0, tzinfo=timezone.utc),
        odds=odds,
        home_goals=None if goals is None else goals[0],
        away_goals=None if goals is None else goals[1],
        finished=goals is not None,
        practice=False,
    )


def test_public_history_singles_and_treble():
    won = _leg("Won", 12, 1.64, (2, 1), "a")
    lost = _leg("Lost", 13, 1.63, (0, 0), "b")
    waiting = _leg("Wait", 18, 1.66, None, "c")
    report = build_public_history(
        [
            HistorySlip(
                slip_id="s1",
                placed_at=datetime(2026, 10, 2, 8, 0, tzinfo=timezone.utc),
                legs=[won, lost, waiting],
            )
        ]
    )

    assert report["matches_won"] == 1
    assert report["matches_lost"] == 1
    assert report["matches_pending"] == 1
    assert report["trebles_placed"] == 1
    assert report["trebles_lost"] == 1
    assert report["treble_profit"] == -2000
    assert report["stake"] == 2000
    assert report["single_profit"] == round(((1.64 - 1) - 1) * 2000, 2)
    assert report["slips"][0]["result"] == "lost"


def test_settled_treble_loss_is_one_stake():
    won = _leg("Won", 15, 1.50, (3, 0), "a")
    lost = _leg("Lost", 16, 1.80, (1, 0), "b")
    also = _leg("Also", 17, 1.40, (2, 2), "c")
    report = build_public_history(
        [HistorySlip(slip_id="s2", placed_at=datetime(2026, 10, 2, 8, 0, tzinfo=timezone.utc), legs=[won, lost, also])]
    )
    assert report["trebles_lost"] == 1
    assert report["treble_profit"] == -2000
    assert report["matches_won"] == 2
    assert report["single_profit"] == round(((1.50 - 1) + (1.40 - 1) - 1) * 2000, 2)


def test_same_match_on_two_slips_is_one_single():
    shared = _leg("Shared", 12, 2.00, (2, 0), "same")
    other = _leg("Other", 13, 1.50, (0, 0), "other")
    third = _leg("Third", 14, 1.50, (2, 0), "third")
    extra = _leg("Extra", 15, 1.50, (2, 0), "extra")
    report = build_public_history(
        [
            HistorySlip("s1", datetime(2026, 10, 2, 8, 0, tzinfo=timezone.utc), [shared, other, third]),
            HistorySlip("s2", datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc), [shared, extra, third]),
        ]
    )
    assert report["matches_won"] == 3
    assert report["trebles_placed"] == 2
    assert report["trebles_lost"] == 1
    assert report["trebles_won"] == 1


def test_same_three_matches_from_two_users_is_one_treble():
    first = _leg("One", 12, 1.64, (2, 1), "a")
    second = _leg("Two", 13, 1.63, (2, 0), "b")
    third = _leg("Three", 14, 1.66, (3, 0), "c")
    later = _leg("One", 12, 1.70, (2, 1), "a")
    report = build_public_history(
        [
            HistorySlip("user-a", datetime(2026, 10, 2, 8, 0, tzinfo=timezone.utc), [first, second, third]),
            HistorySlip("user-b", datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc), [third, later, second]),
        ]
    )
    assert report["trebles_placed"] == 1
    assert report["trebles_won"] == 1
    assert len(report["slips"]) == 1
    assert report["treble_profit"] == round((1.64 * 1.63 * 1.66 - 1) * 2000, 2)


def test_two_goals_win_before_full_time_and_nil_nil_does_not():
    reached = _leg("Reached", 15, 1.50, (2, 0), "live-win")
    reached.finished = False
    still_open = _leg("Open", 16, 1.40, (0, 0), "live-open")
    still_open.finished = False
    report = build_public_history(
        [HistorySlip("s-live", datetime(2026, 10, 2, 8, 0, tzinfo=timezone.utc), [reached, still_open, _leg("Later", 18, 1.60, None, "later")])]
    )
    assert report["matches_won"] == 1
    assert report["matches_lost"] == 0
    assert report["matches_pending"] == 2
    assert report["single_profit"] == round((1.50 - 1) * 2000, 2)
    assert report["trebles_pending"] == 1
    assert report["slips"][0]["legs"][0]["result"] == "won"
    assert report["slips"][0]["legs"][1]["result"] == "pending"


def test_desk_slip_follows_the_same_goal_rule():
    kickoff = datetime(2026, 10, 2, 15, 0, tzinfo=timezone.utc)

    def fixture(status: MatchStatus, goals: tuple[int, int] | None) -> Fixture:
        return Fixture(
            home_team="Home",
            away_team="Away",
            kickoff_at=kickoff,
            status=status,
            home_goals=None if goals is None else goals[0],
            away_goals=None if goals is None else goals[1],
        )

    won = fixture(MatchStatus.LIVE, (1, 1))
    open_match = fixture(MatchStatus.LIVE, (0, 0))
    lost = fixture(MatchStatus.FINISHED, (1, 0))
    assert slip_status_from_fixtures([won, won, won]) == SlipStatus.WON
    assert slip_status_from_fixtures([open_match, won, won]) == SlipStatus.LIVE
    assert slip_status_from_fixtures([lost, open_match, won]) == SlipStatus.LOST
