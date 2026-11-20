"""CampaignEngine: every number the agent or the dashboard shows comes from here.

The engine loads the scored customer table produced by ``liftpilot train`` and
answers questions with plain dictionaries:

* facts        - ``data_profile``, ``experiment_readout``, ``rfm_segments``, ``model_report``
* decisions    - ``plan`` (who to contact under given money assumptions)
* evidence     - ``evaluate`` (what that rule really earned in the held-out experiment)
* safeguards   - ``fairness``, ``design_holdout``, eligibility rules
* action       - ``export`` (writes the audience file; needs a human approval)

The language model never does arithmetic: it calls these methods.
"""

from __future__ import annotations

import hashlib
import json
import math
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from liftpilot import config, fairness
from liftpilot.policy.economics import (
    Economics,
    break_even_uplift,
    expected_spend,
    incremental_profit,
)
from liftpilot.policy.evaluation import evaluate_policy
from liftpilot.policy.optimizer import Plan, allocate
from liftpilot.uplift import metrics

ADULT_AGE = 18


def _r(x: Any, digits: int = 4) -> Any:
    """Round floats so tool outputs stay short and comparable."""
    if x is None:
        return None
    if isinstance(x, (float, np.floating)):
        if math.isnan(x) or math.isinf(x):
            return None
        return round(float(x), digits)
    if isinstance(x, (int, np.integer)):
        return int(x)
    return x


@dataclass
class StoredPlan:
    plan_id: str
    economics: Economics
    budget: float | None
    audience: str
    index: pd.Index
    plan: Plan
    rules: dict[str, Any]
    created: str
    summary: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] | None = None
    messages: dict[str, str] = field(default_factory=dict)


class ApprovalRequired(Exception):
    """Raised when an action is attempted without a valid human approval."""


