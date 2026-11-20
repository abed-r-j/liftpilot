"""The CHECK method, applied to one agent run before a human approves it.

The course's closing session gives a five-step method for any AI answer:
Claims, Hunt the source, Evidence and numbers, Cross-check, Keep a human
sign-off. This module writes one line per step from the tool results of a run.
No sentence here comes from the language model, and a missing field gives a
plain "not available" line instead of an error.
"""

from __future__ import annotations

from typing import Any

from liftpilot.agent.report import latest_results
from liftpilot.agent.runtime import CAMPAIGN_STEPS, _fingerprint

FAIRNESS_LINE = 0.80


def _money(x: Any, cur: str) -> str:
    return f"{x:,.0f} {cur}".strip() if isinstance(x, (int, float)) else "not available"


def check_items(run: Any, audit_events: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    """Five items: ``letter``, ``title`` (the lecture's own words) and ``text``.

    When the run made a plan but did not complete the campaign checklist, the
    missing steps are named in "Hunt the source" and again, first, in "Keep a
    human sign-off".
    """
    steps = list(getattr(run, "steps", None) or [])
    plan_ids = getattr(run, "plan_ids", None) or []
    pid = plan_ids[-1] if plan_ids else None
    r = latest_results(steps, pid) if pid else {}
    plan = r.get("plan_campaign") or {}
    ev = r.get("evaluate_plan") or {}
    fair = r.get("audit_fairness") or {}
    cur = str(plan.get("currency") or ev.get("currency") or "")

    # C - Claims
    g = getattr(run, "grounding", None)
    if g is None:
        claims = "The numbers in the briefing were not checked in this run."
    else:
        loose = [str(x) for x in (getattr(g, "ungrounded", None) or [])]
        claims = (
            f"The briefing states {getattr(g, 'checked', '?')} numbers; "
            f"{getattr(g, 'grounded', '?')} were matched to a tool result or to a number in "
            "the request."
        )
        if loose:
            claims += " Not matched, do not rely on them: " + ", ".join(loose[:8]) + "."

    # H - Hunt the source
    if not steps:
        hunt = "No tool was called in this run, so there is no source to open."
    else:
        names = ", ".join(dict.fromkeys(str(getattr(s, "tool", "?")) for s in steps))
        hunt = f"{len(steps)} tool calls ({names}). "
        if audit_events is None:
            hunt += "The audit log could not be read, so the result hashes were not compared."
        else:
            logged = {
                e.get("result_sha256")
                for e in audit_events
                if isinstance(e, dict)
                and e.get("run_id") == getattr(run, "run_id", None)
                and e.get("event") == "tool"
            }
            found = sum(_fingerprint(getattr(s, "result", None)) in logged for s in steps)
            hunt += (
                f"{found} of {len(steps)} result hashes are in the audit log. "
                "Each result can be opened under 'What the agent did'."
            )

    # steps of the campaign checklist that this run did not complete for its plan
    def for_this_plan(s: Any) -> bool:
        res = getattr(s, "result", None)
        args = getattr(s, "args", None)
        named = [d.get("plan_id") for d in (res, args) if isinstance(d, dict) and d.get("plan_id")]
        return not named or pid in named

    done = {
        getattr(s, "tool", "")
        for s in steps
        if not (isinstance(getattr(s, "result", None), dict) and "error" in s.result)
        and for_this_plan(s)
    }
    missing = [t for t in CAMPAIGN_STEPS if t not in done] if pid else []
    if missing:
        hunt += " Steps not done in this run: " + ", ".join(missing) + "."

    # E - Evidence and numbers
    ci = ev.get("profit_ci_95")
    if (
        ev
        and isinstance(ci, (list, tuple))
        and len(ci) == 2
        and all(isinstance(x, (int, float)) and x == x for x in ci)
    ):
        lo, hi = ci
        zero = (
            "the interval includes zero, so a loss is possible"
            if lo < 0 < hi
            else "the whole interval is below zero"
            if hi <= 0
            else "the interval does not include zero"
        )
        evidence = (
            f"Experiment replay: {_money(ev.get('real_incremental_profit'), cur)} incremental "
            f"profit, 95% interval {_money(lo, cur)} to {_money(hi, cur)}; {zero}."
        )
        if ev.get("money_caveat"):
            evidence += f" Caveat: {ev['money_caveat']}."
    else:
        evidence = (
            "No experiment replay in this run. The plan has only the model's own expectation "
            "behind it."
        )

    # C - Cross-check
    parts = []
    if plan and ev:
        parts.append(
            f"Model expects {_money(plan.get('expected_incremental_profit'), cur)}; the "
            f"experiment replay shows {_money(ev.get('real_incremental_profit'), cur)}."
        )
    elif plan:
        parts.append(
            f"Model expects {_money(plan.get('expected_incremental_profit'), cur)}; there is "
            "no replay to compare it with."
        )
    ratios, low = [], []
    for key, label in (("gender", "gender"), ("age_band", "age band")):
        block = fair.get(key) if isinstance(fair, dict) else None
        ratio = block.get("lowest_over_highest_rate") if isinstance(block, dict) else None
        if isinstance(ratio, (int, float)):
            ratios.append(f"{label} {ratio:.2f}")
            if ratio < FAIRNESS_LINE:
                low.append(label)
    if ratios:
        parts.append(
            f"Fairness ratios against the {FAIRNESS_LINE:.2f} line: {', '.join(ratios)}; "
            + (f"under the line: {', '.join(low)}." if low else "none is under the line.")
        )
    else:
        parts.append("No fairness audit in this run.")
    cross = " ".join(parts)

    # K - Keep a human sign-off
    keep = (
        "Nothing is exported until a named person approves. The approval and the name are "
        "written to the audit log."
    )
    if missing:
        keep = (
            "Steps not done in this run: "
            + ", ".join(missing)
            + "; do not approve before they are done. "
            + keep
        )
    return [
        {"letter": "C", "title": "Claims", "text": claims},
        {"letter": "H", "title": "Hunt the source", "text": hunt},
        {"letter": "E", "title": "Evidence and numbers", "text": evidence},
        {"letter": "C", "title": "Cross-check", "text": cross},
        {"letter": "K", "title": "Keep a human sign-off", "text": keep},
    ]


def safe_check_items(
    run: Any, audit_events: list[dict[str, Any]] | None = None
) -> list[dict[str, str]]:
    """``check_items`` for the approval screen: a malformed run gives one plain row.

    The screen where a person approves must never show a stack trace in place
    of the checks, so anything unexpected in a run becomes a row that says the
    block could not be built and where to look instead.
    """
    try:
        return check_items(run, audit_events)
    except Exception:  # whatever is wrong with the run, the screen must still render
        return [
            {
                "letter": "!",
                "title": "CHECK",
                "text": "could not be built for this run; open 'What the agent did' and check "
                "each result by hand before you approve.",
            }
        ]


def designed_holdout_share(run: Any, default: float | None = 0.10) -> float | None:
    """The hold-out share designed in this run for its plan, else ``default``.

    The export control starts at this value, so that the share written in the
    briefing and the share exported agree unless the approver changes it.
    """
    plan_ids = getattr(run, "plan_ids", None) or []
    pid = plan_ids[-1] if plan_ids else None
    for s in reversed(list(getattr(run, "steps", None) or [])):
        res = getattr(s, "result", None)
        if (
            getattr(s, "tool", None) == "design_holdout"
            and isinstance(res, dict)
            and "error" not in res
            and (pid is None or res.get("plan_id") == pid)
        ):
            share = res.get("holdout_share")
            if isinstance(share, (int, float)) and not isinstance(share, bool) and 0 < share <= 0.5:
                return max(round(float(share), 2), 0.01)
    return default
