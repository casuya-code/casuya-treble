import math
from datetime import datetime, timezone
from uuid import uuid4

from shared.corner_model import (
    FEATURE_NAMES,
    CornerModel,
    CornerTrees,
    build_features,
    ft_corner_leg,
    pmf,
    priced_ft_corner_leg,
    side_probabilities,
    train_model,
)
from shared.corners import project_corner_history
from shared.models import Fixture
from shared.poisson import poisson_pmf
from shared.team_strength import HistoryIndex


def _feats(**values) -> dict[str, float]:
    base = {name: 0.0 for name in FEATURE_NAMES}
    base["expected_total"] = 10.0
    base.update(values)
    return base


def _row(home, away, hc, ac, day) -> Fixture:
    return Fixture(
        id=uuid4(),
        home_team=home,
        away_team=away,
        league="England / Premier League",
        kickoff_at=datetime(2026, 8, day, 15, 0, tzinfo=timezone.utc),
        home_corners=hc,
        away_corners=ac,
    )


def _history(days=14):
    rows = []
    for day in range(1, days + 1):
        rows.append(_row("Hosts", "Filler", 8, 2, day))
        rows.append(_row("Marker", "Guests", 3, 7, day))
    return rows


def test_probabilities_partition_the_outcome_space():
    over, under, push = side_probabilities(9.0, 0.0, 9.5)
    assert push == 0.0
    assert math.isclose(over + under, 1.0, rel_tol=1e-6)
    assert over > 0.4  # a mean of 9 against 9.5 is close to a coin flip

    over, under, push = side_probabilities(10.0, 0.0, 10.0)
    assert math.isclose(over + under + push, 1.0, rel_tol=1e-6)
    assert push > 0.0  # a whole line can push


def test_poisson_fallback_matches_the_shared_pmf():
    for k in range(0, 12):
        assert math.isclose(pmf(k, 8.5, 0.0), poisson_pmf(k, 8.5), rel_tol=1e-9)


def test_overdispersion_widens_the_tails():
    _o0, _u0, push0 = side_probabilities(10.0, 0.0, 10.0)
    _o1, _u1, push1 = side_probabilities(10.0, 6.0, 10.0)
    assert push1 < push0  # negative binomial spreads mass away from the mean


def test_features_need_a_full_history():
    thin = [_row("Hosts", "Guests", 6, 4, day) for day in range(1, 5)]
    assert (
        build_features(
            project_corner_history(thin),
            home_key="hosts",
            away_key="guests",
            today=datetime(2026, 8, 20, tzinfo=timezone.utc).date(),
            kickoff_day=datetime(2026, 8, 20, tzinfo=timezone.utc).date(),
        )
        is None
    )


def test_features_are_produced_from_a_healthy_history():
    rows = project_corner_history(_history())
    feats = build_features(
        rows,
        home_key="hosts",
        away_key="guests",
        today=datetime(2026, 8, 20, tzinfo=timezone.utc).date(),
        kickoff_day=datetime(2026, 8, 20, tzinfo=timezone.utc).date(),
    )
    assert feats is not None
    assert feats["expected_total"] > 8  # Hosts are a high-corner home side
    assert feats["home_games"] == 10 and feats["away_games"] == 10
    assert feats["rest_home"] > 0


def test_footystats_style_form_and_over95_features():
    # Every fixture here finishes on 10 corners, so the five-match form (FootyStats/
    # APWin) and the over-9.5 rates are all pinned and measurable.
    rows = project_corner_history(_history())
    feats = build_features(
        rows,
        home_key="hosts",
        away_key="guests",
        today=datetime(2026, 8, 20, tzinfo=timezone.utc).date(),
        kickoff_day=datetime(2026, 8, 20, tzinfo=timezone.utc).date(),
    )
    assert feats is not None
    assert feats["home_form5"] == 10.0 and feats["away_form5"] == 10.0
    assert feats["home_over95_rate"] == 1.0 and feats["away_over95_rate"] == 1.0
    assert feats["league_over95_rate"] == 1.0


def test_the_booster_learns_a_linear_signal():
    samples = []
    for i in range(240):
        expected = 6.0 + (i % 80) * 0.1
        label = 0.5 * expected + 4.0
        samples.append((_feats(expected_total=expected, league_total=expected), label))
    model = train_model(
        samples,
        n_estimators=80,
        learning_rate=0.1,
        max_depth=3,
        min_leaf=8,
        subsample=1.0,
        max_features=4,
        random_state=1,
    )
    assert model.metrics["mae"] < 0.8
    assert abs(model.predict(_feats(expected_total=12.0, league_total=12.0)) - 10.0) < 1.0


def test_model_round_trips_through_json(tmp_path):
    samples = [(_feats(expected_total=e), 0.5 * e + 4.0) for e in (6.0, 8.0, 10.0, 12.0, 14.0)] * 20
    model = train_model(samples, n_estimators=20, max_depth=2, min_leaf=4, subsample=1.0, max_features=4)
    path = tmp_path / "m.json"
    model.save(path)
    reloaded = CornerModel.load(path)
    assert reloaded.predict(_feats(expected_total=11.0)) == model.predict(_feats(expected_total=11.0))


def _constant_model(mean: float) -> CornerModel:
    trees = CornerTrees()
    trees.base = mean
    trees.trees = []
    trees.dispersion = 0.0
    return CornerModel(trees)


def _upcoming(**kw) -> Fixture:
    fixture = _row("Hosts", "Guests", None, None, 1)
    fixture.home_corners = None
    fixture.away_corners = None
    fixture.ft_corner_lines = kw.pop("ft_corner_lines", None)
    for key, value in kw.items():
        setattr(fixture, key, value)
    return fixture


def test_a_low_expected_total_tips_the_under_side():
    history = _history()
    index = HistoryIndex(project_corner_history(history))
    fixture = _upcoming(ft_corner_lines={"9.5": {"over": 1.94, "under": 1.66}})
    leg = ft_corner_leg(fixture, _constant_model(8.0), index)
    assert leg is not None
    assert leg.market == "Under 9.5 Corners"
    assert leg.odds == 1.66


def test_a_high_expected_total_tips_the_over_side():
    history = _history()
    index = HistoryIndex(project_corner_history(history))
    fixture = _upcoming(ft_corner_lines={"9.5": {"over": 1.94, "under": 1.66}})
    leg = ft_corner_leg(fixture, _constant_model(13.0), index)
    assert leg is not None
    assert leg.market == "Over 9.5 Corners"
    assert leg.odds == 1.94


def test_no_price_means_no_leg():
    history = _history()
    index = HistoryIndex(project_corner_history(history))
    fixture = _upcoming(ft_corner_lines={})
    assert ft_corner_leg(fixture, _constant_model(8.0), index) is None


def test_whole_lines_are_skipped_because_they_can_push():
    history = _history()
    index = HistoryIndex(project_corner_history(history))
    fixture = _upcoming(ft_corner_lines={"10.0": {"over": 2.0, "under": 1.9}})
    assert ft_corner_leg(fixture, _constant_model(8.0), index) is None


def test_priced_leg_reads_a_half_line():
    fixture = _upcoming(ft_corner_lines={"9.5": {"over": 1.94, "under": 1.66}, "10.0": {"over": 2.9, "under": 1.3}})
    leg = priced_ft_corner_leg(fixture)
    assert leg is not None
    assert leg.market == "Over 9.5 Corners"
    assert leg.odds == 1.94
