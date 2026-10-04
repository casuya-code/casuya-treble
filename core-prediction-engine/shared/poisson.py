"""Dixon-Coles adjusted Poisson for Over 1.5 goals.

Raw Poisson treats the two teams as one goal total and under-weights 0-0 and 1-1.
The correction rescales those low scorelines before the Over 1.5 chance is read off.
"""

import math

# Dixon & Coles dependence. Negative rho puts extra chance on 0-0 and 1-1.
DIXON_COLES_RHO = -0.13
MAX_GOALS = 8


def poisson_pmf(k: int, lam: float) -> float:
    lam = max(lam, 1e-6)
    return math.exp(-lam) * (lam**k) / math.factorial(k)


def _tau(home_goals: int, away_goals: int, lambda_home: float, lambda_away: float, rho: float) -> float:
    if home_goals == 0 and away_goals == 0:
        return 1.0 - lambda_home * lambda_away * rho
    if home_goals == 0 and away_goals == 1:
        return 1.0 + lambda_home * rho
    if home_goals == 1 and away_goals == 0:
        return 1.0 + lambda_away * rho
    if home_goals == 1 and away_goals == 1:
        return 1.0 - rho
    return 1.0


def scoreline_probabilities(
    lambda_home: float,
    lambda_away: float,
    *,
    rho: float = DIXON_COLES_RHO,
) -> dict[tuple[int, int], float]:
    """Independent Poisson scorelines, rescaled on 0-0, 1-0, 0-1, and 1-1."""
    lambda_home = max(lambda_home, 0.05)
    lambda_away = max(lambda_away, 0.05)
    raw: dict[tuple[int, int], float] = {}
    for home_goals in range(MAX_GOALS + 1):
        for away_goals in range(MAX_GOALS + 1):
            weight = _tau(home_goals, away_goals, lambda_home, lambda_away, rho)
            raw[(home_goals, away_goals)] = max(0.0, weight) * poisson_pmf(home_goals, lambda_home) * poisson_pmf(
                away_goals, lambda_away
            )
    total = sum(raw.values()) or 1.0
    return {score: weight / total for score, weight in raw.items()}


def total_goals_lambda(lambda_home: float, lambda_away: float) -> float:
    return max(lambda_home + lambda_away, 0.05)


def prob_over_15(lambda_home: float, lambda_away: float) -> float:
    """Chance of two or more goals after the low-score correction."""
    grid = scoreline_probabilities(lambda_home, lambda_away)
    under = grid[(0, 0)] + grid[(1, 0)] + grid[(0, 1)]
    return float(max(0.0, min(1.0, 1.0 - under)))


def fair_odds_from_probability(probability: float) -> float:
    p = max(probability, 1e-6)
    return round(1.0 / p, 3)


def implied_probability(decimal_odds: float) -> float:
    return 1.0 / decimal_odds if decimal_odds > 1.0 else 0.0


def edge_vs_market(model_probability: float, decimal_odds: float) -> float | None:
    if decimal_odds is None or decimal_odds <= 1.0:
        return None
    return model_probability - implied_probability(decimal_odds)


def leg_won_over_15(home_goals: int, away_goals: int) -> bool:
    return (home_goals + away_goals) >= 2
