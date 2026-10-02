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
    combined = combined_decimal_odds([leg.leg_odds for leg in slip.legs])
    lines = [
        f"CASUYA TREBLE ({slip.time_category.value})",
        f"Combined target: {combined:.2f}+ | Model: {slip.model_probability * 100:.1f}%",
        "",
    ]
    for i, leg in enumerate(slip.legs, start=1):
        fx = fixtures_by_id[leg.fixture_id]
        kick = fx.kickoff_at.astimezone().strftime("%d %b %H:%M")
        lines.append(f"{i}. {fx.home_team} v {fx.away_team}")
        lines.append(f"   {leg.market} @ {leg.leg_odds:.2f}  ({kick})")
    lines.extend(["", "Place as accumulator on BetPawa — verify combined odds on site."])
    return "\n".join(lines)
