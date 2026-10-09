"""The Absolute Intersect Filter — a strict boolean-AND network of ten gates.

Any gate failing (including a 9/10 result) means AUTOMATED_REJECTION. There is
no weighted scoring and no partial credit anywhere in this module. A gate whose
input data is missing fails: the filter is forbidden from guessing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

GATE_HOME_RATE = "g1_home_over_rate_68"
GATE_AWAY_RATE = "g2_away_over_rate_68"
GATE_AWAY_LAST10 = "g3_away_last10_over_rate_65"
GATE_H2H_PACE = "g4_h2h_pace_101_5"
GATE_LINEUP = "g5_lineup_confirmed"
GATE_NO_B2B = "g6_no_back_to_back"
GATE_NOT_TANKING = "g7_not_tanking_or_dead_rubber"
GATE_EDGE = "g8_model_edge_6_5"
GATE_MOVEMENT = "g9_line_movement_under_1_5"
GATE_CONFIDENT_OVER = "g10_model_confident_over"

GATE_ORDER: tuple[str, ...] = (
    GATE_HOME_RATE,
    GATE_AWAY_RATE,
    GATE_AWAY_LAST10,
    GATE_H2H_PACE,
    GATE_LINEUP,
    GATE_NO_B2B,
    GATE_NOT_TANKING,
    GATE_EDGE,
    GATE_MOVEMENT,
    GATE_CONFIDENT_OVER,
)

# Catalog for the UI: label + how the threshold reads.
GATE_CATALOG: tuple[dict[str, str], ...] = (
    {"gate": GATE_HOME_RATE, "label": "Home O/U rate", "threshold": ">= 68% over (season)"},
    {"gate": GATE_AWAY_RATE, "label": "Away O/U rate", "threshold": ">= 68% over (season)"},
    {"gate": GATE_AWAY_LAST10, "label": "Away last-10 O/U", "threshold": ">= 65% over"},
    {"gate": GATE_H2H_PACE, "label": "H2H pace", "threshold": ">= 101.5 possessions"},
    {"gate": GATE_LINEUP, "label": "Lineup confirmed", "threshold": "top-4 usage + rim protector clear"},
    {"gate": GATE_NO_B2B, "label": "No back-to-back", "threshold": "neither team played yesterday"},
    {"gate": GATE_NOT_TANKING, "label": "Not tanking", "threshold": "no dead-rubber risk"},
    {"gate": GATE_EDGE, "label": "Model edge", "threshold": ">= 6.5% vs market"},
    {"gate": GATE_MOVEMENT, "label": "Line stability", "threshold": "movement < 1.5 pts"},
    {"gate": GATE_CONFIDENT_OVER, "label": "Confident over", "threshold": "model over, P(over) >= 60%"},
)


@dataclass(frozen=True)
class Thresholds:
    """Filter thresholds (normally built from Settings)."""

    home_away_over_rate_min: float
    last10_over_rate_min: float
    min_rate_samples: int
    min_rate_samples_last10: int
    h2h_pace_min: float
    min_h2h_meetings: int
    tanking_win_pct_max: float
    tanking_min_games: int
    model_edge_min: float
    line_movement_max: float
    p_over_min: float

    @classmethod
    def from_settings(cls, settings) -> "Thresholds":  # noqa: ANN001 - shared.config.Settings
        return cls(
            home_away_over_rate_min=settings.bb_home_away_over_rate_min,
            last10_over_rate_min=settings.bb_last10_over_rate_min,
            min_rate_samples=settings.bb_min_rate_samples,
            min_rate_samples_last10=settings.bb_min_rate_samples_last10,
            h2h_pace_min=settings.bb_h2h_pace_min,
            min_h2h_meetings=settings.bb_min_h2h_meetings,
            tanking_win_pct_max=settings.bb_tanking_win_pct_max,
            tanking_min_games=settings.bb_tanking_min_games,
            model_edge_min=settings.bb_model_edge_min,
            line_movement_max=settings.bb_line_movement_max,
            p_over_min=settings.bb_p_over_min,
        )


@dataclass(frozen=True)
class GateCheck:
    gate: str
    passed: bool
    reason: str


@dataclass(frozen=True)
class AbsoluteFilterReport:
    gates: tuple[GateCheck, ...]

    @property
    def passed(self) -> bool:
        return all(g.passed for g in self.gates)

    @property
    def failures(self) -> list[GateCheck]:
        return [g for g in self.gates if not g.passed]

    @property
    def passed_count(self) -> int:
        return sum(1 for g in self.gates if g.passed)

    def as_checks(self) -> dict[str, dict[str, object]]:
        return {
            g.gate: {"passed": g.passed, "reason": g.reason}
            for g in self.gates
        }


@dataclass
class GameContext:
    """Everything the ten gates need for one game. None == missing data."""

    home_name: str = ""
    away_name: str = ""

    home_rate: float | None = None
    home_samples: int = 0
    away_rate: float | None = None
    away_samples: int = 0
    away_last10_rate: float | None = None
    away_last10_samples: int = 0

    h2h_pace: float | None = None
    h2h_meetings: int = 0

    lineup_confirmed: bool = False
    lineup_reason: str = "no lineup data"

    home_b2b: bool | None = None
    away_b2b: bool | None = None

    standings_available: bool = False
    tanking_teams: tuple[str, ...] = ()

    market_total: float | None = None
    fair_implied_over: float | None = None
    first_line: float | None = None
    current_line: float | None = None

    model_total: float | None = None
    p_over: float | None = None

    extras: dict[str, object] = field(default_factory=dict)


def _rate_gate(
    gate: str,
    rate: float | None,
    samples: int,
    needed: int,
    minimum: float,
) -> GateCheck:
    if rate is None or samples < needed:
        return GateCheck(
            gate,
            False,
            f"insufficient data ({samples}/{needed} samples)",
        )
    if rate < minimum:
        return GateCheck(gate, False, f"{rate:.1%} over from {samples} games, need {minimum:.0%}")
    return GateCheck(gate, True, f"{rate:.1%} over from {samples} games")


def evaluate(ctx: GameContext, th: Thresholds) -> AbsoluteFilterReport:
    """Run all ten gates. One failure rejects the tip outright."""
    checks: list[GateCheck] = []

    # 1-3: over/under hit rates.
    checks.append(
        _rate_gate(GATE_HOME_RATE, ctx.home_rate, ctx.home_samples, th.min_rate_samples, th.home_away_over_rate_min)
    )
    checks.append(
        _rate_gate(GATE_AWAY_RATE, ctx.away_rate, ctx.away_samples, th.min_rate_samples, th.home_away_over_rate_min)
    )
    checks.append(
        _rate_gate(
            GATE_AWAY_LAST10,
            ctx.away_last10_rate,
            ctx.away_last10_samples,
            th.min_rate_samples_last10,
            th.last10_over_rate_min,
        )
    )

    # 4: head-to-head pace proxy.
    if ctx.h2h_pace is None or ctx.h2h_meetings < th.min_h2h_meetings:
        checks.append(
            GateCheck(
                GATE_H2H_PACE,
                False,
                f"insufficient data ({ctx.h2h_meetings}/{th.min_h2h_meetings} meetings)",
            )
        )
    elif ctx.h2h_pace < th.h2h_pace_min:
        checks.append(GateCheck(GATE_H2H_PACE, False, f"{ctx.h2h_pace:.1f} poss, need {th.h2h_pace_min:.1f}"))
    else:
        checks.append(GateCheck(GATE_H2H_PACE, True, f"{ctx.h2h_pace:.1f} possessions over {ctx.h2h_meetings} H2H"))

    # 5: lineup confirmation (top-4 usage + rim protector).
    if ctx.lineup_confirmed:
        checks.append(GateCheck(GATE_LINEUP, True, ctx.lineup_reason))
    else:
        checks.append(GateCheck(GATE_LINEUP, False, ctx.lineup_reason))

    # 6: no back-to-back for either team.
    if ctx.home_b2b is None or ctx.away_b2b is None:
        checks.append(GateCheck(GATE_NO_B2B, False, "insufficient schedule data"))
    elif ctx.home_b2b:
        checks.append(GateCheck(GATE_NO_B2B, False, f"{ctx.home_name} played yesterday"))
    elif ctx.away_b2b:
        checks.append(GateCheck(GATE_NO_B2B, False, f"{ctx.away_name} played yesterday"))
    else:
        checks.append(GateCheck(GATE_NO_B2B, True, "fresh for both teams"))

    # 7: tanking / dead-rubber risk.
    if not ctx.standings_available:
        checks.append(GateCheck(GATE_NOT_TANKING, False, "standings unavailable"))
    elif ctx.tanking_teams:
        checks.append(GateCheck(GATE_NOT_TANKING, False, "tanking risk: " + ", ".join(ctx.tanking_teams)))
    else:
        checks.append(GateCheck(GATE_NOT_TANKING, True, "no tanking signal"))

    # 8: model edge vs vig-removed market probability.
    if ctx.p_over is None or ctx.fair_implied_over is None:
        checks.append(GateCheck(GATE_EDGE, False, "insufficient model/market data"))
    else:
        edge = ctx.p_over - ctx.fair_implied_over
        # 1e-9 absorbs float noise exactly at the configured threshold.
        if edge < th.model_edge_min - 1e-9:
            checks.append(
                GateCheck(GATE_EDGE, False, f"edge {edge:+.1%}, need {th.model_edge_min:+.1%}")
            )
        else:
            checks.append(
                GateCheck(
                    GATE_EDGE,
                    True,
                    f"edge {edge:+.1%} (model {ctx.p_over:.1%} vs market {ctx.fair_implied_over:.1%})",
                )
            )

    # 9: line movement since the first snapshot.
    if ctx.first_line is None or ctx.current_line is None:
        checks.append(GateCheck(GATE_MOVEMENT, False, "no market snapshots"))
    else:
        movement = abs(ctx.current_line - ctx.first_line)
        if movement >= th.line_movement_max:
            checks.append(
                GateCheck(GATE_MOVEMENT, False, f"{ctx.first_line:.1f} -> {ctx.current_line:.1f} ({movement:.1f} pts)")
            )
        else:
            checks.append(
                GateCheck(GATE_MOVEMENT, True, f"stable: {ctx.first_line:.1f} -> {ctx.current_line:.1f}")
            )

    # 10: confident, always-over projection.
    if ctx.model_total is None or ctx.market_total is None or ctx.p_over is None:
        checks.append(GateCheck(GATE_CONFIDENT_OVER, False, "insufficient model/market data"))
    elif ctx.model_total <= ctx.market_total:
        checks.append(
            GateCheck(
                GATE_CONFIDENT_OVER,
                False,
                f"model {ctx.model_total:.1f} not over market {ctx.market_total:.1f}",
            )
        )
    elif ctx.p_over < th.p_over_min:
        checks.append(GateCheck(GATE_CONFIDENT_OVER, False, f"P(over) {ctx.p_over:.1%} < {th.p_over_min:.0%}"))
    else:
        checks.append(
            GateCheck(
                GATE_CONFIDENT_OVER,
                True,
                f"model {ctx.model_total:.1f} > {ctx.market_total:.1f}, P(over) {ctx.p_over:.1%}",
            )
        )

    # Guarantee catalog order even if a branch above appended out of order.
    by_gate = {c.gate: c for c in checks}
    ordered = tuple(by_gate[gate] for gate in GATE_ORDER)
    return AbsoluteFilterReport(gates=ordered)
