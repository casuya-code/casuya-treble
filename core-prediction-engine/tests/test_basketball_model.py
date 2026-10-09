"""Pure model math + history helpers for the basketball filter."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from shared.basketball import model
from shared.basketball.filters import (
    FinishedGame,
    aggregate_players,
    back_to_back,
    h2h_pace,
    over_rate,
    top_usage_and_rim,
)


def game(
    day: str,
    home: str,
    away: str,
    hs: int,
    as_: int,
    line: float | None,
    season_type: int = 2,
) -> FinishedGame:
    return FinishedGame(
        tipoff=datetime.fromisoformat(day).replace(tzinfo=timezone.utc),
        home_team_id=home,
        away_team_id=away,
        home_score=hs,
        away_score=as_,
        line=line,
        season_type=season_type,
    )


# --- model ------------------------------------------------------------------


def test_expected_total_math():
    home_exp, away_exp = model.expected_total(
        home_ppg_at_home=115.0,
        home_apg_at_home=108.0,
        away_ppg_away=112.0,
        away_apg_away=110.0,
        home_advantage=1.03,
    )
    assert home_exp == pytest.approx(((115 + 110) / 2) * 1.03)
    assert away_exp == pytest.approx((112 + 108) / 2)
    total = model.predicted_total(115.0, 108.0, 112.0, 110.0, home_advantage=1.03)
    assert total == pytest.approx(home_exp + away_exp)


def test_p_over_is_half_at_own_prediction():
    assert model.p_over(227.5, 227.5, 12.5) == pytest.approx(0.5)


def test_p_over_is_monotone_in_line():
    predicted = 230.0
    values = [model.p_over(predicted, line, 12.5) for line in (210, 220, 230, 240, 250)]
    assert values == sorted(values, reverse=True)
    assert values[0] > 0.9
    assert values[-1] < 0.1


def test_p_over_rejects_bad_sd():
    with pytest.raises(ValueError):
        model.p_over(230.0, 227.5, 0.0)


def test_american_odds_conversion():
    assert model.american_to_decimal(-110) == pytest.approx(1 + 100 / 110)
    assert model.american_to_decimal(150) == pytest.approx(2.5)
    assert model.american_to_decimal(2.2) == pytest.approx(2.2)  # decimal passes through
    assert model.american_to_decimal(None) is None
    assert model.normalize_odds(-110.0) == pytest.approx(1 + 100 / 110)
    assert model.normalize_odds(0.0) is None


def test_fair_implied_over_removes_vig():
    assert model.fair_implied_over(1.91, 1.91) == pytest.approx(0.5)
    # symmetric vig lifts both raw implieds; fair split stays proportional
    fair = model.fair_implied_over(1.87, 1.95)
    assert fair is not None
    assert 0.48 < fair < 0.52


def test_fair_implied_over_accepts_american_odds():
    # -110 / -110 is a fair 50/50 split after vig removal
    assert model.fair_implied_over(-110, -110) == pytest.approx(0.5)
    fair = model.fair_implied_over(-105, -115)  # -105 over is slightly cheaper
    assert fair is not None
    assert 0.47 < fair < 0.51


def test_fair_implied_over_handles_missing_or_invalid():
    assert model.fair_implied_over(None, 1.9) is None
    assert model.fair_implied_over(1.9, None) is None
    assert model.fair_implied_over(0.9, 1.9) is None


def test_model_edge_is_probability_difference():
    assert model.model_edge(0.60, 1.91, 1.91) == pytest.approx(0.10)
    assert model.model_edge(0.60, -110, -110) == pytest.approx(0.10)
    assert model.model_edge(None, 1.91, 1.91) is None
    assert model.model_edge(0.60, None, None) is None
    assert model.model_edge(0.60, -110, None) is None


# --- rates ------------------------------------------------------------------


def test_over_rate_counts_only_lines_newest_first():
    games = [
        game("2026-01-01T00:00:00", "H", "A", 110, 100, 200.5),  # total 210 > 200.5 over
        game("2026-01-05T00:00:00", "H", "A", 90, 95, 200.5),  # 185 not over
        game("2026-01-09T00:00:00", "H", "A", 100, 100, None),  # no line, excluded
        game("2026-01-13T00:00:00", "H", "A", 120, 110, 210.5),  # 230 > 210.5 over
    ]
    rate, samples = over_rate(games, window=82)
    assert samples == 3
    assert rate == pytest.approx(2 / 3)


def test_over_rate_respects_window_and_empty_input():
    games = [
        game(f"2026-02-{day:02d}T00:00:00", "H", "A", 100, 100, 199.5)  # 200 over
        for day in range(1, 6)
    ]
    games.append(game("2026-01-01T00:00:00", "H", "A", 80, 80, 199.5))  # older, 160 under
    rate, samples = over_rate(games, window=5)
    assert samples == 5
    assert rate == 1.0  # the older non-over game falls outside the window
    assert over_rate([], 10) == (None, 0)


# --- h2h pace ---------------------------------------------------------------


def test_h2h_pace_uses_newest_regular_season_meetings_in_either_venue():
    meetings = [
        game("2025-11-01T00:00:00", "H", "A", 110, 105, None),  # combined 215
        game("2025-12-01T00:00:00", "A", "H", 100, 112, None),  # combined 212, swapped venue
        game("2026-01-01T00:00:00", "H", "A", 120, 110, None),  # combined 230
    ]
    unrelated = game("2026-01-15T00:00:00", "H", "Z", 99, 88, None)
    playoff = game("2026-02-01T00:00:00", "H", "A", 130, 120, None, season_type=3)
    pace, meetings_count = h2h_pace(
        meetings + [unrelated, playoff], "H", "A", window=5, league_ppp=1.12
    )
    assert meetings_count == 3
    expected = (215 + 212 + 230) / 3 / (2 * 1.12)
    assert pace == pytest.approx(expected)


def test_h2h_pace_window_and_empty():
    games = [
        game(f"2026-03-{day:02d}T00:00:00", "H", "A", 115, 115, None)  # combined 230
        for day in range(1, 8)
    ]
    pace, count = h2h_pace(games, "H", "A", window=3, league_ppp=1.12)
    assert count == 3
    assert pace == pytest.approx(230 / (2 * 1.12))
    assert h2h_pace([], "H", "A", window=5, league_ppp=1.12) == (None, 0)


# --- back-to-back (US Eastern dates) ----------------------------------------


def test_back_to_back_uses_eastern_calendar_days():
    # 7:30pm ET Nov 4 tip, then 7:30pm ET Nov 5 tip -> B2B
    played = [game("2025-11-05T00:30:00", "H", "Z", 100, 90, None)]
    target = datetime.fromisoformat("2025-11-06T00:30:00").replace(tzinfo=timezone.utc)
    assert back_to_back(played, target) is True

    # afternoon game Nov 4 (2pm ET) then evening Nov 5 -> still B2B despite >24h
    played = [game("2025-11-04T19:00:00", "H", "Z", 100, 90, None)]  # 2pm ET Nov 4
    target = datetime.fromisoformat("2025-11-06T00:30:00").replace(tzinfo=timezone.utc)
    assert back_to_back(played, target) is True

    # two days off -> fresh
    played = [game("2025-11-03T00:30:00", "H", "Z", 100, 90, None)]
    assert back_to_back(played, target) is False


def test_back_to_back_unknown_without_history():
    target = datetime.now(timezone.utc)
    assert back_to_back([], target) is None


# --- usage + rim protector --------------------------------------------------


def test_top_usage_and_rim_protector():
    rows: list[tuple[str, str, int, int]] = []
    # alpha: 30 ppg over 10 games (top usage), bravo 25 ppg, charlie 20, delta 15
    for name, pid, ppg, bpg in (
        ("Alpha", "1", 30, 0),
        ("Bravo", "2", 25, 1),
        ("Charlie", "3", 20, 0),
        ("Delta", "4", 15, 0),
        ("Rimmy", "5", 8, 3),  # low usage, elite blocks
        ("Bench", "6", 5, 0),
    ):
        for _ in range(10):
            rows.append((pid, name, ppg, bpg))
    # one-game wonder should not qualify
    rows.append(("7", "Wonder", 40, 5))

    players = aggregate_players(rows)
    top4, rim = top_usage_and_rim(players, min_games=8)
    assert [p.name for p in top4] == ["Alpha", "Bravo", "Charlie", "Delta"]
    assert rim is not None and rim.name == "Rimmy"


def test_top_usage_insufficient_data():
    assert top_usage_and_rim([], min_games=8) == ([], None)
    rows = [("1", "Solo", 10, 1)] * 3  # only 3 games < 8
    top4, rim = top_usage_and_rim(aggregate_players(rows), min_games=8)
    assert top4 == [] and rim is None
