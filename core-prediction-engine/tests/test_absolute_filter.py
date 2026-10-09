"""Absolute Intersect Filter semantics: strict AND, zero tolerance for gaps."""

from __future__ import annotations

import pytest

from shared.basketball.absolute_filter import (
    GATE_AWAY_LAST10,
    GATE_AWAY_RATE,
    GATE_CONFIDENT_OVER,
    GATE_EDGE,
    GATE_HOME_RATE,
    GATE_H2H_PACE,
    GATE_LINEUP,
    GATE_MOVEMENT,
    GATE_NO_B2B,
    GATE_NOT_TANKING,
    GATE_ORDER,
    GameContext,
    Thresholds,
    evaluate,
)
from shared.config import settings

ALL_GATES = set(GATE_ORDER)


def thresholds() -> Thresholds:
    return Thresholds.from_settings(settings)


def passing_ctx() -> GameContext:
    """A context that satisfies every gate with margin."""
    return GameContext(
        home_name="Home Hawks",
        away_name="Away Ace",
        home_rate=0.72,
        home_samples=45,
        away_rate=0.70,
        away_samples=45,
        away_last10_rate=0.70,
        away_last10_samples=10,
        h2h_pace=103.0,
        h2h_meetings=5,
        lineup_confirmed=True,
        lineup_reason="5 key players clear",
        home_b2b=False,
        away_b2b=False,
        standings_available=True,
        tanking_teams=(),
        market_total=227.5,
        fair_implied_over=0.50,
        first_line=227.5,
        current_line=227.5,
        model_total=235.0,
        p_over=0.60,
    )


def failing(report, gate: str) -> bool:
    return any(g.gate == gate and not g.passed for g in report.gates)


def test_all_pass_is_ordered_and_complete():
    report = evaluate(passing_ctx(), thresholds())
    assert report.passed is True
    assert [g.gate for g in report.gates] == list(GATE_ORDER)
    assert len(report.gates) == 10
    assert all(g.reason for g in report.gates)
    assert report.passed_count == 10


def test_empty_context_fails_every_gate():
    report = evaluate(GameContext(home_name="A", away_name="B"), thresholds())
    assert report.passed is False
    assert report.passed_count == 0
    assert len(report.failures) == 10


def test_single_failure_rejects_despite_nine_passing():
    ctx = passing_ctx()
    ctx.home_rate = 0.50  # gate 1 only
    report = evaluate(ctx, thresholds())
    assert report.passed is False
    assert report.passed_count == 9
    assert [g.gate for g in report.failures] == [GATE_HOME_RATE]


@pytest.mark.parametrize(
    ("mutate", "gate"),
    [
        (lambda c: setattr(c, "away_rate", 0.50), GATE_AWAY_RATE),
        (lambda c: setattr(c, "away_last10_rate", 0.50), GATE_AWAY_LAST10),
        (lambda c: setattr(c, "h2h_pace", 100.0), GATE_H2H_PACE),
        (lambda c: setattr(c, "lineup_confirmed", False), GATE_LINEUP),
        (lambda c: setattr(c, "home_b2b", True), GATE_NO_B2B),
        (lambda c: setattr(c, "standings_available", False), GATE_NOT_TANKING),
        (lambda c: setattr(c, "tanking_teams", ("Tanking Titans",)), GATE_NOT_TANKING),
        (lambda c: setattr(c, "fair_implied_over", 0.56), GATE_EDGE),
        (lambda c: setattr(c, "current_line", 231.0), GATE_MOVEMENT),
        (lambda c: setattr(c, "model_total", 220.0), GATE_CONFIDENT_OVER),
        (lambda c: setattr(c, "p_over", 0.58), GATE_CONFIDENT_OVER),
    ],
)
def test_each_gate_rejects_on_its_own(mutate, gate):
    ctx = passing_ctx()
    mutate(ctx)
    report = evaluate(ctx, thresholds())
    assert report.passed is False
    assert failing(report, gate)
    # the rejection is exactly one gate — no partial credit anywhere else
    assert [g.gate for g in report.failures] == [gate]


@pytest.mark.parametrize(
    ("mutate", "gate"),
    [
        (lambda c: setattr(c, "h2h_meetings", 2), GATE_H2H_PACE),
        (lambda c: setattr(c, "home_b2b", None), GATE_NO_B2B),
        (lambda c: setattr(c, "away_b2b", None), GATE_NO_B2B),
        (lambda c: setattr(c, "p_over", None), GATE_EDGE),
        (lambda c: setattr(c, "fair_implied_over", None), GATE_EDGE),
        (lambda c: setattr(c, "first_line", None), GATE_MOVEMENT),
        (lambda c: setattr(c, "current_line", None), GATE_MOVEMENT),
        (lambda c: setattr(c, "model_total", None), GATE_CONFIDENT_OVER),
        (lambda c: setattr(c, "market_total", None), GATE_CONFIDENT_OVER),
    ],
)
def test_missing_data_is_a_failure_not_a_guess(mutate, gate):
    ctx = passing_ctx()
    mutate(ctx)
    report = evaluate(ctx, thresholds())
    assert report.passed is False
    assert failing(report, gate)
    failed = {g.gate for g in report.failures}
    assert gate in failed


def test_rate_thresholds_are_inclusive():
    th = thresholds()
    ctx = passing_ctx()
    ctx.home_rate = th.home_away_over_rate_min  # exactly 68%
    ctx.away_rate = th.home_away_over_rate_min
    ctx.away_last10_rate = th.last10_over_rate_min  # exactly 65%
    report = evaluate(ctx, th)
    assert not failing(report, GATE_HOME_RATE)
    assert not failing(report, GATE_AWAY_RATE)
    assert not failing(report, GATE_AWAY_LAST10)

    ctx.home_rate = th.home_away_over_rate_min - 0.001
    report = evaluate(ctx, th)
    assert failing(report, GATE_HOME_RATE)


def test_edge_boundary_is_inclusive_at_6_5_percent():
    th = thresholds()
    ctx = passing_ctx()
    ctx.fair_implied_over = 0.50
    ctx.p_over = 0.50 + th.model_edge_min  # exactly +6.5pp
    report = evaluate(ctx, th)
    assert not failing(report, GATE_EDGE)

    ctx.p_over = 0.50 + th.model_edge_min - 0.0001
    report = evaluate(ctx, th)
    assert failing(report, GATE_EDGE)


def test_line_movement_strictly_below_threshold():
    th = thresholds()
    ctx = passing_ctx()
    ctx.first_line = 227.5
    ctx.current_line = 227.5 + th.line_movement_max  # exactly 1.5 -> reject
    report = evaluate(ctx, th)
    assert failing(report, GATE_MOVEMENT)

    ctx.current_line = 227.5 + th.line_movement_max - 0.01
    report = evaluate(ctx, th)
    assert not failing(report, GATE_MOVEMENT)


def test_h2h_pace_boundary():
    th = thresholds()
    ctx = passing_ctx()
    ctx.h2h_pace = th.h2h_pace_min  # exactly 101.5 -> pass
    report = evaluate(ctx, th)
    assert not failing(report, GATE_H2H_PACE)

    ctx.h2h_pace = th.h2h_pace_min - 0.1
    report = evaluate(ctx, th)
    assert failing(report, GATE_H2H_PACE)


def test_checks_serialisable_for_audit_table():
    report = evaluate(passing_ctx(), thresholds())
    checks = report.as_checks()
    assert set(checks) == ALL_GATES
    for value in checks.values():
        assert isinstance(value["passed"], bool)
        assert isinstance(value["reason"], str)
