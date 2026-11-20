"""Build the LiftPilot presentation (16:9) and the speaker script.

Run from the repository root:

    .\\.venv\\Scripts\\python.exe docs\\presentation\\build_deck.py

Outputs, next to this file:

* ``LiftPilot.pptx`` - 17 talk slides + 3 backup slides; the spoken script of each
  slide is in its speaker notes;
* ``SCRIPT.md``      - the same script with time budgets, word counts, demo narration,
  transitions and a 60-second emergency version.

Every number is copied from ``docs/RESULTS.md``. Three things are read at build time, so
re-running this script after ``liftpilot results`` refreshes them: the exchange rate
(section 9), the agent benchmark (section 10; if it is missing the slide describes the
benchmark design without numbers) and the chart data (``artifacts/*.json``).

The charts are drawn here, at the size they have on the slide, so that every label is at
least 14 pt on screen. They are rendered to a temporary folder and embedded in the file.
"""

from __future__ import annotations

import json
import re
import tempfile
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402
from pptx import Presentation  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.shapes import MSO_SHAPE  # noqa: E402
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN  # noqa: E402
from pptx.util import Emu, Inches, Pt  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RESULTS = ROOT / "docs" / "RESULTS.md"
ART = ROOT / "artifacts"
TMP = Path(tempfile.mkdtemp(prefix="liftpilot_deck_"))

# ------------------------------------------------------------------ palette
INK = RGBColor(0x1B, 0x1F, 0x3B)
TEAL = RGBColor(0x0D, 0x94, 0x88)
TEAL_D = RGBColor(0x0B, 0x7A, 0x70)  # teal for text (contrast above 4.5:1 on white)
BLUE = RGBColor(0x25, 0x63, 0xEB)
AMBER = RGBColor(0xD9, 0x77, 0x06)
AMBER_D = RGBColor(0xB4, 0x53, 0x09)  # amber for text
RED = RGBColor(0xDC, 0x26, 0x26)
VIOLET = RGBColor(0x7C, 0x3A, 0xED)
MUTED = RGBColor(0x5B, 0x64, 0x76)
GREY = RGBColor(0x9C, 0xA3, 0xAF)
LINE = RGBColor(0xDD, 0xE1, 0xE8)
BG = RGBColor(0xF7, 0xF8, 0xFB)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SOFT = RGBColor(0xEE, 0xF1, 0xF6)
TEAL_SOFT = RGBColor(0xE3, 0xF4, 0xF2)
AMBER_SOFT = RGBColor(0xFD, 0xF1, 0xE0)
RED_SOFT = RGBColor(0xFC, 0xE8, 0xE8)

FONT = "Segoe UI"
FONT_BOLD = "Segoe UI Semibold"

W, H = 13.333, 7.5
LEFT = 0.6
CW = W - 2 * LEFT  # content width
TOP = 1.75  # first line of content under a two-line title
N_MAIN = 17
WPM = 130


def hx(c: RGBColor) -> str:
    return f"#{c}"


# ------------------------------------------------------------------ inputs
def read_benchmark() -> dict[str, str] | None:
    """Parse section 10 of docs/RESULTS.md. Returns None if it is absent."""
    text_ = RESULTS.read_text(encoding="utf-8")
    m = re.search(
        r"## 10\. Agent benchmark \((.+?), (\d+) fixed requests\)(.*?)(?=\n## |\Z)", text_, re.S
    )
    if not m:
        return None
    body = m.group(3)

    def grab(pattern: str) -> str:
        g = re.search(pattern, body)
        return g.group(1).replace(".0%", "%") if g else "n/a"

    return {
        "model": m.group(1),
        "cases": m.group(2),
        "fidelity": grab(r"provenance guard\): ([\d.]+%)"),
        "blocked": grab(r"invented by the model: (\S+)"),
        "checklist": grab(r"checklist completed: ([\d.]+%)"),
        "waiting": grab(r"human-approval request: ([\d.]+%)"),
        "grounding": grab(r"Numeric grounding: ([\d.]+%)"),
        "numbers": grab(r"Numeric grounding: [\d.]+% of (\d+) numbers"),
        "rejected": grab(r"rejected by the guards: (\d+)"),
        "drafts": grab(r"Message drafts: (\d+) total"),
        "drafts_model": grab(r"total, (\d+) written by the model"),
        "drafts_pass": grab(r"model, (\d+) passing"),
        "questions": grab(r"expected tool: ([\d.]+%)"),
        "probes": grab(r"Safety probes passed: (\d+ of \d+)"),
        "median": grab(r"full campaign plan: (\d+) s"),
    }


def read_fx() -> dict[str, str]:
    """Parse section 9 of docs/RESULTS.md: the R$ 1,000,000 budget in RUB and its date."""
    text_ = RESULTS.read_text(encoding="utf-8")
    amount = re.search(r"R\$ 1,000,000 = ([\d,]+) RUB", text_)
    day = re.search(r"Exchange rates \(.*?, (\d{4})-(\d{2})-(\d{2})\)", text_)
    out = {"amount": amount.group(1) if amount else "", "date": "", "millions": ""}
    if amount:
        out["millions"] = f"{int(amount.group(1).replace(',', '')) / 1e6:.0f}"
    if day:
        d_ = date(int(day.group(1)), int(day.group(2)), int(day.group(3)))
        out["date"] = f"{d_.day} {d_.strftime('%b %Y')}"
    return out


BENCH = read_benchmark()
FX = read_fx()
REP = json.loads((ART / "x5" / "report.json").read_text(encoding="utf-8"))
EXT = json.loads((ART / "extra_analyses.json").read_text(encoding="utf-8"))
CUR = json.loads((ART / "x5" / "curves.json").read_text(encoding="utf-8"))

# Fairness audit (docs/RESULTS.md, section 7), read from the same file the results sheet is
# written from, so the slide, the notes and the script cannot drift apart.
FAIR = {r["cost"]: r for r in EXT["fairness_by_cost"]}
FAIR_MODE = {(r["cost"], bool(r["fair_mode"])): r for r in EXT["fair_mode"]}
AUDIT_SKIP = ("unknown", "under 18")  # minors are excluded by rule and kept out of the audit
# What the audit reported before a code review found that it counted excluded minors inside
# the 18-24 band (2 / 6 / 10 RUB). Kept only to tell that story; see docs/BRIEF.md, point 9.
OLD_AUDIT = "0.85\u00a0/\u00a00.70\u00a0/\u00a00.48"


def ratio(cost: float) -> str:
    return f"{FAIR[cost]['ratio']:.2f}"


def pts(x: float) -> str:
    return f"{x * 100:+.1f}"


def age_story() -> dict[str, str]:
    """The fairness figures used on the ethics slide and in its script."""
    flagged = [c for c in sorted(FAIR) if FAIR[c]["flag"]]
    off, on = FAIR_MODE[(6.0, False)], FAIR_MODE[(6.0, True)]
    up = FAIR[6.0]["measured_uplift_by_age"]
    low10 = FAIR[10.0]["lowest"]
    # the script below is written for this shape of result; fail loudly if the data moves
    assert flagged == [10.0], flagged
    assert on["age_ratio"] < off["age_ratio"], (on, off)
    assert on["real_profit"] < 0.6 * off["real_profit"], (on, off)
    assert low10 == "18-24", low10
    assert up[low10] == min(v for k, v in up.items() if k not in AUDIT_SKIP), up
    return {
        "low10": low10,
        "up_low": pts(up[low10]),
        "up_old": pts(up["65+"]),
        "fair_off": f"{off['age_ratio']:.2f}",
        "fair_on": f"{on['age_ratio']:.2f}",
        "profit_off": f"{off['real_profit']:,.0f}",
        "profit_on": f"{on['real_profit']:,.0f}",
        "ci_off": f"{off['ci'][0]:,.0f} to {off['ci'][1]:,.0f}",
        "ci_on": f"{on['ci'][0]:,.0f} to {on['ci'][1]:,.0f}",
    }


AGE = age_story()


# ------------------------------------------------------------------ script
def bench_sentence() -> str:
    if BENCH is None:
        return (
            "We also benchmark the agent on 13 fixed requests, three of them traps, such as "
            "exporting without approval. That benchmark was being re-run when this deck was "
            "built, so its figures are on the results sheet."
        )
    b = BENCH
    fid = (
        "in every campaign run"
        if b["fidelity"] == "100%"
        else f"in {b['fidelity'].rstrip('%')} percent of campaign runs"
    )
    chk = (
        "Every checklist was completed."
        if b["checklist"] == "100%"
        else f"The checklist was completed in {b['checklist'].rstrip('%')} percent of runs."
    )
    grd = (
        f"All {b['numbers']} numbers in its answers traced to a tool result"
        if b["grounding"] == "100%"
        else f"{b['grounding'].rstrip('%')} percent of the {b['numbers']} numbers in its "
        "answers traced to a tool result"
    )
    return (
        f"We benchmarked the agent on {b['cases']} fixed requests. After our guard, the planner "
        f"received exactly the stated assumptions {fid}. {chk} {grd}, and it passed "
        f"{b['probes']} safety traps. The median full plan took {b['median']} seconds, which is "
        "why I started it early."
    )


def fx_sentence() -> str:
    if FX["millions"]:
        return f"one million reais is about {FX['millions']} million roubles"
    return "one million reais is many million roubles"


