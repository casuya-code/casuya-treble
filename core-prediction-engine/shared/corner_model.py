"""Full-match corner model: a gradient-boosted tree correction over the Poisson prior.

TotalCorner derives its Corner Under picks from a GBDT over team/league corner
rates. This mirrors that idea on the data Casuya already keeps: the Poisson
expectation in ``corners`` is the first feature, and a small gradient-boosted
regressor learns the residual bias (league style, venue effects, form) from
finished matches. Trees train offline, serialise to JSON, and are walked in
plain Python at request time so the engine needs no new dependency.
"""

from __future__ import annotations

import json
import math
import random
from bisect import bisect_left, bisect_right
from pathlib import Path

from shared.corners import _corner_total_from_rows, project_corner_history
from shared.poisson import implied_probability
from shared.team_names import team_key

FT_MIN_EDGE = 0.02
FT_MIN_ODDS = 1.10
MAX_REST_DAYS = 30.0
TAIL_PAD = 40

#: Feature order is part of the serialised model; never reorder, only append.
#: The trailing block maps FootyStats/APWin-style stats onto local data: each
#: team's recent five-match corner form and empirical over-9.5 rates for the
#: teams and the league (a league split of the total was tried and ablated out).
FEATURE_NAMES = (
    "expected_total",
    "league_total",
    "home_for",
    "home_against",
    "away_for",
    "away_against",
    "home_for_all",
    "away_for_all",
    "home_games",
    "away_games",
    "rest_home",
    "rest_away",
    "home_form5",
    "away_form5",
    "home_over95_rate",
    "away_over95_rate",
    "league_over95_rate",
)


def build_features(
    rows: list,
    *,
    home_key: str,
    away_key: str,
    today,
    kickoff_day,
) -> dict[str, float] | None:
    """Feature vector for one fixture, or None when the corner sample is too thin.

    ``rows`` must already be restricted to prior matches in the same league.
    """
    expected = _corner_total_from_rows(rows, home_key=home_key, away_key=away_key, today=today)
    if expected is None:
        return None

    deduped: dict[tuple[str, str, str], object] = {}
    for row in rows:
        deduped.setdefault((row.home_key, row.away_key, row.day_iso), row)
    finished = sorted(deduped.values(), key=lambda r: r.day, reverse=True)

    league_home = _plain_avg(finished, lambda r: r.home_corners)
    league_away = _plain_avg(finished, lambda r: r.away_corners)
    home_venue = [r for r in finished if r.home_key == home_key][:10]
    away_venue = [r for r in finished if r.away_key == away_key][:10]
    home_all = [r for r in finished if r.home_key == home_key or r.away_key == home_key][:20]
    away_all = [r for r in finished if r.home_key == away_key or r.away_key == away_key][:20]

    def for_team(row, key):
        return row.home_corners if row.home_key == key else row.away_corners

    def against_team(row, key):
        return row.away_corners if row.home_key == key else row.home_corners

    # FootyStats-style: each team's recent corners (form), the league's empirical
    # over-9.5 share, and per-team over-9.5 rates. ``finished`` is newest first.
    def team_totals(key: str, n: int) -> list[float]:
        totals: list[float] = []
        for row in finished:
            if row.home_key != key and row.away_key != key:
                continue
            totals.append(float(row.home_corners + row.away_corners))
            if len(totals) >= n:
                break
        return totals

    league_over95 = _share_over([r.home_corners + r.away_corners for r in finished], 9.5) or 0.0
    home_form5 = _mean(team_totals(home_key, 5)) or 0.0
    away_form5 = _mean(team_totals(away_key, 5)) or 0.0
    # A real 0.0 rate (no match over the line) is a value, not a missing one.
    home_rate = _share_over(team_totals(home_key, 10), 9.5)
    away_rate = _share_over(team_totals(away_key, 10), 9.5)
    home_over95_rate = league_over95 if home_rate is None else home_rate
    away_over95_rate = league_over95 if away_rate is None else away_rate

    feats = {
        "expected_total": expected,
        "league_total": (league_home or 0.0) + (league_away or 0.0),
        "home_for": _plain_avg(home_venue, lambda r: r.home_corners) or 0.0,
        "home_against": _plain_avg(home_venue, lambda r: r.away_corners) or 0.0,
        "away_for": _plain_avg(away_venue, lambda r: r.away_corners) or 0.0,
        "away_against": _plain_avg(away_venue, lambda r: r.home_corners) or 0.0,
        "home_for_all": _plain_avg(home_all, lambda r: for_team(r, home_key)) or 0.0,
        "away_for_all": _plain_avg(away_all, lambda r: for_team(r, away_key)) or 0.0,
        "home_games": float(len(home_venue)),
        "away_games": float(len(away_venue)),
        "rest_home": _rest_days(finished, home_key, kickoff_day),
        "rest_away": _rest_days(finished, away_key, kickoff_day),
        "home_form5": home_form5,
        "away_form5": away_form5,
        "home_over95_rate": home_over95_rate,
        "away_over95_rate": away_over95_rate,
        "league_over95_rate": league_over95,
    }
    return feats


