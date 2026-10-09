"""Candidate-rule scoring and closing-line-value math (pure)."""

from __future__ import annotations

from shared.basketball import shadow


def g(**kw) -> shadow.ShadowGame:
    base = dict(
        passed=False,
        model_total=220.0,
        p_over=0.5,
        edge=None,
        line=220.0,
        close=220.0,
        over_odds=1.9,
        under_odds=1.9,
        total=220,
    )
    base.update(kw)
    return shadow.ShadowGame(**base)


def test_side_for_official_and():
    assert shadow.side_for("official_and", g(passed=True)) == "over"
    assert shadow.side_for("official_and", g(passed=False)) is None


def test_side_for_model_rules():
    assert shadow.side_for("model_over", g(model_total=225.0, line=220.0)) == "over"
    assert shadow.side_for("model_over", g(model_total=215.0, line=220.0)) is None
    assert shadow.side_for("model_over_confident", g(model_total=225.0, line=220.0, p_over=0.61)) == "over"
    assert shadow.side_for("model_over_confident", g(model_total=225.0, line=220.0, p_over=0.55)) is None


def test_side_for_value_overrule_and_fade():
    assert shadow.side_for("value_overrule", g(edge=0.25, line=230.0)) == "over"
    assert shadow.side_for("value_overrule", g(edge=0.24, line=230.0)) is None
    assert shadow.side_for("value_overrule", g(edge=0.30, line=231.0)) is None
    assert shadow.side_for("fade_conviction", g(model_total=225.0, line=220.0)) == "under"
    assert shadow.side_for("fade_conviction", g(model_total=224.9, line=220.0)) is None


def test_clv_points_sign_for_each_side():
    # Over: a lower decision line than the close is positive value.
    assert shadow.clv_points("over", 225.0, 230.0) == 5.0
    assert shadow.clv_points("over", 225.0, 220.0) == -5.0
    # Under: a higher decision line than the close is positive value.
    assert shadow.clv_points("under", 225.0, 220.0) == 5.0
    assert shadow.clv_points("under", 225.0, 230.0) == -5.0


def test_score_end_to_end():
    games = [
        # model very bullish -> over hits; fade would have lost
        g(
            passed=False,
            model_total=228.0,
            p_over=0.72,
            edge=0.30,
            line=220.0,
            close=222.0,
            total=230,
        ),
        # model slightly under; no over rule and no fade fire
        g(
            passed=False,
            model_total=226.0,
            p_over=0.55,
            edge=0.10,
            line=235.0,
            close=235.0,
            total=228,
        ),
    ]
    by_key = {r["key"]: r for r in shadow.score(games)}
    assert by_key["official_and"]["n"] == 0

    over = by_key["model_over"]
    assert over["n"] == 1 and over["won"] == 1 and over["lost"] == 0
    assert over["hit_rate"] == 1.0
    assert abs(float(over["roi"]) - 0.9) < 1e-9
    assert over["clv_n"] == 1 and abs(float(over["avg_clv"]) - 2.0) < 1e-9
    assert float(over["beat_close_pct"]) == 1.0

    conf = by_key["model_over_confident"]
    assert conf["n"] == 1 and conf["won"] == 1

    val = by_key["value_overrule"]
    assert val["n"] == 1 and val["won"] == 1

    fade = by_key["fade_conviction"]
    assert fade["n"] == 1 and fade["won"] == 0 and fade["lost"] == 1
    assert float(fade["hit_rate"]) == 0.0
    assert abs(float(fade["roi"]) + 1.0) < 1e-9
    assert abs(float(fade["avg_clv"]) + 2.0) < 1e-9  # under at 220 vs close 222