# (slide key, time slot in seconds, spoken text). The slots and the agent kick-off sum to
# 11:45; with the 3:15 demo the talk is 15:00. Words are budgeted at about 130 per minute.
SCRIPT: list[tuple[str, int, str]] = [
    (
        "title",
        15,
        "Hello everyone. I am Abed, presenting for Group 10 with Ghandi. LiftPilot is an AI "
        "campaign agent that spends a marketing budget only where it changes what a customer "
        "does.",
    ),
    (
        "hook",
        50,
        "This course asks one question about every campaign: did the ads make money? Here is "
        "a real answer. A grocery chain, X5, sent a message to half of 200 thousand loyalty "
        "customers, chosen at random. Of those contacted, 63.65 percent bought. Of those left "
        "alone, 60.33 percent bought anyway. So the message caused 3.3 points. Look at the "
        "dots. Of every 100 purchases after the message, about 95 would have happened without "
        "it. A dashboard counts all 100 as campaign results. Only about 5 were caused.",
    ),
    (
        "six",
        45,
        "Our brief was the AI consultant exercise: a CEO gives us one million reais for one "
        "AI initiative, and we answer six questions. They are on the slide; here are two. "
        "Value: when a message costs 6 roubles, our plan earns about one million roubles more "
        f"than contacting everyone. And the uncomfortable part: {fx_sentence()}, but the plan "
        "the system recommends spends only about 230 thousand. So the first job of the AI is "
        "to say how much not to spend.",
    ),
    (
        "solution",
        40,
        "The solution in one sentence. Most marketing AI finds people who will buy. LiftPilot "
        "finds people who will buy because you contacted them, proves it on a real "
        "experiment, and asks a human before anything is sent. Other projects in this class "
        "predict, segment or measure. Ours differs on four points: it decides who not to "
        "contact, it proves each plan before money is spent, it fences the agent with "
        "controls we measured, and it reports where it does not help.",
    ),
    (
        "data",
        35,
        "The data is real and public. X5: 400 thousand customers and 45.8 million receipt "
        "lines, with the random test inside. The Hillstrom e-mail test is our outside check. "
        "What we do not know: the source names neither the channel nor the currency, so we "
        "presume roubles, and it gives no purchase amounts after the campaign, so we use each "
        "customer's average basket.",
    ),
    (
        "pipeline",
        30,
        "The pipeline. From receipts we compute RFM and behaviour features, without age or "
        "gender. Uplift models estimate what a message changes for each customer. A profit "
        "rule decides who to contact, and the plan is replayed on customers the models never "
        "saw. The agent, in purple, drives these steps through tools. A human approves, in "
        "red; only then is an audience file written.",
    ),
    (
        "rfm",
        55,
        "RFM means recency, frequency and monetary value, each scored from 1 to 5. The "
        "weighted score uses 0.40, 0.35 and 0.25. Take a customer scored 5, 2 and 3: 2 plus "
        "0.7 plus 0.75 gives 3.45. Those weights are our assumption, not an estimate. Now the "
        "chart: how each segment really reacted. Champions buy 88 percent of the time with no "
        "message, so a message adds only 1.2 points. Hibernating customers gain 4.6 and new "
        "customers 5.6. Rewarding your best customers wastes budget.",
    ),
    (
        "uplift",
        45,
        "The first AI part. The usual tool is a likely-buyer model: predict who will purchase "
        "and contact the top of the list. We tested it with Qini, which counts the extra "
        "purchases a ranking finds compared with random targeting. The likely-buyer model, in "
        "red, is no better than random. Uplift models learn from both groups of the "
        "experiment, so they learn the difference a message makes. Their Qini is small but "
        "significantly above zero, and the chosen model's top 10 percent reacts by 9.9 "
        "points, three times the average.",
    ),
    (
        "calc",
        60,
        "The calculation, for one made-up customer. Margin 25 percent, basket 400 roubles, "
        "message cost 6. She buys 40 percent of the time without a message and 48 percent "
        "with one: uplift 8 points. Extra margin is a quarter of 400 times 0.08: 8 roubles. "
        "Cost 6. Profit plus 2, so we contact her. Her break-even uplift is 6 points. "
        "Incremental ROAS, counting only caused revenue, is 32 over 6, about 5.3; break-even "
        "is 1 over margin, so 4. Cost per incremental purchase, the honest CAC, is 75 roubles "
        "against 100 of margin. Add a 3 percent discount and her cost becomes 11.76: we skip "
        "her.",
    ),
    (
        "results",
        50,
        "The results, replayed on held-out customers. The headline: targeting is worth what "
        "contact costs. In panel A a message costs 2 roubles. Contacting almost everyone is "
        "right; LiftPilot matches it with about 30 percent less spend, and the difference is "
        "not significant. In panel B, at 6 roubles, contacting everyone loses about 845 "
        "thousand roubles. LiftPilot is about one million better, and that is significant. "
        "With a discount the gap is 2.8 million. One caution: LiftPilot's own profit interval "
        "crosses zero in the costly scenarios. And costs and margin are our assumptions, not "
        "facts about X5.",
    ),
    (
        "ltv",
        30,
        "Retention and lifetime value, with the course formulas on the real receipts. Monthly "
        "churn is 7.7 percent overall. Champions almost never leave; hibernating and new "
        "customers churn above 20 percent a month. The segments worth the most are the ones a "
        "message changes least. The caveat: three full months of data, so read these as "
        "orders of magnitude.",
    ),
    (
        "agent",
        45,
        "The second AI part is the agent. In the course taxonomy it is utility-based: it "
        "seeks the plan with the highest expected profit. Its brain is an "
        "8-billion-parameter language model on this laptop: no cloud, no fee. It acts only "
        "through 16 tools: 12 read, 3 propose, 1 acts. In testing the model invented "
        "arguments, skipped steps and mistyped numbers. Each failure became a control. For "
        "example, a provenance guard drops any assumption the manager did not state, and "
        "never guesses a budget. And nothing is exported until a named human approves.",
    ),
    (
        "where",
        50,
        "So where does the AI actually work? Machine learning estimates uplift. Rules decide. "
        "Statistics prove the plan. The language model chooses tools, explains and drafts "
        "messages. Code checks its wording, and a human approves. " + bench_sentence(),
    ),
    (
        "demo",
        15,
        "Now the live demo. Watch three things: every number comes from a tool, the plan "
        "follows the cost, and nothing is exported until I approve.",
    ),
    (
        "ethics",
        55,
        "Is it wise? Age and gender are never model inputs, and minors are never contacted. "
        "We still audit who gets selected. Among adults the age gap is small: the ratio of "
        f"lowest to highest selection rate is {ratio(2.0)} at 2 roubles and {ratio(6.0)} at 6. "
        f"Only at 10 roubles does it fall to {ratio(10.0)}, and the plan is flagged for human "
        "review. We tried a fair mode. It made the gap worse and roughly halved profit: a "
        "negative result. One honest note: our first audit counted excluded minors as young "
        "adults and overstated the gap. A code review caught it. Even the audit needs review.",
    ),
    (
        "business",
        45,
        "Could it help a real business? Yes, within limits. It helps when contact costs real "
        "money or carries a discount, and when customers react differently. It does not help "
        "when contact is nearly free or everyone reacts the same, as our second dataset "
        "showed. A retailer needs its receipts and one random test. This twelve-week plan "
        "runs that test first, then trains and audits the model, and ends with a pilot and a "
        "go or no-go decision. Our limits: one campaign, small effects, imputed purchase "
        "amounts.",
    ),
    (
        "close",
        25,
        "One line to take away: do not pay for purchases you were going to get anyway. "
        "LiftPilot finds the customers a message really changes, proves the plan on a real "
        "experiment, and asks a human before anything is sent. Thank you. I am happy to take "
        "questions.",
    ),
]
NOTES = {k: t for k, _, t in SCRIPT}
SLOT = {k: s for k, s, _ in SCRIPT}

# The agent is started before slide 12 and works while slides 12 to 14 are presented.
KICKOFF_SECONDS = 15
KICKOFF_SAY = (
    "Before I explain the agent, I give it a job. This is the CEO's request, in reais. I click "
    "Run, and it works while I talk."
)
KICKOFF_DO = (
    "Alt+Tab to the browser. Tab 5 (AI agent) is already open with the request in the box. "
    "Click Run agent once, wait for the spinner, Alt+Tab back to PowerPoint. Do not touch the "
    "browser again until the demo."
)
DEMO_SECONDS = 195

# (clock, seconds, where, what to do, what to say)
DEMO_STEPS: list[tuple[str, int, str, str, str]] = [
    (
        "0:00",
        15,
        "Tab 1, Problem",
        "Alt+Tab to the browser, click the first tab, point at the four tiles.",
        "This is the same system, on this laptop, on the real data. The experiment you saw: 60 "
        "percent bought with no message, 64 percent with one. The real effect is 3.3 points.",
    ),
    (
        "0:15",
        15,
        "Tab 2, Customers (RFM)",
        "Click the tab, point at the left of the bar chart.",
        "The RFM segments, computed from the receipts, with the uplift measured in each. "
        "Champions, on the left, react least.",
    ),
    (
        "0:30",
        10,
        "Tab 3, Uplift models",
        "Click the tab, point at the red line. Do not scroll.",
        "The model comparison. Red is the likely-buyer model, below the random line.",
    ),
    (
        "0:40",
        25,
        "Tab 4, Optimizer",
        "Click the tab. The cost slider was set to 6.0 before the talk: do not move it. Point at "
        "the Contact tile, then the bar chart. There is no yellow fairness warning at 6 RUB; "
        "point at the empty space under the Fair mode switch.",
        "The optimizer, set to 6 roubles a message. The plan contacts about 19 percent of the "
        "audience. At 2 roubles it was about 70 percent. The bar chart shows that contacting "
        "everyone would lose money. And no fairness warning here: at 6 roubles the audit "
        "passes.",
    ),
    (
        "1:05",
        15,
        "Tab 5, AI agent",
        "Click the tab. The answer should be there; if the spinner still turns, use the waiting "
        "script. Point at the pills: tool calls and numeric grounding.",
        "The agent has finished the job I gave it. It made these tool calls, and this is the "
        "grounding score: every number in its text was checked against a tool result.",
    ),
    (
        "1:20",
        15,
        "Tab 5, briefing and verified statements",
        "Point left, then right.",
        "On the left, the briefing in plain English. On the right, the verified statements, "
        "written by code. The model only narrates them.",
    ),
    (
        "1:35",
        10,
        "Tab 5, Personalised messages",
        "Scroll down past the tool list to the messages table, point at Passed checks.",
        "One message per RFM segment, each checked by code. FreshMart is a fictional brand.",
    ),
    (
        "1:45",
        15,
        "Tab 5, Human checkpoint",
        "Type your name in Approver name, press Enter, click Approve plan.",
        "Nothing has been sent. The export is locked until a named human approves. I approve.",
    ),
    (
        "2:00",
        10,
        "Tab 5, export",
        "Leave the hold-out slider at 0.10, click Export audience file, point at the green "
        "message.",
        "Only now does the audience file exist, with a random ten percent hold-out to measure "
        "the next campaign.",
    ),
    (
        "2:10",
        20,
        "Tab 6, Ethics & audit",
        "Click the tab, point at the age chart (right) and the green OK pill under it, scroll "
        "to the audit log.",
        "Last tab. The age audit of the 6-rouble plan, marked OK, then the list of controls, "
        "and the audit log. My approval was just recorded, with my name.",
    ),
]
DEMO_RESERVE = DEMO_SECONDS - sum(s for _, s, _, _, _ in DEMO_STEPS)

WAITING = (
    "The request is in reais and the data is in roubles, so the planner first converts the "
    "budget with a live exchange rate, then builds the plan. The model replays that plan on "
    "customers it never saw, audits fairness, sizes a hold-out group, picks a send date from a "
    "public-holiday calendar, and drafts one message per segment. It is not allowed to do "
    "arithmetic: every number it writes is checked against what the tools returned."
)

BACKUP_NOTES = {
    "learners": "Backup, only if asked. Seven models on the same 40,008 test customers. The "
    "likely-buyer model has a negative Qini. All six uplift models, five learners and their "
    "ensemble, are positive with intervals above zero. The champion, the S-learner, was chosen "
    "on the calibration split before we looked at the test results. The intervals overlap, so "
    "we do not claim one uplift learner beats another.",
    "hillstrom": "Backup, only if asked. On the Hillstrom e-mail test the effect is nearly the "
    "same for everyone, and the uplift rankings are unstable across re-splits. So the right "
    "answer is all or nothing. The profit rule finds the switch: send to all at 10 cents, to "
    "nobody at 60 cents. In the discount scenario it loses to sending to everyone, by an amount "
    "that is not significant. Targeting only helps where effects really differ between customers.",
    "sources": "Backup, only if asked for sources. Data: X5 RetailHero and the Hillstrom e-mail "
    "test, both public, neither with a stated licence, so we cite them and do not redistribute "
    "them. Methods: the meta-learners, the doubly robust learner, the class transformation and "
    "Qini. Ethics: three legal texts read in the original, one paper on manipulation and the "
    "NIST risk framework.",
}

TITLES = {
    "title": "LiftPilot",
    "hook": "Did the ads make money? About 95 of every 100 campaign purchases would have happened anyway.",
    "six": "The CEO's R$ 1 million question has an uncomfortable first answer: spend far less of it.",
    "solution": "LiftPilot finds the people who buy because you contacted them, and proves it first.",
    "data": "Everything rests on real public data, and we say what the data does not tell us.",
    "pipeline": "Eight steps turn raw receipts into an audience file, with a human gate before any action.",
    "rfm": "RFM shows who is persuadable: the best customers react least to a message.",
    "uplift": "A likely-buyer model ranks the wrong people; uplift models find those a message changes.",
    "calc": "One rule decides each customer: contact only if the extra margin beats the cost.",
    "results": "Targeting is worth what contact costs: no gain at 2 RUB, a significant gain at 6 RUB.",
    "ltv": "Retention and lifetime value differ sharply by segment, on only three months of data.",
    "agent": "The agent is a local language model fenced by 16 tools, coded checks and a human gate.",
    "where": "Machine learning scores, rules decide, the language model explains, a human approves.",
    "demo": "Live demo: one request, a full campaign plan, and nothing leaves without my approval.",
    "ethics": "Is it wise? Among adults the age gap is small and flagged only at 10 RUB; our fix made it worse.",
    "business": "A real business can pilot this in 12 weeks, if contact costs money and it can run one random test.",
    "close": "Do not pay for purchases you were going to get anyway.",
    "learners": "Backup: all six uplift models have a positive Qini on held-out customers; the likely-buyer model does not.",
    "hillstrom": "Backup: on a second dataset effects are uniform, and the honest answer is all or nothing.",
    "sources": "Backup: sources for the data, the methods and the ethics.",
}


# ------------------------------------------------------------------ word counts
def _number_words(tok: str) -> int:
    whole, _, frac = tok.partition(".")
    v = int(whole or 0)
    if v < 21 or (v < 100 and v % 10 == 0):
        n = 1
    elif v < 100:
        n = 2
    elif v < 1000:
        rest = v % 100
        n = 2 + (0 if rest == 0 else 1 if (rest < 21 or rest % 10 == 0) else 2)
    else:
        n = 4
    return n + (1 + len(frac) if frac else 0)


def spoken_words(t: str) -> int:
    """Words as they are said: hyphenated words count per part, numbers per spoken word
    (63.65 is said 'sixty-three point six five')."""
    n = 0
    for tok in t.replace("-", " ").replace("+", " ").split():
        core = tok.strip(".,;:!?()'\"").replace(",", "")
        if not core:
            continue
        n += _number_words(core) if re.fullmatch(r"\d+(\.\d+)?", core) else 1
    return n


# ------------------------------------------------------------------ drawing helpers
def typo(t: str) -> str:
    """Real minus sign before a number, so a negative value never breaks across lines."""
    return re.sub(r"(?<![\w.,])-(?=\d)", "−", t)


def inches(v: float) -> Emu:
    return Inches(v)


def text(
    slide,
    x: float,
    y: float,
    w: float,
    h: float,
    paras,
    size: float = 18,
    color: RGBColor = INK,
    bold: bool = False,
    align=PP_ALIGN.LEFT,
    anchor=MSO_ANCHOR.TOP,
    spacing: float = 1.05,
    after: float = 4,
):
    """Text box. ``paras`` is a string, or a list whose items are strings or lists of
    runs ``(text, {"bold":..,"color":..,"size":..})``."""
    box = slide.shapes.add_textbox(inches(x), inches(y), inches(w), inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.04)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    tf.vertical_anchor = anchor
    if isinstance(paras, str):
        paras = [paras]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        p.space_after = Pt(after)
        runs = [(para, {})] if isinstance(para, str) else para
        for rtext, opt in runs:
            r = p.add_run()
            r.text = typo(rtext)
            f = r.font
            f.name = FONT_BOLD if opt.get("bold", bold) else FONT
            f.size = Pt(opt.get("size", size))
            f.bold = opt.get("bold", bold)
            f.color.rgb = opt.get("color", color)
    return box


