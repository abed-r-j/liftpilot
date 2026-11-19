from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from liftpilot.policy.economics import (
    Economics,
    break_even_uplift,
    expected_spend,
    incremental_profit,
    realised_profit,
)
from liftpilot.policy.evaluation import evaluate_policy, profit_curve
from liftpilot.policy.optimizer import allocate, top_k


def test_break_even_roas_is_one_over_margin():
    assert Economics(margin=0.4).break_even_roas == pytest.approx(2.5)


def test_incremental_profit_hand_calculation():
    econ = Economics(margin=0.25, contact_cost=2.0, discount=0.05)
    # basket 800, uplift 4 points, 60% buy when contacted
    g = incremental_profit(econ, [800.0], [0.04], [0.60])
    assert g[0] == pytest.approx(0.25 * 800 * 0.04 - 0.05 * 800 * 0.60 - 2.0)
    s = expected_spend(econ, [800.0], [0.60])
    assert s[0] == pytest.approx(2.0 + 0.05 * 800 * 0.60)
    be = break_even_uplift(econ, [800.0], [0.60])
    assert be[0] == pytest.approx((2.0 + 24.0) / (0.25 * 800))
    # exactly at break-even the gain is zero
    assert incremental_profit(econ, [800.0], be, [0.60])[0] == pytest.approx(0.0, abs=1e-9)


def test_discount_must_stay_below_margin():
    with pytest.raises(ValidationError):
        Economics(margin=0.2, discount=0.25)


def test_realised_profit_charges_only_treated():
    econ = Economics(margin=0.3, contact_cost=1.0, discount=0.1)
    out = realised_profit(econ, [100.0, 100.0, 0.0], [1, 0, 1])
    assert out.tolist() == pytest.approx([0.2 * 100 - 1.0, 30.0, -1.0])


def test_allocate_never_selects_unprofitable_or_ineligible():
    econ = Economics(margin=0.25, contact_cost=2.0)
    value = np.full(6, 1000.0)
    uplift = np.array([0.05, 0.02, 0.008, 0.0, -0.03, 0.05])
    p1 = np.full(6, 0.5)
    eligible = np.array([True, True, True, True, True, False])
    plan = allocate(econ, value, uplift, p1, eligible=eligible)
    # gains: 10.5, 3, 0, -2, -9.5, (10.5 but not eligible)
    assert plan.selected.tolist() == [True, True, False, False, False, False]
    assert plan.expected_incremental_profit == pytest.approx(13.5)
    assert plan.expected_spend == pytest.approx(4.0)


def test_allocate_respects_budget_and_prefers_best_ratio():
    econ = Economics(margin=0.25, contact_cost=2.0)
    value = np.full(5, 1000.0)
    uplift = np.array([0.02, 0.05, 0.03, 0.04, 0.01])
    plan = allocate(econ, value, uplift, np.full(5, 0.5), budget=4.0)
    assert plan.selected.tolist() == [False, True, False, True, False]
    assert plan.expected_spend <= 4.0
    assert allocate(econ, value, uplift, np.full(5, 0.5), budget=0.0).n_selected == 0
    with pytest.raises(ValueError, match="negative"):
        allocate(econ, value, uplift, np.full(5, 0.5), budget=-1)


def test_greedy_allocation_matches_brute_force_on_small_cases():
    rng = np.random.default_rng(3)
    econ = Economics(margin=0.3, contact_cost=1.0, discount=0.05)
    for _ in range(20):
        n = 9
        value = rng.uniform(100, 900, n)
        uplift = rng.uniform(-0.02, 0.08, n)
        p1 = rng.uniform(0.2, 0.8, n)
        budget = float(rng.uniform(5, 60))
        plan = allocate(econ, value, uplift, p1, budget=budget)
        gain, spend = plan.gain, plan.spend
        best = 0.0
        for mask in range(1 << n):
            sel = np.array([(mask >> i) & 1 for i in range(n)], dtype=bool)
            if spend[sel].sum() <= budget:
                best = max(best, float(gain[sel].sum()))
        # greedy is optimal up to the single most valuable customer
        assert plan.expected_incremental_profit >= best - max(gain.max(), 0.0) - 1e-9
        assert plan.expected_incremental_profit <= best + 1e-9
        assert plan.expected_spend <= budget + 1e-9


def test_top_k_respects_eligibility():
    sel = top_k([0.9, 0.8, 0.7, 0.6], 2, eligible=[False, True, True, True])
    assert sel.tolist() == [False, True, True, False]


def test_policy_evaluation_recovers_known_effect():
    rng = np.random.default_rng(0)
    n = 40_000
    t = rng.integers(0, 2, n)
    persuadable = rng.random(n) < 0.3
    p = 0.2 + 0.10 * t * persuadable
    y = (rng.random(n) < p).astype(float)
    revenue = y * 500.0
    econ = Economics(margin=0.3, contact_cost=3.0)
    res = evaluate_policy("persuadables", econ, persuadable, t, y, revenue, n_boot=100)
    n_a = persuadable.sum()
    assert res.incremental_conversions == pytest.approx(0.10 * n_a, rel=0.2)
    assert res.spend == pytest.approx(3.0 * n_a)
    expected_profit = n_a * (0.3 * 500 * 0.10 - 3.0)
    assert res.profit_ci_low < expected_profit < res.profit_ci_high
    assert res.prob_profit_positive > 0.95

    others = evaluate_policy("others", econ, ~persuadable, t, y, revenue, n_boot=100)
    # no uplift there: contacting them just burns the message cost
    assert others.incremental_profit < 0
    nobody = evaluate_policy("nobody", econ, np.zeros(n, bool), t, y, revenue, n_boot=10)
    assert nobody.incremental_profit == 0 and nobody.spend == 0


def test_profit_curve_starts_at_zero_and_ends_at_treat_all():
    rng = np.random.default_rng(1)
    n = 5_000
    t = rng.integers(0, 2, n)
    y = (rng.random(n) < 0.3 + 0.05 * t).astype(float)
    revenue = y * 200.0
    econ = Economics(margin=0.3, contact_cost=1.0)
    curve = profit_curve(econ, rng.random(n), t, y, revenue)
    everyone = evaluate_policy("all", econ, np.ones(n, bool), t, y, revenue, n_boot=0)
    assert curve["incremental_profit"][0] == 0
    assert curve["incremental_profit"][-1] == pytest.approx(everyone.incremental_profit)
