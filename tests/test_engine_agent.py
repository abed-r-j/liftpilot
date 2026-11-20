from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from liftpilot import rfm
from liftpilot.agent.copy_guard import Offer, check_copy, fallback_template
from liftpilot.agent.grounding import check_grounding
from liftpilot.agent.runtime import Agent, AuditLog
from liftpilot.agent.tools import Toolbox
from liftpilot.engine import ApprovalRequired


# --------------------------------------------------------------------------- RFM
def test_rfm_scores_and_segments():
    df = pd.DataFrame(
        {
            "recency_days": [1, 2, 3, 50, 60, 70, 90, 100, 110, 120],
            "frequency": [30, 28, 2, 25, 3, 2, 1, 1, 29, 1],
            "monetary": [9000, 8000, 300, 7000, 400, 200, 100, 150, 9500, 50],
        }
    )
    out = rfm.add_rfm(df)
    assert set(out["r_score"]) == {1, 2, 3, 4, 5}
    assert out.loc[0, "r_score"] == 5 and out.loc[9, "r_score"] == 1
    assert out.loc[0, "rfm_segment"] == "Champions"
    assert out.loc[8, "rfm_segment"] == "Cannot lose them"
    assert out.loc[9, "rfm_segment"] == "Hibernating"
    assert out["rfm_score"].between(1, 5).all()
    with pytest.raises(ValueError, match="weights"):
        rfm.add_rfm(df, weights={"recency": 0, "frequency": 0, "monetary": 0})


def test_shrunk_basket_pulls_rare_buyers_to_the_mean():
    avg = pd.Series([1000.0, 1000.0])
    freq = pd.Series([1.0, 100.0])
    out = rfm.shrunk_basket(
        pd.concat([avg, pd.Series([100.0])], ignore_index=True),
        pd.concat([freq, pd.Series([500.0])], ignore_index=True),
    )
    assert out[0] < out[1] <= 1000.0


# ------------------------------------------------------------------------ pipeline
def test_pipeline_report_is_complete(tiny_artifacts, tiny_experiment):
    out, report = tiny_artifacts
    for key in (
        "dataset",
        "experiment_readout",
        "learners",
        "champion",
        "policies",
        "scenarios",
        "types",
        "rfm_segments",
        "fairness",
        "liftpilot_vs_everyone",
    ):
        assert key in report
    assert (out / "customers.parquet").exists() and (out / "models.joblib").exists()
    json.loads((out / "report.json").read_text())
    assert report["champion"] != "response"
    # lapsed customers were built to be the persuadable ones: the scores must recover that
    scored = pd.read_parquet(out / "customers.parquet")
    truth = tiny_experiment.frame["true_tau"].reindex(scored.index)
    assert np.corrcoef(scored["uplift_score"], truth)[0, 1] > 0.5
    assert np.corrcoef(scored["score_response"], truth)[0, 1] < 0.5
    lapsed = scored["uplift"][truth > 0].mean()
    recent = scored["uplift"][truth == 0].mean()
    assert lapsed == pytest.approx(0.20, abs=0.07) and recent == pytest.approx(0.0, abs=0.07)
    assert set(scored["type"]) <= {"contact", "skip: gain below cost", "skip: no expected effect"}


# -------------------------------------------------------------------------- engine
def test_plan_contacts_only_profitable_eligible_customers(engine):
    plan = engine.plan()
    stored = engine.plans[plan["plan_id"]]
    part = engine.customers.loc[stored.index]
    sel = part[stored.plan.selected]
    assert plan["customers_to_contact"] == len(sel) > 0
    assert (sel["uplift"] > 0).all()
    assert "no_expected_effect" in plan["removed_by_rule"]
    assert (sel["age"] >= 18).all()
    assert (stored.plan.gain[stored.plan.selected] > 0).all()
    assert plan["removed_by_rule"]["under_18"] > 0
    assert plan["audience"] == "next" and (part["split"] == "new").all()


def test_budget_and_cost_change_the_plan(engine):
    free = engine.plan()
    capped = engine.plan(budget=2000.0)
    assert capped["expected_spend"] <= 2000.0
    assert capped["customers_to_contact"] < free["customers_to_contact"]
    costly = engine.plan(contact_cost=50.0)
    assert costly["customers_to_contact"] < free["customers_to_contact"]
    rows = engine.sensitivity("contact_cost", [1.0, 5.0, 20.0])
    counts = [r["customers_to_contact"] for r in rows]
    assert counts == sorted(counts, reverse=True)
    with pytest.raises(ValueError, match="parameter"):
        engine.sensitivity("nonsense", [1.0])