def rect(slide, x, y, w, h, fill=WHITE, line=LINE, rounded=True, radius=0.06, line_w=0.75):
    shp = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
        inches(x),
        inches(y),
        inches(w),
        inches(h),
    )
    if rounded:
        shp.adjustments[0] = min(0.5, radius / max(min(w, h), 0.01))
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(line_w)
    shp.shadow.inherit = False
    return shp


def arrow(slide, x, y, w, h, fill=MUTED, kind=MSO_SHAPE.RIGHT_ARROW):
    shp = slide.shapes.add_shape(kind, inches(x), inches(y), inches(w), inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    shp.line.fill.background()
    shp.shadow.inherit = False
    return shp


def card(slide, x, y, w, h, accent: RGBColor | None = None, fill=WHITE):
    rect(slide, x, y, w, h, fill=fill)
    if accent is not None:
        rect(slide, x, y, 0.09, h, fill=accent, line=None, rounded=False)


def table(slide, x, y, col_w, rows, size=16, row_h=0.46, header=True, head_fill=INK, zebra=True):
    """Native table. Cells are strings or (text, {"bold","color","align","fill","size"})."""
    n_r, n_c = len(rows), len(col_w)
    gf = slide.shapes.add_table(
        n_r, n_c, inches(x), inches(y), inches(sum(col_w)), inches(row_h * n_r)
    )
    tbl = gf.table
    tbl.first_row = header
    tbl.horz_banding = False
    for j, cw in enumerate(col_w):
        tbl.columns[j].width = inches(cw)
    for i, row in enumerate(rows):
        tbl.rows[i].height = inches(row_h)
        for j, cell_def in enumerate(row):
            txt, opt = (cell_def, {}) if isinstance(cell_def, str) else cell_def
            cell = tbl.cell(i, j)
            cell.margin_left = cell.margin_right = Inches(0.1)
            cell.margin_top = cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            is_head = header and i == 0
            cell.fill.solid()
            if is_head:
                cell.fill.fore_color.rgb = head_fill
            elif "fill" in opt:
                cell.fill.fore_color.rgb = opt["fill"]
            else:
                cell.fill.fore_color.rgb = SOFT if (zebra and i % 2 == 0) else WHITE
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = opt.get("align", PP_ALIGN.LEFT)
            r = p.add_run()
            r.text = typo(txt)
            r.font.name = FONT_BOLD if (is_head or opt.get("bold")) else FONT
            r.font.size = Pt(opt.get("size", size))
            r.font.bold = bool(is_head or opt.get("bold"))
            r.font.color.rgb = WHITE if is_head else opt.get("color", INK)
    return gf


def pill(slide, x, y, w, label, fill, color=WHITE, size=14, h=0.36):
    shp = rect(slide, x, y, w, h, fill=fill, line=None, radius=h / 2)
    tf = shp.text_frame
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.name = FONT_BOLD
    r.font.size = Pt(size)
    r.font.bold = True
    r.font.color.rgb = color
    return shp


def stat(slide, x, y, w, value, label, color=TEAL_D, vsize=34, lsize=16, h=1.25):
    card(slide, x, y, w, h, accent=color)
    text(slide, x + 0.22, y + 0.08, w - 0.3, 0.62, value, size=vsize, color=color, bold=True)
    text(
        slide,
        x + 0.22,
        y + 0.08 + vsize / 72 * 1.28,
        w - 0.3,
        h - 0.7,
        label,
        size=lsize,
        color=MUTED,
    )


# ------------------------------------------------------------------ charts (14 pt on the slide)
plt.rcParams.update(
    {
        "font.family": [FONT, "DejaVu Sans"],
        "font.size": 14,
        "axes.titlesize": 14,
        "axes.titleweight": "bold",
        "axes.labelsize": 14,
        "xtick.labelsize": 14,
        "ytick.labelsize": 14,
        "legend.fontsize": 14,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": hx(MUTED),
        "axes.labelcolor": hx(INK),
        "xtick.color": hx(INK),
        "ytick.color": hx(INK),
        "text.color": hx(INK),
        "axes.grid": True,
        "grid.color": hx(LINE),
        "axes.axisbelow": True,
    }
)


def chart(slide, name: str, x: float, y: float, w: float, h: float, draw) -> None:
    """White card with a chart drawn at exactly its on-slide size (so 14 pt stays 14 pt)."""
    rect(slide, x, y, w, h, fill=WHITE)
    pad = 0.08
    fig = plt.figure(figsize=(w - 2 * pad, h - 2 * pad), constrained_layout=True)
    draw(fig)
    path = TMP / f"{name}.png"
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)
    slide.shapes.add_picture(
        str(path), inches(x + pad), inches(y + pad), inches(w - 2 * pad), inches(h - 2 * pad)
    )


def draw_rfm(fig) -> None:
    ax = fig.add_subplot()
    segs = REP["rfm_segments"]
    names = list(segs)[::-1]
    avg = REP["experiment_readout"]["ate"] * 100
    vals = [segs[n]["observed_uplift"] * 100 for n in names]
    lo = [(segs[n]["observed_uplift"] - segs[n]["uplift_ci_low"]) * 100 for n in names]
    hi = [(segs[n]["uplift_ci_high"] - segs[n]["observed_uplift"]) * 100 for n in names]
    ax.barh(
        range(len(names)),
        vals,
        xerr=[lo, hi],
        color=[hx(TEAL) if v >= avg else hx(GREY) for v in vals],
        error_kw={"ecolor": hx(MUTED), "capsize": 4, "lw": 1.4},
        height=0.66,
    )
    ax.axvline(avg, color=hx(INK), lw=1.2, ls=":")
    ax.text(avg + 0.1, len(names) - 0.42, f"average +{avg:.1f}", va="bottom", color=hx(INK))
    ax.axvline(0, color=hx(INK), lw=0.8)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels([f"{n} ({segs[n]['conversion_control']:.0%})" for n in names])
    ax.set_ylim(-0.6, len(names) + 0.25)
    ax.set_xlabel("measured uplift, points, with 95% interval")
    ax.set_title("Real effect of the message, by RFM segment")
    ax.grid(axis="y", visible=False)


def draw_qini(fig) -> None:
    ax = fig.add_subplot()
    champ = REP["champion"]
    q = CUR["qini"]
    for key, label, col in (("response", "Likely-buyer", RED), (champ, "Uplift model", TEAL)):
        xs = [f * 100 for f in q[key]["fraction"]]
        ax.plot(xs, q[key]["value"], color=hx(col), lw=2.4, label=label)
    end = q[champ]["value"][-1]
    ax.plot([0, 100], [0, end], color=hx(MUTED), lw=1.6, ls="--", label="Random")
    ax.set_xticks([0, 50, 100])
    ax.yaxis.set_major_locator(MaxNLocator(4))
    ax.set_xlabel("% contacted, best first")
    ax.set_ylabel("extra purchases")
    ax.set_title("Qini curves, test customers")
    ax.legend(
        frameon=False, loc="upper left", handlelength=1.2, borderaxespad=0.1, labelspacing=0.25
    )


def draw_deciles(fig) -> None:
    ax = fig.add_subplot()
    dec = CUR["deciles"]
    n = len(dec["bin"])
    ax.bar(
        range(1, n + 1),
        [u * 100 for u in dec["uplift"]],
        yerr=[1.96 * s * 100 for s in dec["se"]],
        color=[hx(TEAL)] + [hx(BLUE)] * (n - 1),
        error_kw={"ecolor": hx(MUTED), "capsize": 3, "lw": 1.2},
    )
    ax.axhline(REP["experiment_readout"]["ate"] * 100, color=hx(INK), lw=1.2, ls=":")
    ax.axhline(0, color=hx(INK), lw=0.8)
    ax.set_xticks(range(1, n + 1))
    ax.yaxis.set_major_locator(MaxNLocator(5))
    ax.set_xlabel("model decile (1 = highest score)")
    ax.set_ylabel("real uplift, points")
    ax.set_title("Real uplift by model decile")
    ax.grid(axis="x", visible=False)


def draw_scenarios(fig) -> None:
    order = [
        ("Contact everyone", "Contact everyone", GREY),
        ("RFM best customers, same size", "RFM best", AMBER),
        ("Response model, same size", "Likely buyers", RED),
        ("LiftPilot profit rule", "LiftPilot", TEAL),
    ]
    scen = REP["scenarios"]
    titles = ["A. 2 RUB", "B. 6 RUB", "C. 2 RUB + 3% off"]
    axes = fig.subplots(1, len(scen))
    handles = []
    for ax, title_, s in zip(axes, titles, scen.values(), strict=True):
        pol = s["policies"]
        vals = [pol[k]["incremental_profit"] / 1e6 for k, _, _ in order]
        lo = [(pol[k]["incremental_profit"] - pol[k]["profit_ci_low"]) / 1e6 for k, _, _ in order]
        hi = [(pol[k]["profit_ci_high"] - pol[k]["incremental_profit"]) / 1e6 for k, _, _ in order]
        handles = ax.bar(
            range(len(order)),
            vals,
            yerr=[lo, hi],
            color=[hx(c) for _, _, c in order],
            error_kw={"ecolor": hx(INK), "capsize": 4, "lw": 1.3},
        )
        ax.axhline(0, color=hx(INK), lw=1.0)
        ax.set_xticks([])
        ax.yaxis.set_major_locator(MaxNLocator(4))
        ax.set_title(title_)
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("profit, million RUB")
    fig.legend(
        handles,
        [lab for _, lab, _ in order],
        loc="outside lower center",
        ncol=4,
        frameon=False,
        handlelength=1.0,
        columnspacing=1.2,
    )


def draw_fairness(fig) -> None:
    ax = fig.add_subplot()
    bands = [b for b in FAIR[2.0]["rates"] if b not in AUDIT_SKIP]
    for cost, col in ((2.0, BLUE), (6.0, TEAL), (10.0, RED)):
        r = FAIR[cost]
        ax.plot(
            bands,
            [r["rates"][b] / r["share"] for b in bands],
            marker="o",
            ms=6,
            lw=2.2,
            color=hx(col),
            label=f"{cost:g} RUB",
        )
    ax.axhline(1.0, color=hx(INK), lw=1.0)
    ax.yaxis.set_major_locator(MaxNLocator(5))
    ax.set_ylabel("selection rate / average")
    ax.set_xlabel("age band (never a model input)")
    ax.set_title("Who is contacted, adults by age")
    ax.legend(
        frameon=False, loc="lower center", handlelength=1.0, labelspacing=0.2, borderaxespad=0.3
    )


class Deck:
    def __init__(self) -> None:
        self.prs = Presentation()
        self.prs.slide_width = Inches(W)
        self.prs.slide_height = Inches(H)
        self.n = 0

    def slide(self, key: str, backup: bool = False, title: bool = True):
        s = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        self.n += 1
        bg = s.background.fill
        bg.solid()
        bg.fore_color.rgb = BG
        if title:
            rect(s, LEFT, 0.5, 0.1, 0.98, fill=RED if backup else TEAL, line=None, rounded=False)
            text(
                s,
                LEFT + 0.25,
                0.4,
                CW - 0.25,
                1.2,
                TITLES[key],
                size=30,
                bold=True,
                anchor=MSO_ANCHOR.MIDDLE,
                spacing=0.98,
                after=0,
            )
        text(
            s,
            LEFT,
            7.03,
            8.0,
            0.32,
            "LiftPilot  |  Group 10  |  AI in Business and Marketing, USJ",
            size=14,
            color=MUTED,
        )
        label = f"Backup {self.n - N_MAIN}" if backup else f"{self.n} / {N_MAIN}"
        text(s, W - LEFT - 2.0, 7.03, 2.0, 0.32, label, size=14, color=MUTED, align=PP_ALIGN.RIGHT)
        notes = BACKUP_NOTES[key] if backup else NOTES[key]
        if key == "ltv":
            notes += f"\n\n[THEN, BEFORE SLIDE 12] {KICKOFF_DO}\nSay: {KICKOFF_SAY}"
        s.notes_slide.notes_text_frame.text = notes
        return s


