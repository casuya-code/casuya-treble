from datetime import datetime, timedelta, timezone

from shared.basketball import backtest


def _game(day: int, home: str, away: str, hs: int, as_: int, line: float | None, st: int = 2):
    return backtest.HistGame(
        tipoff=datetime(2025, 11, 1, tzinfo=timezone.utc) + timedelta(days=day),
        season_type=st,
        home_team_id=home,
        away_team_id=away,
        home_score=hs,
        away_score=as_,
        line=line,
        over_odds=1.9,
        under_odds=1.9,
    )


def _build() -> list[backtest.HistGame]:
    games = [
        # A home twice: scores 110, allows 100 -> home splits (110, 100)
        _game(0, "A", "X", 110, 100, 205.0),
        _game(1, "A", "X", 110, 100, 205.0),
        # B away twice: scores 105, allows 95 -> away splits (105, 95)
        _game(2, "Y", "B", 95, 105, 205.0),
        _game(3, "Y", "B", 95, 105, 205.0),
    ]
    return games


def test_replay_produces_row_once_min_samples_met():
    games = _build()
    # min_samples=2: both venue splits are ready for the 5th game.
    target = _game(4, "A", "B", 105, 105, 200.0)  # total 210 > line 200 -> over
    rows = backtest.replay(games + [target], min_samples=2)
    assert len(rows) == 1
    row = rows[0]
    assert abs(row.model_total - 208.075) < 1e-9
    assert row.outcome == "over"
    assert backtest.over_bet(row) is True
    assert row.edge is not None and row.edge > 0.05


def test_replay_skips_when_history_insufficient():
    games = _build()[:1]  # only one A-home game and no B-away games
    target = _game(4, "A", "B", 105, 105, 200.0)
    assert backtest.replay(games + [target], min_samples=2) == []


def test_replay_ignores_preseason_targets():
    games = _build()
    target = _game(4, "A", "B", 105, 105, 200.0, st=1)  # preseason target
    assert backtest.replay(games + [target], min_samples=2) == []


def test_summarize_hit_rate_and_roi():
    games = _build()
    over = _game(4, "A", "B", 105, 105, 200.0)  # over
    under = _game(5, "A", "B", 90, 90, 200.0)  # total 180 < 200 -> under
    rows = [r for r in backtest.replay(games + [over, under], min_samples=2) if backtest.over_bet(r)]
    # Only the over game is above its line; the under game has model 205 > 200 too,
    # so both are "model over" leans. Verify counting on both.
    summary = backtest.summarize(rows)
    assert summary["n"] == 2
    assert summary["won"] == 1
    assert summary["lost"] == 1
    assert summary["hit_rate"] == 0.5
    # ROI: win pays 0.9, loss costs 1.0 -> -0.05 per bet.
    assert summary["roi"] is not None
    assert abs(float(summary["roi"]) - (-0.05)) < 1e-9


def test_edge_sweep_filters():
    games = _build()
    target = _game(4, "A", "B", 105, 105, 200.0)
    rows = backtest.replay(games + [target], min_samples=2)
    assert backtest.edge_sweep(rows, edge_minima=(0.0,), line_caps=(None,))[0]["n"] == 1
    assert backtest.edge_sweep(rows, edge_minima=(0.5,), line_caps=(None,))[0]["n"] == 0
    assert backtest.edge_sweep(rows, edge_minima=(0.0,), line_caps=(150.0,))[0]["n"] == 0
