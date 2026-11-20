"""The agent loop: think -> call a tool -> read the result -> repeat -> answer.

Design choices that keep the agent useful rather than decorative:

* It is a **utility-based agent**: its goal is a number (incremental profit)
  and its tools let it compute, test and act on that number.
* It cannot do arithmetic or invent facts: numbers come from tools, and a
  grounding check rejects any number that no tool produced.
* It cannot spend or send: the only action tool refuses to run until a human
  approved the plan in the interface.
* Every step is appended to an audit log (who asked, which tool, which
  arguments, a fingerprint of the result), so a run can be reviewed later.
* If the local model is not running, a scripted planner drives the same tools
  in a fixed order, so the system degrades to "automation" instead of failing.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from liftpilot import config
from liftpilot.agent.grounding import (
    CURRENCY_WORDS,
    GroundingReport,
    check_grounding,
    stated_amounts,
)
from liftpilot.agent.llm import LLMUnavailable, OllamaClient
from liftpilot.agent.report import bypass_advice, overclaims, status_claims, verified_statements
from liftpilot.agent.tools import Toolbox

SYSTEM_PROMPT = """You are LiftPilot, a campaign-planning agent for a retailer's marketing manager.

Goal: maximise INCREMENTAL profit, the profit that exists only because a customer was contacted. \
Customers who would buy anyway, or who will not buy either way, should not be contacted.

How you work:
- You have tools. Every fact and every number must come from a tool result. Never calculate, \
estimate or invent numbers; quote them as the tools return them.
- To plan a campaign, call the tools in this order: plan_campaign, evaluate_plan, \
audit_fairness, design_holdout, schedule_campaign, draft_messages, request_approval. Start with \
plan_campaign straight away. Use the other tools only when the manager asks about data, \
segments, models, one customer or what-if questions.
- ARGUMENTS: pass ONLY values the manager stated in this conversation. If the manager gave no \
budget, do not pass budget. If the manager mentioned no discount, do not pass discount. Do not \
pass segments unless the manager asked to restrict the campaign. Percentages become fractions \
(25% -> 0.25). If the budget is in another currency, pass budget_currency.
- If a tool returns an error, correct the arguments and call the tool again.
- You may not send messages or spend money. You prepare the plan and ask for approval. Only \
call export_audience after the manager says the plan was approved.