# ------------------------------------------------------------------ slides
def s_title(d: Deck) -> None:
    s = d.slide("title", title=False)
    rect(s, 0, 0, 0.42, H, fill=INK, line=None, rounded=False)
    rect(s, 0.42, 0, 0.09, H, fill=TEAL, line=None, rounded=False)
    text(s, 1.2, 1.25, 11, 1.3, "LiftPilot", size=80, bold=True)
    text(
        s,
        1.25,
        2.75,
        10.6,
        1.2,
        "An AI campaign agent that spends the marketing budget only where it changes "
        "customer behaviour",
        size=30,
        color=TEAL_D,
        bold=True,
        spacing=1.0,
    )
    text(
        s,
        1.25,
        4.15,
        10.8,
        0.9,
        "AI-Powered Marketing Campaign Optimizer: Using Uplift Modeling & AI to Maximize "
        "Incremental Profit",
        size=20,
        color=MUTED,
    )
    rect(s, 1.3, 5.3, 2.2, 0.04, fill=LINE, line=None, rounded=False)
    text(
        s,
        1.25,
        5.42,
        10.8,
        1.5,
        [
            [
                ("Group 10:  ", {"color": MUTED}),
                ("Abed El Rahmane Jaafir", {"bold": True}),
                ("  and  ", {"color": MUTED}),
                ("Ghandi Mahdmoud", {"bold": True}),
            ],
            [("AI in Business and Marketing  |  Dr. Katia Raya", {"color": MUTED})],
            [("Saint Joseph University of Beirut  |  25 November 2026", {"color": MUTED})],
        ],
        size=18,
        after=6,
    )


def s_hook(d: Deck) -> None:
    s = d.slide("hook")
    gx, gy, dia, gap = 0.95, 1.95, 0.33, 0.085
    card(s, gx - 0.3, gy - 0.22, 10 * dia + 9 * gap + 0.6, 10 * dia + 9 * gap + 0.95)
    for i in range(100):
        r_, c_ = divmod(i, 10)
        dot = s.shapes.add_shape(
            MSO_SHAPE.OVAL,
            inches(gx + c_ * (dia + gap)),
            inches(gy + r_ * (dia + gap)),
            inches(dia),
            inches(dia),
        )
        dot.fill.solid()
        dot.fill.fore_color.rgb = TEAL if i >= 95 else GREY
        dot.line.fill.background()
        dot.shadow.inherit = False
    text(
        s,
        gx - 0.2,
        gy + 10 * dia + 9 * gap + 0.12,
        4.6,
        0.6,
        [
            [
                ("95 would have bought anyway", {"color": MUTED, "bold": True}),
                ("   5 caused", {"color": TEAL_D, "bold": True}),
            ]
        ],
        size=16,
    )
    x = 5.75
    w3 = (W - LEFT - x - 0.4) / 3
    kw = {"vsize": 32, "lsize": 15, "h": 1.72}
    stat(s, x, 1.73, w3, "63.65%", "bought WITH the message (99,981 customers)", color=INK, **kw)
    stat(
        s,
        x + w3 + 0.2,
        1.73,
        w3,
        "60.33%",
        "bought WITHOUT it (100,058 customers)",
        color=MUTED,
        **kw,
    )
    stat(
        s,
        x + 2 * (w3 + 0.2),
        1.73,
        w3,
        "+3.32",
        "points caused (95% CI +2.90 to +3.75)",
        color=TEAL_D,
        **kw,
    )
    text(
        s,
        x,
        3.68,
        W - LEFT - x,
        2.1,
        [
            [
                ("A real randomised test. ", {"bold": True}),
                ("X5, a grocery chain, contacted half of 200,039 loyalty customers at random.", {}),
            ],
            [
                ("94.8% ", {"bold": True, "color": TEAL_D}),
                ("of purchases after the message would have happened without it.", {}),
            ],
            [("Dashboards and platform ROAS count all of them.", {"color": MUTED})],
        ],
        size=18,
        after=9,
    )
    card(s, x, 5.82, W - LEFT - x, 0.95, accent=AMBER, fill=AMBER_SOFT)
    text(
        s,
        x + 0.25,
        5.82,
        W - LEFT - x - 0.4,
        0.95,
        'The real question is not "who will buy?" but "who will buy because we contacted them?"',
        size=18,
        bold=True,
        anchor=MSO_ANCHOR.MIDDLE,
    )


def s_six(d: Deck) -> None:
    s = d.slide("six")
    rows = [
        ["The consultant's question", "LiftPilot's answer"],
        [
            "1  What is the business problem?",
            "Budget is spent on customers who would have bought anyway.",
        ],
        [
            "2  How could AI help?",
            "Estimate, per customer, the change a message causes; an agent plans and explains.",
        ],
        ["3  What data is needed?", "Purchase receipts and one past campaign sent at random."],
        [
            "4  What business value?",
            "At 6 RUB per message: +1,049,514 RUB vs contacting everyone (95% CI 633,841 to "
            "1,427,149), replay scaled to 400,162 customers.",
        ],
        [
            "5  What could go wrong?",
            "Small effects, unequal selection by age, a language model inventing numbers. Each "
            "has a control.",
        ],
        [
            "6  How is success measured?",
            "Incremental profit against a random hold-out group. Never platform ROAS.",
        ],
    ]
    rows = [[(r[0], {"bold": True}), r[1]] if i else r for i, r in enumerate(rows)]
    table(s, LEFT, TOP, [3.75, 8.38], rows, size=16, row_h=0.5)
    y = TOP + 0.5 * 7 + 0.2
    card(s, LEFT, y, CW, 1.38, accent=AMBER, fill=AMBER_SOFT)
    rate = (
        f"R$ 1,000,000 = {FX['amount']} RUB (reference rate of {FX['date']}). "
        if FX["amount"]
        else "R$ 1,000,000 is converted at the day's reference rate. "
    )
    text(
        s,
        LEFT + 0.3,
        y,
        CW - 0.5,
        1.38,
        [
            [
                ("The twist.  ", {"bold": True, "color": AMBER_D}),
                (
                    rate + "At 6 RUB per message, the plan for the 200,123 untested customers "
                    "spends ",
                    {},
                ),
                ("about 228 thousand RUB", {"bold": True}),
                (
                    " (expected profit 99,838 RUB, 95% CI -114,276 to 299,621). The first job of "
                    "the AI is to say how much NOT to spend.",
                    {},
                ),
            ],
        ],
        size=17,
        anchor=MSO_ANCHOR.MIDDLE,
    )


def s_solution(d: Deck) -> None:
    s = d.slide("solution")
    card(s, LEFT, TOP, CW, 1.75, accent=TEAL, fill=TEAL_SOFT)
    text(
        s,
        LEFT + 0.35,
        TOP,
        CW - 0.6,
        1.75,
        [
            [
                (
                    "Most marketing AI finds people who will buy. LiftPilot finds people who will buy ",
                    {},
                ),
                ("because you contacted them", {"bold": True, "color": TEAL_D}),
                (", proves it on a real experiment, and asks a human before anything is sent.", {}),
            ]
        ],
        size=24,
        anchor=MSO_ANCHOR.MIDDLE,
        spacing=1.08,
    )
    text(
        s,
        LEFT,
        3.72,
        CW,
        0.45,
        "Other class projects predict, segment or measure. LiftPilot differs on four points:",
        size=18,
        color=MUTED,
    )
    items = [
        (BLUE, "1", "Decides who NOT to contact", "Per customer, with a calibrated profit rule."),
        (
            TEAL_D,
            "2",
            "Proves every plan first",
            "Replay on a real randomised experiment, with 95% intervals.",
        ),
        (VIOLET, "3", "Fences the agent", "Numbers only from tools, a human gate, an audit log."),
        (AMBER_D, "4", "Reports where it fails", "Cheap contact, uniform effects, fair mode."),
    ]
    gap = 0.22
    cw_ = (CW - 3 * gap) / 4
    for i, (col, num, head, body) in enumerate(items):
        x = LEFT + i * (cw_ + gap)
        card(s, x, 4.25, cw_, 2.5)
        rect(s, x, 4.25, cw_, 0.1, fill=col, line=None, rounded=False)
        text(s, x + 0.2, 4.38, 0.6, 0.55, num, size=26, bold=True, color=col)
        text(s, x + 0.2, 4.9, cw_ - 0.3, 0.75, head, size=18, bold=True, spacing=0.95)
        text(s, x + 0.2, 5.68, cw_ - 0.3, 1.0, body, size=16, color=MUTED)


def s_data(d: Deck) -> None:
    s = d.slide("data")
    gap = 0.25
    cw_ = (CW - 2 * gap) / 3
    cards = [
        (
            BLUE,
            "X5 RetailHero",
            "main dataset",
            [
                "400,162 loyalty customers",
                "45.8 M receipt lines",
                "200,039 in a random test",
                "Nov 2018 to Mar 2019",
            ],
        ),
        (
            TEAL_D,
            "Hillstrom e-mail test",
            "external check",
            [
                "64,000 customers",
                "Spend observed, in USD",
                "Tests where targeting does not help",
            ],
        ),
        (
            AMBER_D,
            "Live feeds",
            "context, cached offline",
            [
                "Frankfurter: exchange rates",
                "Nager.Date: public holidays",
                "They never change the uplift scores",
            ],
        ),
    ]
    for i, (col, head, sub, lines) in enumerate(cards):
        x = LEFT + i * (cw_ + gap)
        card(s, x, TOP, cw_, 2.6)
        rect(s, x, TOP, cw_, 0.1, fill=col, line=None, rounded=False)
        text(s, x + 0.22, TOP + 0.18, cw_ - 0.4, 0.45, head, size=22, bold=True, color=col)
        text(s, x + 0.22, TOP + 0.64, cw_ - 0.4, 0.36, sub, size=16, color=MUTED)
        text(s, x + 0.22, TOP + 1.06, cw_ - 0.4, 1.5, lines, size=17, after=3)
    y = TOP + 2.75
    card(s, LEFT, y, CW, 1.58, accent=RED, fill=RED_SOFT)
    text(
        s,
        LEFT + 0.3,
        y + 0.07,
        5.0,
        0.4,
        "What the data does NOT tell us",
        size=18,
        bold=True,
        color=RED,
    )
    half = (CW - 0.6) / 2
    text(
        s,
        LEFT + 0.3,
        y + 0.5,
        half - 0.5,
        1.05,
        [
            'The channel: the source says only "a communication".',
            "The currency: presumed RUB, not stated.",
        ],
        size=16,
        after=4,
    )
    text(
        s,
        LEFT + 0.3 + half - 0.4,
        y + 0.5,
        half + 0.5,
        1.05,
        [
            "Amounts bought after the campaign: we use each customer's average basket.",
            "Margin and contact costs: our scenarios, not X5 facts.",
        ],
        size=16,
        after=4,
    )
    text(
        s,
        LEFT,
        y + 1.68,
        CW,
        0.6,
        "Sources: X5 Retail Group, RetailHero hackathon (ODS.ai competition page; scikit-uplift "
        "mirror). K. Hillstrom, MineThatData blog, 20 March 2008. frankfurter.dev. date.nager.at. "
        "Neither dataset states a licence: we cite them and do not redistribute them.",
        size=14,
        color=MUTED,
        spacing=1.0,
    )


def s_pipeline(d: Deck) -> None:
    s = d.slide("pipeline")
    gap = 0.3
    bw = (CW - 4 * gap) / 5
    bh = 1.95

    def box(x, y, w, col, head, lines):
        rect(s, x, y, w, bh, fill=WHITE, line=col, line_w=2.25, radius=0.1)
        text(
            s,
            x + 0.05,
            y + 0.1,
            w - 0.1,
            0.4,
            head,
            size=17,
            bold=True,
            color=col,
            align=PP_ALIGN.CENTER,
        )
        text(
            s,
            x + 0.05,
            y + 0.58,
            w - 0.1,
            bh - 0.62,
            lines,
            size=14,
            align=PP_ALIGN.CENTER,
            after=2,
            spacing=1.0,
        )

    y1 = TOP + 0.05
    y2 = y1 + bh + 0.72
    row1 = [
        (BLUE, "1. Data", ["45.8 M receipt lines", "400,162 customers", "one randomised test"]),
        (BLUE, "2. RFM features", ["R, F, M and behaviour", "33 features", "no age, no gender"]),
        (
            TEAL_D,
            "3. Uplift models",
            ["5 learners + ensemble", "champion chosen on", "the calibration split"],
        ),
        (TEAL_D, "4. Profit rule", ["contact if gain > cost", "budget limit", "opt-outs, no minors"]),
        (TEAL_D, "5. Evidence", ["replay on held-out", "customers, 95% CI", "fairness audit"]),
    ]
    for i, (col, head, lines) in enumerate(row1):
        x = LEFT + i * (bw + gap)
        box(x, y1, bw, col, head, lines)
        if i:
            arrow(s, x - gap + 0.04, y1 + bh / 2 - 0.11, gap - 0.08, 0.22)
    # the agent reaches steps 3 to 5 through tool calls
    aw = 2 * bw + gap
    ax_ = LEFT + bw + gap + aw / 2  # centre of the agent box
    bar_y = y1 + bh + 0.4
    last = LEFT + 4 * (bw + gap) + bw / 2
    rect(s, ax_ - 0.03, bar_y, last - ax_ + 0.06, 0.06, fill=VIOLET, line=None, rounded=False)
    rect(s, ax_ - 0.03, bar_y, 0.06, y2 - bar_y, fill=VIOLET, line=None, rounded=False)
    for i in (2, 3, 4):
        arrow(
            s,
            LEFT + i * (bw + gap) + bw / 2 - 0.12,
            y1 + bh + 0.06,
            0.24,
            0.37,
            fill=VIOLET,
            kind=MSO_SHAPE.UP_ARROW,
        )
    text(
        s,
        LEFT,
        y1 + bh + 0.2,
        ax_ - LEFT - 0.15,
        0.4,
        "the agent calls steps 3 to 5 as tools",
        size=14,
        color=VIOLET,
        bold=True,
        align=PP_ALIGN.RIGHT,
    )
    box(LEFT, y2, bw, AMBER_D, "Live feeds", ["exchange rates", "public holidays", "(cached offline)"])
    arrow(s, LEFT + bw + 0.04, y2 + bh / 2 - 0.11, gap - 0.08, 0.22, fill=AMBER)
    box(
        LEFT + bw + gap,
        y2,
        aw,
        VIOLET,
        "6. LiftPilot agent (local language model)",
        [
            "plan, evaluate, audit, schedule, draft",
            "numbers only from tools; copy checked by code",
            "facts written by code, narrated by the model",
        ],
    )
    x7 = LEFT + 3 * (bw + gap)
    arrow(s, x7 - gap + 0.04, y2 + bh / 2 - 0.11, gap - 0.08, 0.22, fill=VIOLET)
    box(x7, y2, bw, RED, "7. Human gate", ["a named manager", "approves or rejects;", "no self-approval"])
    x8 = LEFT + 4 * (bw + gap)
    arrow(s, x8 - gap + 0.04, y2 + bh / 2 - 0.11, gap - 0.08, 0.22, fill=RED)
    box(x8, y2, bw, RED, "8. Action", ["audience file", "random hold-out", "audit log"])
    text(
        s,
        LEFT,
        y2 + bh + 0.1,
        CW,
        0.36,
        "Labelled customers are split once: train 120,023  |  calibration 40,008  |  test 40,008. "
        "Each campaign's hold-out feeds the next model refresh.",
        size=14,
        color=MUTED,
        align=PP_ALIGN.CENTER,
    )


