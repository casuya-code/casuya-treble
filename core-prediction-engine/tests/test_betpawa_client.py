from shared.betpawa_client import parse_events_payload

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
