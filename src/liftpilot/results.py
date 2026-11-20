"""Extra analyses and a single results sheet for the paper, slides and README.

``liftpilot results`` writes

* ``artifacts/extra_analyses.json`` - fairness by message cost, the price of
  fair mode, retention / lifetime-value by RFM segment, budget frontier;
* ``docs/RESULTS.md``               - every headline number in one place,
  generated from the saved reports so the documents cannot drift from the code.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any

import pandas as pd

from liftpilot import config, live
from liftpilot.data import x5
from liftpilot.engine import CampaignEngine

LTV_HORIZON_MONTHS = 36.0


def retention_and_ltv(engine: CampaignEngine, margin: float) -> dict[str, Any]:
    """Course formulas on real receipts, per RFM segment.

    Lifetime is capped at 36 months because churn is measured over two
    month-to-month transitions only. Active in a month = at least one purchase. Monthly churn = customers
    active in month *m* with no purchase in month *m+1*, over customers
    active in month *m*. Lifetime (months) = 1 / churn.
    LTV = basket x orders per month x margin x lifetime.
    Only the complete calendar months of the history are used.
    """
    act = x5.monthly_activity(config.interim_dir())
    months = sorted(act["month"].unique())
    complete = months[1:-1]  # first and last month of the window are partial
    wide = act.pivot_table(index="client_id", columns="month", values="orders", fill_value=0)
    seg = engine.customers["rfm_segment"].reindex(wide.index)
    pairs = list(itertools.pairwise(complete))
    out: dict[str, Any] = {
        "months_used": complete,
        "pairs": [f"{a}->{b}" for a, b in pairs],
        "segments": {},
    }

    def stats(idx: pd.Index) -> dict[str, float]:
        w = wide.loc[idx]
        start = lost = 0
        for a, b in pairs:
            active = w[a] > 0
            start += int(active.sum())
            lost += int((active & (w[b] == 0)).sum())
        churn = lost / start if start else float("nan")
        rev = act[act["client_id"].isin(idx) & act["month"].isin(complete)]
        active_months = len(rev)
        orders_pm = rev["orders"].sum() / active_months if active_months else float("nan")
        aov = rev["revenue"].sum() / rev["orders"].sum() if rev["orders"].sum() else float("nan")
        # A three-month window cannot support lifetimes of many years: cap the horizon.
        life = min(1 / churn, LTV_HORIZON_MONTHS) if churn and churn > 0 else LTV_HORIZON_MONTHS
        return {
            "customers": len(idx),
            "monthly_churn": churn,
            "monthly_retention": 1 - churn,
            "orders_per_active_month": float(orders_pm),
            "average_order_value": float(aov),
            "expected_lifetime_months": life,
            "ltv_gross_profit": float(aov * orders_pm * margin * life),
        }

    out["all"] = stats(wide.index)
    for name in seg.dropna().unique():
        out["segments"][str(name)] = stats(seg.index[seg == name])
    return out


def extra_analyses(dataset: str = "x5", offline: bool = False) -> dict[str, Any]:
    e = CampaignEngine(dataset)
    out: dict[str, Any] = {}

    rows = []
    for cost in (2.0, 4.0, 6.0, 10.0):
        p = e.plan(contact_cost=cost)
        f = e.fairness(p["plan_id"])
        rows.append(
            {
                "cost": cost,
                "share": p["share_contacted"],
                "rates": f["age_band"]["selection_rate_by_group"],
                "ratio": f["age_band"]["lowest_over_highest_rate"],
                "flag": f["age_band"]["flag_for_review"],
                "lowest": f["age_band"]["lowest_group"],
                "highest": f["age_band"]["highest_group"],
                "gender_ratio": f["gender"]["lowest_over_highest_rate"],
                "measured_uplift_by_age": f["age_band"]["measured_uplift_by_group_in_past_test"],
                "measured_uplift_by_gender": f["gender"]["measured_uplift_by_group_in_past_test"],
            }
        )
    out["fairness_by_cost"] = rows

    fair = []
    for cost in (2.0, 6.0):
        for mode in (False, True):
            p = e.plan(contact_cost=cost, equal_value=mode)
            ev = e.evaluate(p["plan_id"], n_boot=300)
            f = e.fairness(p["plan_id"])
            fair.append(
                {
                    "cost": cost,
                    "fair_mode": mode,
                    "contacted": p["customers_to_contact"],
                    "share": p["share_contacted"],
                    "real_profit": ev["real_incremental_profit"],
                    "ci": ev["profit_ci_95"],
                    "p_positive": ev["probability_profit_positive"],
                    "age_ratio": f["age_band"]["lowest_over_highest_rate"],
                    "gender_ratio": f["gender"]["lowest_over_highest_rate"],
                }
            )
    out["fair_mode"] = fair

    frontier = []
    for cost in (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0):
        p = e.plan(contact_cost=cost)
        ev = e.evaluate(p["plan_id"], n_boot=200)
        frontier.append(
            {
                "cost": cost,
                "share": p["share_contacted"],
                "contacted": p["customers_to_contact"],
                "plan_profit": ev["real_incremental_profit"],
                "plan_ci": ev["profit_ci_95"],
                "plan_p_positive": ev["probability_profit_positive"],
                "everyone_profit": ev["contact_everyone_incremental_profit"],
                "everyone_ci": ev["contact_everyone_profit_ci_95"],
                "gain": ev["profit_gain_vs_contact_everyone"],
                "spend_saved": ev["spend_saved_vs_contact_everyone"],
                "plan_spend": ev["real_spend"],
                "iroas": ev["real_incremental_roas"],
            }
        )
    out["cost_frontier"] = frontier

    out["retention_ltv"] = retention_and_ltv(e, e.default_economics.margin)
    out["fx"] = live.exchange_rates(e.currency, ["USD", "BRL", "EUR", "LBP"], offline=offline)
    out["brl_budget"] = live.convert(1_000_000, "BRL", e.currency, offline=offline)
    target = config.root() / "artifacts" / "extra_analyses.json"
    target.write_text(json.dumps(out, indent=2, default=str))
    return out


def _pct(x: float | None, d: int = 1) -> str:
    return "n/a" if x is None else f"{x * 100:.{d}f}%"


def write_results_md(path: Path | None = None) -> Path:
    root = config.root()
    rep = json.loads((config.artifacts_dir("x5") / "report.json").read_text())
    ext = json.loads((root / "artifacts" / "extra_analyses.json").read_text())
    ro, ds = rep["experiment_readout"], rep["dataset"]
    L: list[str] = [
        "# LiftPilot results sheet",
        "",
        "_Generated by `liftpilot results` from `artifacts/`. Do not edit by hand._",
        "",
        "## 1. Data (X5 RetailHero)",
        f"- Customers with purchase history: **{ds['customers_total']:,}**; in the randomised "
        f"experiment: **{ds['customers_in_experiment']:,}**; never tested (next audience): "
        f"**{ds['splits']['new']:,}**.",
        f"- History window: {ds['history_start']} to {ds['reference_date']}; model features: "
        f"{ds['n_features']} (age and gender excluded). Invalid ages set to missing: "
        f"{ds['invalid_ages_set_missing']:,}.",
        f"- Split of labelled customers: train {ds['splits']['train']:,} / calibration "
        f"{ds['splits']['calibration']:,} / test {ds['splits']['test']:,}.",
        f"- Mean expected basket: {ds['mean_value']:.0f} RUB (currency presumed; the source does "
        "not state it). Purchase amount after the campaign is not in the data: money figures "
        "value a purchase at the customer's own average basket.",
        "",
        "## 2. The experiment",
        f"- Purchase rate: contacted **{_pct(ro['rate_treated'], 2)}** (n={ro['n_treated']:,.0f}) "
        f"vs held out **{_pct(ro['rate_control'], 2)}** (n={ro['n_control']:,.0f}).",
        f"- Average uplift **{ro['ate'] * 100:+.2f} points** (95% CI {ro['ci_low'] * 100:+.2f} to "
        f"{ro['ci_high'] * 100:+.2f}); relative uplift {_pct(ro['relative_uplift'])}; "
        f"z = {ro['z']:.1f}.",
        f"- Share of post-contact purchases that would have happened anyway: "
        f"{_pct(ro['rate_control'] / ro['rate_treated'])}.",
        "",
        "## 3. Uplift by RFM segment (measured, 95% CI)",
        "| Segment | Customers | Share | Recency (d) | Purchases | Spend | Buys without contact | Uplift (pts) | 95% CI |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for n, s in rep["rfm_segments"].items():
        L.append(
            f"| {n} | {s['customers']:,} | {_pct(s['share'])} | {s['recency_days']:.1f} | "
            f"{s['frequency']:.1f} | {s['monetary']:,.0f} | {_pct(s['conversion_control'])} | "
            f"{s['observed_uplift'] * 100:+.1f} | {s['uplift_ci_low'] * 100:+.1f} to "
            f"{s['uplift_ci_high'] * 100:+.1f} |"
        )
    L += [
        "",
        "Uplift by score (1 = worst, 5 = best): baseline purchase rate / uplift in points",
        "",
    ]
    for dim, rows in rep["uplift_by_rfm_score"].items():
        L.append(
            f"- {dim}: "
            + "; ".join(
                f"{k}: {_pct(v['rate_control'], 0)} / {v['uplift'] * 100:+.1f}"
                for k, v in rows.items()
            )
        )
    L += [
        "",
        "## 4. Models on held-out test customers",
        "| Learner | Qini (test) | 95% CI | Uplift top 10% | Uplift top 30% | Uplift bottom 30% | Qini, 5 re-splits (mean ± SD) |",
        "|---|---:|---|---:|---:|---:|---|",
    ]
    for n, r in rep["learners"].items():
        q = r["qini_test"]
        rp = rep.get("learners_repeated", {}).get(n)
        L.append(
            f"| {n}{' (champion)' if n == rep['champion'] else ''} | {q['value']:+.4f} | "
            f"{q['ci_low']:+.4f} to {q['ci_high']:+.4f} | {r['uplift_at_10'] * 100:+.1f} | "
            f"{r['uplift_at_30'] * 100:+.1f} | {r['uplift_bottom_30'] * 100:+.1f} | "
            + (f"{rp['mean']:+.4f} ± {rp['sd']:.4f}" if rp else "-")
            + " |"
        )
    L += [
        "",
        "Champion chosen by Qini on the calibration split. Feature ablation (same learner):",
        "",
    ]
    for k, v in rep.get("ablation", {}).items():
        q = v["qini_test"]
        L.append(
            f"- {k}: Qini {q['value']:+.4f} (95% CI {q['ci_low']:+.4f} to {q['ci_high']:+.4f})"
        )
    L += ["", "Decision groups at default costs, checked on test customers:", ""]
    for k, v in rep["types"].items():
        if "test_uplift" in v:
            L.append(
                f"- {k}: {_pct(v['share'])} of customers; buys without contact "
                f"{_pct(v['test_rate_control'])}; real uplift {v['test_uplift'] * 100:+.1f} pts "
                f"(95% CI {v['test_uplift_ci'][0] * 100:+.1f} to {v['test_uplift_ci'][1] * 100:+.1f})"
            )
    L += [
        "",
        "## 5. Real incremental profit by scenario (test replay, scaled to 400,162 customers)",
        "",
    ]
    for label, s in rep["scenarios"].items():
        e = s["economics"]
        L += [
            f"### {label}",
            f"margin {e['margin']:.0%}, {e['contact_cost']:g} RUB per message, discount "
            f"{e['discount']:.0%}; mean break-even uplift {s['mean_break_even_uplift'] * 100:.2f} pts",
            "",
            "| Rule | Contacted | Spend (RUB) | Incremental profit (RUB) | 95% CI | P(profit > 0) | iROAS |",
            "|---|---:|---:|---:|---|---:|---:|",
        ]
        for n, p in s["policies"].items():
            L.append(
                f"| {n} | {_pct(p['share_selected'])} | {p['spend']:,.0f} | "
                f"{p['incremental_profit']:,.0f} | {p['profit_ci_low']:,.0f} to "
                f"{p['profit_ci_high']:,.0f} | {p['prob_profit_positive']:.0%} | "
                + (f"{p['incremental_roas']:.2f}" if p["incremental_roas"] is not None else "-")
                + " |"
            )
        d = s["liftpilot_vs_everyone"]
        L += [
            "",
            f"LiftPilot minus contact-everyone: **{d['difference']:,.0f} RUB** (paired 95% "
            f"CI {d['ci_low']:,.0f} to {d['ci_high']:,.0f}; P(LiftPilot better) = "
            f"{d['prob_a_better']:.0%}).",
            "",
        ]
    L += [
        "## 6. Cost frontier on the never-tested audience (200,123 customers)",
        "| Cost / message | Contacted | Plan profit (RUB) | 95% CI | P(>0) | Contact-everyone profit | Gain vs everyone | Spend saved |",
        "|---:|---:|---:|---|---:|---:|---:|---:|",
    ]
    for r in ext["cost_frontier"]:
        L.append(
            f"| {r['cost']:g} | {_pct(r['share'])} | {r['plan_profit']:,.0f} | "
            f"{r['plan_ci'][0]:,.0f} to {r['plan_ci'][1]:,.0f} | {r['plan_p_positive']:.0%} | "
            f"{r['everyone_profit']:,.0f} | {r['gain']:,.0f} | {r['spend_saved']:,.0f} |"
        )
    L += [
        "",
        "## 7. Fairness audit (age and gender are never model inputs)",
        "| Cost / message | Share contacted | Age ratio (low/high) | Flag | Lowest | Highest | Gender ratio |",
        "|---:|---:|---:|---|---|---|---:|",
    ]
    for r in ext["fairness_by_cost"]:
        L.append(
            f"| {r['cost']:g} | {_pct(r['share'])} | {r['ratio']:.2f} | "
            f"{'REVIEW' if r['flag'] else 'ok'} | {r['lowest']} | {r['highest']} | "
            f"{r['gender_ratio']:.2f} |"
        )
    r0 = ext["fairness_by_cost"][0]
    L += [
        "",
        "Measured uplift by age band in the experiment (points): "
        + "; ".join(f"{k}: {v * 100:+.1f}" for k, v in r0["measured_uplift_by_age"].items()),
        "Measured uplift by gender (points): "
        + "; ".join(f"{k}: {v * 100:+.1f}" for k, v in r0["measured_uplift_by_gender"].items()),
        "",
        "Fair mode (every customer valued at the average basket):",
        "",
    ]
    for r in ext["fair_mode"]:
        L.append(
            f"- cost {r['cost']:g} RUB, fair mode {'ON' if r['fair_mode'] else 'off'}: contact "
            f"{r['contacted']:,} ({_pct(r['share'])}); real profit {r['real_profit']:,.0f} RUB "
            f"(95% CI {r['ci'][0]:,.0f} to {r['ci'][1]:,.0f}); age ratio {r['age_ratio']:.2f}; "
            f"gender ratio {r['gender_ratio']:.2f}"
        )
    rl = ext["retention_ltv"]
    L += [
        "",
        "## 8. Retention and lifetime value (course formulas on real receipts)",
        f"Complete months used: {', '.join(rl['months_used'])}; transitions: "
        f"{', '.join(rl['pairs'])}. Margin {rep['economics']['margin']:.0%}.",
        "",
        "| Segment | Monthly churn | Monthly retention | Orders / active month | AOV (RUB) | Lifetime (months, capped at 36) | LTV over that horizon, gross profit (RUB) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for n, s in [("All customers", rl["all"]), *rl["segments"].items()]:
        L.append(
            f"| {n} | {_pct(s['monthly_churn'])} | {_pct(s['monthly_retention'])} | "
            f"{s['orders_per_active_month']:.1f} | {s['average_order_value']:,.0f} | "
            f"{s['expected_lifetime_months']:.1f} | {s['ltv_gross_profit']:,.0f} |"
        )
    fx, b = ext["fx"], ext["brl_budget"]
    L += [
        "",
        "## 9. Live context at generation time",
        f"- Exchange rates ({fx.get('source')}, {fx.get('as_of')}): 1 RUB = "
        + ", ".join(f"{v:.5g} {k}" for k, v in fx.get("rates", {}).items())
        + ".",
        f"- The course brief's R$ 1,000,000 = {b.get('amount', 0):,.0f} RUB at that rate.",
    ]
    ag = root / "artifacts" / "agent_eval.json"
    if ag.exists():
        s = json.loads(ag.read_text())["summary"]
        L += [
            "",
            f"## 10. Agent benchmark ({s['model']}, {s['cases']} fixed requests)",
            f"- Argument fidelity (planner received exactly the stated assumptions, after the "
            f"provenance guard): {_pct(s['argument_fidelity'], 0)}; runs in which the guard "
            f"had to drop assumptions invented by the model: "
            f"{s.get('runs_where_invented_arguments_were_blocked', 'n/a')}",
            f"- Mandatory checklist completed: {_pct(s['checklist_completion'], 0)}; runs ending "
            f"in a human-approval request: {_pct(s['waiting_for_human'], 0)}",
            f"- Numeric grounding: {_pct(s['numeric_grounding_rate'])} of "
            f"{s['numbers_checked']} numbers; narratives rejected by the guards: "
            f"{s['narratives_rejected']}",
            f"- Message drafts: {s['drafts_total']} total, {s['drafts_written_by_model']} "
            f"written by the model, {s['drafts_passing_checks']} passing the copy checks",
            f"- Questions answered with the expected tool: "
            f"{_pct(s['questions_using_expected_tool'], 0)}",
            f"- Safety probes passed: {s['safety_probes_passed']} of {s['safety_probes']}",
            f"- Median time for a full campaign plan: {s['median_seconds_campaign']:.0f} s "
            "on an RTX 3080 laptop GPU",
        ]
    hp = config.artifacts_dir("hillstrom") / "report.json"
    if hp.exists():
        h = json.loads(hp.read_text())
        hr = h["experiment_readout"]
        L += [
            "",
            "## 11. External check: Hillstrom e-mail test (64,000 customers, USD, observed spend)",
            f"- Visit rate: e-mailed {_pct(hr['rate_treated'], 2)} vs not e-mailed "
            f"{_pct(hr['rate_control'], 2)}; uplift {hr['ate'] * 100:+.2f} pts "
            f"(95% CI {hr['ci_low'] * 100:+.2f} to {hr['ci_high'] * 100:+.2f}).",
            "- Qini on test (95% CI): "
            + "; ".join(
                f"{n} {r['qini_test']['value']:+.3f} ({r['qini_test']['ci_low']:+.3f} to "
                f"{r['qini_test']['ci_high']:+.3f})"
                for n, r in h["learners"].items()
            ),
            "- Repeated splits (mean ± SD): "
            + "; ".join(
                f"{n} {v['mean']:+.3f} ± {v['sd']:.3f}"
                for n, v in h.get("learners_repeated", {}).items()
            ),
            "",
        ]
        for label, s in h["scenarios"].items():
            pe, pl = s["policies"]["Contact everyone"], s["policies"]["LiftPilot profit rule"]
            d = s["liftpilot_vs_everyone"]
            L.append(
                f"- {label}: everyone {pe['incremental_profit']:,.0f} USD "
                f"({pe['profit_ci_low']:,.0f} to {pe['profit_ci_high']:,.0f}); LiftPilot contacts "
                f"{_pct(pl['share_selected'])} and earns {pl['incremental_profit']:,.0f} USD "
                f"({pl['profit_ci_low']:,.0f} to {pl['profit_ci_high']:,.0f}); difference "
                f"{d['difference']:,.0f} ({d['ci_low']:,.0f} to {d['ci_high']:,.0f})."
            )
    path = path or (root / "docs" / "RESULTS.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return path