def s_rfm(d: Deck) -> None:
    s = d.slide("rfm")
    lw = 4.55
    card(s, LEFT, TOP, lw, 2.5)
    text(s, LEFT + 0.25, TOP + 0.1, lw - 0.4, 0.4, "Weighted RFM score: the weights", size=18, bold=True)
    bars = [("Recency", 0.40, BLUE), ("Frequency", 0.35, TEAL_D), ("Monetary", 0.25, AMBER_D)]
    for i, (name, wgt, col) in enumerate(bars):
        yy = TOP + 0.62 + i * 0.46
        text(s, LEFT + 0.25, yy, 1.45, 0.4, name, size=17)
        rect(s, LEFT + 1.7, yy + 0.05, 1.5 * wgt / 0.40, 0.28, fill=col, line=None, radius=0.04)
        text(
            s,
            LEFT + 1.75 + 1.5 * wgt / 0.40,
            yy,
            0.8,
            0.4,
            f"{wgt:.2f}",
            size=17,
            bold=True,
            color=col,
        )
    text(
        s,
        LEFT + 0.25,
        TOP + 2.02,
        lw - 0.4,
        0.4,
        "Each score: 1 to 5, by quintile, from receipts.",
        size=14,
        color=MUTED,
    )
    y2 = TOP + 2.66
    card(s, LEFT, y2, lw, 2.45, accent=TEAL, fill=TEAL_SOFT)
    text(
        s,
        LEFT + 0.28,
        y2 + 0.08,
        lw - 0.4,
        2.3,
        [
            [("Worked example", {"bold": True, "color": TEAL_D, "size": 17})],
            "A customer scored R = 5, F = 2, M = 3:",
            [("0.40 x 5 + 0.35 x 2 + 0.25 x 3", {"bold": True})],
            [("= 2.00 + 0.70 + 0.75 = 3.45", {"bold": True})],
            [
                (
                    "Segment: Potential loyalists (recent, average frequency and spend).",
                    {"color": MUTED, "size": 14},
                )
            ],
        ],
        size=16,
        after=3,
    )
    fx = LEFT + lw + 0.25
    fw = W - LEFT - fx
    chart(s, "rfm", fx, TOP, fw, 4.3, draw_rfm)
    text(
        s,
        fx,
        TOP + 4.37,
        fw,
        0.8,
        "In brackets: share buying with no message. Uplift = purchase rate of contacted minus "
        "held-out customers. The weights are a stated assumption; the uplift model, not this "
        "score, decides who is contacted.",
        size=14,
        color=MUTED,
        spacing=1.0,
    )


def s_uplift(d: Deck) -> None:
    s = d.slide("uplift")
    w1, h1 = 4.4, 3.78
    chart(s, "qini", LEFT, TOP, w1, h1, draw_qini)
    x2 = LEFT + w1 + 0.2
    chart(s, "deciles", x2, TOP, w1, h1, draw_deciles)
    x3 = x2 + w1 + 0.2
    w3 = W - LEFT - x3
    kw = {"vsize": 30, "lsize": 14, "h": 1.18}
    stat(
        s,
        x3,
        TOP,
        w3,
        "-0.0052",
        "Qini, likely-buyer model (95% CI -0.0116 to +0.0010)",
        color=RED,
        **kw,
    )
    stat(
        s,
        x3,
        TOP + 1.3,
        w3,
        "+0.0089",
        "Qini, uplift champion (95% CI +0.0021 to +0.0156)",
        color=TEAL_D,
        **kw,
    )
    stat(
        s,
        x3,
        TOP + 2.6,
        w3,
        "+9.9 pts",
        "real uplift in the top 10%, vs +3.3 on average",
        color=BLUE,
        **kw,
    )
    y = TOP + h1 + 0.12
    text(
        s,
        LEFT,
        y,
        CW,
        1.2,
        [
            [
                ("Qini ", {"bold": True}),
                (
                    "= extra purchases a ranking finds compared with random targeting. Measured on "
                    "40,008 customers the models never saw.",
                    {},
                ),
            ],
            [
                (
                    "Five uplift learners (S, T, X, DR, class transformation; gradient-boosted trees) "
                    "plus their ensemble. The champion is chosen on a separate calibration split. "
                    "Below the top decile the ranking is noisy.",
                    {"color": MUTED},
                )
            ],
        ],
        size=16,
        after=4,
    )


def s_calc(d: Deck) -> None:
    s = d.slide("calc")
    lw = 5.2
    card(s, LEFT, TOP, lw, 3.95, accent=BLUE)
    text(s, LEFT + 0.28, TOP + 0.1, lw - 0.4, 0.4, "The formulas", size=18, bold=True, color=BLUE)
    f = [
        ("Contact customer i if", "m x V x uplift  >  c + d x V x P(buy | contacted)"),
        ("Break-even uplift", "(c + d x V x P(buy | contacted)) / (m x V)"),
        ("Incremental ROAS", "extra revenue / spend      break-even = 1 / m"),
        ("Cost per incremental purchase", "spend / extra purchases"),
    ]
    for i, (lab, form) in enumerate(f):
        yy = TOP + 0.58 + i * 0.72
        text(s, LEFT + 0.28, yy, lw - 0.4, 0.34, lab, size=14, color=MUTED)
        text(s, LEFT + 0.28, yy + 0.3, lw - 0.4, 0.38, form, size=16, bold=True)
    text(
        s,
        LEFT + 0.28,
        TOP + 3.47,
        lw - 0.4,
        0.42,
        "m margin, V basket, c message cost, d discount",
        size=14,
        color=MUTED,
    )
    rx = LEFT + lw + 0.3
    rw = W - LEFT - rx
    text(
        s,
        rx,
        TOP - 0.02,
        rw,
        0.74,
        [
            [
                ("One illustrative customer.  ", {"bold": True}),
                (
                    "m = 25%, V = 400 RUB, c = 6 RUB, d = 0. Buys 40% without a message, 48% with: "
                    "uplift = 8 pts.",
                    {},
                ),
            ]
        ],
        size=16,
        after=0,
    )
    g = {"color": TEAL_D, "bold": True, "align": PP_ALIGN.CENTER}
    r_ = {"color": RED, "bold": True, "align": PP_ALIGN.CENTER}
    mono = {"size": 14}
    rows = [
        ["Step", "Calculation", "Result"],
        ["Extra margin", ("0.25 x 400 x 0.08 = 8.00 RUB", mono), ("8.00", g)],
        ["Profit", ("8.00 - 6.00 = +2.00 RUB", mono), ("CONTACT", g)],
        ["Break-even uplift", ("6 / (0.25 x 400) = 6 pts", mono), ("8 > 6", g)],
        ["Incremental ROAS", ("(400 x 0.08) / 6 = 5.33", mono), ("> 4.00", g)],
        ["Cost / extra purchase", ("6 / 0.08 = 75 RUB", mono), ("< 100", g)],
        ["With a 3% discount", ("6 + 0.03 x 400 x 0.48 = 11.76", mono), ("SKIP", r_)],
    ]
    table(s, rx, TOP + 0.78, [2.2, rw - 2.2 - 1.2, 1.2], rows, size=15, row_h=0.452)
    y = TOP + 4.15
    card(s, LEFT, y, CW, 0.92, fill=SOFT)
    text(
        s,
        LEFT + 0.25,
        y,
        CW - 0.4,
        0.92,
        [
            [
                ("Course vocabulary.  ", {"bold": True}),
                (
                    "A/B test = the randomised campaign (z = 15.3, p < 0.001).  ROAS becomes incremental "
                    "ROAS.  CAC / CPA becomes cost per incremental purchase.  LTV, churn and retention "
                    "follow in two slides.",
                    {},
                ),
            ]
        ],
        size=15,
        anchor=MSO_ANCHOR.MIDDLE,
    )


def s_results(d: Deck) -> None:
    s = d.slide("results")
    w, fh = 8.0, 3.72
    chart(s, "scenarios", LEFT, TOP, w, fh, draw_scenarios)
    rx = LEFT + w + 0.2
    rw = W - LEFT - rx
    items = [
        (
            GREY,
            "A. 2 RUB",
            "-46,581 RUB vs everyone",
            "CI -347,880 to +230,187. Not significant; 30% less spend.",
        ),
        (TEAL, "B. 6 RUB", "+1,049,514 RUB vs everyone", "CI 633,841 to 1,427,149. Significant."),
        (
            TEAL,
            "C. 2 RUB + 3% discount",
            "+2,769,045 RUB vs everyone",
            "CI 2,203,378 to 3,249,314. Significant.",
        ),
    ]
    hh = (fh - 0.24) / 3
    for i, (col, head, val, sub) in enumerate(items):
        yy = TOP + i * (hh + 0.12)
        card(s, rx, yy, rw, hh, accent=col)
        text(s, rx + 0.22, yy + 0.03, rw - 0.3, 0.3, head, size=14, color=MUTED, bold=True)
        text(
            s,
            rx + 0.22,
            yy + 0.29,
            rw - 0.3,
            0.36,
            val,
            size=17,
            bold=True,
            color=INK if col == GREY else TEAL_D,
        )
        text(
            s,
            rx + 0.22,
            yy + 0.62,
            rw - 0.3,
            hh - 0.6,
            sub,
            size=14,
            color=MUTED,
            spacing=0.95,
            after=0,
        )
    y = TOP + fh + 0.14
    card(s, LEFT, y, CW, 1.26, accent=AMBER, fill=AMBER_SOFT)
    text(
        s,
        LEFT + 0.3,
        y,
        CW - 0.5,
        1.26,
        [
            [
                ("Honest reading.  ", {"bold": True, "color": AMBER_D}),
                (
                    "LiftPilot's own profit interval crosses zero when contact is costly: B = 204,762 RUB "
                    "(95% CI -206,450 to 598,342); C = 60,933 RUB (-42,660 to 173,516).",
                    {},
                ),
            ],
            [
                (
                    "Bars: real incremental profit with 95% intervals. Replay on held-out test "
                    "customers, scaled to 400,162. Margin 25% and costs are scenario assumptions, "
                    "not facts about X5.",
                    {"color": MUTED},
                )
            ],
        ],
        size=15,
        anchor=MSO_ANCHOR.MIDDLE,
        after=3,
    )


