"""Verified statements: the facts of a plan, written by code from tool results.

A small local model is good at wording and unreliable at reading a pile of
JSON: in testing it called the customers who are deliberately left alone "a
hold-out" and described a difference as "significant" when its interval
crossed zero. So the meaning of every figure is fixed here, in ordinary code,
and the model's job is reduced to narrating these sentences for a manager.
The interface always shows the statements next to the narrative.
"""

from __future__ import annotations

import re
from typing import Any


def latest_results(steps: list[Any], plan_id: str) -> dict[str, dict[str, Any]]:
    last: dict[str, dict[str, Any]] = {}
    for s in steps:
        if (
            isinstance(s.result, dict)
            and "error" not in s.result
            and (
                s.result.get("plan_id") == plan_id
                or s.tool in ("schedule_campaign", "get_experiment_readout")
            )
        ):
            last[s.tool] = s.result
    return last


def _n(x: Any) -> str:
    return f"{x:,.0f}" if isinstance(x, (int, float)) else str(x)


def verified_statements(steps: list[Any], plan_id: str | None) -> list[str]:
    if not plan_id:
        return []
    r = latest_results(steps, plan_id)
    out: list[str] = []
    plan = r.get("plan_campaign")
    if not plan:
        return out
    cur = plan["currency"]
    a = plan["assumptions"]
    out.append(
        f"Assumptions: gross margin {a['gross_margin']:.0%}, {a['cost_per_message']:g} {cur} per "
        f"message, discount {a['discount_share_of_basket']:.1%} of basket"
        + (
            f", budget {_n(a['budget'])} {cur}"
            if a.get("budget") is not None
            else ", no budget cap"
        )
        + (
            ". Fair mode is on: every customer is valued at the average basket"
            if str(plan.get("decision_mode", "")).startswith("fair")
            else ""
        )
        + "."
    )
    ignored = plan.get("ignored_arguments", {}).get("values")
    if ignored:
        out.append(
            "The model proposed assumptions the manager never stated ("
            + ", ".join(f"{k} = {v}" for k, v in ignored.items())
            + "); they were ignored and the system defaults were used."
        )
    conv = plan.get("budget_conversion")
    if conv and "from" in conv:
        out.append(
            f"Budget conversion ({'live' if conv.get('live') else 'cached'} rate, "
            f"{conv.get('as_of', 'date unknown')}): {_n(conv['from']['amount'])} "
            f"{conv['from']['currency']} = {_n(conv['amount'])} {cur}."
        )
    out.append(
        f"Decision: contact {_n(plan['customers_to_contact'])} of "
        f"{_n(plan['customers_in_audience'])} customers ({plan['share_contacted']:.1%}). "
        f"The other {_n(plan['customers_not_contacted'])} are left alone because contacting "
        "them is expected to cost more than it brings in (they are not a hold-out)."
    )
    removed = {k: v for k, v in plan.get("removed_by_rule", {}).items() if v}
    if removed:
        names = {
            "opted_out": "opted out",
            "under_18": "minors",
            "no_expected_effect": "no positive effect expected",
            "outside_chosen_segments": "outside the chosen segments",
        }
        out.append(
            "Excluded by rule before optimising: "
            + ", ".join(f"{_n(v)} {names.get(k, k)}" for k, v in removed.items())
            + "."
        )
    out.append(
        f"Model expects: spend {_n(plan['expected_spend'])} {cur} and incremental profit "
        f"{_n(plan['expected_incremental_profit'])} {cur}."
    )
    ev = r.get("evaluate_plan")
    if ev:
        lo, hi = ev["profit_ci_95"]
        out.append(
            f"Experiment replay (real behaviour of held-out randomised customers, scaled to this "
            f"audience): incremental profit {_n(ev['real_incremental_profit'])} {cur}, 95% "
            f"interval {_n(lo)} to {_n(hi)} {cur}; probability that the profit is positive "
            f"{ev['probability_profit_positive']:.0%}."
        )
        out.append(
            f"If everyone were contacted instead: incremental profit "
            f"{_n(ev['contact_everyone_incremental_profit'])} {cur} for a spend of "
            f"{_n(ev['contact_everyone_spend'])} {cur}. The plan earns "
            f"{_n(abs(ev['profit_gain_vs_contact_everyone']))} {cur} "
            f"{'more' if ev['profit_gain_vs_contact_everyone'] >= 0 else 'less'} and spends "
            f"{_n(ev['spend_saved_vs_contact_everyone'])} {cur} less."
        )
        if ev.get("real_incremental_roas") is not None:
            out.append(
                f"Incremental ROAS of the plan: {ev['real_incremental_roas']:.2f} (extra revenue "
                f"per unit of spend); a campaign breaks even at {ev['break_even_roas']:.2f}."
            )
        if lo < 0 < hi:
            likely = ev["probability_profit_positive"] > 0.5 and ev["real_incremental_profit"] > 0
            out.append(
                "The interval includes zero: the plan is more likely than not to be profitable, "
                "but this is not statistically certain."
                if likely
                else "The interval includes zero and the estimate is not clearly positive: on "
                "this evidence the plan cannot be expected to make money."
            )
        elif hi <= 0:
            out.append("The whole interval is below zero: the replay shows this plan loses money.")
    fair = r.get("audit_fairness")
    if fair:
        parts, flagged = [], []
        for key, label in (("gender", "gender"), ("age_band", "age band")):
            f = fair.get(key)
            if not f or f.get("lowest_over_highest_rate") is None:
                continue
            parts.append(f"{label} ratio {f['lowest_over_highest_rate']:.2f}")
            if f["flag_for_review"]:
                flagged.append(label)
        if parts:
            out.append(
                "Fairness (lowest selection rate divided by highest, flag under 0.80): "
                + ", ".join(parts)
                + ". "
                + (
                    "Needs human review: " + ", ".join(flagged) + "."
                    if flagged
                    else "No group gap needs review."
                )
                + " Age and gender are not model inputs."
            )
    hold = r.get("design_holdout")
    if hold and "error" not in hold:
        if hold.get("feasible"):
            out.append(
                f"Measurement: keep a random {hold['holdout_share']:.0%} of the selected "
                f"customers ({_n(hold['holdout_customers'])}) uncontacted, to measure the real "
                f"uplift of this campaign (able to detect {hold['uplift_to_detect']:.1%})."
            )
        else:
            out.append(f"Measurement: {hold['advice']}")
    sched = r.get("schedule_campaign")
    if sched and sched.get("recommended_send_date"):
        hol = sched.get("holidays_inside_window") or []
        if not sched.get("calendar_known", True):
            out.append(
                f"Send date: {sched['recommended_send_date']}. The holiday calendar was not "
                "available (no connection, no cache): only weekends were avoided."
            )
        else:
            out.append(
                f"Send date: {sched['recommended_send_date']} "
                f"({'live' if sched.get('live') else 'cached'} holiday calendar); "
                + (
                    f"public holidays inside the measurement window: "
                    f"{', '.join(h['date'] for h in hol)}."
                    if hol
                    else "no public holiday inside the measurement window."
                )
            )
    drafts = r.get("draft_messages", {}).get("messages")
    if drafts:
        ok = all(m["passed_checks"] for m in drafts.values())
        out.append(
            f"Messages: one draft per RFM segment ({len(drafts)} drafts); "
            f"{'all passed' if ok else 'NOT all passed'} the automatic copy checks."
        )
    appr = r.get("request_approval")
    out.append(
        "Status: waiting for human approval; nothing has been sent."
        if appr
        else "Status: no approval requested; nothing has been sent."
    )
    if ev and ev.get("money_caveat"):
        out.append(f"Caveat: {ev['money_caveat']}.")
    return out


OVERCLAIM = re.compile(
    r"\b(significant(ly)?|guarantee[ds]?|certain(ly)?|proves?|proven|will (definitely|surely)|"
    r"no risk|risk[- ]free|"
    r"(drafts?|messages?|sms|texts?|campaign) (were|was|have been|has been|already)? ?sent)\b",
    re.IGNORECASE,
)


def overclaims(answer: str, steps: list[Any], plan_id: str | None) -> list[str]:
    """Words that promise more certainty than the evidence gives."""
    found = sorted({m.group(0).lower() for m in OVERCLAIM.finditer(answer)})
    if not found or not plan_id:
        return found
    ev = latest_results(steps, plan_id).get("evaluate_plan")
    if ev and ev["profit_ci_95"][0] > 0:
        # a positive interval does support "significantly positive" style wording
        found = [w for w in found if not w.startswith("significant")]
    return found
