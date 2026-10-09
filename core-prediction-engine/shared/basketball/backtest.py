"""Shadow backtest for the basketball filter.

Replays the expected-total model over finished games and scores *candidate*
selection rules (model edge, line caps, season over-rate floors) without
touching the live ten-gate filter. This answers "what would the proposed rule
have done?" using the historical sample instead of the handful of games that
happen to have stored gate runs.

Nothing here writes to the database or changes live behaviour.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime

from . import model

MAX_TEAM_GAMES = 220  # mirrors _finished_team_games limit
DEFAULT_RATE_WINDOW = 82
DEFAULT_MIN_SAMPLES = 10
DEFAULT_HOME_ADVANTAGE = 1.03
DEFAULT_SD = 12.5


@dataclass(frozen=True)
class HistGame:
    """One finished game used as backtest history (line may be missing)."""

    tipoff: datetime
    season_type: int
    home_team_id: str
    away_team_id: str
    home_score: int
    away_score: int
    line: float | None
    over_odds: float | None = None
    under_odds: float | None = None

    @property
    def total(self) -> int:
        return self.home_score + self.away_score


@dataclass(frozen=True)
class ReplayRow:
    """A game the model produced a total for, with its realised outcome."""

    tipoff: datetime
    line: float
    model_total: float
    p_over: float
    edge: float | None
    outcome: str  # over | under | push
    total: int
    over_decimal: float | None
    under_decimal: float | None
    home_rate: float | None
    home_samples: int
    away_rate: float | None
    away_samples: int
    away_last10: float | None
    away_last10_samples: int


@dataclass(frozen=True)
class _TeamGame:
    is_home: bool
    scored: int
    allowed: int
    line: float | None


def _rate(history: list[_TeamGame], window: int) -> tuple[float | None, int]:
    with_line = [g for g in history if g.line is not None]
    sample = with_line[-window:]
    if not sample:
        return None, 0
    hits = sum(1 for g in sample if g.scored + g.allowed > float(g.line))  # type: ignore[arg-type]
    return hits / len(sample), len(sample)


def replay(
    games: list[HistGame],
    *,
    rate_window: int = DEFAULT_RATE_WINDOW,
    min_samples: int = DEFAULT_MIN_SAMPLES,
    home_advantage: float = DEFAULT_HOME_ADVANTAGE,
    sd: float = DEFAULT_SD,
) -> list[ReplayRow]:
    """Walk games in time order and emit a model verdict for each one.

    History is regular-season only (season_type == 2), mirroring the live
    filter. A game is only evaluated once both teams have at least
    ``min_samples`` prior venue-split games, so the model never guesses.
    """
    ordered = sorted(games, key=lambda g: g.tipoff)
    history: dict[str, deque[_TeamGame]] = {}
    rows: list[ReplayRow] = []

    for g in ordered:
        if g.season_type != 2:
            continue  # keep history regular-season only, like the live filter

        home_hist = list(history.get(g.home_team_id, ()))
        away_hist = list(history.get(g.away_team_id, ()))
        home_splits = [h for h in home_hist if h.is_home]
        away_splits = [h for h in away_hist if not h.is_home]

        if g.line is not None and len(home_splits) >= min_samples and len(away_splits) >= min_samples:
            home_ppg = sum(h.scored for h in home_splits) / len(home_splits)
            home_apg = sum(h.allowed for h in home_splits) / len(home_splits)
            away_ppg = sum(h.scored for h in away_splits) / len(away_splits)
            away_apg = sum(h.allowed for h in away_splits) / len(away_splits)
            model_total = model.predicted_total(
                home_ppg, home_apg, away_ppg, away_apg, home_advantage=home_advantage
            )
            p_over = model.p_over(model_total, g.line, sd)
            fair = model.fair_implied_over(g.over_odds, g.under_odds)
            edge = p_over - fair if fair is not None else None

            home_rate, home_samples = _rate(home_hist, rate_window)
            away_rate, away_samples = _rate(away_hist, rate_window)
            away_l10, away_l10_n = _rate(away_hist, 10)

            if g.total > g.line:
                outcome = "over"
            elif g.total < g.line:
                outcome = "under"
            else:
                outcome = "push"

            rows.append(
                ReplayRow(
                    tipoff=g.tipoff,
                    line=float(g.line),
                    model_total=model_total,
                    p_over=p_over,
                    edge=edge,
                    outcome=outcome,
                    total=g.total,
                    over_decimal=model.normalize_odds(g.over_odds),
                    under_decimal=model.normalize_odds(g.under_odds),
                    home_rate=home_rate,
                    home_samples=home_samples,
                    away_rate=away_rate,
                    away_samples=away_samples,
                    away_last10=away_l10,
                    away_last10_samples=away_l10_n,
                )
            )

        # The game (if regular season) becomes history for both teams.
        entry_home = _TeamGame(True, g.home_score, g.away_score, g.line)
        entry_away = _TeamGame(False, g.away_score, g.home_score, g.line)
        history.setdefault(g.home_team_id, deque(maxlen=MAX_TEAM_GAMES)).append(entry_home)
        history.setdefault(g.away_team_id, deque(maxlen=MAX_TEAM_GAMES)).append(entry_away)

    return rows


def summarize(rows: list[ReplayRow]) -> dict[str, object]:
    """Win/loss/push and flat-stake ROI (1u per bet) for a selection."""
    won = sum(1 for r in rows if r.outcome == "over")
    lost = sum(1 for r in rows if r.outcome == "under")
    push = sum(1 for r in rows if r.outcome == "push")
    decided = won + lost
    profit = 0.0
    staked = 0
    for r in rows:
        if r.over_decimal and r.over_decimal > 1.0:
            staked += 1
            if r.outcome == "over":
                profit += r.over_decimal - 1.0
            elif r.outcome == "under":
                profit -= 1.0
    return {
        "n": len(rows),
        "won": won,
        "lost": lost,
        "push": push,
        "hit_rate": (won / decided) if decided else None,
        "roi": (profit / staked) if staked else None,
        "roi_n": staked,
    }


def over_bet(row: ReplayRow) -> bool:
    """Mirror of the live g10 lean: model must sit above the market total."""
    return row.model_total > row.line


def edge_sweep(
    rows: list[ReplayRow],
    *,
    edge_minima: tuple[float, ...],
    line_caps: tuple[float | None, ...],
) -> list[dict[str, object]]:
    """Metrics for every (min edge, max line) candidate rule."""
    out: list[dict[str, object]] = []
    for em in edge_minima:
        for lc in line_caps:
            sel = [
                r
                for r in rows
                if r.edge is not None
                and r.edge >= em - 1e-9
                and over_bet(r)
                and (lc is None or r.line <= lc)
            ]
            out.append({"edge_min": em, "line_max": lc, **summarize(sel)})
    return out


def rate_sweep(
    rows: list[ReplayRow],
    *,
    home_away_minima: tuple[float, ...],
    last10_minima: tuple[float, ...],
) -> list[dict[str, object]]:
    """Metrics for the over-rate gates at various floors (g1-g3 replay)."""
    out: list[dict[str, object]] = []
    for ha in home_away_minima:
        for l10 in last10_minima:
            sel = [
                r
                for r in rows
                if over_bet(r)
                and r.home_rate is not None
                and r.home_rate >= ha - 1e-9
                and r.away_rate is not None
                and r.away_rate >= ha - 1e-9
                and r.away_last10 is not None
                and r.away_last10 >= l10 - 1e-9
            ]
            out.append({"home_away_min": ha, "last10_min": l10, **summarize(sel)})
    return out


def line_buckets(
    rows: list[ReplayRow], edges: tuple[float, ...]
) -> list[dict[str, object]]:
    """Over rate / ROI by market-total band (tests the 'low lines overshoot' claim)."""
    out: list[dict[str, object]] = []
    for lo, hi in zip(edges, edges[1:]):
        sel = [r for r in rows if lo <= r.line < hi and over_bet(r)]
        out.append({"lo": lo, "hi": hi, **summarize(sel)})
    return out