def test_opt_outs_are_never_contacted(engine):
    first = engine.plan()
    chosen = engine.plans[first["plan_id"]]
    victim = chosen.index[chosen.plan.selected][0]
    engine.suppression.add(victim)
    again = engine.plan()
    stored = engine.plans[again["plan_id"]]
    assert victim not in set(stored.index[stored.plan.selected])
    assert again["removed_by_rule"]["opted_out"] == 1


def test_evaluate_reports_real_result_with_interval(engine):
    plan = engine.plan(contact_cost=10.0)
    ev = engine.evaluate(plan["plan_id"], n_boot=30)
    assert ev["profit_ci_95"][0] <= ev["real_incremental_profit"] <= ev["profit_ci_95"][1]
    assert ev["real_spend"] < ev["contact_everyone_spend"]
    # built-in truth: only lapsed customers respond, so targeting must beat contacting everyone
    assert ev["profit_gain_vs_contact_everyone"] > 0
    assert "imputed" in ev["money_caveat"]


def test_fairness_holdout_and_explanation(engine):
    plan = engine.plan()
    fair = engine.fairness(plan["plan_id"])
    assert set(fair["gender"]["selection_rate_by_group"]) >= {"female", "male"}
    assert fair["gender"]["lowest_over_highest_rate"] > 0.8  # gender is pure noise here
    hold = engine.design_holdout(plan["plan_id"], minimum_detectable_uplift=0.10)
    assert hold["feasible"] and 0 < hold["holdout_share"] <= 0.5
    cid = engine.customers.index[0]
    exp = engine.explain_customer(cid)
    assert exp["decision"] in ("contact", "do not contact") and "break-even" in exp["reason"]
    with pytest.raises(KeyError):
        engine.explain_customer("nobody")


def test_export_is_blocked_without_human_approval(engine, tmp_path):
    plan = engine.plan()
    pid = plan["plan_id"]
    with pytest.raises(ApprovalRequired):
        engine.export(pid, "guess", out_dir=tmp_path)
    engine.request_approval(pid)
    with pytest.raises(ApprovalRequired):
        engine.export(pid, "guess", out_dir=tmp_path)  # requested, not approved
    with pytest.raises(ApprovalRequired):
        engine.human_approve(pid, "  ")
    code = engine.human_approve(pid, "Marketing manager")
    with pytest.raises(ApprovalRequired):
        engine.export(pid, "wrong-code", out_dir=tmp_path)
    res = engine.export(pid, code, holdout_share=0.2, out_dir=tmp_path)
    audience = pd.read_csv(res["file"])
    assert len(audience) == plan["customers_to_contact"]
    assert set(audience["group"]) == {"send", "holdout_do_not_send"}
    assert res["customers_in_holdout"] == (audience["group"] == "holdout_do_not_send").sum()
    manifest = json.loads((tmp_path / pid / "plan.json").read_text())
    assert manifest["approved_by"] == "Marketing manager"


# ---------------------------------------------------------------------- guardrails
def test_copy_guard_accepts_clean_and_rejects_manipulative_copy():
    offer = Offer(brand="FreshMart")
    good = "FreshMart: thanks for shopping with us. Fresh picks are in store this week. Reply STOP to opt out."
    assert check_copy(good, offer).ok
    bad = {
        "FreshMart: LAST CHANCE! Only 3 left, hurry. Reply STOP to opt out.": "urgency",
        "FreshMart: get 50% off today. Reply STOP to opt out.": "number",
        "FreshMart: we noticed you stopped coming. Reply STOP to opt out.": "surveillance",
        "FreshMart: fresh picks this week in store.": "opt-out",
        "Fresh picks this week. Reply STOP to opt out.": "brand",
        "FreshMart: see http://x.co now. Reply STOP to opt out.": "links",
        "FreshMart: " + "great food " * 20 + "Reply STOP to opt out.": "too long",
    }
    for text, expected in bad.items():
        verdict = check_copy(text, offer)
        assert not verdict.ok, text
        assert any(expected in p for p in verdict.problems), (text, verdict.problems)


def test_real_deadline_and_listed_numbers_are_allowed():
    offer = Offer(brand="FreshMart", allowed_numbers=["10%"], deadline="30 November")
    ok = "FreshMart: 10% off fruit until 30 November. Reply STOP to opt out."
    assert check_copy(ok, offer).ok
    assert not check_copy(ok.replace("10%", "20%"), offer).ok


