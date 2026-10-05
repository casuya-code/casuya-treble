from datetime import datetime, timedelta, timezone

from shared.betpawa_client import BetPawaOver15, keep_for_import, parse_events_payload

SAMPLE = {
    "responses": [
        {
            "responses": [
                {
                    "id": "37578911",
                    "participants": [
                        {"name": "Kazakhstan", "position": 1},
                        {"name": "Moldova", "position": 2},
                    ],
                    "startTime": "2026-10-02T14:00:00Z",
                    "category": {"name": "Football"},
                    "region": {"name": "International"},
                    "competition": {"name": "UEFA Nations League"},
                    "markets": [
                        {
                            "marketType": {"id": "5000"},
                            "row": [
                                {
                                    "specifier": {"total": "1.5"},
                                    "prices": [
                                        {"name": "Over", "odds": 1.49},
                                        {"name": "Under", "odds": 2.7},
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    ]
}


def test_parse_finished_score_and_ignore_a_blank_one():
    from shared.betpawa_client import parse_event_score

    finished = parse_event_score(
        {
            "additionalInfo": {"live": None},
            "results": {
                "participantPeriodResults": [
                    {
                        "participant": {"type": "HOME"},
                        "periodResults": [
                            {"period": {"slug": "FULL_TIME_EXCLUDING_OVERTIME"}, "result": "2", "type": "SCORE"}
                        ],
                    },
                    {
                        "participant": {"type": "AWAY"},
                        "periodResults": [
                            {"period": {"slug": "FULL_TIME_EXCLUDING_OVERTIME"}, "result": "1", "type": "SCORE"}
                        ],
                    },
                ]
            },
        }
    )
    assert finished is not None
    assert finished.home_goals == 2
    assert finished.away_goals == 1
    assert finished.live is False

    assert parse_event_score({"additionalInfo": {}, "results": {}}) is None
    rows = parse_events_payload(SAMPLE)
    assert len(rows) == 1
    row = rows[0]
    assert row.external_id == "betpawa:37578911"
    assert row.home_team == "Kazakhstan"
    assert row.away_team == "Moldova"
    assert row.decimal_odds == 1.49
    assert "UEFA Nations League" in row.league


def _row(league: str, days: int) -> BetPawaOver15:
    kickoff = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc) + timedelta(days=days)
    return BetPawaOver15("betpawa:1", "1", "Home", "Away", league, kickoff, 1.4)


def test_rated_leagues_are_kept_further_ahead_than_the_rest_of_the_board():
    now = datetime(2026, 10, 5, 8, 0, tzinfo=timezone.utc)
    soon = _row("Football / Uruguay / Primera Division", 1)
    later_other = _row("Football / Uruguay / Primera Division", 4)
    later_rated = _row("Football / England / Premier League", 5)
    later_argentina = _row("Football / Argentina / Liga Profesional", 4)
    assert keep_for_import(soon, now) is True
    assert keep_for_import(later_other, now) is False
    assert keep_for_import(later_rated, now) is True
    assert keep_for_import(later_argentina, now) is True


def test_a_price_row_without_odds_is_skipped():
    event = {
        "id": "9",
        "participants": [{"name": "A", "position": 1}, {"name": "B", "position": 2}],
        "startTime": "2026-10-06T15:00:00Z",
        "competition": {"name": "League"},
        "markets": [
            {
                "marketType": {"id": "5000"},
                "row": [
                    {"specifier": {"total": "1.5"}, "prices": [{"name": "Over"}]},
                    {
                        "specifier": {"total": "1.5"},
                        "prices": [{"name": "Over", "odds": 1.33}],
                    },
                ],
            }
        ],
    }
    rows = parse_events_payload([event])
    assert len(rows) == 1
    assert rows[0].decimal_odds == 1.33
