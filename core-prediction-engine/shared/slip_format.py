from math import prod

from uuid import UUID

from shared.models import Fixture, Slip
from shared.poisson import edge_vs_market, implied_probability


def combined_decimal_odds(leg_odds: list[float]) -> float:
    return round(prod(leg_odds), 2)


def slip_implied_win_probability(combined_odds: float) -> float:
    return implied_probability(combined_odds)


def average_leg_edge(legs_model_p: list[float], legs_odds: list[float]) -> float | None:
    edges = []
    for p, odds in zip(legs_model_p, legs_odds, strict=True):
        edge = edge_vs_market(p, odds)
        if edge is not None:
            edges.append(edge)
    if not edges:
        return None
    return sum(edges) / len(edges)


def build_betpawa_copy(slip: Slip, fixtures_by_id: dict[UUID, Fixture]) -> str:
    """Match names only, one per line, ready to paste into BetPawa search."""
    lines: list[str] = []
    for leg in slip.legs:
        fx = fixtures_by_id[leg.fixture_id]
        lines.append(f"{fx.home_team} v {fx.away_team}")
    return "\n".join(lines)
