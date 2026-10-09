"""Shadow paper-record: score candidate rules without touching the official record.

The live filter is strict and rarely bets, so any experimental idea (a value
overrule, fading the model, a different threshold) must be *measured separately*
before it is trusted. Everything here is pure: feed it settled games and it
returns per-rule hit rate, flat-stake ROI and closing-line value (CLV).

CLV is the point: a bet that consistently beats the closing line has an edge
even before the win/loss sample is large enough to prove it.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.config import settings

# (key, human label, side the rule bets)
CANDIDATE_RULES: tuple[tuple[str, str], ...] = (
    ("official_and", "Strict 10-gate AND (OVER)"),
    ("model_over", "Model leans OVER (any line)"),
    ("model_over_confident", "Model OVER, p_over >= 60% (official paper)"),
    ("value_overrule", "Value Overrule: edge >= 25% & line <= 230 (OVER)"),
    ("fade_conviction", "Fade conviction: model - line >= 5 (UNDER)"),
)


@dataclass(frozen=True)
class ShadowGame:
    """One settled, evaluated game in a form every candidate rule can score."""

    passed: bool
    model_total: float
    p_over: float | None
    edge: float | None
    line: float  # the line the bet would have been struck at (decision line)
    close: float | None  # closing line, for CLV (may be None)
    over_odds: float | None
    under_odds: float | None
    total: int  # actual combined score


def side_for(rule: str, g: ShadowGame) -> str | None:
    """Return 'over'/'under' when the rule bets, else None."""
    if rule == "official_and":
        return "over" if g.passed else None
    if rule == "model_over":
        return "over" if g.model_total > g.line else None
    if rule == "model_over_confident":
        return "over" if g.model_total > g.line and (g.p_over or 0.0) >= settings.bb_p_over_min else None
    if rule == "value_overrule":
        return "over" if g.edge is not None and g.edge >= 0.25 and g.line <= 230.0 else None
    if rule == "fade_conviction":
        return "under" if (g.model_total - g.line) >= 5.0 else None
    raise ValueError(f"unknown rule: {rule}")


def clv_points(side: str, decision_line: float, closing_line: float) -> float:
    """Line value vs the close. Positive is good for either side."""
    if side == "over":
        return closing_line - decision_line
    return decision_line - closing_line


def _settle(side: str, line: float, total: int) -> str:
    if total > line:
        return "over"
    if total < line:
        return "under"
    return "push"


def score(games: list[ShadowGame]) -> list[dict[str, object]]:
    """Per-rule metrics over a settled set of games."""
    out: list[dict[str, object]] = []
    for rule, label in CANDIDATE_RULES:
        won = lost = push = 0
        profit = 0.0
        staked = 0
        clv: list[float] = []
        for g in games:
            side = side_for(rule, g)
            if side is None:
                continue
            result = _settle(side, g.line, g.total)
            if result == "push":
                push += 1
                continue
            hit = result == side
            won += 1 if hit else 0
            lost += 0 if hit else 1
            odds = g.over_odds if side == "over" else g.under_odds
            if odds and odds > 1.0:
                staked += 1
                profit += (odds - 1.0) if hit else -1.0
            if g.close is not None:
                clv.append(clv_points(side, g.line, g.close))
        decided = won + lost
        out.append(
            {
                "key": rule,
                "label": label,
                "n": won + lost + push,
                "won": won,
                "lost": lost,
                "push": push,
                "hit_rate": (won / decided) if decided else None,
                "roi": (profit / staked) if staked else None,
                "roi_n": staked,
                "clv_n": len(clv),
                "avg_clv": (sum(clv) / len(clv)) if clv else None,
                "beat_close_pct": (sum(1 for x in clv if x > 0) / len(clv)) if clv else None,
            }
        )
    return out