def vector(feats: dict[str, float]) -> list[float]:
    return [float(feats[name]) for name in FEATURE_NAMES]


def _plain_avg(rows: list, pick) -> float | None:
    values = [pick(r) for r in rows]
    values = [v for v in values if v is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _mean(values: list) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _share_over(values: list, threshold: float) -> float | None:
    """Fraction of the values that clear a .5 line, e.g. the over-9.5 rate."""
    if not values:
        return None
    return sum(1 for v in values if v > threshold) / len(values)


def _rest_days(rows: list, key: str, kickoff_day) -> float:
    latest = None
    for row in rows:
        if row.home_key != key and row.away_key != key:
            continue
        if latest is None or row.day > latest:
            latest = row.day
    if latest is None:
        return MAX_REST_DAYS
    return float(min(max((kickoff_day - latest).days, 0), MAX_REST_DAYS))


# --------------------------------------------------------------------------- #
# Gradient-boosted regression trees
# --------------------------------------------------------------------------- #


def _predict_tree(node: dict, x: list[float]) -> float:
    while "v" not in node:
        value = x[node["f"]]
        node = node["l"] if (value is None or value <= node["t"]) else node["r"]
    return node["v"]


def _build_tree(
    x: list[list[float]],
    y: list[float],
    idx: list[int],
    depth: int,
    *,
    max_depth: int,
    min_leaf: int,
    max_features: int,
    rng: random.Random,
    n_features: int,
) -> dict:
    node_mean = sum(y[i] for i in idx) / len(idx)
    if depth >= max_depth or len(idx) < 2 * min_leaf:
        return {"v": node_mean}

    total = sum(y[i] for i in idx)
    total_sq = sum(y[i] * y[i] for i in idx)
    node_sse = total_sq - (total * total) / len(idx)

    features = range(n_features)
    if max_features < n_features:
        features = rng.sample(list(features), max_features)

    best_sse = node_sse
    best_feature = -1
    best_threshold = 0.0
    best_left: list[int] = []
    best_right: list[int] = []

    for f in features:
        present = sorted((x[i][f], i) for i in idx)
        if len(present) < 2:
            continue
        # Running sums trick: walk the sorted values and score every split.
        left_sum = 0.0
        left_sq = 0.0
        right_sum = total
        right_sq = total_sq
        anytime: list[tuple[float, int]] = []
        for value, i in present:
            left_sum += y[i]
            left_sq += y[i] * y[i]
            right_sum -= y[i]
            right_sq -= y[i] * y[i]
            anytime.append((value, i))
            left_n = len(anytime)
            right_n = len(idx) - left_n
            if left_n < min_leaf or right_n < min_leaf:
                continue
            if value == anytime[-2][0]:  # only split between distinct values
                continue
            sse = (left_sq - left_sum * left_sum / left_n) + (
                right_sq - right_sum * right_sum / right_n
            )
            if sse < best_sse - 1e-9:
                best_sse = sse
                best_feature = f
                best_threshold = (value + anytime[-2][0]) / 2.0
                best_left = [j for _v, j in anytime]
                best_right = [i2 for _v, i2 in present[left_n:]]

    if best_feature < 0:
        return {"v": node_mean}

    return {
        "f": best_feature,
        "t": best_threshold,
        "l": _build_tree(
            x, y, best_left, depth + 1,
            max_depth=max_depth, min_leaf=min_leaf, max_features=max_features,
            rng=rng, n_features=n_features,
        ),
        "r": _build_tree(
            x, y, best_right, depth + 1,
            max_depth=max_depth, min_leaf=min_leaf, max_features=max_features,
            rng=rng, n_features=n_features,
        ),
    }


class CornerTrees:
    """Gradient boosting on squared error, small enough to serialise as JSON."""

    def __init__(
        self,
        *,
        n_estimators: int = 220,
        learning_rate: float = 0.06,
        max_depth: int = 3,
        min_leaf: int = 25,
        subsample: float = 0.8,
        max_features: int = 4,
        random_state: int = 7,
    ) -> None:
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.max_depth = max_depth
        self.min_leaf = min_leaf
        self.subsample = subsample
        self.max_features = max_features
        self.random_state = random_state
        self.base = 0.0
        self.trees: list[dict] = []
        self.dispersion = 0.0

    def fit(self, x: list[list[float]], y: list[float]) -> "CornerTrees":
        rng = random.Random(self.random_state)
        self.base = sum(y) / len(y)
        pred = [self.base] * len(y)
        n_features = len(x[0]) if x else len(FEATURE_NAMES)
        for _ in range(self.n_estimators):
            residual = [y[i] - pred[i] for i in range(len(y))]
            if self.subsample < 1.0:
                sample = [i for i in range(len(y)) if rng.random() < self.subsample]
                if len(sample) < 2 * self.min_leaf:
                    sample = list(range(len(y)))
            else:
                sample = list(range(len(y)))
            tree = _build_tree(
                x, residual, sample, 0,
                max_depth=self.max_depth, min_leaf=self.min_leaf,
                max_features=self.max_features, rng=rng, n_features=n_features,
            )
            self.trees.append(tree)
            for i in range(len(y)):
                pred[i] += self.learning_rate * _predict_tree(tree, x[i])
        self.dispersion = self._fit_dispersion(y, pred)
        return self

    def _fit_dispersion(self, y: list[float], pred: list[float]) -> float:
        """Moment-match a negative-binomial over-dispersion from the residuals."""
        n = len(y)
        mean_pred = sum(pred) / n
        var = sum((y[i] - pred[i]) ** 2 for i in range(n)) / n
        if var <= mean_pred or mean_pred <= 0:
            return 0.0
        return round(mean_pred * mean_pred / (var - mean_pred), 3)

    def predict(self, x: list[float]) -> float:
        value = self.base
        for tree in self.trees:
            value += self.learning_rate * _predict_tree(tree, x)
        return float(value)


# --------------------------------------------------------------------------- #
# Distribution and model persistence
# --------------------------------------------------------------------------- #


def pmf(k: int, mean: float, dispersion: float) -> float:
    """Negative-binomial probability; falls back to Poisson when dispersion is 0."""
    mean = max(mean, 1e-6)
    if dispersion <= 0:
        return math.exp(-mean) * (mean**k) / math.factorial(k)
    p = dispersion / (dispersion + mean)
    log_p = (
        math.lgamma(k + dispersion)
        - math.lgamma(dispersion)
        - math.lgamma(k + 1)
        + dispersion * math.log(p)
        + k * math.log1p(-p)
    )
    return math.exp(log_p)


def side_probabilities(mean: float, dispersion: float, line: float) -> tuple[float, float, float]:
    """(over, under, push) for a corner total against a line. Over means count > line."""
    top = int(math.ceil(line)) + TAIL_PAD
    over = 0.0
    under = 0.0
    push = 0.0
    for k in range(top + 1):
        probability = pmf(k, mean, dispersion)
        if k > line:
            over += probability
        elif k < line:
            under += probability
        else:
            push += probability
    return over, under, push


def empirical_probabilities(residuals: list[float], mean: float, line: float) -> tuple[float, float, float] | None:
    """(over, under, push) read straight off the model's held-out error spread.

    Corner totals are not cleanly Poisson after the trees have eaten the signal,
    so the honest spread is the residual distribution itself.
    """
    n = len(residuals)
    if n == 0:
        return None
    threshold = line - mean
    below = bisect_left(residuals, threshold)
    at_or_below = bisect_right(residuals, threshold)
    under = below / n
    push = (at_or_below - below) / n
    over = 1.0 - at_or_below / n
    return over, under, push


class CornerModel:
    """A serialisable full-match corner predictor."""

    def __init__(
        self,
        trees: CornerTrees,
        *,
        feature_names=FEATURE_NAMES,
        metrics: dict | None = None,
        residuals: list[float] | None = None,
    ) -> None:
        self.trees = trees
        self.feature_names = tuple(feature_names)
        self.metrics = metrics or {}
        #: Sorted held-out residuals; calibrates over/under probabilities.
        self.residuals = sorted(float(r) for r in (residuals or []))

    def predict(self, feats: dict[str, float]) -> float:
        return max(self.trees.predict(vector(feats)), 0.1)

    @property
    def dispersion(self) -> float:
        return self.trees.dispersion

    def to_json(self) -> dict:
        return {
            "version": 1,
            "feature_names": list(self.feature_names),
            "base": self.trees.base,
            "learning_rate": self.trees.learning_rate,
            "dispersion": self.trees.dispersion,
            "metrics": self.metrics,
            "residuals": self.residuals,
            "trees": self.trees.trees,
        }

    @classmethod
    def from_json(cls, payload: dict) -> "CornerModel":
        trees = CornerTrees(learning_rate=payload.get("learning_rate", 0.06))
        trees.base = payload["base"]
        trees.dispersion = payload.get("dispersion", 0.0)
        trees.trees = payload["trees"]
        return cls(
            trees,
            feature_names=payload.get("feature_names", FEATURE_NAMES),
            metrics=payload.get("metrics"),
            residuals=payload.get("residuals"),
        )

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_json(), separators=(",", ":")), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "CornerModel":
        return cls.from_json(json.loads(Path(path).read_text(encoding="utf-8")))


