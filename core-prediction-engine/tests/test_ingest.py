"""Instrumentation inputs: injury parsing and line-snapshot change detection."""

from __future__ import annotations

from shared.basketball import ingest
from shared.models import BBLineSnapshot


def test_parse_injuries_carries_team_id_and_status():
    summary = {
        "injuries": [
            {
                "team": {"id": "13", "displayName": "Lakers"},
                "injuries": [
                    {
                        "athlete": {"id": "9", "displayName": "Star"},
                        "type": {"name": "INJURY_STATUS_QUESTIONABLE"},
                        "details": {"fantasyStatus": {"abbreviation": "GTD"}},
                    }
                ],
            }
        ]
    }
    parsed = ingest.parse_injuries(summary)
    assert parsed is not None
    assert parsed["9"]["team_id"] == "13"
    assert parsed["9"]["name"] == "Star"
    assert parsed["9"]["status"] == "INJURY_STATUS_QUESTIONABLE"
    assert parsed["9"]["fantasy"] == "GTD"


def test_parse_injuries_skips_entries_without_athlete_id():
    summary = {"injuries": [{"team": {"id": "1"}, "injuries": [{"athlete": {}, "status": "x"}]}]}
    assert ingest.parse_injuries(summary) == {}


def test_parse_injuries_none_when_block_absent():
    assert ingest.parse_injuries({}) is None
    assert ingest.parse_injuries({"injuries": None}) is None


def test_same_line_flags_total_and_odds_moves():
    snap = BBLineSnapshot(over_under=222.5, over_odds=1.91, under_odds=1.91)
    assert ingest._same_line(snap, 222.5, 1.91, 1.91) is True
    assert ingest._same_line(snap, 223.5, 1.91, 1.91) is False
    assert ingest._same_line(snap, 222.5, 1.95, 1.91) is False
    assert ingest._same_line(snap, 222.5, 1.91, 1.87) is False
