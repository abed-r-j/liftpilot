"""Static figures (PNG at 300 dpi and PDF) for the paper and the slides.

Every figure is drawn from the saved evaluation report, so the pictures and
the tables can never disagree. Run ``liftpilot results``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from liftpilot import config

INK, MUTED, GRID = "#1b1f3b", "#6b7280", "#e5e7eb"
BLUE, TEAL, AMBER, RED, VIOLET, GREY = (
    "#2563eb",
    "#0d9488",
    "#d97706",
    "#dc2626",
    "#7c3aed",
    "#9ca3af",
)

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.edgecolor": MUTED,
        "axes.labelcolor": INK,
        "axes.titlesize": 10,
        "axes.titleweight": "bold",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "xtick.color": INK,
        "ytick.color": INK,
        "legend.frameon": False,
        "legend.fontsize": 8,
        "figure.dpi": 120,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
    }
)


def _load(dataset: str) -> tuple[dict[str, Any], dict[str, Any]]:
    d = config.artifacts_dir(dataset)
    return json.loads((d / "report.json").read_text()), json.loads((d / "curves.json").read_text())


def _save(fig: plt.Figure, out: Path, name: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"{name}.png")
    fig.savefig(out / f"{name}.pdf")
    plt.close(fig)


def fig_segments(rep: dict[str, Any], out: Path) -> None:
    seg = rep["rfm_segments"]
    names = list(seg)
    up = [seg[n]["observed_uplift"] * 100 for n in names]
    lo = [(seg[n]["observed_uplift"] - seg[n]["uplift_ci_low"]) * 100 for n in names]
    hi = [(seg[n]["uplift_ci_high"] - seg[n]["observed_uplift"]) * 100 for n in names]
    base = [seg[n]["conversion_control"] * 100 for n in names]
    avg = rep["experiment_readout"]["ate"] * 100
    fig, ax = plt.subplots(figsize=(7.0, 3.1))
    ax.bar(
        names,
        up,
        yerr=[lo, hi],
        color=[TEAL if u >= avg else GREY for u in up],
        error_kw={"ecolor": MUTED, "capsize": 3, "lw": 1},
    )
    ax.axhline(avg, color=INK, ls=":", lw=1)
    ax.text(len(names) - 0.5, avg + 0.15, f"average {avg:.1f}", ha="right", fontsize=8, color=INK)
    ax.set_ylabel("measured uplift (points)")
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels([n.replace(" ", "\n", 1) for n in names], fontsize=8)
    for i, b in enumerate(base):
        ax.text(i, -1.15, f"{b:.0f}%", ha="center", fontsize=8, color=MUTED)
    ax.text(-0.7, -1.15, "buy with\nno message:", ha="right", va="center", fontsize=7, color=MUTED)
    ax.set_ylim(-1.6, max(u + h for u, h in zip(up, hi, strict=True)) + 0.8)
    ax.set_title("Real effect of the campaign by RFM segment (95% intervals)")
    _save(fig, out, "fig_rfm_segments")


def fig_qini(rep: dict[str, Any], cur: dict[str, Any], out: Path) -> None:
    champ = rep["champion"]
    fig, ax = plt.subplots(figsize=(3.5, 2.9))
    series = [
        ("response", "Likely-buyer model", RED, "-"),
        ("rfm", "RFM score", AMBER, "-"),
        (champ, f"Uplift model ({champ.replace('_', '-')})", TEAL, "-"),
    ]
    for key, label, color, ls in series:
        c = cur["qini"].get(key)
        if c:
            ax.plot(
                [f * 100 for f in c["fraction"]],
                c["value"],
                color=color,
                ls=ls,
                lw=1.8,
                label=label,
            )
    end = cur["qini"][champ]["value"][-1]
    ax.plot([0, 100], [0, end], color=GREY, ls="--", lw=1.2, label="Random")
    ax.set_xlabel("% of customers contacted, best first")
    ax.set_ylabel("extra purchases caused (test set)")
    ax.set_title("Qini curves on held-out customers")
    ax.legend(loc="upper left")
    _save(fig, out, "fig_qini")


def fig_deciles(rep: dict[str, Any], cur: dict[str, Any], out: Path) -> None:
    d = cur["deciles"]
    x = [f"D{int(b) + 1}" for b in d["bin"]]
    fig, ax = plt.subplots(figsize=(3.5, 2.9))
    ax.bar(
        x,
        [u * 100 for u in d["uplift"]],
        yerr=[1.96 * s * 100 for s in d["se"]],
        color=[TEAL] + [BLUE] * (len(x) - 1),
        error_kw={"ecolor": MUTED, "capsize": 2, "lw": 1},
    )
    ax.axhline(rep["experiment_readout"]["ate"] * 100, color=INK, ls=":", lw=1)
    ax.set_ylabel("real uplift (points)")
    ax.set_xlabel("model decile (D1 = highest score)")
    ax.set_title("Real uplift by model decile")
    _save(fig, out, "fig_deciles")


def fig_scenarios(rep: dict[str, Any], out: Path, name: str = "fig_scenarios") -> None:
    scen = rep["scenarios"]
    order = [
        "Contact everyone",
        "RFM best customers, same size",
        "Response model, same size",
        "LiftPilot profit rule",
    ]
    colors = {
        "Contact everyone": GREY,
        "RFM best customers, same size": AMBER,
        "Response model, same size": RED,
        "LiftPilot profit rule": TEAL,
    }
    short = {
        "Contact everyone": "Contact everyone",
        "RFM best customers, same size": "RFM best",
        "Response model, same size": "Likely buyers",
        "LiftPilot profit rule": "LiftPilot",
    }
    cur_ = rep["economics"]["currency"]
    unit = 1e6 if cur_ == "RUB" else 1e3
    fig, axes = plt.subplots(1, len(scen), figsize=(7.0, 2.9), sharey=False)
    for ax, (label, s) in zip(axes, scen.items(), strict=True):
        pol = [p for p in order if p in s["policies"]]
        vals = [s["policies"][p]["incremental_profit"] / unit for p in pol]
        lo = [
            (s["policies"][p]["incremental_profit"] - s["policies"][p]["profit_ci_low"]) / unit
            for p in pol
        ]
        hi = [
            (s["policies"][p]["profit_ci_high"] - s["policies"][p]["incremental_profit"]) / unit
            for p in pol
        ]
        ax.bar(
            range(len(pol)),
            vals,
            yerr=[lo, hi],
            color=[colors[p] for p in pol],
            error_kw={"ecolor": MUTED, "capsize": 3, "lw": 1},
        )
        ax.axhline(0, color=INK, lw=0.8)
        ax.set_xticks(range(len(pol)))
        ax.set_xticklabels([short[p].replace(" ", "\n") for p in pol], fontsize=7)
        ax.set_title(label.split(" (")[0].replace(". ", ". ", 1), fontsize=8)
        share = s["policies"]["LiftPilot profit rule"]["share_selected"]
        ax.text(
            0.98,
            0.02,
            f"LiftPilot contacts {share:.0%}",
            transform=ax.transAxes,
            ha="right",
            fontsize=7,
            color=MUTED,
        )
    axes[0].set_ylabel(
        f"real incremental profit ({'million' if unit == 1e6 else 'thousand'} {cur_})"
    )
    fig.suptitle(
        "Real incremental profit of four targeting rules under three cost scenarios "
        "(95% intervals)",
        fontsize=9,
        fontweight="bold",
        y=1.02,
    )
    fig.tight_layout()
    _save(fig, out, name)


def fig_calibration(rep: dict[str, Any], out: Path) -> None:
    c = rep["calibration"]
    x = list(range(1, len(c["bin_uplift_observed"]) + 1))
    fig, ax = plt.subplots(figsize=(3.5, 2.7))
    ax.scatter(
        x, [v * 100 for v in c["bin_uplift_observed"]], s=14, color=BLUE, label="observed in bin"
    )
    ax.step(
        x,
        [v * 100 for v in c["bin_uplift_fitted"]],
        where="mid",
        color=TEAL,
        lw=1.8,
        label="calibrated (isotonic)",
    )
    ax.axhline(0, color=INK, lw=0.8)
    ax.set_xlabel("score bin (low to high)")
    ax.set_ylabel("uplift (points)")
    ax.set_title("From model score to calibrated uplift")
    ax.legend(loc="upper left")
    _save(fig, out, "fig_calibration")


def fig_fairness(rows: list[dict[str, Any]], out: Path) -> None:
    """``rows``: one dict per message cost with selection rates by age band."""
    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    # minors are excluded from contact by rule and from the audit: not plotted
    bands = [b for b in rows[0]["rates"] if b not in ("unknown", "under 18")]
    palette = [BLUE, VIOLET, RED, AMBER]
    for r, color in zip(rows, palette, strict=False):
        overall = r["share"]
        ax.plot(
            bands,
            [r["rates"][b] / overall for b in bands],
            marker="o",
            ms=4,
            lw=1.6,
            color=color,
            label=f"{r['cost']:g} RUB (ratio {r['ratio']:.2f})",
        )
    ax.axhline(1.0, color=INK, lw=0.8)
    ax.set_ylabel("selection rate relative to average")
    ax.set_xlabel("age band (never a model input)")
    ax.set_title("Who is contacted, by age, as cost rises")
    ax.legend(title="cost per message", title_fontsize=7)
    _save(fig, out, "fig_fairness_age")


def fig_architecture(out: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.4, 3.5))
    ax.set_xlim(0, 100)
    ax.set_ylim(-2, 48)
    ax.axis("off")

    def box(x: float, y: float, w: float, h: float, title: str, body: str, color: str) -> None:
        ax.add_patch(
            FancyBboxPatch(
                (x, y),
                w,
                h,
                boxstyle="round,pad=0.3,rounding_size=1.2",
                fc="white",
                ec=color,
                lw=1.4,
            )
        )
        ax.text(
            x + w / 2,
            y + h - 2.4,
            title,
            ha="center",
            va="center",
            fontsize=7,
            fontweight="bold",
            color=color,
        )
        ax.text(
            x + w / 2,
            y + (h - 4) / 2,
            body,
            ha="center",
            va="center",
            fontsize=6.2,
            color=INK,
            linespacing=1.35,
        )

    def arrow(x1: float, y1: float, x2: float, y2: float, color: str = MUTED) -> None:
        ax.add_patch(
            FancyArrowPatch(
                (x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=9, color=color, lw=1.1
            )
        )

    box(1, 28, 17, 18, "1. Data", "45.8 M receipt lines\n400k customers\nrandomised test", BLUE)
    box(
        21.5,
        28,
        17,
        18,
        "2. RFM features",
        "R, F, M + behaviour\nfrom raw receipts\nno age, no gender",
        BLUE,
    )
    box(
        42,
        28,
        17,
        18,
        "3. Uplift models",
        "6 learners, ensemble\nchampion chosen on\ncalibration split",
        TEAL,
    )
    box(
        62.5,
        28,
        17,
        18,
        "4. Profit rule",
        "contact if gain > cost\nbudget knapsack\neligibility rules",
        TEAL,
    )
    box(
        83, 28, 16, 18, "5. Evidence", "replay on held-out\ncustomers, 95% CI\nfairness audit", TEAL
    )
    for x in (18.6, 39.1, 59.6, 80.1):
        arrow(x, 37, x + 2.2, 37)

    box(
        21.5,
        2,
        37.5,
        19,
        "6. LiftPilot agent (local LLM)",
        "plan - evaluate - audit - schedule - draft\n"
        "numbers only from tools; copy checked by code\n"
        "facts written by code, narrated by the model",
        VIOLET,
    )
    box(1, 2, 17, 19, "Live feeds", "exchange rates\npublic holidays\n(cached offline)", AMBER)
    box(
        62.5,
        2,
        17,
        19,
        "7. Human gate",
        "manager approves\nor rejects; agent\ncannot self-approve",
        RED,
    )
    box(83, 2, 16, 19, "8. Action", "audience file +\nrandom hold-out\naudit log", RED)
    arrow(18.6, 11.5, 20.8, 11.5, AMBER)
    arrow(59.6, 11.5, 61.8, 11.5, VIOLET)
    arrow(80.1, 11.5, 82.3, 11.5, RED)
    arrow(50.5, 27.4, 44, 21.9, VIOLET)
    arrow(71, 27.4, 50, 21.9, VIOLET)
    arrow(91, 27.4, 56, 21.9, VIOLET)
    ax.text(40, 24.4, "tool calls", fontsize=6.5, color=VIOLET, ha="center")
    ax.text(
        50,
        -0.6,
        "Each campaign's hold-out result feeds the next model refresh (back to step 1).",
        fontsize=6.5,
        color=MUTED,
        ha="center",
    )
    _save(fig, out, "fig_architecture")


def fig_gantt(out: Path) -> None:
    """Twelve-week pilot roadmap for a retailer adopting the system."""
    tasks = [
        ("Data audit, consent and opt-out lists", 0, 2, BLUE),
        ("Receipts → RFM feature pipeline", 1, 2, BLUE),
        ("Design + run baseline randomised test", 2, 3, AMBER),
        ("Train, calibrate, select uplift model", 5, 2, TEAL),
        ("Off-policy evaluation + fairness audit", 6, 1.5, TEAL),
        ("Agent tools, guardrails, approval flow", 4, 3.5, VIOLET),
        ("Staff training, governance sign-off", 7, 1.5, RED),
        ("Pilot campaign with random hold-out", 8.5, 2, AMBER),
        ("Read-out, model refresh, go / no-go", 10.5, 1.5, TEAL),
    ]
    fig, ax = plt.subplots(figsize=(7.0, 3.0))
    for i, (_name, start, dur, color) in enumerate(tasks):
        ax.barh(i, dur, left=start, color=color, height=0.6)
        ax.text(start + dur + 0.15, i, f"{dur:g} wk", va="center", fontsize=7, color=MUTED)
    ax.set_yticks(range(len(tasks)))
    ax.set_yticklabels([t[0] for t in tasks], fontsize=8)
    ax.invert_yaxis()
    ax.set_xticks(range(0, 13))
    ax.set_xticklabels([f"W{i}" for i in range(0, 13)], fontsize=7)
    ax.set_xlim(0, 12.6)
    ax.grid(axis="y", visible=False)
    for x, label in ((5, "M1: test read-out"), (8.5, "M2: model approved"), (12, "M3: decision")):
        ax.axvline(x, color=INK, ls=":", lw=1)
        ax.text(x, -0.9, label, ha="center", fontsize=7, color=INK)
    ax.set_title("Twelve-week pilot roadmap", pad=14)
    _save(fig, out, "fig_gantt")


def make_all(out: Path | None = None) -> list[str]:
    out = out or (config.root() / "docs" / "figures")
    rep, cur = _load("x5")
    fig_segments(rep, out)
    fig_qini(rep, cur, out)
    fig_deciles(rep, cur, out)
    fig_scenarios(rep, out)
    fig_calibration(rep, out)
    fig_architecture(out)
    fig_gantt(out)
    extra = config.root() / "artifacts" / "extra_analyses.json"
    if extra.exists():
        fig_fairness(json.loads(extra.read_text())["fairness_by_cost"], out)
    if (config.artifacts_dir("hillstrom") / "report.json").exists():
        hrep, _ = _load("hillstrom")
        fig_scenarios(hrep, out, "fig_scenarios_hillstrom")
    return sorted(p.name for p in out.glob("*.png"))