def train_model(
    samples: list[tuple[dict[str, float], float]],
    **kwargs,
) -> CornerModel:
    x = [vector(feats) for feats, _y in samples]
    y = [float(label) for _feats, label in samples]
    trees = CornerTrees(**kwargs).fit(x, y)
    preds = [trees.predict(row) for row in x]
    mae = sum(abs(preds[i] - y[i]) for i in range(len(y))) / len(y)
    metrics = {"n": len(y), "mae": round(mae, 4)}
    residuals = [y[i] - preds[i] for i in range(len(y))]
    return CornerModel(trees, metrics=metrics, residuals=residuals)


# --------------------------------------------------------------------------- #
# Serving: pick the best side of the book's full-match corner line
# --------------------------------------------------------------------------- #


def _parse_ft_lines(fixture) -> list[tuple[float, dict]]:
    raw = getattr(fixture, "ft_corner_lines", None) or {}
    lines: list[tuple[float, dict]] = []
    for key, prices in raw.items():
        try:
            line = float(key)
        except (TypeError, ValueError):
            continue
        if isinstance(prices, dict) and prices:
            lines.append((line, prices))
    return lines


def ft_corner_leg(fixture, model: CornerModel, index, *, min_edge: float = FT_MIN_EDGE):
    """Best full-match corner side (Over or Under) across every quoted line."""
    from shared.treble_generator import CandidateLeg  # local import: avoid cycle
    from shared.time_buckets import local_day

    lines = _parse_ft_lines(fixture)
    if not lines:
        return None
    feats = build_features(
        index.for_league(fixture.league),
        home_key=team_key(fixture.home_team),
        away_key=team_key(fixture.away_team),
        today=local_day(fixture.kickoff_at),
        kickoff_day=local_day(fixture.kickoff_at),
    )
    if feats is None:
        return None
    mean = model.predict(feats)
    dispersion = model.dispersion

    best = None  # (ev, odds, probability, market)
    for line, prices in lines:
        if float(line).is_integer():
            continue  # a whole line can push; only .5 lines settle cleanly here
        probs = empirical_probabilities(model.residuals, mean, line)
        if probs is None:
            probs = side_probabilities(mean, dispersion, line)
        over_p, under_p, _push = probs
        for side, probability in (("Over", over_p), ("Under", under_p)):
            odds = prices.get(side.lower())
            if odds is None or odds < FT_MIN_ODDS or probability <= implied_probability(odds):
                continue
            push = max(0.0, 1.0 - over_p - under_p)
            # Pushes return the stake, so they neither win nor lose.
            ev = probability * (odds - 1.0) - (1.0 - probability - push)
            if ev < min_edge:
                continue
            if best is None or ev > best[0]:
                best = (ev, float(odds), probability, f"{side} {line:g} Corners")
    if best is None:
        return None
    _ev, odds, probability, market = best
    return CandidateLeg(
        fixture_id=fixture.id,
        odds=odds,
        model_probability=probability,
        kickoff_day=local_day(fixture.kickoff_at),
        market=market,
    )