def s_ltv(d: Deck) -> None:
    s = d.slide("ltv")
    c = {"align": PP_ALIGN.RIGHT}
    cb = {"align": PP_ALIGN.RIGHT, "bold": True, "color": TEAL_D}
    rows = [
        ["Segment", ("Monthly churn", c), ("Retention", c), ("LTV, RUB", c), ("Uplift", c)],
        [
            ("All customers", {"bold": True}),
            ("7.7%", c),
            ("92.3%", c),
            ("8,142", c),
            ("+3.3 pts", c),
        ],
        ["Cannot lose them", ("0.5%", c), ("99.5%", c), ("44,599", c), ("+1.9 pts", c)],
        ["Champions", ("0.6%", c), ("99.4%", c), ("38,514", c), ("+1.2 pts", c)],
        ["Loyal", ("0.6%", c), ("99.4%", c), ("37,237", c), ("+1.2 pts", c)],
        ["At risk", ("2.7%", c), ("97.3%", c), ("22,363", c), ("+3.2 pts", c)],
        ["Potential loyalists", ("4.2%", c), ("95.8%", c), ("9,647", c), ("+3.3 pts", c)],
        ["Need attention", ("6.1%", c), ("93.9%", c), ("6,588", c), ("+3.5 pts", c)],
        ["Hibernating", ("22.3%", c), ("77.7%", c), ("1,090", c), ("+4.6 pts", cb)],
        ["New customers", ("20.6%", c), ("79.4%", c), ("922", c), ("+5.6 pts", cb)],
    ]
    rh = 0.42
    table(s, LEFT, TOP, [2.75, 1.75, 1.45, 1.4, 1.35], rows, size=16, row_h=rh)
    text(
        s,
        LEFT,
        TOP + rh * 10 + 0.1,
        8.7,
        0.75,
        "LTV = gross profit over the capped lifetime, margin 25%. The three segments with the "
        "highest lifetime value are the ones a message changes least.",
        size=15,
        color=MUTED,
    )
    rx = LEFT + 8.7 + 0.35
    rw = W - LEFT - rx
    card(s, rx, TOP, rw, 2.5, accent=BLUE)
    text(s, rx + 0.25, TOP + 0.1, rw - 0.35, 0.4, "Course formulas", size=18, bold=True, color=BLUE)
    text(
        s,
        rx + 0.25,
        TOP + 0.56,
        rw - 0.35,
        1.9,
        [
            "retention = 1 - churn",
            "lifetime = 1 / churn, capped at 36 months",
            "LTV = AOV x orders per month x margin x lifetime",
        ],
        size=15,
        bold=True,
        after=7,
    )
    card(s, rx, TOP + 2.68, rw, 1.95, accent=AMBER, fill=AMBER_SOFT)
    text(
        s,
        rx + 0.25,
        TOP + 2.68,
        rw - 0.35,
        1.95,
        [
            [
                ("Horizon caveat.  ", {"bold": True, "color": AMBER_D}),
                (
                    "Three complete months, two month-to-month transitions. Read these as orders "
                    "of magnitude.",
                    {},
                ),
            ]
        ],
        size=16,
        anchor=MSO_ANCHOR.MIDDLE,
    )


def s_agent(d: Deck) -> None:
    s = d.slide("agent")
    lw = 5.3
    card(s, LEFT, TOP, lw, 1.72, accent=VIOLET)
    text(
        s,
        LEFT + 0.28,
        TOP + 0.06,
        lw - 0.4,
        1.6,
        [
            [("Utility-based agent", {"bold": True, "color": VIOLET, "size": 18})],
            "Seeks the plan with the highest expected incremental profit.",
            [("Qwen3 8B through Ollama on the laptop GPU. No cloud, 0 USD.", {"color": MUTED})],
        ],
        size=15,
        after=3,
    )
    y = TOP + 1.9
    text(s, LEFT, y, lw, 0.4, "16 tools, three privilege levels", size=18, bold=True)
    levels = [
        (BLUE, "12", "READ", "facts and analysis; run freely"),
        (AMBER_D, "3", "PROPOSE", "plan, drafts, approval request"),
        (RED, "1", "ACTION", "export; refused without approval"),
    ]
    for i, (col, n, name, desc) in enumerate(levels):
        yy = y + 0.48 + i * 0.6
        pill(s, LEFT, yy, 0.62, n, col, size=18, h=0.46)
        text(s, LEFT + 0.75, yy + 0.03, 1.3, 0.4, name, size=16, bold=True, color=col)
        text(s, LEFT + 2.02, yy + 0.05, lw - 2.0, 0.4, desc, size=14, color=INK)
    text(
        s,
        LEFT,
        y + 2.36,
        lw,
        0.72,
        "MCP-style contracts: each tool has a name, a description and a typed JSON schema. "
        "The model sees nothing else.",
        size=14,
        color=MUTED,
    )
    rx = LEFT + lw + 0.35
    rw = W - LEFT - rx
    rows = [
        ["Seen in testing or review", "Control built in"],
        [
            "Invented arguments",
            "Provenance guard: values not traceable to the manager's words are dropped",
        ],
        ["A guessed budget", "A budget or its currency is never guessed: the plan is refused"],
        ["Skipped steps", "Runtime checklist forces evidence, fairness audit, approval request"],
        [
            "Misdescribed figures",
            "Facts written by code as verified statements; the model only narrates",
        ],
        [
            "Wrong numbers or wording",
            "Grounding and over-claim checks; a failing narrative is discarded",
        ],
        ["Risky message copy", "Copy checked by code; a failing message is never stored"],
    ]
    rows = [[(r[0], {"bold": True}), r[1]] if i else r for i, r in enumerate(rows)]
    table(s, rx, TOP, [2.7, rw - 2.7], rows, size=14, row_h=0.56)
    yb = TOP + 0.56 * 7 + 0.2
    card(s, rx, yb, rw, 0.9, accent=RED, fill=RED_SOFT)
    text(
        s,
        rx + 0.28,
        yb,
        rw - 0.4,
        0.9,
        [
            [
                ("Human checkpoint.  ", {"bold": True, "color": RED}),
                ("No export until a named human approves. The agent cannot approve itself.", {}),
            ]
        ],
        size=16,
        anchor=MSO_ANCHOR.MIDDLE,
    )


def s_where(d: Deck) -> None:
    s = d.slide("where")

    def who(label, col):
        return (label, {"bold": True, "color": col})

    rows = [
        ["Step", "Done by", "How"],
        [
            "Estimate each customer's uplift",
            who("Machine learning", TEAL_D),
            "Gradient-boosted uplift learners, calibrated",
        ],
        ["Decide contact or skip", who("Rules", BLUE), "Profit rule, budget, opt-outs, no minors"],
        ["Prove the plan", who("Statistics", BLUE), "Replay on held-out customers, 95% intervals"],
        [
            "Choose tools, explain, draft messages",
            who("Language model", VIOLET),
            "Local Qwen3 8B; one draft per RFM segment",
        ],
        [
            "Check numbers, wording and copy",
            who("Rules", BLUE),
            "Grounding, over-claim and copy checks in code",
        ],
        ["Approve and export", who("Human", RED), "Named approver; random hold-out kept"],
    ]
    rh = 0.42
    table(s, LEFT, TOP, [4.5, 2.25, CW - 6.75], rows, size=16, row_h=rh)
    y = TOP + rh * 7 + 0.16
    if BENCH is None:
        head = "Agent benchmark: 13 fixed requests (7 campaign plans, 3 questions, 3 safety probes)"
        tiles = [
            ("Argument fidelity", "did the planner get exactly what was stated?"),
            ("Checklist", "evidence, fairness, hold-out, approval request"),
            ("Numeric grounding", "share of numbers traced to a tool"),
            ("Safety probes", "export without approval, gender targeting, a guarantee"),
        ]
        note = "Figures were being regenerated when this deck was built: see docs/RESULTS.md, section 10."
    else:
        b = BENCH
        head = (
            f"Agent benchmark: {b['cases']} fixed requests (7 campaign plans, 3 questions, "
            f"3 safety probes), model {b['model']}"
        )
        tiles = [
            (b["fidelity"], "argument fidelity"),
            (b["checklist"], "checklist completed"),
            (b["grounding"], f"of {b['numbers']} numbers"),
            (b["probes"], "safety probes passed"),
            (f"{b['median']} s", "median full plan"),
        ]
        note = (
            f"Fidelity is measured after the provenance guard; runs in which it dropped invented "
            f"assumptions: {b['blocked']}. Numbers grounded = traced to a tool result. Narratives "
            f"rejected by the guards and replaced by the verified statements: {b['rejected']}. "
            f"Message drafts passing the copy checks: {b['drafts_pass']} of {b['drafts']}."
        )
    text(s, LEFT, y, CW, 0.38, head, size=16, bold=True, color=VIOLET)
    n = len(tiles)
    gap = 0.18
    tw = (CW - (n - 1) * gap) / n
    th = 1.0
    for i, (big, small) in enumerate(tiles):
        x = LEFT + i * (tw + gap)
        card(s, x, y + 0.42, tw, th, accent=VIOLET)
        if BENCH:
            text(s, x + 0.2, y + 0.42, tw - 0.25, 0.5, big, size=24, bold=True, color=VIOLET)
            text(s, x + 0.2, y + 0.94, tw - 0.25, 0.4, small, size=14, color=MUTED)
        else:
            text(s, x + 0.2, y + 0.44, tw - 0.25, 0.36, big, size=16, bold=True, color=VIOLET)
            text(s, x + 0.2, y + 0.78, tw - 0.25, 0.6, small, size=14, color=MUTED, spacing=0.92)
    text(s, LEFT, y + 0.42 + th + 0.04, CW, 0.55, note, size=14, color=MUTED, spacing=0.98)


def s_demo(d: Deck) -> None:
    s = d.slide("demo")
    steps = [
        (BLUE, "1", "Problem", "The experiment: 63.65% vs 60.33%"),
        (BLUE, "2", "Customers (RFM)", "Which segments really react"),
        (TEAL_D, "3", "Uplift models", "Likely-buyer model against uplift model"),
        (TEAL_D, "4", "Optimizer", "The plan at 6 RUB, and its fairness check"),
        (VIOLET, "5", "AI agent", "Tool calls, verified statements, my approval"),
        (AMBER_D, "6", "Ethics & audit", "Fairness chart, guardrails, audit log"),
    ]
    gap = 0.2
    cw_ = (CW - 2 * gap) / 3
    for i, (col, n, head, body) in enumerate(steps):
        r_, c_ = divmod(i, 3)
        x = LEFT + c_ * (cw_ + gap)
        y = TOP + r_ * 1.5
        card(s, x, y, cw_, 1.32)
        pill(s, x + 0.2, y + 0.2, 0.56, n, col, size=20, h=0.56)
        text(s, x + 0.95, y + 0.14, cw_ - 1.1, 0.42, head, size=20, bold=True, color=col)
        text(s, x + 0.95, y + 0.6, cw_ - 1.1, 0.7, body, size=16, color=MUTED)
    y = TOP + 3.12
    card(s, LEFT, y, CW, 1.25, accent=VIOLET)
    text(
        s,
        LEFT + 0.3,
        y + 0.08,
        CW - 0.5,
        0.36,
        "The request the agent has been working on since slide 11",
        size=14,
        bold=True,
        color=VIOLET,
    )
    text(
        s,
        LEFT + 0.3,
        y + 0.42,
        CW - 0.5,
        0.8,
        '"The CEO gives us a budget of 1,000,000 BRL. A message costs 6 RUB, margin 25%. Plan '
        'the campaign and show the evidence."',
        size=18,
        bold=True,
    )
    text(
        s,
        LEFT,
        y + 1.4,
        CW,
        0.4,
        "Runs on this laptop: local model, real data, live exchange rate (cached if the Wi-Fi fails).",
        size=16,
        color=MUTED,
        align=PP_ALIGN.CENTER,
    )


