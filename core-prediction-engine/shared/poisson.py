"""Poisson-based Over 1.5 goals probability from expected team scoring rates."""

import math


def poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * (lam**k) / math.factorial(k)


def total_goals_lambda(lambda_home: float, lambda_away: float) -> float:
    return max(lambda_home + lambda_away, 0.05)


def prob_over_15(lambda_home: float, lambda_away: float) -> float:
    lam = total_goals_lambda(lambda_home, lambda_away)
    p0 = poisson_pmf(0, lam)
    p1 = poisson_pmf(1, lam)
    return float(max(0.0, min(1.0, 1.0 - p0 - p1)))


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
