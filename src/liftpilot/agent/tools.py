"""The agent's tools: the only way it can learn a fact or do anything.

Each tool is a thin, documented wrapper over ``CampaignEngine`` or a live
feed. Tools are split by privilege:

* ``read``    - facts and analysis; run freely;
* ``propose`` - creates a plan or a draft; nothing leaves the system;
* ``action``  - writes the audience file; refused unless a human approved.

The same registry is served to the language model (as JSON schemas) and to the
scripted planner, so both are bound by the same rules.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from liftpilot import live
from liftpilot.agent.copy_guard import (
    SEGMENT_ANGLE,
    Offer,
    check_copy,
    fallback_template,
)
from liftpilot.agent.llm import LLMUnavailable, OllamaClient
from liftpilot.engine import ApprovalRequired, CampaignEngine
from liftpilot.rfm import SEGMENT_DESCRIPTION

COUNTRY_OF_DATASET = {"x5": "RU", "hillstrom": "US"}


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]
    privilege: str = "read"

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": [k for k, v in self.parameters.items() if v.pop("required", False)],
                },
            },
        }


def _num(desc: str, required: bool = False) -> dict[str, Any]:
    return {"type": "number", "description": desc, "required": required}


def _str(desc: str, required: bool = False) -> dict[str, Any]:
    return {"type": "string", "description": desc, "required": required}


class Toolbox:
    def __init__(
        self,
        engine: CampaignEngine,
        llm: OllamaClient | None = None,
        offer: Offer | None = None,
        offline: bool = False,
    ) -> None:
        self.engine = engine
        self.llm = llm
        self.offer = offer or Offer()
        self.offline = offline
        self.tools: dict[str, Tool] = {t.name: t for t in self._build()}
        self._schemas = [t.schema() for t in self.tools.values()]

    # ------------------------------------------------------------------ registry
    def schemas(self) -> list[dict[str, Any]]:
        return self._schemas

    def call(self, name: str, args: dict[str, Any] | None) -> Any:
        """Run a tool. Errors come back as data so the model can correct itself."""
        if name not in self.tools:
            return {"error": f"unknown tool '{name}'", "available": sorted(self.tools)}
        try:
            clean = {k: v for k, v in (args or {}).items() if v is not None and v != ""}
            return self.tools[name].handler(**clean)
        except ApprovalRequired as exc:
            return {"error": str(exc), "blocked_by": "human approval gate"}
        except (TypeError, ValueError, KeyError) as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}

    # --------------------------------------------------------------------- tools
    def _plan(
        self,
        budget: float | None = None,
        budget_currency: str | None = None,
        margin: float | None = None,
        contact_cost: float | None = None,
        discount: float | None = None,
        segments: list[str] | None = None,
        safety_margin: float = 0.0,
        fair_mode: bool = False,
    ) -> dict[str, Any]:
        fx = None
        if (
            budget is not None
            and budget_currency
            and (budget_currency.upper() != self.engine.currency)
        ):
            fx = live.convert(float(budget), budget_currency, self.engine.currency, self.offline)
            if "error" in fx:
                return {"error": fx["error"]}
            budget = float(fx["amount"])
        if isinstance(segments, str):
            segments = [s.strip() for s in segments.split(",") if s.strip()]
        out = self.engine.plan(
            margin=margin,
            contact_cost=contact_cost,
            discount=discount,
            budget=budget,
            segments=segments,
            safety_margin=float(safety_margin or 0.0),
            equal_value=str(fair_mode).lower() in ("true", "1", "yes"),
        )
        if fx:
            out["budget_conversion"] = fx
        return out

    def _schedule(self, country: str | None = None, earliest_date: str | None = None) -> Any:
        cc = country or COUNTRY_OF_DATASET.get(self.engine.dataset, "US")
        tomorrow = datetime.now(UTC).date() + timedelta(days=1)
        try:
            start = date.fromisoformat(earliest_date) if earliest_date else tomorrow
        except ValueError:
            start = tomorrow
        # a campaign cannot be scheduled in the past, whatever date was passed
        return live.schedule_send(cc, max(start, tomorrow), offline=self.offline)

    def _convert(self, amount: float, from_currency: str, to_currency: str) -> Any:
        return live.convert(float(amount), from_currency, to_currency, self.offline)

    def _draft(
        self, plan_id: str, offer_text: str | None = None, deadline: str | None = None
    ) -> dict[str, Any]:
        sp = self.engine._get(plan_id)
        offer = self.offer.model_copy(
            update={k: v for k, v in {"offer_text": offer_text, "deadline": deadline}.items() if v}
        )
        if self.engine.approval_status(plan_id) == "approved":
            raise ApprovalRequired(
                "messages cannot be redrafted after the plan was approved: the approver has not "
                "seen the new wording. Create a new plan and ask for approval again."
            )
        # the offer wording comes from the manager or the model: it must itself be clean
        probe = check_copy(f"{offer.brand}: {offer.offer_text}. {offer.opt_out}.", offer)
        if not probe.ok:
            raise ValueError(
                "the offer text was refused by the copy checks: "
                + "; ".join(probe.problems)
                + ". Numbers and deadlines must be on the approved offer sheet."
            )
        by_seg = sp.summary.get(
            "contacted_by_rfm_segment",
            {"All customers": {"contacted": sp.plan.n_selected}},
        )
        results: dict[str, Any] = {}
        for segment, info in by_seg.items():
            if info["contacted"] == 0:
                continue
            text, origin, problems = "", "template", []
            if self.llm is not None:
                try:
                    text, origin, problems = self._draft_one(segment, offer)
                except LLMUnavailable:
                    text = ""
            if not text:
                text, origin = fallback_template(segment, offer), "pre-approved template"
            verdict = check_copy(text, offer)
            if not verdict.ok:  # a template must always pass; last line of defence
                text, origin = f"{offer.brand}: {offer.offer_text}. {offer.opt_out}.", "minimal"
                verdict = check_copy(text, offer)
            if verdict.ok:  # a message that fails the checks is never stored
                sp.messages[segment] = text
            else:
                sp.messages.pop(segment, None)
            results[segment] = {
                "customers": info["contacted"],
                "message": text,
                "characters": len(text),
                "written_by": origin,
                "passed_checks": verdict.ok,
                "rejected_draft_reasons": problems,
            }
        return {
            "plan_id": plan_id,
            "channel": offer.channel,
            "offer": offer.offer_text,
            "checks": "length, opt-out, brand named, no unlisted numbers, no pressure tactics, "
            "no sensitive attributes, no links",
            "messages": results,
            "status": "drafts only; nothing is sent",
        }

    def _draft_one(self, segment: str, offer: Offer) -> tuple[str, str, list[str]]:
        assert self.llm is not None
        system = (
            "You write one short, honest text message for a shop's own customers. "
            "Output only the message text, nothing else."
        )
        ask = (
            f"Sender: {offer.brand}. Audience: customers in the '{segment}' group "
            f"({SEGMENT_DESCRIPTION.get(segment, '')}). Angle: {SEGMENT_ANGLE.get(segment, 'friendly')}. "
            f"What we offer: {offer.offer_text}. "
            f"{'Valid until ' + offer.deadline + '. ' if offer.deadline else ''}"
            f"Tone: {offer.tone}. Rules: at most {offer.max_chars - 10} characters; start with "
            f"'{offer.brand}:'; end with '{offer.opt_out}.'; no numbers"
            f"{' except ' + ', '.join(offer.allowed_numbers) if offer.allowed_numbers else ''}; "
            "no urgency, no pressure, no promises, no links; do not mention how you know anything "
            "about the customer."
        )
        problems: list[str] = []
        for _ in range(2):
            text = self.llm.complete(system, ask, max_tokens=120).strip().strip('"').strip()
            text = " ".join(text.split())
            verdict = check_copy(text, offer)
            if verdict.ok:
                return text, "language model, passed checks", problems
            problems = verdict.problems
            ask += f"\nYour previous draft was rejected: {'; '.join(problems)}. Write a new one."
        return "", "template", problems

    def _export(self, plan_id: str, holdout_share: float = 0.1) -> dict[str, Any]:
        status = self.engine.approval_status(plan_id)
        if status != "approved":
            raise ApprovalRequired(
                f"plan {plan_id} is '{status}'. A human must approve it in the interface first."
            )
        code = self.engine._approvals[plan_id]["code"]
        return self.engine.export(plan_id, code, holdout_share=float(holdout_share))

    def _build(self) -> list[Tool]:
        e = self.engine
        cur = e.currency
        return [
            Tool(
                "get_data_profile",
                "What customer data exists: size, time window, currency, caveats.",
                {},
                e.data_profile,
            ),
            Tool(
                "get_experiment_readout",
                "Result of the past randomised test (contacted vs held out): purchase rates, "
                "uplift, confidence interval, p-value.",
                {},
                e.experiment_readout,
            ),
            Tool(
                "get_rfm_segments",
                "RFM segments (Champions, At risk, ...) with size, behaviour and the uplift "
                "actually measured in each.",
                {},
                e.rfm_segments,
            ),
            Tool(
                "get_model_report",
                "Quality of the uplift models on unseen customers (Qini with confidence "
                "intervals), the chosen model and customer types.",
                {},
                e.model_report,
            ),
            Tool(
                "get_baseline_policies",
                "Real incremental profit of standard targeting rules (contact everyone, best "
                "RFM customers, likely buyers, ...) at default costs.",
                {},
                e.baseline_policies,
            ),
            Tool(
                "plan_campaign",
                "Choose which customers to contact to maximise expected incremental profit. "
                f"Money is in {cur} unless budget_currency says otherwise. Returns a plan_id.",
                {
                    "budget": _num("maximum total spend. ONLY if the manager stated a budget"),
                    "budget_currency": _str(
                        f"currency of the stated budget, e.g. BRL, USD; default {cur}"
                    ),
                    "margin": _num("gross margin as a fraction, e.g. 0.25. ONLY if stated"),
                    "contact_cost": _num(f"cost of one message in {cur}. ONLY if stated"),
                    "discount": _num(
                        "discount to buyers as a fraction of basket, e.g. 0.03. ONLY if the "
                        "manager said the message carries a discount; must be below margin"
                    ),
                    "segments": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "ONLY if the manager asked to restrict the "
                        "campaign to named RFM segments",
                    },
                    "fair_mode": {
                        "type": "boolean",
                        "description": "true ONLY if the manager asks for fair mode / equal treatment "
                        "of small and large spenders",
                    },
                },
                self._plan,
                "propose",
            ),
            Tool(
                "evaluate_plan",
                "Evidence for a plan: replays its rule on held-out randomised customers and "
                "returns the REAL incremental profit with a 95% interval, versus contacting "
                "everyone.",
                {"plan_id": _str("id returned by plan_campaign", True)},
                e.evaluate,
            ),
            Tool(
                "run_sensitivity",
                "Re-plan under several values of one assumption (margin, contact_cost, "
                "discount or budget).",
                {
                    "parameter": _str("margin | contact_cost | discount | budget", True),
                    "values": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "values to try",
                        "required": True,
                    },
                },
                e.sensitivity,
            ),
            Tool(
                "audit_fairness",
                "Selection rate of a plan by gender and age band, and whether any gap needs "
                "human review.",
                {"plan_id": _str("plan to audit", True)},
                e.fairness,
            ),
            Tool(
                "design_holdout",
                "Size of the random hold-out group needed to measure the next campaign's real "
                "uplift.",
                {
                    "plan_id": _str("plan to measure", True),
                    "minimum_detectable_uplift": _num("smallest uplift to detect, e.g. 0.02"),
                },
                e.design_holdout,
            ),
            Tool(
                "explain_customer",
                "Why one customer is or is not contacted: RFM, uplift, break-even uplift, "
                "expected profit.",
                {"client_id": _str("customer id", True), "plan_id": _str("optional plan")},
                e.explain_customer,
            ),
            Tool(
                "schedule_campaign",
                "LIVE public-holiday calendar: recommended send date and measurement window.",
                {
                    "country": _str("ISO country code, e.g. RU, BR, US"),
                    "earliest_date": _str("YYYY-MM-DD"),
                },
                self._schedule,
            ),
            Tool(
                "convert_currency",
                "LIVE exchange rate conversion (central-bank reference rates).",
                {
                    "amount": _num("amount", True),
                    "from_currency": _str("e.g. RUB", True),
                    "to_currency": _str("e.g. BRL", True),
                },
                self._convert,
            ),
            Tool(
                "draft_messages",
                "Draft one personalised message per RFM segment of a plan. Drafts are checked "
                "by code (length, opt-out, no invented numbers, no pressure tactics).",
                {
                    "plan_id": _str("plan", True),
                    "offer_text": _str("what the message offers, in plain words"),
                    "deadline": _str("real end date of the offer, if any"),
                },
                self._draft,
                "propose",
            ),
            Tool(
                "request_approval",
                "Ask the human marketing manager to approve a plan. Always required before "
                "any export.",
                {"plan_id": _str("plan", True)},
                e.request_approval,
                "propose",
            ),
            Tool(
                "export_audience",
                "Write the approved audience file for the messaging tool, with a random "
                "hold-out group. Fails unless a human approved the plan.",
                {
                    "plan_id": _str("approved plan", True),
                    "holdout_share": _num("share kept uncontacted for measurement, default 0.1"),
                },
                self._export,
                "action",
            ),
        ]