How you answer (short, plain business English, no tables):
1. Decision: how many customers to contact, how many to leave alone, and why they are left.
2. Evidence: what the model EXPECTS, then what the experiment replay REALLY showed \
(evaluate_plan) with its 95% interval, and the comparison with contacting everyone.
3. Safeguards: fairness result, hold-out size, send date.
4. Messages: say that drafts per segment are ready (do not repeat them all).
5. Next step: the plan waits for the manager's approval; nothing has been sent.
Mention the main caveat of the data once.
"""

EVIDENCE_STEPS = ["evaluate_plan", "audit_fairness"]
CAMPAIGN_STEPS = [
    *EVIDENCE_STEPS,
    "design_holdout",
    "schedule_campaign",
    "draft_messages",
    "request_approval",
]
CAMPAIGN_WORDS = ("campaign", "plan", "launch", "prepare", "send", "contact", "target")

MAX_TOOL_CHARS = 6000


@dataclass
class Step:
    tool: str
    args: dict[str, Any]
    result: Any
    seconds: float
    privilege: str


@dataclass
class AgentRun:
    run_id: str
    request: str
    mode: str  # "llm" or "scripted"
    steps: list[Step] = field(default_factory=list)
    answer: str = ""
    grounding: GroundingReport | None = None
    plan_ids: list[str] = field(default_factory=list)
    pending_approval: str | None = None
    seconds: float = 0.0
    messages: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    said: str = ""  # everything the manager wrote in this conversation
    statements: list[str] = field(default_factory=list)
    overclaims: list[str] = field(default_factory=list)
    rejected_narrative: str | None = None
    # what the runtime had to do itself, kept so that a test run can show which guard fired
    nudges: int = 0
    forced_steps: list[str] = field(default_factory=list)
    first_draft_problems: list[str] = field(default_factory=list)

    def tool_results(self) -> list[Any]:
        return [s.result for s in self.steps]


class AuditLog:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (config.runs_dir() / "audit.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, run_id: str, event: str, **data: Any) -> None:
        rec = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "run_id": run_id,
            "event": event,
            **data,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")

    def read(self, last: int = 200) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()[-last:]
        return [json.loads(line) for line in lines if line.strip()]


def _fingerprint(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _compact(obj: Any) -> str:
    text = json.dumps(obj, default=str, separators=(",", ":"))
    return text if len(text) <= MAX_TOOL_CHARS else text[:MAX_TOOL_CHARS] + '..."(truncated)"'


class Agent:
    def __init__(
        self,
        toolbox: Toolbox,
        llm: OllamaClient | None = None,
        audit: AuditLog | None = None,
        max_steps: int = 14,
    ) -> None:
        self.toolbox = toolbox
        self.llm = llm
        self.audit = audit or AuditLog()
        self.max_steps = max_steps

    # ---------------------------------------------------------------- plumbing
    @staticmethod
    def _provenance(
        args: dict[str, Any], said: str, data_currency: str = ""
    ) -> tuple[dict[str, Any], dict[str, Any], str | None]:
        """Keep only planning assumptions the manager actually stated.

        A language model asked to "use the usual costs" will happily supply a
        cost of its own. Money assumptions are therefore accepted only if the
        same number appears in the manager's words (as written, as a
        percentage, or with a unit such as "1 million" or "50k"); anything
        else is dropped and the system default applies.

        A budget is a spending limit, so it is never guessed: if the amount or
        its currency cannot be matched to the manager's words, no plan is made
        and the third return value says what to clarify.
        """
        stated = stated_amounts(said)
        text = said.lower()
        mentioned = {iso for iso, words in CURRENCY_WORDS.items() if any(w in text for w in words)}
        kept: dict[str, Any] = {}
        dropped: dict[str, Any] = {}
        for key, value in args.items():
            ok = True
            if key in ("margin", "contact_cost", "discount", "budget", "safety_margin"):
                try:
                    v = float(value)
                except (TypeError, ValueError):
                    ok = False
                else:
                    ok = any(abs(v - s) < 1e-9 or abs(v * 100 - s) < 1e-6 for s in stated)
            elif key == "budget_currency":
                ok = str(value).upper() in mentioned
            elif key == "fair_mode":
                ok = (
                    (str(value).lower() not in ("true", "1", "yes"))
                    or "fair" in text
                    or ("equal" in text)
                )
            (kept if ok else dropped)[key] = value
        problem = None
        foreign = mentioned - {data_currency.upper()}
        if "budget" in dropped:
            problem = (
                f"budget {dropped['budget']} does not match any amount in the manager's "
                "request. Pass the budget exactly as stated, or ask the manager to restate it."
            )
        elif "budget" in kept and "budget_currency" not in kept and foreign:
            problem = (
                "the request states a budget in a foreign currency "
                f"({', '.join(sorted(foreign))}); pass budget_currency with that ISO code."
            )
        elif "budget" not in kept and re.search(r"\bbudget of\b|\bbudget is\b|\bbudget:", text):
            problem = "the manager stated a budget; pass it as `budget` (with budget_currency)."
        if "budget" not in kept:
            kept.pop("budget_currency", None)
        return kept, dropped, problem

    @staticmethod
    def _holdout_provenance(
        args: dict[str, Any], said: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Keep a detection target for the hold-out only if the manager stated it.

        The stress test showed the model filling ``minimum_detectable_uplift``
        with a value of its own (the example from the tool description, or a
        figure it picked), and not the same one each time: the same request
        gave hold-outs of different sizes. Same rule as for money assumptions:
        a value the manager did not write is dropped and the system default
        (the mean expected uplift of the selected customers) applies.

        "Stated" is strict here. The value must be a fraction between 0 and 1,
        and the manager must have written it next to detection wording ("detect
        an uplift of 2%", "a 2% uplift"). A number written for something else,
        such as the 6 of "6 RUB" or the 25 of "margin 25%", does not count.
        The wording is matched in English only: a target stated in another
        language is dropped and the default applies.
        """
        key = "minimum_detectable_uplift"
        if key not in args:
            return args, {}
        try:
            v = float(args[key])
        except (TypeError, ValueError):
            v = float("nan")
        ok = False
        if 0 < v < 1:
            unit = r"\s*(?:%|per ?cent|percent(?:age)? points?|points?|pp\b)"
            forms = [re.escape(f"{v * 100:.6g}") + unit, re.escape(f"{v:.6g}") + r"(?![\d%])"]
            for num in (r"(?<![\d.,])" + f for f in forms):
                if re.search(
                    r"(?:detect|uplift|lift|effect)[^.;\n]{0,40}?" + num, said, re.I
                ) or re.search(num + r"\s+(?:of\s+)?(?:uplift|lift|effect)", said, re.I):
                    ok = True
        if ok:
            return args, {}
        return {k: a for k, a in args.items() if k != key}, {key: args[key]}

    def _execute(self, run: AgentRun, name: str, args: dict[str, Any]) -> Any:
        start = time.perf_counter()
        dropped: dict[str, Any] = {}
        problem = None
        if name == "plan_campaign" and run.mode == "llm":
            args, dropped, problem = self._provenance(
                args, run.said or run.request, self.toolbox.engine.currency
            )
        elif name == "design_holdout" and run.mode == "llm":
            args, dropped = self._holdout_provenance(args, run.said or run.request)
        result = {"error": problem} if problem else self.toolbox.call(name, args)
        if dropped and isinstance(result, dict) and not problem:
            result["ignored_arguments"] = {
                "values": dropped,
                "reason": "not stated by the manager; system defaults were used instead",
            }
        tool = self.toolbox.tools.get(name)
        step = Step(
            name,
            args,
            result,
            round(time.perf_counter() - start, 3),
            tool.privilege if tool else "unknown",
        )
        run.steps.append(step)
        if isinstance(result, dict):
            pid = result.get("plan_id")
            if pid and pid not in run.plan_ids and "error" not in result:
                run.plan_ids.append(pid)
            if result.get("status") == "pending_human_approval":
                run.pending_approval = pid
        self.audit.write(
            run.run_id,
            "tool",
            tool=name,
            args=args,
            privilege=step.privilege,
            seconds=step.seconds,
            result_sha256=_fingerprint(result),
            error=result.get("error") if isinstance(result, dict) else None,
        )
        return result

    def _missing_steps(self, run: AgentRun) -> tuple[str | None, list[str]]:
        """Checklist enforced by the runtime, not left to the model's goodwill.

        Any plan the agent creates must come with evidence and a fairness audit.
        A campaign run must also reach the human-approval step.

        A run is a campaign run when the model itself called ``plan_campaign``
        and got a plan, whatever language the request is in. The stress test
        showed why the request's words are not enough: the same request in
        Arabic contains none of the English keywords, so the run stopped after
        the fairness audit. The keywords stay as a second trigger.
        """
        if not run.plan_ids:
            return None, []
        pid = run.plan_ids[-1]
        done = {
            s.tool
            for s in run.steps
            if not (isinstance(s.result, dict) and "error" in s.result)
            and (s.args.get("plan_id") == pid or s.tool == "schedule_campaign")
        }
        planned = any(
            s.tool == "plan_campaign"
            and isinstance(s.result, dict)
            and "error" not in s.result
            and s.result.get("plan_id") == pid
            for s in run.steps
        )
        text = run.request.lower()
        wants_campaign = (
            planned
            or any(w in text for w in CAMPAIGN_WORDS)
            or bool(done & {"draft_messages", "request_approval", "design_holdout"})
        )
        required = CAMPAIGN_STEPS if wants_campaign else EVIDENCE_STEPS
        return pid, [s for s in required if s not in done]

    @staticmethod
    def _narration_prompt(run: AgentRun) -> list[dict[str, Any]]:
        """Ask the model to narrate verified statements; it gets no raw JSON here."""
        facts = "\n".join(f"- {s}" for s in run.statements)
        return [
            {
                "role": "system",
                "content": (
                    "You are LiftPilot, a campaign-planning agent. You write a short briefing for a "
                    "marketing manager from verified statements. Keep every number and its meaning "
                    "exactly; copy numbers digit for digit. Do not add facts, numbers, or words of "
                    "certainty such as 'significant' or 'guaranteed'. Nothing has been sent yet: "
                    "messages are drafts waiting for approval. Plain business English."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"The manager asked: {run.request}\n\nVERIFIED STATEMENTS:\n{facts}\n\n"
                    "Write the briefing in five short parts with these bold labels: **Decision**, "
                    "**Evidence**, **Safeguards**, **Messages**, **Next step**. In Evidence, give "
                    "what the model expects, then what the experiment replay showed with its "
                    "interval, then the comparison with contacting everyone. End with the caveat. "
                    "About 150 words."
                ),
            },
        ]

    def _loud(self, answer: str, run: AgentRun, pid: str | None) -> list[str]:
        """Wording the evidence does not support: over-confident words, sentences
        saying a plan was approved or exported when neither happened, and advice
        to go ahead without approval.

        "Happened" is judged for the plans of this run only (the ones it made
        or named in a tool call). An approval given to another plan earlier in
        the same session does not make the sentence true for this one.
        """
        found = overclaims(answer, run.steps, pid)
        engine = self.toolbox.engine
        mine = {
            *run.plan_ids,
            *(s.args.get("plan_id") for s in run.steps if isinstance(s.args, dict)),
        }
        happened = any(
            s.tool == "export_audience"
            and isinstance(s.result, dict)
            and s.result.get("status") == "exported"
            for s in run.steps
        ) or any(
            engine.approval_status(p) == "approved"
            for p in mine
            if isinstance(p, str) and p in engine.plans
        )
        if not happened:
            found += [f'"{s}" (nothing was approved or exported)' for s in status_claims(answer)]
            found += [f'"{s}" (approval cannot be skipped)' for s in bypass_advice(answer)]
        return found

    def _finish(self, run: AgentRun, started: float) -> AgentRun:
        sources: list[Any] = [*run.tool_results(), run.request]
        pid = run.plan_ids[-1] if run.plan_ids else None
        if not run.statements:
            run.statements = verified_statements(run.steps, pid)
        run.overclaims = self._loud(run.answer, run, pid) if run.mode == "llm" else []
        run.grounding = check_grounding(run.answer, sources)
        run.seconds = round(time.perf_counter() - started, 2)
        self.audit.write(
            run.run_id,
            "answer",
            mode=run.mode,
            chars=len(run.answer),
            numbers_checked=run.grounding.checked,
            numbers_grounded=run.grounding.grounded,
            ungrounded=run.grounding.ungrounded,
            seconds=run.seconds,
            pending_approval=run.pending_approval,
        )
        return run

    # --------------------------------------------------------------------- run
    def run(self, request: str, history: list[dict[str, Any]] | None = None) -> AgentRun:
        """Answer one request, using the local model if it is available."""
        run = AgentRun(run_id=uuid.uuid4().hex[:10], request=request, mode="llm")
        started = time.perf_counter()
        self.audit.write(run.run_id, "request", text=request)
        if self.llm is None or not self.llm.available():
            text = request.lower()
            has_assumptions = bool(stated_amounts(request) - {float(i) for i in range(11)}) or any(
                w in text for words in CURRENCY_WORDS.values() for w in words
            )
            if has_assumptions:
                # without the model nothing can read assumptions out of free text, and
                # planning on defaults while the request names other figures would mislead
                run.mode = "scripted"
                run.error = "local model not available"
                run.answer = (
                    "The local language model is not running, so the costs or budget written in "
                    "this request cannot be read. No plan was made. Set the assumptions with the "
                    "controls in the Optimizer tab and use the scripted planner, or start Ollama."
                )
                return self._finish(run, started)
            run.error = "local model not available; scripted planner used with default costs"
            return self.run_scripted(request, run=run)
        run.said = " ".join(
            [str(m.get("content", "")) for m in (history or []) if m.get("role") == "user"]
            + [request]
        )
        today = datetime.now(UTC).date().isoformat()
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT + f"\nToday's date is {today}."},
            *(history or []),
            {"role": "user", "content": request},
        ]
        nudges = 0
        try:
            for _ in range(self.max_steps):
                msg = self.llm.chat(messages, tools=self.toolbox.schemas())
                calls = msg.get("tool_calls") or []
                messages.append(
                    {
                        "role": "assistant",
                        "content": msg.get("content", ""),
                        **({"tool_calls": calls} if calls else {}),
                    }
                )
                if not calls:
                    pid, missing = self._missing_steps(run)
                    if missing and nudges < 2:
                        nudges += 1
                        run.nudges = nudges
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    f"Not finished. For plan {pid} you must still call, in this order: "
                                    f"{', '.join(missing)}. Call them now, then answer."
                                ),
                            }
                        )
                        continue
                    if missing and pid:
                        # the model would not comply: the runtime completes the checklist itself
                        run.forced_steps = list(missing)
                        for name in missing:
                            result = self._execute(
                                run, name, {"plan_id": pid} if name != "schedule_campaign" else {}
                            )
                            messages.append(
                                {"role": "tool", "tool_name": name, "content": _compact(result)}
                            )
                        messages.append(
                            {
                                "role": "user",
                                "content": "All steps are done. Write the final answer now.",
                            }
                        )
                        msg = self.llm.chat(messages)
                    run.statements = verified_statements(run.steps, pid)
                    if run.statements:
                        msg = self.llm.chat(self._narration_prompt(run), max_tokens=600)
                        messages.append({"role": "assistant", "content": msg.get("content", "")})
                    run.answer = str(msg.get("content", "")).strip()
                    break
                for call in calls:
                    fn = call.get("function", {})
                    name = fn.get("name", "")
                    args = fn.get("arguments") or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except ValueError:
                            args = {}
                    result = self._execute(run, name, args)
                    messages.append(
                        {"role": "tool", "tool_name": name, "content": _compact(result)}
                    )
            else:
                run.answer = "I reached the step limit before finishing; see the tool trace."
            # one repair attempt if the answer has numbers no tool produced, or over-claims
            sources = [*run.tool_results(), request]
            check = check_grounding(run.answer, sources)
            pid = run.plan_ids[-1] if run.plan_ids else None
            loud = self._loud(run.answer, run, pid)
            if run.answer and (not check.ok or loud):
                problems = []
                if not check.ok:
                    problems.append(
                        "these numbers are not in any tool result: "
                        + ", ".join(check.ungrounded[:12])
                    )
                if loud:
                    problems.append(
                        "this wording claims more certainty than the evidence gives, or says "
                        "that something happened which did not: " + ", ".join(loud)
                    )
                run.first_draft_problems = [
                    *(f"number not in any tool result: {n}" for n in check.ungrounded),
                    *loud,
                ]
                base = self._narration_prompt(run) if run.statements else messages
                msg = self.llm.chat(
                    [
                        *base,
                        {"role": "assistant", "content": run.answer},
                        {
                            "role": "user",
                            "content": "Rewrite your answer. Problems: "
                            + "; ".join(problems)
                            + ". Keep only numbers given to you and neutral "
                            "wording.",
                        },
                    ],
                    max_tokens=600,
                )
                fixed = str(msg.get("content", "")).strip()
                better = len(check_grounding(fixed, sources).ungrounded) <= len(check.ungrounded)
                if fixed and better and len(self._loud(fixed, run, pid)) <= len(loud):
                    run.answer = fixed
                still_bad = not check_grounding(run.answer, sources).ok or self._loud(
                    run.answer, run, pid
                )
                if still_bad and run.statements:
                    # last line of defence: the narrative is discarded, the facts stand
                    run.rejected_narrative = run.answer
                    run.answer = "\n".join(f"- {s}" for s in run.statements)
        except LLMUnavailable as exc:
            run.error = str(exc)
            if not run.steps:
                return self.run_scripted(request, run=run)
            run.answer = run.answer or "The local model stopped responding; partial trace kept."
        run.messages = messages
        return self._finish(run, started)

    def run_scripted(
        self,
        request: str,
        run: AgentRun | None = None,
        budget: float | None = None,
        budget_currency: str | None = None,
        margin: float | None = None,
        contact_cost: float | None = None,
        discount: float | None = None,
    ) -> AgentRun:
        """Fixed-order plan with the same tools; no language model involved."""
        run = run or AgentRun(run_id=uuid.uuid4().hex[:10], request=request, mode="scripted")
        run.mode = "scripted"
        started = time.perf_counter()
        ex = self._execute
        args = {
            k: v
            for k, v in {
                "budget": budget,
                "budget_currency": budget_currency,
                "margin": margin,
                "contact_cost": contact_cost,
                "discount": discount,
            }.items()
            if v is not None
        }
        readout = ex(run, "get_experiment_readout", {})
        plan = ex(run, "plan_campaign", args)
        if "error" in plan:
            run.answer = f"Could not build a plan: {plan['error']}"
            return self._finish(run, started)
        pid = plan["plan_id"]
        for name in CAMPAIGN_STEPS:
            ex(run, name, {} if name == "schedule_campaign" else {"plan_id": pid})
        run.statements = verified_statements(run.steps, pid)
        run.answer = "\n".join(
            [
                f"Past test: contacting lifted the purchase rate by {readout['uplift_points']:.2%} "
                f"on average (p-value {readout['p_value']}).",
                *run.statements,
            ]
        )
        return self._finish(run, started)


def build_agent(dataset: str = "x5", use_llm: bool = True, offline: bool = False) -> Agent:
    from liftpilot.engine import CampaignEngine

    engine = CampaignEngine(dataset)
    llm = OllamaClient() if use_llm else None
    return Agent(Toolbox(engine, llm=llm, offline=offline), llm=llm)
