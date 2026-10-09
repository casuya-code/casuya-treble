"""Expected-total model for basketball over/under lines (pure functions).

The model scores each team from its recent finished regular-season games:

    home_exp = ((home points at home + away points allowed away) / 2) * home_adv
    away_exp =  (away points away + home points allowed home) / 2
    predicted_total = home_exp + away_exp

P(over) treats the final total as normally distributed around the prediction
with a configurable standard deviation (NBA combined totals vary ~12.5 pts).
"""

from __future__ import annotations

from statistics import NormalDist

DEFAULT_HOME_ADVANTAGE = 1.03
DEFAULT_TOTAL_SD = 12.5


def expected_total(
    home_ppg_at_home: float,
    home_apg_at_home: float,
    away_ppg_away: float,
    away_apg_away: float,
    *,
    home_advantage: float = DEFAULT_HOME_ADVANTAGE,
) -> tuple[float, float]:
    """Return (expected home score, expected away score)."""
    home_exp = ((home_ppg_at_home + away_apg_away) / 2.0) * home_advantage
    away_exp = (away_ppg_away + home_apg_at_home) / 2.0
    return home_exp, away_exp


def predicted_total(
    home_ppg_at_home: float,
    home_apg_at_home: float,
    away_ppg_away: float,
    away_apg_away: float,
    *,
    home_advantage: float = DEFAULT_HOME_ADVANTAGE,
) -> float:
    home_exp, away_exp = expected_total(
        home_ppg_at_home,
        home_apg_at_home,
        away_ppg_away,
        away_apg_away,
        home_advantage=home_advantage,
    )
    return home_exp + away_exp


def p_over(predicted: float, line: float, sd: float = DEFAULT_TOTAL_SD) -> float:
    """Probability the combined score lands over `line`."""
    if sd <= 0:
        raise ValueError("sd must be positive")
    return 1.0 - NormalDist(mu=predicted, sigma=sd).cdf(line)


def american_to_decimal(odds: float | None) -> float | None:
    """Convert a raw American moneyline (-110, +150) to decimal odds."""
    if odds is None:
        return None
    if odds < 0:
        return 1.0 + 100.0 / abs(odds)  # -110 -> 1.9091
    if odds >= 100:
        return 1.0 + odds / 100.0  # +150 -> 2.50
    return odds  # already decimal (1 < odds < 100)


def normalize_odds(odds: float | None) -> float | None:
    """Return decimal odds whether the input is American or decimal."""
    if odds is None or odds == 0:
        return None
    if odds < 0 or odds >= 100:
        return american_to_decimal(odds)
    return odds


def fair_implied_over(over_odds: float | None, under_odds: float | None) -> float | None:
    """Vig-removed implied probability of OVER from an odds pair (American or decimal)."""
    over_dec = normalize_odds(over_odds)
    under_dec = normalize_odds(under_odds)
    if over_dec is None or under_dec is None:
        return None
    if over_dec <= 1.0 or under_dec <= 1.0:
        return None
    implied_over = 1.0 / over_dec
    implied_under = 1.0 / under_dec
    total = implied_over + implied_under
    if total <= 0:
        return None
    return implied_over / total


def model_edge(p_over_value: float | None, over_odds: float | None, under_odds: float | None) -> float | None:
    """Model probability minus vig-removed market probability of OVER."""
    implied = fair_implied_over(over_odds, under_odds)
    if p_over_value is None or implied is None:
        return None
    return p_over_value - implied