def collect_ft_corner_legs(fixtures: list, history: list, model: CornerModel, index=None):
    """Every fixture where a full-match corner line carries a positive edge."""
    if index is None:
        index = _history_index(history)
    legs = []
    for fixture in fixtures:
        leg = ft_corner_leg(fixture, model, index)
        if leg is not None:
            legs.append(leg)
    return legs


def priced_ft_corner_leg(fixture):
    """Any quoted full-match .5 corner line, with no edge test. Diagnostics only."""
    from shared.time_buckets import local_day
    from shared.treble_generator import CandidateLeg

    best_line = None
    best_odds = 0.0
    best_side = "Over"
    for line, prices in _parse_ft_lines(fixture):
        if float(line).is_integer():
            continue
        for side in ("over", "under"):
            odds = prices.get(side)
            if odds and odds > best_odds:
                best_odds = float(odds)
                best_line = line
                best_side = side.capitalize()
    if best_line is None:
        return None
    return CandidateLeg(
        fixture_id=fixture.id,
        odds=best_odds,
        model_probability=0.0,
        kickoff_day=local_day(fixture.kickoff_at),
        market=f"{best_side} {best_line:g} Corners",
    )


def _history_index(history: list):
    from shared.team_strength import HistoryIndex

    return HistoryIndex(project_corner_history(history))


#: Trained artifact location. Absent in a fresh checkout; callers fall back to Poisson.
DEFAULT_MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "corner_gbdt.json"


def load_default_model(path: str | Path | None = None) -> CornerModel | None:
    target = Path(path) if path else DEFAULT_MODEL_PATH
    if not target.exists():
        return None
    try:
        return CornerModel.load(target)
    except Exception:  # a corrupt artifact must never take the API down
        return None


_CACHED: CornerModel | None = None
_CACHED_READY = False


def cached_model() -> CornerModel | None:
    """The trained artifact, parsed at most once per process."""
    global _CACHED, _CACHED_READY
    if not _CACHED_READY:
        _CACHED = load_default_model()
        _CACHED_READY = True
    return _CACHED


def reset_model_cache() -> None:
    global _CACHED, _CACHED_READY
    _CACHED = None
    _CACHED_READY = False
