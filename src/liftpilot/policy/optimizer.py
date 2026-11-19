"""Decide who to contact: maximise expected incremental profit under a budget.

The problem is a knapsack:

    maximise   sum_i x_i g_i
    subject to sum_i x_i s_i <= B,   x_i in {0, 1}

with ``g_i`` the expected incremental profit and ``s_i`` the expected spend of
contacting customer ``i``. Because each customer is tiny relative to the
budget, the greedy rule "highest profit per unit of spend first, stop at zero
profit or when the money runs out" is optimal up to one customer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from liftpilot.policy.economics import Economics, expected_spend, incremental_profit

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


@dataclass(frozen=True)
class Plan:
    """Result of an allocation over a customer base."""

    selected: BoolArray
    gain: FloatArray  # expected incremental profit per customer if contacted
    spend: FloatArray  # expected spend per customer if contacted
    budget: float | None
    eligible: BoolArray

    @property
    def n_selected(self) -> int:
        return int(self.selected.sum())

    @property
    def expected_incremental_profit(self) -> float:
        return float(self.gain[self.selected].sum())

    @property
    def expected_spend(self) -> float:
        return float(self.spend[self.selected].sum())

    @property
    def budget_left(self) -> float | None:
        return None if self.budget is None else float(self.budget - self.expected_spend)

    def summary(self) -> dict[str, float | int | None]:
        spend = self.expected_spend
        return {
            "customers_total": len(self.selected),
            "customers_eligible": int(self.eligible.sum()),
            "customers_selected": self.n_selected,
            "share_selected": self.n_selected / max(len(self.selected), 1),
            "expected_spend": spend,
            "expected_incremental_profit": self.expected_incremental_profit,
            "expected_incremental_roi": (
                self.expected_incremental_profit / spend if spend > 0 else None
            ),
            "budget": self.budget,
            "budget_left": self.budget_left,
        }


def allocate(
    econ: Economics,
    value: Any,
    uplift: Any,
    p1: Any,
    budget: float | None = None,
    eligible: Any | None = None,
    min_gain: float = 0.0,
) -> Plan:
    """Select customers to contact.

    Parameters
    ----------
    budget:
        Maximum expected spend. ``None`` means "contact everyone who is
        expected to be profitable".
    eligible:
        Boolean mask of customers the campaign is allowed to contact (consent,
        frequency caps, suppression lists). Ineligible customers are never
        selected, whatever their uplift.
    min_gain:
        Safety margin: contact only if expected incremental profit exceeds it.
    """
    gain = incremental_profit(econ, value, uplift, p1)
    spend = expected_spend(econ, value, p1)
    n = len(gain)
    ok = np.ones(n, dtype=bool) if eligible is None else np.asarray(eligible, dtype=bool).ravel()
    if len(ok) != n:
        raise ValueError("eligible mask has the wrong length")
    if budget is not None and budget < 0:
        raise ValueError("budget cannot be negative")

    candidates = np.flatnonzero(ok & (gain > min_gain))
    selected = np.zeros(n, dtype=bool)
    if len(candidates) == 0:
        return Plan(selected, gain, spend, budget, ok)

    if budget is None:
        selected[candidates] = True
        return Plan(selected, gain, spend, budget, ok)

    ratio = gain[candidates] / np.maximum(spend[candidates], 1e-12)
    order = candidates[np.argsort(-ratio, kind="stable")]
    cumulative = np.cumsum(spend[order])
    n_fit = int(np.searchsorted(cumulative, budget, side="right"))
    selected[order[:n_fit]] = True
    return Plan(selected, gain, spend, budget, ok)


def top_k(score: Any, k: int, eligible: Any | None = None) -> BoolArray:
    """Baseline rule: contact the ``k`` best customers by any score."""
    s = np.asarray(score, dtype=np.float64).ravel()
    ok = np.ones(len(s), dtype=bool) if eligible is None else np.asarray(eligible, dtype=bool)
    order = np.argsort(-np.where(ok, s, -np.inf), kind="stable")
    selected = np.zeros(len(s), dtype=bool)
    selected[order[: min(k, int(ok.sum()))]] = True
    return selected
