from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from shared.venues import venue_for
from shared.weather import holds_for_weather, weather_reason


def _payload(hour: str, rain: float, snow: float, gust: float) -> dict:
    return {
        "hourly": {
            "time": [hour, "2026-10-05T16:00"],
            "precipitation": [rain, 0],
            "snowfall": [snow, 0],
            "wind_gusts_10m": [gust, 10],
        }
    }


def test_known_grounds_follow_the_bookmaker_name():
    assert venue_for("Man City") == venue_for("Manchester City")
    assert venue_for("Nott'm Forest") == venue_for("Nottingham Forest")
    assert venue_for("Paris Saint-Germain") != venue_for("Paris FC")
    assert venue_for("Kazakhstan") is None


def test_only_a_downpour_snow_or_gale_holds_the_match():
    kickoff = datetime(2026, 10, 5, 15, 30, tzinfo=timezone.utc)
    assert weather_reason(_payload("2026-10-05T15:00", 1.2, 0, 30), kickoff) is None
    assert weather_reason(_payload("2026-10-05T15:00", 6.0, 0, 20), kickoff) == "rain"
    assert weather_reason(_payload("2026-10-05T15:00", 1.0, 1.2, 20), kickoff) == "snow"
    assert weather_reason(_payload("2026-10-05T15:00", 0, 0, 80), kickoff) == "wind"
    assert weather_reason(_payload("2026-10-05T18:00", 20, 0, 90), kickoff) is None


def test_a_wet_home_ground_is_left_off_and_an_unknown_ground_stays():
    kickoff = datetime(2026, 10, 5, 15, 0, tzinfo=timezone.utc)
    wet = SimpleNamespace(id=uuid4(), home_team="Arsenal", away_team="Chelsea", kickoff_at=kickoff)
    unknown = SimpleNamespace(id=uuid4(), home_team="Kazakhstan", away_team="Moldova", kickoff_at=kickoff)
    point = venue_for("Arsenal")
    assert point is not None
    key = (round(point[0], 2), round(point[1], 2))
    held = holds_for_weather([wet, unknown], {key: _payload("2026-10-05T15:00", 8, 0, 10)})
    assert [fixture.home_team for fixture, _reason in held] == ["Arsenal"]
    assert held[0][1] == "rain"
