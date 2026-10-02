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


def test_parse_betpawa_over_15():
    rows = parse_events_payload(SAMPLE)
    assert len(rows) == 1
    row = rows[0]
    assert row.external_id == "betpawa:37578911"
    assert row.home_team == "Kazakhstan"
    assert row.away_team == "Moldova"
    assert row.decimal_odds == 1.49
    assert "UEFA Nations League" in row.league