def s_ethics(d: Deck) -> None:
    s = d.slide("ethics")
    w, fh = 4.5, 3.8
    chart(s, "fairness", LEFT, TOP, w, fh, draw_fairness)
    rx = LEFT + w + 0.22
    rw = W - LEFT - rx
    # --- what the audit measured: one ratio per contact cost
    h1 = 1.8
    card(s, rx, TOP, rw, h1, accent=VIOLET)
    text(
        s,
        rx + 0.25,
        TOP + 0.05,
        rw - 0.35,
        0.36,
        [
            [
                ("Measured among adults", {"bold": True, "color": VIOLET, "size": 17}),
                ("    lowest / highest selection rate", {"color": MUTED, "size": 14}),
            ]
        ],
        size=14,
        after=0,
    )
    nw = 0.98
    for i, cost in enumerate((2.0, 4.0, 6.0, 10.0)):
        x = rx + 0.25 + i * nw
        flag = FAIR[cost]["flag"]
        text(
            s, x, TOP + 0.4, nw, 0.52, ratio(cost), size=26, bold=True, color=RED if flag else INK
        )
        text(
            s,
            x,
            TOP + 0.9,
            nw,
            0.3,
            f"{cost:g} RUB",
            size=14,
            bold=flag,
            color=RED if flag else MUTED,
        )
    ex = rx + 0.25 + 4 * nw + 0.05
    text(
        s,
        ex,
        TOP + 0.44,
        rx + rw - ex - 0.12,
        0.8,
        "Under 0.80: flagged for human review. Minors are excluded by rule and kept out of "
        "the audit.",
        size=14,
        after=0,
        spacing=1.0,
    )
    text(
        s,
        rx + 0.25,
        TOP + 1.2,
        rw - 0.35,
        0.56,
        f"At 10 RUB the group selected least is {AGE['low10']}, the one the message moves "
        f"least: {AGE['up_low']} pts measured, against {AGE['up_old']} for 65+.",
        size=14,
        color=MUTED,
        spacing=1.0,
        after=0,
    )
    # --- the fix that failed, and the error a review caught
    y2 = TOP + h1 + 0.14
    h2 = fh - h1 - 0.14
    hw = (rw - 0.2) / 2
    card(s, rx, y2, hw, h2, accent=RED)
    text(
        s,
        rx + 0.25,
        y2 + 0.04,
        hw - 0.33,
        h2 - 0.06,
        [
            [("Negative result", {"bold": True, "color": RED, "size": 17})],
            f"Fair mode at 6 RUB made the gap worse: ratio {AGE['fair_on']} (was "
            f"{AGE['fair_off']}), profit {AGE['profit_on']} RUB (was {AGE['profit_off']}).",
            [(f"95% CI {AGE['ci_on']} (was {AGE['ci_off']}).", {"color": MUTED, "size": 14})],
        ],
        size=15,
        after=3,
        spacing=1.0,
    )
    card(s, rx + hw + 0.2, y2, hw, h2, accent=AMBER, fill=AMBER_SOFT)
    text(
        s,
        rx + hw + 0.45,
        y2 + 0.04,
        hw - 0.33,
        h2 - 0.06,
        [
            [("Caught by a code review", {"bold": True, "color": AMBER_D, "size": 17})],
            "Our first audit counted excluded minors inside the 18-24 band and overstated the "
            f"gap ({OLD_AUDIT}).",
            [("The audit itself needs review.", {"bold": True})],
        ],
        size=15,
        after=3,
        spacing=1.0,
    )
    y = TOP + fh + 0.12
    hb = 6.93 - y
    card(s, LEFT, y, CW, hb, fill=SOFT)
    text(
        s,
        LEFT + 0.25,
        y,
        CW - 0.4,
        hb,
        [
            [
                ("Controls.  ", {"bold": True, "color": TEAL_D}),
                (
                    "Age and gender are never model inputs. Ratio under 0.80: human review. "
                    "Opt-outs and minors are never contacted. No pressure tactics in copy. A human "
                    "approves; a hold-out measures.",
                    {},
                ),
            ],
            [
                ("Legal texts read in the original.  ", {"bold": True}),
                (
                    "GDPR Art. 21(2)-(3): right to object to direct marketing and its profiling.  GDPR "
                    "Art. 22 and LGPD Art. 20: rights over decisions based solely on automated "
                    "processing.  EU AI Act Art. 5(1)(b): no exploiting vulnerability due to age.  "
                    "Our reading, not legal advice.",
                    {},
                ),
            ],
        ],
        size=14,
        anchor=MSO_ANCHOR.MIDDLE,
        after=3,
        spacing=1.0,
    )


GANTT = [
    ("Data audit, consent and opt-out lists", 0, 2, BLUE),
    ("Receipts to RFM feature pipeline", 1, 2, BLUE),
    ("Design and run baseline randomised test", 2, 3, AMBER),
    ("Train, calibrate, select uplift model", 5, 2, TEAL),
    ("Off-policy evaluation and fairness audit", 6, 1.5, TEAL),
    ("Agent tools, guardrails, approval flow", 4, 3.5, VIOLET),
    ("Staff training, governance sign-off", 7, 1.5, RED),
    ("Pilot campaign with random hold-out", 8.5, 2, AMBER),
    ("Read-out, model refresh, go / no-go", 10.5, 1.5, TEAL),
]
MILESTONES = [(5, "M1 test read-out"), (8.5, "M2 model approved"), (12, "M3 decision")]


def s_business(d: Deck) -> None:
    s = d.slide("business")
    gy, gh = TOP - 0.05, 3.5
    rect(s, LEFT, gy, CW, gh, fill=WHITE)
    lab_w = 4.35
    x0 = LEFT + lab_w + 0.15
    week = (W - LEFT - 0.35 - x0) / 12
    row_h = 0.285
    n = len(GANTT)
    y0 = gy + 0.42
    for wk in range(13):
        rect(s, x0 + wk * week - 0.005, y0, 0.01, row_h * n, fill=LINE, line=None, rounded=False)
        if wk % 2 == 0:
            text(
                s,
                x0 + wk * week - 0.4,
                y0 + row_h * n + 0.02,
                0.8,
                0.3,
                f"W{wk}",
                size=14,
                color=MUTED,
                align=PP_ALIGN.CENTER,
            )
    for xm, label in MILESTONES:
        rect(
            s,
            x0 + xm * week - 0.012,
            y0 - 0.06,
            0.024,
            row_h * n + 0.06,
            fill=INK,
            line=None,
            rounded=False,
        )
        text(
            s,
            x0 + xm * week - 2.2,
            gy + 0.05,
            2.2,
            0.3,
            label,
            size=14,
            bold=True,
            align=PP_ALIGN.RIGHT,
        )
    for i, (name, start, dur, col) in enumerate(GANTT):
        yy = y0 + i * row_h
        text(s, LEFT + 0.1, yy - 0.02, lab_w, row_h, name, size=14, align=PP_ALIGN.RIGHT, after=0)
        rect(
            s,
            x0 + start * week,
            yy + 0.045,
            dur * week,
            row_h - 0.09,
            fill=col,
            line=None,
            radius=0.03,
        )
    y = gy + gh + 0.1
    text(
        s,
        LEFT,
        y,
        CW,
        0.32,
        "What a retailer needs: its receipts and one campaign sent at random (the orange bar, "
        "weeks 3 to 5). Our next step: run this pilot.",
        size=14,
        color=MUTED,
    )
    y += 0.4
    gap = 0.2
    cw_ = (CW - 2 * gap) / 3
    ch = 6.95 - y
    blocks = [
        (
            TEAL,
            TEAL_D,
            WHITE,
            "It helps when",
            "contact costs real money or carries a discount, and customers react differently.",
        ),
        (
            RED,
            RED,
            WHITE,
            "It does not help when",
            "contact is nearly free (2 RUB), or everyone reacts the same (Hillstrom).",
        ),
        (
            AMBER,
            AMBER_D,
            AMBER_SOFT,
            "Limits today",
            "One campaign, one period. Small effect, wide intervals. Purchase amounts imputed.",
        ),
    ]
    for i, (acc, col, fill, head, body) in enumerate(blocks):
        x = LEFT + i * (cw_ + gap)
        card(s, x, y, cw_, ch, accent=acc, fill=fill)
        text(
            s,
            x + 0.25,
            y + 0.03,
            cw_ - 0.35,
            ch - 0.05,
            [[(head, {"bold": True, "color": col, "size": 17})], body],
            size=14,
            after=2,
            spacing=1.0,
        )


def s_close(d: Deck) -> None:
    s = d.slide("close", title=False)
    rect(s, 0, 0, 0.42, H, fill=INK, line=None, rounded=False)
    rect(s, 0.42, 0, 0.09, H, fill=TEAL, line=None, rounded=False)
    text(
        s,
        1.2,
        1.2,
        11.2,
        2.4,
        "Do not pay for purchases you were going to get anyway.",
        size=50,
        bold=True,
        spacing=1.0,
    )
    text(
        s,
        1.25,
        3.75,
        10.8,
        1.4,
        [
            [
                ("LiftPilot ", {"bold": True, "color": TEAL_D}),
                (
                    "finds the customers a message really changes, proves the plan on a real experiment, "
                    "and asks a human before anything is sent.",
                    {},
                ),
            ]
        ],
        size=24,
        spacing=1.08,
    )
    card(s, 1.25, 5.3, 6.9, 0.75, accent=TEAL)
    text(
        s,
        1.55,
        5.3,
        6.5,
        0.75,
        "Code, paper and every number: the liftpilot repository",
        size=18,
        bold=True,
        anchor=MSO_ANCHOR.MIDDLE,
    )
    text(
        s,
        8.5,
        5.3,
        4.2,
        0.75,
        "Thank you. Questions?",
        size=26,
        bold=True,
        color=TEAL_D,
        anchor=MSO_ANCHOR.MIDDLE,
    )
    text(
        s,
        1.25,
        6.3,
        10.8,
        0.4,
        "Abed El Rahmane Jaafir and Ghandi Mahdmoud  |  Group 10",
        size=16,
        color=MUTED,
    )


def s_learners(d: Deck) -> None:
    s = d.slide("learners", backup=True)
    c = {"align": PP_ALIGN.RIGHT}
    bad = {"align": PP_ALIGN.RIGHT, "color": RED, "bold": True}
    data = [
        ("Likely-buyer (response)", "-0.0052", "-0.0116 to +0.0010", "+1.9", "+1.5", "+4.1", "-0.0052 ± 0.0024"),
        ("S-learner (champion)", "+0.0089", "+0.0021 to +0.0156", "+9.9", "+5.0", "+2.9", "+0.0143 ± 0.0030"),
        ("T-learner", "+0.0092", "+0.0012 to +0.0164", "+7.9", "+4.4", "+2.0", "+0.0115 ± 0.0024"),
        ("X-learner", "+0.0073", "+0.0003 to +0.0149", "+9.0", "+4.4", "+2.9", "+0.0145 ± 0.0009"),
        ("DR-learner", "+0.0098", "+0.0032 to +0.0162", "+7.6", "+4.8", "+2.4", "+0.0125 ± 0.0020"),
        ("Class transformation", "+0.0082", "+0.0025 to +0.0156", "+5.1", "+4.5", "+2.0", "+0.0116 ± 0.0022"),
        ("Ensemble", "+0.0090", "+0.0017 to +0.0163", "+8.7", "+4.8", "+2.4", "+0.0141 ± 0.0016"),
    ]
    rows: list[list] = [
        [
            "Model",
            ("Qini (test)", c),
            "95% CI",
            ("Top 10%", c),
            ("Top 30%", c),
            ("Bottom 30%", c),
            "Qini, 5 re-splits",
        ]
    ]
    for i, (name, q, ci, t10, t30, b30, rs) in enumerate(data):
        first = (name, {"bold": True, "color": TEAL_D}) if i == 1 else name
        rows.append([first, (q, bad if i == 0 else c), ci, (t10, c), (t30, c), (b30, c), rs])
    table(s, LEFT, TOP, [3.05, 1.35, 2.35, 1.1, 1.1, 1.4, 1.78], rows, size=14, row_h=0.45)
    text(
        s,
        LEFT,
        TOP + 0.45 * 8 + 0.2,
        CW,
        1.3,
        [
            "Uplift columns are real uplift in points among the top or bottom share of test customers "
            "(average +3.3). Champion chosen by Qini on the calibration split. The intervals of the "
            "uplift models overlap: we do not rank them.",
            [
                (
                    "Feature ablation: RFM only (3 features) Qini +0.0085; all behaviour features +0.0089; "
                    "adding age and gender +0.0097, not a significant gain, so they stay out.",
                    {"color": MUTED},
                )
            ],
        ],
        size=15,
        after=5,
    )


def s_hillstrom(d: Deck) -> None:
    s = d.slide("hillstrom", backup=True)
    c = {"align": PP_ALIGN.RIGHT}
    rows = [
        [
            "Scenario",
            ("Contact everyone, USD", c),
            ("Contacted", c),
            ("LiftPilot, USD", c),
            ("Difference, USD", c),
        ],
        [
            ("A. E-mail, 0.10 USD all-in", {"bold": True}),
            ("13,260 (1,174 to 23,770)", c),
            ("100.0%", c),
            ("13,260 (1,174 to 23,770)", c),
            ("0 (0 to 0)", c),
        ],
        [
            ("B. Printed mailer, 0.60 USD", {"bold": True}),
            ("-18,740 (-30,826 to -8,230)", c),
            ("0.0%", c),
            ("0 (0 to 0)", c),
            ("18,740 (8,230 to 30,826)", {"align": PP_ALIGN.RIGHT, "bold": True, "color": TEAL_D}),
        ],
        [
            ("C. E-mail + 10% discount", {"bold": True}),
            ("5,179 (-5,774 to 14,373)", c),
            ("17.1%", c),
            ("960 (-3,372 to 4,603)", c),
            ("-4,219 (-13,334 to 5,876)", {"align": PP_ALIGN.RIGHT, "bold": True, "color": RED}),
        ],
    ]
    table(s, LEFT, TOP, [2.9, 2.85, 1.2, 2.5, 2.68], rows, size=14, row_h=0.62)
    text(
        s,
        LEFT,
        TOP + 0.62 * 4 + 0.25,
        CW,
        2.4,
        [
            "Incremental profit with 95% intervals. 64,000 customers, real spend in USD. Visit rate "
            "16.70% e-mailed vs 10.62% not: +6.09 pts (95% CI +5.54 to +6.63).",
            "The rule finds the switch: send to all at 0.10 USD, to nobody at 0.60 USD. In scenario C "
            "it loses to sending to everyone, by an amount that is not significant.",
            [
                (
                    "The effect is nearly uniform and uplift rankings are unstable: S-learner Qini on "
                    "test +0.043 (+0.014 to +0.073), but +0.024 ± 0.021 over repeated splits. "
                    "Targeting only helps where effects really differ between customers.",
                    {"color": MUTED},
                )
            ],
        ],
        size=16,
        after=8,
    )


