from __future__ import annotations

import numpy as np
import pytest

from liftpilot.uplift import metrics
from liftpilot.uplift.calibration import UpliftCalibrator
from liftpilot.uplift.learners import LEARNERS, make_learner

FAST = {"n_estimators": 80, "min_child_samples": 50}


def test_qini_curve_endpoints_equal_total_incremental(synthetic_rct):
    d = synthetic_rct
    curve = metrics.qini_curve(d["y"], d["t"], d["tau"])
    t, y = d["t"], d["y"]
    expected = y[t == 1].sum() - y[t == 0].sum() * (t == 1).sum() / (t == 0).sum()
    assert curve.x[0] == 0 and curve.y[0] == 0
    assert curve.y[-1] == pytest.approx(expected)


def test_true_uplift_ranks_better_than_random_and_baseline(synthetic_rct):
    d = synthetic_rct
    rng = np.random.default_rng(0)
    q_true = metrics.qini_coefficient(d["y"], d["t"], d["tau"])
    q_rand = metrics.qini_coefficient(d["y"], d["t"], rng.random(len(d["y"])))
    q_base = metrics.qini_coefficient(d["y"], d["t"], d["base"])
    assert q_true > 0.05
    assert abs(q_rand) < 0.02
    assert q_true > q_base + 0.03


def test_qini_matches_scikit_uplift(synthetic_rct):
    sklift_metrics = pytest.importorskip("sklift.metrics")
    d = synthetic_rct
    score = d["tau"] + np.random.default_rng(1).normal(0, 0.05, len(d["tau"]))
    ours = metrics.qini_coefficient(d["y"], d["t"], score)
    theirs = sklift_metrics.qini_auc_score(d["y"], score, d["t"], negative_effect=True)
    assert ours == pytest.approx(theirs, abs=2e-3)


def test_uplift_at_k_recovers_planted_effect(synthetic_rct):
    d = synthetic_rct
    top = metrics.uplift_at_k(d["y"], d["t"], d["tau"], k=0.3)
    assert top == pytest.approx(0.15, abs=0.03)


def test_average_treatment_effect_reads_like_an_ab_test():
    # Course worked example: A 200/10,000 vs B 250/10,000 -> z = 2.38, p = 0.017
    y = np.r_[np.ones(200), np.zeros(9800), np.ones(250), np.zeros(9750)]
    t = np.r_[np.zeros(10000), np.ones(10000)]
    res = metrics.average_treatment_effect(y, t)
    assert res["ate"] == pytest.approx(0.005)
    assert res["relative_uplift"] == pytest.approx(0.25)
    assert res["z"] == pytest.approx(2.38, abs=0.02)
    assert res["p_value"] == pytest.approx(0.017, abs=0.002)


def test_metrics_reject_bad_input():
    with pytest.raises(ValueError, match="same length"):
        metrics.qini_curve([1, 0], [1, 0, 1], [0.1, 0.2])
    with pytest.raises(ValueError, match="both treated and control"):
        metrics.qini_curve([1, 0], [1, 1], [0.1, 0.2])
    with pytest.raises(ValueError, match="only 0 and 1"):
        metrics.qini_curve([1, 0], [2, 0], [0.1, 0.2])
    with pytest.raises(ValueError, match="NaN"):
        metrics.qini_curve([1, 0], [1, 0], [np.nan, 0.2])


@pytest.mark.parametrize("name", sorted(set(LEARNERS) - {"response"}))
def test_learners_find_the_persuadables(synthetic_rct, name):
    d = synthetic_rct
    X, t, y, tau = d["X"], d["t"], d["y"], d["tau"]
    cut = 16_000
    model = make_learner(name, seed=0, params=FAST).fit(X[:cut], t[:cut], y[:cut])
    pred = model.predict(X[cut:])
    assert pred.shape == (len(X) - cut,)
    assert np.isfinite(pred).all()
    assert np.corrcoef(pred, tau[cut:])[0, 1] > 0.5
    assert metrics.qini_coefficient(y[cut:], t[cut:], pred) > 0.04


def test_response_model_is_a_poor_uplift_ranker(synthetic_rct):
    d = synthetic_rct
    X, t, y = d["X"], d["t"], d["y"]
    cut = 16_000
    response = make_learner("response", params=FAST).fit(X[:cut], t[:cut], y[:cut]).predict(X[cut:])
    uplift = make_learner("t_learner", params=FAST).fit(X[:cut], t[:cut], y[:cut]).predict(X[cut:])
    q_resp = metrics.qini_coefficient(y[cut:], t[cut:], response)
    q_upl = metrics.qini_coefficient(y[cut:], t[cut:], uplift)
    assert q_upl > q_resp


def test_learner_rejects_single_arm(synthetic_rct):
    d = synthetic_rct
    with pytest.raises(ValueError, match="both 0 and 1"):
        make_learner("t_learner").fit(d["X"][:100], np.ones(100), d["y"][:100])
    with pytest.raises(KeyError):
        make_learner("nope")


def test_calibration_maps_scores_to_real_uplift(synthetic_rct):
    d = synthetic_rct
    # A score on an arbitrary scale (x10, shifted) that still orders correctly.
    score = 10 * d["tau"] + 3 + np.random.default_rng(2).normal(0, 0.2, len(d["tau"]))
    half = len(score) // 2
    cal = UpliftCalibrator(n_bins=20).fit(score[:half], d["t"][:half], d["y"][:half])
    assert cal.is_informative()
    pred = cal.predict(score[half:])
    assert np.all(np.diff(pred[np.argsort(score[half:])]) >= -1e-12)
    high = pred[d["tau"][half:] == 0.15].mean()
    low = pred[d["tau"][half:] == -0.08].mean()
    assert high == pytest.approx(0.15, abs=0.04)
    assert low == pytest.approx(-0.08, abs=0.05)
