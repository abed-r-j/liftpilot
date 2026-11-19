"""Off-policy evaluation: what would a targeting rule have earned for real?

The test customers were contacted at random, so for ANY rule "contact the
customers in set A" we can read its real effect from the experiment without
running it: inside A, the randomly contacted customers show what happens when
we contact, and the randomly held-out customers show what happens when we do
not. With ``r`` the realised profit of each customer:

    incremental profit of A  =  |A| * ( mean r of treated in A  -  mean r of control in A )

This is the Hajek (self-normalised inverse-propensity) estimator of the policy
value difference against "contact nobody". Uncertainty comes from a bootstrap
that resamples customers within each experimental arm.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from liftpilot.policy.economics import Economics, realised_profit

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class PolicyValue:
    name: str
    n_customers: int
    n_selected: int
    share_selected: float
    incremental_conversions: float
    incremental_revenue: float
    spend: float
    incremental_profit: float
    profit_ci_low: float
    profit_ci_high: float
    prob_profit_positive: float
    incremental_roas: float | None
    incremental_roi: float | None
    cost_per_incremental_conversion: float | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _diff_in_means(values: FloatArray, t: FloatArray) -> float:
    n_t = t.sum()
    n_c = len(t) - n_t
    if n_t == 0 or n_c == 0:
        return 0.0
    return float(values[t == 1].mean() - values[t == 0].mean())


def _components(
    econ: Economics, sel: NDArray[np.bool_], t: FloatArray, y: FloatArray, revenue: FloatArray
) -> tuple[float, float, float, float]:
    """(incremental conversions, incremental revenue, spend, incremental profit) for set A."""
    n_a = int(sel.sum())
    if n_a == 0:
        return 0.0, 0.0, 0.0, 0.0
    t_a, y_a, rev_a = t[sel], y[sel], revenue[sel]
    inc_conv = n_a * _diff_in_means(y_a, t_a)
    inc_rev = n_a * _diff_in_means(rev_a, t_a)
    treated = t_a == 1
    mean_treated_rev = float(rev_a[treated].mean()) if treated.any() else 0.0
    spend = n_a * (econ.contact_cost + econ.discount * mean_treated_rev)
    profit = realised_profit(econ, rev_a, t_a)
    inc_profit = n_a * _diff_in_means(profit, t_a)
    return inc_conv, inc_rev, spend, inc_profit


def evaluate_policy(
    name: str,
    econ: Economics,
    selected: Any,
    t: Any,
    y: Any,
    revenue: Any,
    scale: float = 1.0,
    n_boot: int = 300,
    seed: int = 0,
) -> PolicyValue:
    """Real incremental result of contacting ``selected`` customers.

    ``scale`` multiplies all totals, e.g. (customer base size / test size) to
    express results at the size of the whole customer base.
    """
    sel = np.asarray(selected, dtype=bool).ravel()
    t_arr = np.asarray(t, dtype=np.float64).ravel()
    y_arr = np.asarray(y, dtype=np.float64).ravel()
    rev = np.asarray(revenue, dtype=np.float64).ravel()
    if not (len(sel) == len(t_arr) == len(y_arr) == len(rev)):
        raise ValueError("inputs must have the same length")

    inc_conv, inc_rev, spend, inc_profit = _components(econ, sel, t_arr, y_arr, rev)

    rng = np.random.default_rng(seed)
    idx_t = np.flatnonzero(t_arr == 1)
    idx_c = np.flatnonzero(t_arr == 0)
    draws = np.empty(n_boot)
    for b in range(n_boot):
        idx = np.concatenate(
            [
                rng.choice(idx_t, len(idx_t), replace=True),
                rng.choice(idx_c, len(idx_c), replace=True),
            ]
        )
        draws[b] = _components(econ, sel[idx], t_arr[idx], y_arr[idx], rev[idx])[3]
    low, high = np.percentile(draws, [2.5, 97.5]) if n_boot > 0 else (np.nan, np.nan)

    n_sel = int(sel.sum())
    return PolicyValue(
        name=name,
        n_customers=len(sel),
        n_selected=n_sel,
        share_selected=n_sel / len(sel),
        incremental_conversions=inc_conv * scale,
        incremental_revenue=inc_rev * scale,
        spend=spend * scale,
        incremental_profit=inc_profit * scale,
        profit_ci_low=float(low) * scale,
        profit_ci_high=float(high) * scale,
        prob_profit_positive=float((draws > 0).mean()) if n_boot > 0 else float("nan"),
        incremental_roas=inc_rev / spend if spend > 0 else None,
        incremental_roi=inc_profit / spend if spend > 0 else None,
        cost_per_incremental_conversion=spend / inc_conv if inc_conv > 0 else None,
    )


def compare_policies(
    econ: Economics,
    selected_a: Any,
    selected_b: Any,
    t: Any,
    y: Any,
    revenue: Any,
    scale: float = 1.0,
    n_boot: int = 300,
    seed: int = 0,
) -> dict[str, float]:
    """Incremental profit of rule A minus rule B, with a paired bootstrap.

    Both rules are evaluated on the same resampled customers, so the interval
    describes the difference itself and not two unrelated uncertainties.
    """
    a = np.asarray(selected_a, dtype=bool).ravel()
    b = np.asarray(selected_b, dtype=bool).ravel()
    t_arr = np.asarray(t, dtype=np.float64).ravel()
    y_arr = np.asarray(y, dtype=np.float64).ravel()
    rev = np.asarray(revenue, dtype=np.float64).ravel()

    def diff(idx: Any) -> float:
        pa = _components(econ, a[idx], t_arr[idx], y_arr[idx], rev[idx])[3]
        pb = _components(econ, b[idx], t_arr[idx], y_arr[idx], rev[idx])[3]
        return pa - pb

    point = diff(slice(None))
    rng = np.random.default_rng(seed)
    idx_t = np.flatnonzero(t_arr == 1)
    idx_c = np.flatnonzero(t_arr == 0)
    draws = np.empty(n_boot)
    for i in range(n_boot):
        idx = np.concatenate(
            [
                rng.choice(idx_t, len(idx_t), replace=True),
                rng.choice(idx_c, len(idx_c), replace=True),
            ]
        )
        draws[i] = diff(idx)
    low, high = np.percentile(draws, [2.5, 97.5])
    return {
        "difference": point * scale,
        "ci_low": float(low) * scale,
        "ci_high": float(high) * scale,
        "prob_a_better": float((draws > 0).mean()),
    }


def profit_curve(
    econ: Economics,
    score: Any,
    t: Any,
    y: Any,
    revenue: Any,
    fractions: Any | None = None,
    scale: float = 1.0,
) -> dict[str, FloatArray]:
    """Real incremental profit when contacting the top share of a ranking."""
    s = np.asarray(score, dtype=np.float64).ravel()
    t_arr = np.asarray(t, dtype=np.float64).ravel()
    y_arr = np.asarray(y, dtype=np.float64).ravel()
    rev = np.asarray(revenue, dtype=np.float64).ravel()
    fr = np.linspace(0.0, 1.0, 21) if fractions is None else np.asarray(fractions, dtype=float)
    order = np.argsort(-s, kind="stable")
    n = len(s)
    out: dict[str, list[float]] = {
        "fraction": [],
        "incremental_profit": [],
        "incremental_conversions": [],
        "spend": [],
    }
    for f in fr:
        sel = np.zeros(n, dtype=bool)
        sel[order[: round(f * n)]] = True
        inc_conv, _, spend, inc_profit = _components(econ, sel, t_arr, y_arr, rev)
        out["fraction"].append(float(f))
        out["incremental_profit"].append(inc_profit * scale)
        out["incremental_conversions"].append(inc_conv * scale)
        out["spend"].append(spend * scale)
    return {k: np.asarray(v) for k, v in out.items()}