def test_fallback_templates_always_pass():
    offer = Offer()
    for segment in rfm.SEGMENT_ORDER:
        assert check_copy(fallback_template(segment, offer), offer).ok


def test_grounding_flags_invented_numbers():
    tools = [
        {
            "customers_to_contact": 143100,
            "share_contacted": 0.7152,
            "real_incremental_profit": 739812.4,
            "profit_ci_95": [238365, 1228794],
        }
    ]
    ok = (
        "Contact 143,100 customers (71.5%). Real incremental profit about 740,000 RUB "
        "(95% interval 238,365 to 1,228,794)."
    )
    rep = check_grounding(ok, tools)
    assert rep.ok and rep.checked >= 5
    bad = check_grounding("Profit will be 2,500,000 RUB, a 340% return.", tools)
    assert not bad.ok and len(bad.ungrounded) == 2
    assert check_grounding("No numbers here.", tools).rate == 1.0
    # plan ids and dates are identifiers, not quantities
    assert check_grounding("See plan-1a2b3c4d, send on 2026-11-23.", tools).ok


# --------------------------------------------------------------------------- agent
def test_scripted_agent_runs_full_workflow_and_waits_for_human(engine, tmp_path):
    agent = Agent(
        Toolbox(engine, llm=None, offline=True), llm=None, audit=AuditLog(tmp_path / "audit.jsonl")
    )
    run = agent.run("Plan next campaign", history=None)
    assert run.mode == "scripted"
    names = [s.tool for s in run.steps]
    assert names == [
        "get_experiment_readout",
        "plan_campaign",
        "evaluate_plan",
        "audit_fairness",
        "design_holdout",
        "schedule_campaign",
        "draft_messages",
        "request_approval",
    ]
    assert run.pending_approval == run.plan_ids[0]
    assert run.grounding is not None and run.grounding.ok, run.grounding.ungrounded
    assert "waiting for human approval" in run.answer
    # every drafted message passed the guard
    drafts = next(s.result for s in run.steps if s.tool == "draft_messages")
    assert all(m["passed_checks"] for m in drafts["messages"].values())
    # the action tool refuses until a human approves
    blocked = agent.toolbox.call("export_audience", {"plan_id": run.pending_approval})
    assert blocked["blocked_by"] == "human approval gate"
    engine.human_approve(run.pending_approval, "Manager")
    done = agent.toolbox.call("export_audience", {"plan_id": run.pending_approval})
    assert done["status"] == "exported"
    events = [e["event"] for e in agent.audit.read()]
    assert events.count("tool") == len(run.steps) and "answer" in events


def test_invented_arguments_are_dropped_by_the_provenance_guard():
    said = "Plan a campaign. A message costs 6 RUB, margin 25%, budget 1,000,000 BRL."
    kept, dropped = Agent._provenance(
        {
            "contact_cost": 6,
            "margin": 0.25,
            "budget": 1000000,
            "budget_currency": "BRL",
            "discount": 0.03,
            "fair_mode": True,
        },
        said,
    )
    assert kept == {"contact_cost": 6, "margin": 0.25, "budget": 1000000, "budget_currency": "BRL"}
    assert dropped == {"discount": 0.03, "fair_mode": True}
    kept, dropped = Agent._provenance(
        {"contact_cost": 15, "discount": 0.03, "margin": 0.25, "budget_currency": "USD"},
        "Plan our next campaign with the usual costs.",
    )
    assert kept == {} and set(dropped) == {"contact_cost", "discount", "margin", "budget_currency"}


def test_demographic_targeting_is_refused(engine):
    box = Toolbox(engine, offline=True)
    res = box.call("plan_campaign", {"segments": ["Women over 60"]})
    assert "personal attribute" in res["error"]
    ok = box.call("plan_campaign", {"segments": ["Hibernating"]})
    assert ok["customers_to_contact"] > 0
    assert set(ok["contacted_by_rfm_segment"]) >= {"Hibernating"}


def test_toolbox_returns_errors_as_data(engine):
    box = Toolbox(engine, offline=True)
    assert "error" in box.call("no_such_tool", {})
    assert "error" in box.call("evaluate_plan", {"plan_id": "plan-missing"})
    assert "error" in box.call("plan_campaign", {"margin": 5})
    names = {t["function"]["name"] for t in box.schemas()}
    assert {"plan_campaign", "evaluate_plan", "export_audience", "draft_messages"} <= names
    assert box.tools["export_audience"].privilege == "action"