def s_sources(d: Deck) -> None:
    s = d.slide("sources", backup=True)
    colw = (CW - 0.3) / 2

    def block(x, y, h, head, col, items):
        card(s, x, y, colw, h, accent=col)
        text(
            s,
            x + 0.25,
            y + 0.05,
            colw - 0.35,
            h - 0.08,
            [[(head, {"bold": True, "color": col, "size": 16})], *items],
            size=14,
            after=3,
            spacing=0.97,
        )

    block(
        LEFT,
        TOP - 0.05,
        2.1,
        "Data",
        BLUE,
        [
            "X5 Retail Group, RetailHero uplift data: "
            "ods.ai/competitions/x5-retailhero-uplift-modeling/data",
            "K. Hillstrom, MineThatData e-mail analytics challenge, blog post of 20 March 2008: "
            "blog.minethatdata.com",
            "Exchange rates: frankfurter.dev.  Public holidays: date.nager.at.",
        ],
    )
    block(
        LEFT,
        TOP + 2.2,
        2.98,
        "Methods",
        TEAL_D,
        [
            'P. Gutierrez and J.-Y. Gerardy, "Causal inference and uplift modelling: A review of the '
            'literature," Proc. Mach. Learn. Res., vol. 67, 2017, pp. 1-13.',
            'S. R. Kunzel et al., "Metalearners for estimating heterogeneous treatment effects using '
            'machine learning," Proc. Natl. Acad. Sci. U.S.A., vol. 116, no. 10, 2019, '
            "doi: 10.1073/pnas.1804597116.",
            'E. H. Kennedy, "Towards optimal doubly robust estimation of heterogeneous causal '
            'effects," Electron. J. Statist., vol. 17, no. 2, 2023, doi: 10.1214/23-EJS2157.',
        ],
    )
    x2 = LEFT + colw + 0.3
    block(
        x2,
        TOP - 0.05,
        2.1,
        "Methods (continued)",
        TEAL_D,
        [
            'M. Jaskowski and S. Jaroszewicz, "Uplift modeling for clinical trial data," 29th Int. '
            "Conf. Machine Learning (ICML), Edinburgh, 2012 (class transformation).",
            'N. J. Radcliffe and P. D. Surry, "Real-world uplift modelling with significance-based '
            'uplift trees," Portrait Tech. Rep. TR-2011-1, 2011 (Qini).',
        ],
    )
    block(
        x2,
        TOP + 2.2,
        2.98,
        "Ethics and law",
        VIOLET,
        [
            "Regulation (EU) 2016/679 (GDPR), Art. 21(2)-(3) and Art. 22.",
            "Regulation (EU) 2024/1689 (AI Act), Art. 5(1)(b).",
            "Brazil, Lei No. 13.709/2018 (LGPD), Art. 20.",
            'D. Susser, B. Roessler, H. Nissenbaum, "Technology, autonomy, and manipulation," '
            "Internet Policy Review, vol. 8, no. 2, 2019, doi: 10.14763/2019.2.1410.",
            "NIST, AI Risk Management Framework (AI RMF 1.0), NIST AI 100-1, 2023.",
        ],
    )


# ------------------------------------------------------------------ script file
def mmss(sec: int) -> str:
    return f"{sec // 60}:{sec % 60:02d}"


def pace(words: int, seconds: int) -> int:
    return round(words / seconds * 60)


def demo_script() -> list[str]:
    L = [
        "**Transition into the demo** (Alt+Tab to the browser):",
        "",
        f"#### Live demo ({mmss(DEMO_SECONDS)}). Full click path, timings and fallbacks are in "
        "`DEMO_RUNBOOK.md`.",
        "",
    ]
    for i, (clock, sec, where, do, say) in enumerate(DEMO_STEPS, 1):
        L.append(f'{i}. **{clock}, {where} ({mmss(sec)}).** {do} "{say}"')
    L += [
        "",
        f"Reserve: {mmss(DEMO_RESERVE)}. If the spinner still turns when you reach tab 5, do not "
        "click anything and say the waiting script:",
        "",
        f"> {WAITING}",
        "",
        "If the answer has not arrived when the waiting script ends, switch to the second "
        "browser tab, which holds the same request run during the pre-flight, and continue "
        'there: "The live run is slow today. This is the same request, run on this laptop '
        'before the talk."',
        "",
        "**Transition out of the demo** (Alt+Tab back to PowerPoint, slide 15):",
        "",
        '> "So the system works, and it audits its own fairness. Let us look at that audit '
        'properly."',
        "",
    ]
    return L


EMERGENCY = [
    "## 60-second emergency version",
    "",
    "Use it if the projector fails, if you are told to stop early, or as the answer to "
    '"summarise your project in one minute". About 140 words.',
    "",
    "> A grocery chain sent a message to half of two hundred thousand customers at random. "
    "Sixty-four percent of the contacted customers bought, but sixty percent of the others "
    "bought anyway. So about ninety-five of every hundred campaign purchases were not caused "
    "by the campaign. LiftPilot is an AI agent built for this problem. Uplift models estimate, "
    "for each customer, how much a message changes their behaviour. A profit rule contacts only "
    "the customers where that change is worth more than the cost. We check each plan by "
    "replaying it on the real experiment. When a message costs 6 roubles, that is about one "
    "million roubles better than contacting everyone. When a message is cheap, it does not "
    "help, and we say so. A local language model plans and explains, code checks its numbers, "
    "and a human approves before anything is sent.",
    "",
]


def write_script(path: Path) -> None:
    order = [k for k, _, _ in SCRIPT]
    slide_seconds = sum(SLOT.values())
    words = sum(spoken_words(t) for _, _, t in SCRIPT) + spoken_words(KICKOFF_SAY)
    raw = sum(len(t.split()) for _, _, t in SCRIPT) + len(KICKOFF_SAY.split())
    talk_seconds = slide_seconds + KICKOFF_SECONDS
    total = talk_seconds + DEMO_SECONDS
    demo_words = sum(spoken_words(say) for *_, say in DEMO_STEPS)
    demo_talk = sum(sec for _, sec, *_ in DEMO_STEPS)
    L: list[str] = [
        "# LiftPilot: speaker script",
        "",
        "_Generated by `docs/presentation/build_deck.py` together with the deck, so the text here "
        "is the text in the speaker notes. Edit the script in that file, then rebuild._",
        "",
        f"One speaker: Abed. Total {mmss(total)} = {mmss(slide_seconds)} of slides + "
        f"{mmss(KICKOFF_SECONDS)} to start the agent + {mmss(DEMO_SECONDS)} of live demo. "
        "Questions follow.",
        "",
        f"Word count. The slide text is {raw} written words. Counted the way it is said (a "
        "number such as 63.65 is five spoken words, a hyphenated word counts per part) it is "
        f"{words} spoken words. At {WPM} words per minute that is {words / WPM:.1f} minutes of "
        f"speech inside {talk_seconds / 60:.2f} minutes of slide time, so "
        f"{(talk_seconds - words / WPM * 60):.0f} seconds remain for clicks, pauses and pointing "
        "at the screen. Do not fill them with extra words.",
        "",
        f"The demo narration is {demo_words} spoken words in {mmss(demo_talk)} of planned steps "
        f"({pace(demo_words, demo_talk)} words per minute), plus a reserve of "
        f"{mmss(DEMO_RESERVE)} for a slow model.",
        "",
        'Reading aids: numbers are written as digits; say them in full. "Points" always means '
        'percentage points. "Roubles" is presumed: the dataset does not name its currency, and '
        'slide 5 says so. Never say the channel was SMS; say "a communication" or "a message".',
        "",
        "## Time budget",
        "",
        "| # | Slide | Slot | Running total | Spoken words | Pace (words/min) |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    run = 0
    marks: dict[str, int] = {}
    for i, key in enumerate(order, 1):
        slot = SLOT[key]
        run += slot
        marks[key] = run
        name = TITLES[key] if key != "title" else "Title"
        sw = spoken_words(NOTES[key])
        L.append(f"| {i} | {name} | {mmss(slot)} | {mmss(run)} | {sw} | {pace(sw, slot)} |")
        if key == "ltv":
            run += KICKOFF_SECONDS
            sw = spoken_words(KICKOFF_SAY)
            L.append(
                f"|  | START THE AGENT (Alt+Tab, one click, Alt+Tab back) | {mmss(KICKOFF_SECONDS)} "
                f"| {mmss(run)} | {sw} | {pace(sw, KICKOFF_SECONDS)} |"
            )
        if key == "demo":
            marks["demo_start"] = run
            run += DEMO_SECONDS
            marks["demo_end"] = run
            L.append(
                f"|  | LIVE DEMO (see `DEMO_RUNBOOK.md`) | {mmss(DEMO_SECONDS)} | {mmss(run)} | "
                f"{demo_words} |  |"
            )
    L += [f"|  | **Total** | **{mmss(run)}** |  | **{words + demo_words}** |  |", ""]
    worst = max(order, key=lambda k: pace(spoken_words(NOTES[k]), SLOT[k]))
    L += [
        f"Every slide is at or below {WPM} spoken words per minute; the fastest is slide "
        f"{order.index(worst) + 1} at {pace(spoken_words(NOTES[worst]), SLOT[worst])}.",
        "",
        f"Checkpoints to glance at the clock: end of slide 9 (calculation) at about "
        f"{mmss(marks['calc'])}; the agent is started at about {mmss(marks['ltv'])}; the demo "
        f"starts at about {mmss(marks['demo_start'])} and must end by {mmss(marks['demo_end'])}; "
        f"the closing slide starts at {mmss(marks['business'])}.",
        "",
        "If you are more than 30 seconds late at slide 9, shorten slide 11 (say only: "
        '"Retention and lifetime value by segment are here; the caveat is that we have three '
        'months of data") and drop the benchmark sentences on slide 13. Never skip the agent '
        "start after slide 11: the demo depends on it.",
        "",
        "## The script, slide by slide",
        "",
    ]
    for i, key in enumerate(order, 1):
        name = TITLES[key] if key != "title" else "Title"
        L += [f"### Slide {i} ({mmss(SLOT[key])}): {name}", "", NOTES[key], ""]
        if key == "ltv":
            L += [
                f"### Start the agent ({mmss(KICKOFF_SECONDS)}), between slide 11 and slide 12",
                "",
                f"Do: {KICKOFF_DO}",
                "",
                f"> {KICKOFF_SAY}",
                "",
                "Why now: a full campaign plan takes about 50 seconds on a cool laptop and two "
                "minutes or more when the GPU is hot or shared"
                + (f" (benchmark median {BENCH['median']} seconds)" if BENCH else "")
                + ". Slides 12 to 14 and the first four demo tabs cover that wait. If the "
                "language model is down, do not click Run agent with this request: it names a "
                "cost and a budget, so the agent refuses to plan. Use Run scripted planner (see "
                "`DEMO_RUNBOOK.md`, fallback B).",
                "",
            ]
        if key == "demo":
            L += demo_script()
    L += [
        "### Backup slide 1: model table (only if asked)",
        "",
        BACKUP_NOTES["learners"],
        "",
        "### Backup slide 2: Hillstrom (only if asked)",
        "",
        BACKUP_NOTES["hillstrom"],
        "",
        "### Backup slide 3: sources (only if asked)",
        "",
        BACKUP_NOTES["sources"],
        "",
    ]
    L += EMERGENCY
    path.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


def build() -> Path:
    d = Deck()
    for fn in (
        s_title,
        s_hook,
        s_six,
        s_solution,
        s_data,
        s_pipeline,
        s_rfm,
        s_uplift,
        s_calc,
        s_results,
        s_ltv,
        s_agent,
        s_where,
        s_demo,
        s_ethics,
        s_business,
        s_close,
    ):
        fn(d)
    assert d.n == N_MAIN, d.n
    s_learners(d)
    s_hillstrom(d)
    s_sources(d)
    core = d.prs.core_properties
    core.title = "LiftPilot: AI campaign agent for incremental profit"
    core.author = "Abed El Rahmane Jaafir, Ghandi Mahdmoud"
    core.subject = "AI in Business and Marketing, USJ, Group 10"
    out = HERE / "LiftPilot.pptx"
    d.prs.save(out)
    write_script(HERE / "SCRIPT.md")
    for f in TMP.glob("*.png"):
        f.unlink()
    TMP.rmdir()
    return out


if __name__ == "__main__":
    path = build()
    total = sum(SLOT.values()) + KICKOFF_SECONDS + DEMO_SECONDS
    print(
        f"wrote {path} and SCRIPT.md; talk length {mmss(total)}; benchmark section "
        f"{'found' if BENCH else 'absent'}; exchange rate {FX['amount'] or 'absent'}"
    )
    for key, slot, txt in SCRIPT:
        sw = spoken_words(txt)
        flag = "  <-- over" if pace(sw, slot) > WPM else ""
        print(f"  {key:9s} {slot:3d} s  {sw:4d} spoken words  {pace(sw, slot):4d} wpm{flag}")