class CampaignEngine:
    def __init__(self, dataset: str = "x5", artifacts: Path | None = None) -> None:
        self.dataset = dataset
        self.dir = artifacts or config.artifacts_dir(dataset)
        if not (self.dir / "customers.parquet").exists():
            raise FileNotFoundError(
                f"no trained artifacts in {self.dir}; run `liftpilot train {dataset}` first"
            )
        self.customers = pd.read_parquet(self.dir / "customers.parquet")
        self.report = json.loads((self.dir / "report.json").read_text())
        self.curves = json.loads((self.dir / "curves.json").read_text())
        self.currency: str = self.report["economics"]["currency"]
        self.default_economics = Economics(**self.report["economics"])
        self.plans: dict[str, StoredPlan] = {}
        self._approvals: dict[str, dict[str, Any]] = {}
        self.suppression: set[str] = set()
        path = config.root() / "data" / "suppression_list.txt"
        if path.exists():
            self.suppression = {s.strip() for s in path.read_text().splitlines() if s.strip()}

    # ------------------------------------------------------------------ facts
    def data_profile(self) -> dict[str, Any]:
        d = self.report["dataset"]
        c = self.customers
        return {
            "dataset": d["name"],
            "description": d["description"],
            "currency": self.currency,
            "customers_total": len(c),
            "customers_in_past_experiment": int((c["split"] != "new").sum()),
            "customers_never_tested": int((c["split"] == "new").sum()),
            "history_window": [d.get("history_start"), d.get("reference_date")],
            "features_used_by_model": d["n_features"],
            "sensitive_attributes_excluded_from_model": ["age", "gender"]
            if "gender" in c.columns
            else [],
            "average_basket": _r(float(c["value"].mean()), 2),
            "revenue_is_observed": d["revenue_observed"],
            "note": None
            if d["revenue_observed"]
            else (
                "The public data record whether a purchase happened, not its amount. "
                "Money figures value each purchase at the customer's own average basket."
            ),
        }

    def experiment_readout(self) -> dict[str, Any]:
        ro = self.report["experiment_readout"]
        return {
            "what": "Past randomised test: contacted vs not contacted",
            "customers_contacted": int(ro["n_treated"]),
            "customers_held_out": int(ro["n_control"]),
            "purchase_rate_contacted": _r(ro["rate_treated"]),
            "purchase_rate_held_out": _r(ro["rate_control"]),
            "uplift_points": _r(ro["ate"]),
            "relative_uplift": _r(ro["relative_uplift"]),
            "confidence_interval_95": [_r(ro["ci_low"]), _r(ro["ci_high"])],
            "p_value": _r(ro["p_value"], 6),
            "significant_at_5_percent": bool(ro["p_value"] < 0.05),
        }

    def rfm_segments(self) -> list[dict[str, Any]]:
        rows = []
        for seg, r in self.report.get("rfm_segments", {}).items():
            rows.append(
                {
                    "segment": seg,
                    "customers": r["customers"],
                    "share": _r(r["share"]),
                    "avg_recency_days": _r(r["recency_days"], 1),
                    "avg_purchases": _r(r["frequency"], 1),
                    "avg_spend": _r(r["monetary"], 0),
                    "avg_basket": _r(r["avg_basket"], 0),
                    "purchase_rate_without_contact": _r(r["conversion_control"]),
                    "measured_uplift_points": _r(r["observed_uplift"]),
                    "uplift_ci_95": [_r(r["uplift_ci_low"]), _r(r["uplift_ci_high"])],
                    "share_worth_contacting_at_default_costs": _r(r["share_selected"]),
                }
            )
        return rows

    def model_report(self) -> dict[str, Any]:
        champion = self.report["champion"]
        learners = {
            name: {
                "qini_test": _r(row["qini_test"]["value"]),
                "qini_ci_95": [_r(row["qini_test"]["ci_low"]), _r(row["qini_test"]["ci_high"])],
                "uplift_top_10_percent": _r(row["uplift_at_10"]),
                "uplift_top_30_percent": _r(row["uplift_at_30"]),
                "uplift_bottom_30_percent": _r(row["uplift_bottom_30"]),
            }
            for name, row in self.report["learners"].items()
        }
        return {
            "champion": champion,
            "selection_rule": "highest Qini on the calibration part; test part untouched",
            "learners": learners,
            "decision_groups_at_default_costs": {
                k: {
                    "share": _r(v["share"]),
                    "real_uplift_on_unseen_customers": _r(v.get("test_uplift")),
                    "purchase_rate_without_contact": _r(v.get("test_rate_control")),
                }
                for k, v in self.report["types"].items()
            },
            "top_features": {
                k: _r(v, 3) for k, v in list(self.report.get("feature_importance", {}).items())[:8]
            },
        }

    def baseline_policies(self) -> list[dict[str, Any]]:
        """Real result of standard targeting rules at the default money assumptions."""
        return [
            {
                "policy": name,
                "share_contacted": _r(p["share_selected"]),
                "spend": _r(p["spend"], 0),
                "incremental_purchases": _r(p["incremental_conversions"], 0),
                "incremental_profit": _r(p["incremental_profit"], 0),
                "profit_ci_95": [_r(p["profit_ci_low"], 0), _r(p["profit_ci_high"], 0)],
                "incremental_roas": _r(p["incremental_roas"], 2),
            }
            for name, p in self.report["policies"].items()
        ]

    # ------------------------------------------------------------- decisions
    def _audience(self, audience: str) -> pd.DataFrame:
        c = self.customers
        if audience == "next":
            part = c[c["split"] == "new"]
            return part if len(part) else c
        if audience == "test":
            return c[c["split"] == "test"]
        if audience == "all":
            return c
        raise ValueError("audience must be 'next', 'test' or 'all'")

    def _value(self, part: pd.DataFrame, equal_value: bool) -> pd.Series:
        """Basket value used for the DECISION (realised profit always uses real baskets)."""
        if not equal_value:
            return part["value"]
        return pd.Series(float(self.customers["value"].mean()), index=part.index)

    def _select(
        self,
        econ: Economics,
        part: pd.DataFrame,
        budget: float | None,
        eligible: np.ndarray,
        min_gain: float,
        equal_value: bool,
    ) -> Plan:
        """Allocate; in fair mode make sure the budget holds for REAL expected spend."""
        plan = allocate(
            econ,
            self._value(part, equal_value),
            part["uplift"],
            part["p1"],
            budget=budget,
            eligible=eligible,
            min_gain=min_gain,
        )
        if not equal_value or budget is None or not plan.selected.any():
            return plan
        real_spend = expected_spend(econ, part["value"], part["p1"])
        chosen = np.flatnonzero(plan.selected)
        order = chosen[np.argsort(-plan.gain[chosen], kind="stable")]
        keep = order[np.cumsum(real_spend[order]) <= budget]
        selected = np.zeros(len(part), dtype=bool)
        selected[keep] = True
        return Plan(selected, plan.gain, real_spend, budget, plan.eligible)

    def _eligible(
        self, part: pd.DataFrame, rules: dict[str, Any]
    ) -> tuple[np.ndarray, dict[str, int]]:
        ok = np.ones(len(part), dtype=bool)
        removed: dict[str, int] = {}

        def apply(name: str, mask: np.ndarray) -> None:
            nonlocal ok
            removed[name] = int((ok & ~mask).sum())
            ok &= mask

        apply("opted_out", ~part.index.isin(list(self.suppression)))
        if "age" in part.columns or "age_band" in part.columns:
            minors = (
                (part["age"] < ADULT_AGE).to_numpy()
                if "age" in part.columns
                else np.zeros(len(part), dtype=bool)
            )
            apply("under_18", ~minors)
        if rules.get("exclude_no_effect", True):
            apply("no_expected_effect", (part["uplift"] > 0).to_numpy())
        segments = rules.get("segments")
        if segments and "rfm_segment" in part.columns:
            apply("outside_chosen_segments", part["rfm_segment"].isin(segments).to_numpy())
        return ok, removed

    def plan(
        self,
        margin: float | None = None,
        contact_cost: float | None = None,
        discount: float | None = None,
        budget: float | None = None,
        audience: str = "next",
        segments: list[str] | None = None,
        exclude_no_effect: bool = True,
        safety_margin: float = 0.0,
        equal_value: bool = False,
    ) -> dict[str, Any]:
        """Choose who to contact to maximise expected incremental profit.

        ``equal_value=True`` is the fair mode: every customer is valued at the
        average basket, so a small spender is not passed over just for spending
        less. The decision then depends on the estimated effect only.
        """
        base = self.default_economics
        econ = Economics(
            margin=base.margin if margin is None else margin,
            contact_cost=base.contact_cost if contact_cost is None else contact_cost,
            discount=base.discount if discount is None else discount,
            currency=self.currency,
        )
        part = self._audience(audience)
        if segments:
            known = set(part["rfm_segment"].unique()) if "rfm_segment" in part.columns else set()
            unknown = [s for s in segments if s not in known]
            if unknown:
                raise ValueError(
                    f"unknown segment(s) {unknown}. A campaign can only be restricted to RFM "
                    f"segments: {sorted(known)}. Targeting by age, gender or any other personal "
                    "attribute is not available in this system."
                )
        rules = {
            "exclude_no_effect": exclude_no_effect,
            "segments": segments,
            "safety_margin": safety_margin,
            "equal_value": equal_value,
        }
        eligible, removed = self._eligible(part, rules)
        plan = self._select(econ, part, budget, eligible, safety_margin, equal_value)
        plan_id = (
            "plan-"
            + hashlib.sha1(  # noqa: S324 - identifier, not security
                json.dumps(
                    [econ.model_dump(), budget, audience, rules, len(self.plans)], sort_keys=True
                ).encode()
            ).hexdigest()[:8]
        )
        stored = StoredPlan(
            plan_id=plan_id,
            economics=econ,
            budget=budget,
            audience=audience,
            index=part.index,
            plan=plan,
            rules={**rules, "removed_by_rule": removed},
            created=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        sel = part[plan.selected]
        s = plan.summary()
        if equal_value:
            # report money with real baskets, even though the decision ignored them
            s["expected_incremental_profit"] = float(
                incremental_profit(econ, sel["value"], sel["uplift"], sel["p1"]).sum()
            )
            s["expected_spend"] = float(expected_spend(econ, sel["value"], sel["p1"]).sum())
            s["budget_left"] = None if budget is None else budget - s["expected_spend"]
        inc_rev = float((sel["value"] * sel["uplift"]).sum())
        summary: dict[str, Any] = {
            "plan_id": plan_id,
            "audience": audience,
            "currency": self.currency,
            "assumptions": {
                "gross_margin": econ.margin,
                "cost_per_message": econ.contact_cost,
                "discount_share_of_basket": econ.discount,
                "budget": budget,
                "break_even_roas": _r(econ.break_even_roas, 2),
            },
            "decision_mode": (
                "fair mode: every customer valued at the average basket"
                if equal_value
                else "profit mode: each customer valued at their own average basket"
            ),
            "customers_in_audience": len(part),
            "customers_eligible": int(eligible.sum()),
            "removed_by_rule": removed,
            "customers_to_contact": plan.n_selected,
            "share_contacted": _r(plan.n_selected / max(len(part), 1)),
            "customers_not_contacted": len(part) - plan.n_selected,
            "expected_spend": _r(s["expected_spend"], 0),
            "budget_left": _r(s["budget_left"], 0),
            "expected_incremental_purchases": _r(float(sel["uplift"].sum()), 0),
            "expected_incremental_revenue": _r(inc_rev, 0),
            "expected_incremental_profit": _r(s["expected_incremental_profit"], 0),
            "expected_incremental_roas": _r(inc_rev / s["expected_spend"], 2)
            if s["expected_spend"]
            else None,
            "mean_uplift_of_contacted": _r(float(sel["uplift"].mean())) if len(sel) else None,
            "mean_break_even_uplift": _r(
                float(break_even_uplift(econ, part["value"], part["p1"]).mean())
            ),
            "spend_if_everyone_contacted": _r(
                len(part) * econ.contact_cost
                + econ.discount * float((part["value"] * part["p1"]).sum()),
                0,
            ),
            "expected_profit_if_everyone_contacted": _r(
                float(incremental_profit(econ, part["value"], part["uplift"], part["p1"]).sum()), 0
            ),
        }
        if "rfm_segment" in part.columns:
            by = part.assign(_sel=plan.selected).groupby("rfm_segment", observed=True)["_sel"]
            summary["contacted_by_rfm_segment"] = {
                str(k): {"contacted": int(v.sum()), "share_of_segment": _r(float(v.mean()))}
                for k, v in by
            }
        stored.summary = summary
        self.plans[plan_id] = stored
        return summary

    def _get(self, plan_id: str) -> StoredPlan:
        if plan_id not in self.plans:
            raise KeyError(f"unknown plan_id '{plan_id}'; create one with plan() first")
        return self.plans[plan_id]

    # --------------------------------------------------------------- evidence
    def evaluate(self, plan_id: str, n_boot: int = 300) -> dict[str, Any]:
        """Replay the plan's rule on the held-out randomised test customers.

        The same rule (same money assumptions, same eligibility) is applied to
        customers the model never saw, whose contact was decided by coin flip.
        Their real behaviour gives the real incremental result per customer,
        which is then scaled to the size of the plan's audience.
        """
        sp = self._get(plan_id)
        test = self._audience("test")
        eligible, _ = self._eligible(test, sp.rules)
        ratio_budget = None
        if sp.budget is not None:
            ratio_budget = sp.budget * len(test) / max(len(sp.index), 1)
        plan = self._select(
            sp.economics,
            test,
            ratio_budget,
            eligible,
            float(sp.rules.get("safety_margin", 0.0)),
            bool(sp.rules.get("equal_value")),
        )
        scale = len(sp.index) / len(test)
        t, y, rev = test["t"].to_numpy(), test["y"].to_numpy(), test["revenue"].to_numpy()
        res = evaluate_policy("plan", sp.economics, plan.selected, t, y, rev, scale, n_boot)
        everyone = evaluate_policy(
            "everyone", sp.economics, np.ones(len(test), bool), t, y, rev, scale, n_boot
        )
        skipped = ~plan.selected
        left_out = (
            metrics.average_treatment_effect(y[skipped], t[skipped])
            if (skipped.sum() > 100)
            else None
        )
        out = {
            "plan_id": plan_id,
            "method": "replay on held-out randomised customers (self-normalised IPW), scaled "
            "to the audience size; 95% bootstrap interval",
            "test_customers": len(test),
            "share_contacted_in_test": _r(res.share_selected),
            "real_incremental_purchases": _r(res.incremental_conversions, 0),
            "real_spend": _r(res.spend, 0),
            "real_incremental_profit": _r(res.incremental_profit, 0),
            "profit_ci_95": [_r(res.profit_ci_low, 0), _r(res.profit_ci_high, 0)],
            "probability_profit_positive": _r(res.prob_profit_positive, 2),
            "real_incremental_roas": _r(res.incremental_roas, 2),
            "break_even_roas": _r(sp.economics.break_even_roas, 2),
            "cost_per_incremental_purchase": _r(res.cost_per_incremental_conversion, 2),
            "contact_everyone_incremental_profit": _r(everyone.incremental_profit, 0),
            "contact_everyone_profit_ci_95": [
                _r(everyone.profit_ci_low, 0),
                _r(everyone.profit_ci_high, 0),
            ],
            "contact_everyone_spend": _r(everyone.spend, 0),
            "profit_gain_vs_contact_everyone": _r(
                res.incremental_profit - everyone.incremental_profit, 0
            ),
            "spend_saved_vs_contact_everyone": _r(everyone.spend - res.spend, 0),
            "measured_uplift_among_not_contacted": _r(left_out["ate"]) if left_out else None,
            "currency": self.currency,
            "money_caveat": None
            if self.report["dataset"]["revenue_observed"]
            else ("purchase amounts are imputed with each customer's average basket"),
        }
        sp.evidence = out
        return out

    def sensitivity(
        self, parameter: str, values: list[float], audience: str = "next"
    ) -> list[dict[str, Any]]:
        """Re-plan under different values of one money assumption."""
        if parameter not in ("margin", "contact_cost", "discount", "budget"):
            raise ValueError("parameter must be margin, contact_cost, discount or budget")
        rows = []
        for v in values:
            s = self.plan(audience=audience, **{parameter: float(v)})
            self.plans.pop(s["plan_id"], None)
            rows.append(
                {
                    parameter: v,
                    "customers_to_contact": s["customers_to_contact"],
                    "share_contacted": s["share_contacted"],
                    "expected_spend": s["expected_spend"],
                    "expected_incremental_profit": s["expected_incremental_profit"],
                }
            )
        return rows

    # ------------------------------------------------------------- safeguards
    def fairness(self, plan_id: str) -> dict[str, Any]:
        sp = self._get(plan_id)
        part = self.customers.loc[sp.index]
        out: dict[str, Any] = {"plan_id": plan_id, "model_inputs_exclude": ["age", "gender"]}
        for col in ("gender", "age_band"):
            if col not in part.columns:
                continue
            tab = fairness.audit_groups(part[col], sp.plan.selected)
            di = fairness.disparate_impact(tab)
            # Is a gap backed by a real difference in effect? Measured in the past experiment.
            lab = self.customers[self.customers["split"] != "new"]
            measured = fairness.audit_groups(
                lab[col], np.zeros(len(lab), dtype=bool), lab["t"], lab["y"]
            )
            out[col] = {
                "selection_rate_by_group": {
                    str(k): _r(v) for k, v in tab["selection_rate"].items()
                },
                "measured_uplift_by_group_in_past_test": {
                    str(k): _r(v)
                    for k, v in measured.get("observed_uplift", pd.Series(dtype=float)).items()
                },
                "lowest_over_highest_rate": _r(di["ratio"], 3),
                "flag_for_review": di["flag"],
                "lowest_group": di["lowest"],
                "highest_group": di["highest"],
            }
        out["rule_of_thumb"] = "ratio under 0.8 is flagged for human review"
        return out

    def design_holdout(
        self,
        plan_id: str,
        minimum_detectable_uplift: float | None = None,
        power: float = 0.8,
        alpha: float = 0.05,
    ) -> dict[str, Any]:
        """Size the random hold-out group needed to measure the campaign's uplift."""
        sp = self._get(plan_id)
        part = self.customers.loc[sp.index][sp.plan.selected]
        n = len(part)
        if n == 0:
            return {"plan_id": plan_id, "error": "the plan contacts nobody"}
        p0 = float(part["p0"].mean())
        delta = minimum_detectable_uplift or float(part["uplift"].mean())
        delta = max(delta, 1e-4)
        p1 = min(p0 + delta, 0.999)
        z = stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)
        # unequal allocation: holdout share h of n. Var = p1q1/(n(1-h)) + p0q0/(nh)
        best = None
        for h in np.arange(0.02, 0.51, 0.01):
            se = math.sqrt(p1 * (1 - p1) / (n * (1 - h)) + p0 * (1 - p0) / (n * h))
            if delta / se >= z:
                best = float(h)
                break
        return {
            "plan_id": plan_id,
            "customers_selected": n,
            "expected_purchase_rate_without_contact": _r(p0),
            "uplift_to_detect": _r(delta),
            "power": power,
            "alpha": alpha,
            "holdout_share": _r(best, 2) if best else None,
            "holdout_customers": round(best * n) if best else None,
            "feasible": best is not None,
            "advice": (
                "Keep this random share of selected customers uncontacted; compare purchase "
                "rates after the campaign to read the real uplift."
                if best
                else "Audience too small to detect this uplift even with a 50% hold-out; "
                "accept a larger detectable effect or pool several campaigns."
            ),
        }

    def explain_customer(self, client_id: str, plan_id: str | None = None) -> dict[str, Any]:
        if client_id not in self.customers.index:
            raise KeyError(f"unknown customer '{client_id}'")
        row = self.customers.loc[client_id]
        econ = self._get(plan_id).economics if plan_id else self.default_economics
        be = float(break_even_uplift(econ, [row["value"]], [row["p1"]])[0])
        gain = float(incremental_profit(econ, [row["value"]], [row["uplift"]], [row["p1"]])[0])
        out: dict[str, Any] = {
            "client_id": client_id,
            "purchase_probability_if_not_contacted": _r(row["p0"], 3),
            "estimated_uplift_points": _r(row["uplift"]),
            "break_even_uplift_points": _r(be),
            "expected_basket": _r(row["value"], 0),
            "expected_incremental_profit_if_contacted": _r(gain, 2),
            "decision": "contact" if gain > 0 and row["uplift"] > 0 else "do not contact",
            "currency": self.currency,
        }
        for k in ("recency_days", "frequency", "monetary", "r_score", "f_score", "m_score"):
            if k in row.index:
                out[k] = _r(row[k], 1)
        if "rfm_segment" in row.index:
            out["rfm_segment"] = str(row["rfm_segment"])
        out["reason"] = (
            f"Estimated uplift {row['uplift']:+.1%} is "
            f"{'above' if row['uplift'] > be else 'below'} the break-even uplift {be:.1%} "
            f"for a basket of {row['value']:,.0f} {self.currency}."
        )
        return out

    # ------------------------------------------------------------------ action
    def request_approval(self, plan_id: str) -> dict[str, Any]:
        """Register that a plan is waiting for a human decision. Returns no secret."""
        sp = self._get(plan_id)
        rec = self._approvals.get(plan_id) or {}
        if rec.get("status") == "approved":
            # a later request never takes back a decision a person already made
            return {
                "plan_id": plan_id,
                "status": "already_approved",
                "approved_by": rec.get("approver"),
                "currency": self.currency,
            }
        self._approvals[plan_id] = {"status": "pending", "code": secrets.token_hex(8)}
        return {
            "plan_id": plan_id,
            "status": "pending_human_approval",
            "what_will_happen_if_approved": (
                f"an audience file with {sp.plan.n_selected} customers is written for the "
                "messaging tool; nothing is sent by the agent itself"
            ),
            "expected_spend": sp.summary.get("expected_spend"),
            "currency": self.currency,
        }

    def human_approve(self, plan_id: str, approver: str) -> str:
        """Called by the user interface only, never exposed to the language model."""
        if plan_id not in self._approvals:
            raise ApprovalRequired("no approval was requested for this plan")
        if not approver.strip():
            raise ApprovalRequired("an approver name is required")
        rec = self._approvals[plan_id]
        rec.update(
            status="approved",
            approver=approver.strip(),
            at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        return str(rec["code"])

    def human_reject(self, plan_id: str, approver: str, reason: str = "") -> None:
        self._approvals[plan_id] = {"status": "rejected", "approver": approver, "reason": reason}

    def approval_status(self, plan_id: str) -> str:
        return str(self._approvals.get(plan_id, {}).get("status", "not_requested"))

    def export(
        self,
        plan_id: str,
        approval_code: str,
        holdout_share: float = 0.1,
        seed: int = 0,
        out_dir: Path | None = None,
    ) -> dict[str, Any]:
        """Write the approved audience (with a random hold-out) to disk."""
        sp = self._get(plan_id)
        rec = self._approvals.get(plan_id, {})
        if rec.get("status") != "approved" or not secrets.compare_digest(
            str(rec.get("code", "")), str(approval_code)
        ):
            raise ApprovalRequired("export blocked: a human has not approved this plan")
        if not 0 <= holdout_share < 1:
            raise ValueError("holdout_share must be in [0, 1)")
        part = self.customers.loc[sp.index][sp.plan.selected]
        rng = np.random.default_rng(seed)
        holdout = rng.random(len(part)) < holdout_share
        cols = [c for c in ("rfm_segment", "r_score", "f_score", "m_score") if c in part.columns]
        out = part[cols].copy()
        out["estimated_uplift"] = part["uplift"].round(4)
        out["expected_incremental_profit"] = (
            part["gain"].round(2)
            if (sp.economics == self.default_economics)
            else incremental_profit(sp.economics, part["value"], part["uplift"], part["p1"]).round(
                2
            )
        )
        out["group"] = np.where(holdout, "holdout_do_not_send", "send")
        if sp.messages and "rfm_segment" in out.columns:
            out["message"] = out["rfm_segment"].map(sp.messages).fillna("")
        elif "All customers" in sp.messages:
            out["message"] = sp.messages["All customers"]
        target = (out_dir or config.runs_dir()) / plan_id
        target.mkdir(parents=True, exist_ok=True)
        out.to_csv(target / "audience.csv", encoding="utf-8")
        manifest = {
            "plan_id": plan_id,
            "approved_by": rec.get("approver"),
            "approved_at": rec.get("at"),
            "summary": sp.summary,
            "evidence": sp.evidence,
            "messages": sp.messages,
            "holdout_share": holdout_share,
            "rows_send": int((~holdout).sum()),
            "rows_holdout": int(holdout.sum()),
        }
        (target / "plan.json").write_text(json.dumps(manifest, indent=2, default=str))
        return {
            "plan_id": plan_id,
            "status": "exported",
            "file": str(target / "audience.csv"),
            "customers_to_send": int((~holdout).sum()),
            "customers_in_holdout": int(holdout.sum()),
            "approved_by": rec.get("approver"),
        }
