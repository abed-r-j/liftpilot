"""LiftPilot demo dashboard (Streamlit).

Run with ``liftpilot app`` or ``python -m streamlit run src/liftpilot/app/main.py``.
Everything shown here is computed by ``CampaignEngine`` from the real,
randomised campaign data; the local language model only orchestrates and writes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from liftpilot import config, live
from liftpilot.agent.copy_guard import PRESSURE_PATTERNS, Offer
from liftpilot.agent.llm import OllamaClient
from liftpilot.agent.runtime import Agent, AuditLog
from liftpilot.agent.tools import Toolbox
from liftpilot.engine import ApprovalRequired, CampaignEngine

INK, MUTED, GRID = "#1b1f3b", "#6b7280", "#e5e7eb"
BLUE, TEAL, AMBER, RED, VIOLET, GREY = (
    "#2563eb",
    "#0d9488",
    "#d97706",
    "#dc2626",
    "#7c3aed",
    "#9ca3af",
)
LEARNER_LABEL = {
    "response": "Likely-buyer model (baseline)",
    "s_learner": "S-learner",
    "t_learner": "T-learner",
    "x_learner": "X-learner",
    "dr_learner": "DR-learner",
    "class_transformation": "Class transformation",
    "ensemble": "Ensemble",
    "rfm": "RFM score",
}

st.set_page_config(page_title="LiftPilot", page_icon="🎯", layout="wide")
st.markdown(
    """
    <style>
    .block-container {padding-top: 4.2rem; max-width: 1280px;}
    div[data-testid="stMetric"] {background:#f8fafc; border:1px solid #e5e7eb; border-radius:12px;
        padding:12px 16px;}
    div[data-testid="stMetricValue"] {font-size:1.55rem;}
    .pill {display:inline-block; padding:2px 10px; border-radius:999px; font-size:.78rem;
        font-weight:600; margin-right:6px;}
    .ok {background:#dcfce7; color:#166534;} .warn {background:#fef3c7; color:#92400e;}
    .bad {background:#fee2e2; color:#991b1b;} .info {background:#dbeafe; color:#1e40af;}
    .note {color:#6b7280; font-size:.86rem;}
    .formula {background:#f1f5f9; border-left:4px solid #2563eb; padding:10px 14px;
        border-radius:6px; font-family:ui-monospace,Consolas,monospace; font-size:.9rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------------- resources
@st.cache_resource(show_spinner="Loading customers and models...")
def get_engine(dataset: str) -> CampaignEngine:
    return CampaignEngine(dataset)


@st.cache_resource
def get_llm() -> OllamaClient:
    return OllamaClient()


@st.cache_data(ttl=3600, show_spinner=False)
def get_fx(base: str, offline: bool) -> dict[str, Any]:
    return live.exchange_rates(base, ["USD", "BRL", "EUR", "LBP", "RUB"], offline=offline)


@st.cache_data(show_spinner="Replaying the plan on held-out customers...")
def cached_plan(
    dataset: str,
    margin: float,
    cost: float,
    discount: float,
    budget: float | None,
    segments: tuple[str, ...],
    fair: bool = False,
) -> tuple[dict, dict, dict]:
    eng = get_engine(dataset)
    plan = eng.plan(
        margin=margin,
        contact_cost=cost,
        discount=discount,
        budget=budget,
        segments=list(segments) or None,
        equal_value=fair,
    )
    evidence = eng.evaluate(plan["plan_id"], n_boot=200)
    fair = eng.fairness(plan["plan_id"])
    return plan, evidence, fair


def money(x: float | None, cur: str) -> str:
    if x is None:
        return "-"
    return f"{x:,.0f} {cur}"


def pill(text: str, kind: str = "info") -> str:
    return f'<span class="pill {kind}">{text}</span>'


def style(fig: go.Figure, height: int = 360, **layout: Any) -> go.Figure:
    fig.update_layout(
        height=height,
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
        plot_bgcolor="white",
        paper_bgcolor="white",
        font={"color": INK, "size": 13},
        legend={"orientation": "h", "y": -0.2},
        **layout,
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor="#9ca3af")
    return fig


# --------------------------------------------------------------------------- sidebar
datasets = [d for d in ("x5", "hillstrom") if (config.artifacts_dir(d) / "report.json").exists()]
if not datasets:
    st.error("No trained artifacts found. Run `liftpilot download` then `liftpilot train x5`.")
    st.stop()

with st.sidebar:
    st.markdown("## 🎯 LiftPilot")
    st.caption("Spend the marketing budget only where it changes behaviour.")
    dataset = st.selectbox(
        "Campaign data",
        datasets,
        format_func=lambda d: {
            "x5": "X5 grocery chain (RU, 400k customers)",
            "hillstrom": "Hillstrom e-mail test (US, 64k)",
        }[d],
    )
    offline = st.toggle("Offline mode (use cached live data)", value=False)
    report_cur = st.selectbox("Also show money in", ["USD", "BRL", "EUR", "LBP"], index=0)
    eng = get_engine(dataset)
    cur = eng.currency
    fx = get_fx(cur, offline)
    rate = fx.get("rates", {}).get(report_cur)
    if rate:
        st.markdown(
            pill("LIVE" if fx.get("live") else "CACHED", "ok" if fx.get("live") else "warn")
            + f"1 {cur} = {rate:,.4f} {report_cur}",
            unsafe_allow_html=True,
        )
        st.caption(f"{fx.get('source', '')} · {fx.get('as_of', '')}")
    else:
        st.markdown(pill("FX unavailable", "bad"), unsafe_allow_html=True)
    llm = get_llm()
    llm_ok = llm.available()
    st.markdown(
        pill(f"Local model: {llm.model}", "ok")
        if llm_ok
        else pill("Local model offline: scripted planner", "warn"),
        unsafe_allow_html=True,
    )
    st.caption("Runs on this laptop. No customer data leaves the machine.")


def also(x: float | None) -> str:
    if x is None or not rate:
        return ""
    return f"≈ {x * rate:,.0f} {report_cur}"


rep = eng.report
readout = eng.experiment_readout()
profile = eng.data_profile()
tabs = st.tabs(
    [
        "① Problem",
        "② Customers (RFM)",
        "③ Uplift models",
        "④ Optimizer",
        "⑤ AI agent",
        "⑥ Ethics & audit",
    ]
)

# ===================================================================== 1. PROBLEM
with tabs[0]:
    st.markdown("### Most campaign money is spent on people who would have bought anyway")
    c = st.columns(4)
    c[0].metric("Customers", f"{profile['customers_total']:,}")
    c[1].metric("Bought WITHOUT a message", f"{readout['purchase_rate_held_out']:.1%}")
    c[2].metric("Bought WITH a message", f"{readout['purchase_rate_contacted']:.1%}")
    c[3].metric(
        "Real effect of the message",
        f"+{readout['uplift_points'] * 100:.1f} pts",
        "p < 0.001" if readout["p_value"] < 0.001 else f"p = {readout['p_value']:.3f}",
        delta_color="off",
    )
    st.markdown(
        f"<p class='note'>{profile['description']} Randomised test: "
        f"{readout['customers_contacted']:,} contacted, {readout['customers_held_out']:,} held out. "
        f"95% interval for the effect: {readout['confidence_interval_95'][0] * 100:+.1f} to "
        f"{readout['confidence_interval_95'][1] * 100:+.1f} points.</p>",
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.15, 1])
    with left:
        st.markdown("#### What a dashboard reports vs what the message caused")
        treated, control = readout["purchase_rate_contacted"], readout["purchase_rate_held_out"]
        fig = go.Figure()
        fig.add_bar(
            x=["Contacted customers"],
            y=[control * 100],
            name="Would have bought anyway",
            marker_color=GREY,
            text=[f"{control:.1%}"],
            textposition="inside",
        )
        fig.add_bar(
            x=["Contacted customers"],
            y=[(treated - control) * 100],
            name="Bought BECAUSE of the message",
            marker_color=TEAL,
            text=[f"+{(treated - control) * 100:.1f} pts"],
            textposition="outside",
        )
        fig.update_layout(barmode="stack", yaxis_title="% who purchased", yaxis_range=[0, 80])
        st.plotly_chart(style(fig, 340), use_container_width=True)
        st.markdown(
            f"Of every 100 purchases after the message, about "
            f"**{control / treated * 100:.0f} would have happened anyway**. Counting them as "
            "campaign results is why platform ROAS looks better than reality."
        )
    with right:
        by_f = rep.get("uplift_by_rfm_score", {}).get("f_score")
        if not by_f:
            st.info(
                "This data set has no purchase-frequency history, so the frequency view is "
                "not available. See the X5 data set for the full RFM analysis."
            )
        if by_f:
            st.markdown("#### The more they already buy, the less a message adds")
            keys = sorted(by_f)
            fig = go.Figure()
            fig.add_bar(
                x=keys,
                y=[by_f[k_]["rate_control"] * 100 for k_ in keys],
                name="Buys with NO message (%)",
                marker_color=GREY,
            )
            fig.add_scatter(
                x=keys,
                y=[by_f[k_]["uplift"] * 100 for k_ in keys],
                yaxis="y2",
                name="Effect of the message (points)",
                mode="lines+markers",
                line={"color": TEAL, "width": 4},
                marker={"size": 10},
            )
            fig.update_layout(
                xaxis={
                    "title": "purchase-frequency score (1 = rare buyer, 5 = very frequent)",
                    "type": "category",
                },
                yaxis={"title": "% buying without a message", "range": [0, 100]},
                yaxis2={
                    "title": "effect, points",
                    "overlaying": "y",
                    "side": "right",
                    "range": [0, 6],
                    "showgrid": False,
                },
            )
            st.plotly_chart(style(fig, 340), use_container_width=True)
            lo, hi = by_f[keys[0]], by_f[keys[-1]]
            st.markdown(
                f"<p class='note'>Most frequent buyers: {hi['rate_control']:.0%} buy anyway, the "
                f"message adds {hi['uplift'] * 100:+.1f} points. Rare buyers: "
                f"{lo['rate_control']:.0%} buy anyway, the message adds "
                f"{lo['uplift'] * 100:+.1f} points. Measured in the experiment, not modelled."
                "</p>",
                unsafe_allow_html=True,
            )

    st.markdown("#### The idea in one line")
    st.markdown(
        "<div class='formula'>contact customer i &nbsp;⇔&nbsp; margin × basket<sub>i</sub> × "
        "uplift<sub>i</sub> &nbsp;&gt;&nbsp; message cost + discount × basket<sub>i</sub> × "
        "P(buy | contacted)<sub>i</sub></div>",
        unsafe_allow_html=True,
    )

# ================================================================== 2. CUSTOMERS
with tabs[1]:
    segs = pd.DataFrame(eng.rfm_segments())
    if segs.empty:
        st.info(
            "This dataset has no purchase history, so full RFM segments are not available. "
            "Recency and past spend are still used as model features."
        )
    else:
        st.markdown("### RFM segments, and how each one REALLY reacted to the campaign")
        st.caption(
            f"Recency, Frequency, Monetary computed from {profile['history_window'][0]} to "
            f"{profile['history_window'][1]} from raw receipts. Uplift = purchase rate of "
            "contacted minus held-out customers inside each segment (real experiment)."
        )
        fig = go.Figure()
        err = [(r["uplift_ci_95"][1] - r["uplift_ci_95"][0]) / 2 * 100 for _, r in segs.iterrows()]
        fig.add_bar(
            x=segs["segment"],
            y=segs["measured_uplift_points"] * 100,
            error_y={"type": "data", "array": err, "color": MUTED},
            marker_color=[
                TEAL if v >= readout["uplift_points"] else GREY
                for v in segs["measured_uplift_points"]
            ],
            text=[f"{v * 100:+.1f}" for v in segs["measured_uplift_points"]],
            textposition="outside",
            name="Measured uplift (points)",
        )
        fig.add_hline(
            y=readout["uplift_points"] * 100,
            line_dash="dot",
            line_color=INK,
            annotation_text="average effect",
        )
        fig.update_layout(yaxis_title="uplift, percentage points")
        st.plotly_chart(style(fig, 380, showlegend=False), use_container_width=True)

        best = segs.loc[segs["measured_uplift_points"].idxmax()]
        champ = segs[segs["segment"] == "Champions"]
        if len(champ):
            ch = champ.iloc[0]
            st.markdown(
                f"**Reading:** Champions buy **{ch['purchase_rate_without_contact']:.0%}** of the "
                f"time with no message at all, so a message adds only "
                f"**{ch['measured_uplift_points'] * 100:+.1f} points**. "
                f"**{best['segment']}** adds **{best['measured_uplift_points'] * 100:+.1f} points**. "
                "Rewarding the best customers feels right and wastes the budget."
            )
        show = segs.rename(
            columns={
                "segment": "Segment",
                "customers": "Customers",
                "share": "Share",
                "avg_recency_days": "Recency (days)",
                "avg_purchases": "Purchases",
                "avg_spend": f"Spend ({cur})",
                "avg_basket": f"Basket ({cur})",
                "purchase_rate_without_contact": "Buys without contact",
                "measured_uplift_points": "Measured uplift",
                "share_worth_contacting_at_default_costs": "Worth contacting",
            }
        )
        st.dataframe(
            show.drop(columns=["uplift_ci_95"]).style.format(
                {
                    "Customers": "{:,}",
                    "Share": "{:.1%}",
                    "Buys without contact": "{:.1%}",
                    "Measured uplift": "{:+.1%}",
                    "Worth contacting": "{:.0%}",
                    f"Spend ({cur})": "{:,.0f}",
                    f"Basket ({cur})": "{:,.0f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        by = rep.get("uplift_by_rfm_score", {})
        if by:
            st.markdown("#### Uplift by R, F and M score (1 = worst, 5 = best)")
            cols = st.columns(len(by))
            names = {
                "r_score": "Recency score",
                "f_score": "Frequency score",
                "m_score": "Monetary score",
            }
            for col, (dim, rows) in zip(cols, by.items(), strict=False):
                keys = sorted(rows)
                fig = go.Figure(
                    go.Bar(
                        x=keys,
                        y=[rows[k]["uplift"] * 100 for k in keys],
                        marker_color=BLUE,
                        error_y={
                            "type": "data",
                            "color": MUTED,
                            "array": [
                                (rows[k]["ci_high"] - rows[k]["ci_low"]) / 2 * 100 for k in keys
                            ],
                        },
                    )
                )
                fig.update_layout(title=names[dim], yaxis_title="uplift, points")
                col.plotly_chart(style(fig, 280, showlegend=False), use_container_width=True)
            st.caption("The more often a customer already buys, the less a message changes.")

# ==================================================================== 3. MODELS
with tabs[2]:
    st.markdown("### Can a model find the persuadable customers? Tested on customers it never saw")
    champion = rep["champion"]
    curves = eng.curves
    left, right = st.columns([1.3, 1])
    with left:
        fig = go.Figure()
        palette = {"response": RED, champion: TEAL, "rfm": AMBER}
        for name in ("response", "rfm", champion):
            c_ = curves["qini"].get(name)
            if not c_:
                continue
            fig.add_scatter(
                x=[f * 100 for f in c_["fraction"]],
                y=c_["value"],
                mode="lines",
                name=LEARNER_LABEL.get(name, name),
                line={"color": palette.get(name, BLUE), "width": 3},
            )
        end = curves["qini"][champion]["value"][-1]
        fig.add_scatter(
            x=[0, 100],
            y=[0, end],
            mode="lines",
            name="Random targeting",
            line={"color": GREY, "dash": "dash"},
        )
        fig.update_layout(
            title="Qini curve (held-out test customers)",
            xaxis_title="% of customers contacted, best first",
            yaxis_title="extra purchases caused",
        )
        st.plotly_chart(style(fig, 400), use_container_width=True)
    with right:
        dec = curves["deciles"]
        fig = go.Figure(
            go.Bar(
                x=[f"D{int(b) + 1}" for b in dec["bin"]],
                y=[u * 100 for u in dec["uplift"]],
                error_y={
                    "type": "data",
                    "array": [1.96 * s * 100 for s in dec["se"]],
                    "color": MUTED,
                },
                marker_color=[TEAL if i == 0 else BLUE for i in range(len(dec["bin"]))],
            )
        )
        fig.add_hline(y=readout["uplift_points"] * 100, line_dash="dot", line_color=INK)
        fig.update_layout(
            title="Real uplift by model decile (D1 = highest score)", yaxis_title="uplift, points"
        )
        st.plotly_chart(style(fig, 400, showlegend=False), use_container_width=True)

    rows = []
    for name, r in rep["learners"].items():
        rp = rep.get("learners_repeated", {}).get(name, {})
        rows.append(
            {
                "Model": LEARNER_LABEL.get(name, name) + (" ★" if name == champion else ""),
                "Qini (test)": r["qini_test"]["value"],
                "95% CI low": r["qini_test"]["ci_low"],
                "95% CI high": r["qini_test"]["ci_high"],
                "Uplift top 10%": r["uplift_at_10"],
                "Uplift top 30%": r["uplift_at_30"],
                "Uplift bottom 30%": r["uplift_bottom_30"],
                "Qini, repeated splits": f"{rp['mean']:.4f} ± {rp['sd']:.4f}" if rp else "-",
            }
        )
    st.dataframe(
        pd.DataFrame(rows).style.format(
            {
                "Qini (test)": "{:.4f}",
                "95% CI low": "{:.4f}",
                "95% CI high": "{:.4f}",
                "Uplift top 10%": "{:+.1%}",
                "Uplift top 30%": "{:+.1%}",
                "Uplift bottom 30%": "{:+.1%}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
    resp_q = rep["learners"]["response"]["qini_test"]["value"]
    st.markdown(
        f"**Reading:** the likely-buyer model has Qini **{resp_q:+.4f}** "
        f"({'worse than' if resp_q < 0 else 'about the same as'} random): it finds people who buy, "
        f"not people who can be persuaded. The uplift model's top 10% react "
        f"**{rep['learners'][champion]['uplift_at_10'] * 100:+.1f} points** against "
        f"{readout['uplift_points'] * 100:+.1f} on average. ★ = chosen on the calibration split, "
        "before looking at test results. The effect is real but small: every figure carries its "
        "interval."
    )
    if rep.get("ablation"):
        st.markdown("#### What do the features buy?")
        ab = pd.DataFrame(
            [
                {
                    "Feature set": k,
                    "Features": v["n_features"],
                    "Qini (test)": v["qini_test"]["value"],
                    "95% CI": f"[{v['qini_test']['ci_low']:.4f}, {v['qini_test']['ci_high']:.4f}]",
                }
                for k, v in rep["ablation"].items()
            ]
        )
        st.dataframe(
            ab.style.format({"Qini (test)": "{:.4f}"}), hide_index=True, use_container_width=True
        )
        st.caption(
            "Three RFM numbers carry most of the signal. Adding age and gender does not "
            "bring a significant gain, so the model does not use them."
        )

# ================================================================== 4. OPTIMIZER
with tabs[3]:
    st.markdown("### Who should be contacted? Change the assumptions, watch the plan change")
    d = eng.default_economics
    a, b, c_, dd = st.columns(4)
    margin = a.slider(
        "Gross margin",
        0.05,
        0.70,
        float(d.margin),
        0.01,
        help="Share of revenue left after cost of goods.",
    )
    cost = b.slider(
        f"Cost per message ({cur})",
        0.0,
        float(max(d.contact_cost * 8, 1.0)),
        float(d.contact_cost),
        float(max(d.contact_cost / 20, 0.01)),
    )
    discount = c_.slider(
        "Discount to buyers (share of basket)",
        0.0,
        min(0.30, margin - 0.01),
        float(d.discount),
        0.005,
    )
    use_budget = dd.checkbox("Limit the budget", value=False)
    budget = None
    if use_budget:
        bcur = dd.selectbox(
            "Budget currency", [cur, "BRL", "USD", "EUR"], label_visibility="collapsed"
        )
        bval = dd.number_input(f"Budget ({bcur})", min_value=0.0, value=100000.0, step=10000.0)
        if bcur == cur:
            budget = float(bval)
        else:
            conv = live.convert(bval, bcur, cur, offline)
            if "amount" in conv:
                budget = float(conv["amount"])
                dd.caption(
                    f"= {budget:,.0f} {cur} ({'live' if conv.get('live') else 'cached'} rate, "
                    f"{conv.get('as_of', '')})"
                )
            else:
                dd.error(f"No {bcur}→{cur} rate available; the budget limit is NOT applied.")

    fair_mode = st.toggle(
        "Fair mode: value every customer at the average basket (small spenders are not "
        "passed over for spending less)",
        value=False,
    )
    plan, ev, fair = cached_plan(dataset, margin, cost, discount, budget, (), fair_mode)
    flagged = [k_ for k_ in ("gender", "age_band") if fair.get(k_, {}).get("flag_for_review")]
    if flagged:
        f_ = fair[flagged[0]]
        st.warning(
            f"Fairness audit: selection rates differ by {flagged[0].replace('_', ' ')} "
            f"(lowest ÷ highest = {f_['lowest_over_highest_rate']:.2f}; lowest: "
            f"{f_['lowest_group']}, highest: {f_['highest_group']}). Flagged for human review; "
            "see the Ethics tab."
        )
    st.session_state["last_plan_params"] = {
        "margin": margin,
        "contact_cost": cost,
        "discount": discount,
        "budget": budget,
    }

    k = st.columns(5)
    k[0].metric(
        "Contact",
        f"{plan['customers_to_contact']:,}",
        f"{plan['share_contacted']:.1%} of audience",
        delta_color="off",
    )
    k[1].metric("Leave alone", f"{plan['customers_not_contacted']:,}")
    k[2].metric("Spend", money(ev["real_spend"], cur), also(ev["real_spend"]), delta_color="off")
    k[3].metric(
        "Real incremental profit",
        money(ev["real_incremental_profit"], cur),
        also(ev["real_incremental_profit"]),
        delta_color="off",
    )
    k[4].metric(
        "vs contacting everyone",
        money(ev["profit_gain_vs_contact_everyone"], cur),
        f"spend saved {ev['spend_saved_vs_contact_everyone']:,.0f}",
        delta_color="off",
    )
    st.markdown(
        f"<p class='note'>Audience: {plan['customers_in_audience']:,} customers "
        + (
            "who were never in the experiment"
            if profile["customers_never_tested"]
            else "(this data set has no untested customers, so the audience is the experiment "
            "itself and the expected figures are in-sample)"
        )
        + f'. "Real" figures replay this exact rule on {ev["test_customers"]:,} '
        f"held-out randomised customers and scale to the audience. 95% interval for profit: "
        f"<b>{ev['profit_ci_95'][0]:,.0f} to {ev['profit_ci_95'][1]:,.0f} {cur}</b>; probability "
        f"profit is positive: <b>{ev['probability_profit_positive']:.0%}</b>. "
        f"{'Caveat: ' + ev['money_caveat'] + '.' if ev.get('money_caveat') else ''}</p>",
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.1, 1])
    with left:
        fig = go.Figure()
        fig.add_bar(
            x=["Contact everyone", "LiftPilot plan"],
            y=[ev["contact_everyone_incremental_profit"], ev["real_incremental_profit"]],
            marker_color=[GREY, TEAL],
            error_y={
                "type": "data",
                "symmetric": False,
                "color": MUTED,
                "array": [
                    ev["contact_everyone_profit_ci_95"][1]
                    - ev["contact_everyone_incremental_profit"],
                    ev["profit_ci_95"][1] - ev["real_incremental_profit"],
                ],
                "arrayminus": [
                    ev["contact_everyone_incremental_profit"]
                    - ev["contact_everyone_profit_ci_95"][0],
                    ev["real_incremental_profit"] - ev["profit_ci_95"][0],
                ],
            },
            text=[
                f"{ev['contact_everyone_incremental_profit']:,.0f}",
                f"{ev['real_incremental_profit']:,.0f}",
            ],
            textposition="outside",
        )
        fig.update_layout(title=f"Real incremental profit ({cur}), with 95% intervals")
        st.plotly_chart(style(fig, 360, showlegend=False), use_container_width=True)
    with right:
        seg = plan.get("contacted_by_rfm_segment")
        if seg:
            sdf = pd.DataFrame([{"segment": s, **v} for s, v in seg.items()])
            fig = go.Figure(
                go.Bar(
                    y=sdf["segment"],
                    x=sdf["share_of_segment"] * 100,
                    orientation="h",
                    marker_color=BLUE,
                    text=[f"{v:.0%}" for v in sdf["share_of_segment"]],
                    textposition="outside",
                )
            )
            fig.update_layout(
                title="Share of each RFM segment that is contacted",
                xaxis_range=[0, 115],
                yaxis={"autorange": "reversed"},
            )
            st.plotly_chart(style(fig, 360, showlegend=False), use_container_width=True)
        else:
            st.metric(
                "Real incremental ROAS",
                f"{ev['real_incremental_roas'] or 0:.2f}",
                f"break-even {ev['break_even_roas']:.2f}",
                delta_color="off",
            )

    st.markdown("#### The calculation, with today's numbers")
    be = plan["mean_break_even_uplift"]
    st.markdown(
        f"<div class='formula'>break-even uplift = (message cost + discount × basket × P(buy)) ÷ "
        f"(margin × basket) &nbsp;→&nbsp; on average <b>{be:.2%}</b><br>"
        f"incremental ROAS = extra revenue ÷ spend = <b>{ev['real_incremental_roas'] or 0:.2f}</b>"
        f" &nbsp;|&nbsp; break-even ROAS = 1 ÷ margin = <b>{ev['break_even_roas']:.2f}</b><br>"
        f"cost per extra purchase = spend ÷ extra purchases = "
        f"<b>{ev['cost_per_incremental_purchase'] or 0:,.2f} {cur}</b><br>"
        f"uplift still left among customers we skip = "
        f"<b>{(ev['measured_uplift_among_not_contacted'] or 0) * 100:+.1f} points</b></div>",
        unsafe_allow_html=True,
    )

    with st.expander("Why is this one customer contacted, or not?"):
        pool = "new" if profile["customers_never_tested"] else "test"
        sample = eng.customers.index[eng.customers["split"] == pool][:200].tolist()
        cid = st.selectbox("Customer id", sample)
        if cid:
            info = eng.explain_customer(cid, plan["plan_id"])
            cc = st.columns(4)
            cc[0].metric("Decision", info["decision"].upper())
            cc[1].metric("Estimated uplift", f"{info['estimated_uplift_points'] * 100:+.1f} pts")
            cc[2].metric("Break-even uplift", f"{info['break_even_uplift_points'] * 100:.1f} pts")
            cc[3].metric(
                "Expected profit if contacted",
                f"{info['expected_incremental_profit_if_contacted']:+.2f} {cur}",
            )
            st.write(info["reason"])
            st.json(
                {k_: v for k_, v in info.items() if k_ not in ("reason", "decision")},
                expanded=False,
            )

# ====================================================================== 5. AGENT
with tabs[4]:
    st.markdown("### LiftPilot agent: plans the campaign with the tools, a human approves")
    toolbox = Toolbox(eng, llm=llm if llm_ok else None, offer=Offer(), offline=offline)
    agent = Agent(toolbox, llm=llm if llm_ok else None, audit=AuditLog())
    st.markdown(
        pill("utility-based agent", "info")
        + pill(f"{len(toolbox.tools)} tools", "info")
        + pill("numbers only from tools", "ok")
        + pill("human approval before any action", "ok")
        + pill("runs locally", "ok"),
        unsafe_allow_html=True,
    )

    examples = [
        f"Plan the next campaign. Messages cost {d.contact_cost:g} {cur} each and our gross margin "
        f"is {d.margin:.0%}. Who should we contact, what will it really earn, is it fair, and "
        "what should the messages say?",
        "The CEO gives us a budget of 1,000,000 BRL. A message costs 6 RUB, margin 25%. "
        "Plan the campaign and show the evidence.",
        "Which RFM segments react most to our messages, and which ones should we stop contacting?",
        "What happens to the plan if a message costs 2, 4, 6 or 10?",
    ]
    choice = st.selectbox("Example requests", ["(type your own)", *examples])
    request = st.text_area(
        "Request to the agent", value="" if choice.startswith("(") else choice, height=90
    )
    go_btn, scripted_btn = st.columns([1, 3])
    run_llm = go_btn.button("▶ Run agent", type="primary", disabled=not request.strip())
    run_scripted = scripted_btn.button("Run scripted planner (no language model)")
    if run_llm:
        with st.spinner("Agent is working: calling tools on the real data..."):
            st.session_state["run"] = agent.run(request.strip())
    if run_scripted:
        p = st.session_state.get("last_plan_params", {})
        with st.spinner("Scripted planner is running the same tools..."):
            st.session_state["run"] = agent.run_scripted(
                request.strip() or "Plan the next campaign",
                **{k_: v for k_, v in p.items() if v is not None},
            )

    run = st.session_state.get("run")
    if run is not None:
        g = run.grounding
        badge = (
            pill(f"numeric grounding {g.grounded}/{g.checked}", "ok" if g.ok else "bad")
            if g
            else ""
        )
        st.markdown(
            pill(
                "language model" if run.mode == "llm" else "scripted planner",
                "info" if run.mode == "llm" else "warn",
            )
            + pill(f"{len(run.steps)} tool calls", "info")
            + pill(f"{run.seconds:.0f} s", "info")
            + badge,
            unsafe_allow_html=True,
        )
        if run.error:
            st.caption(run.error)
        left_a, right_a = st.columns([1, 1])
        with left_a:
            st.markdown("#### Agent's briefing")
            if run.rejected_narrative:
                st.warning(
                    "The model's wording failed a check, so it was discarded. "
                    "The verified statements are shown instead."
                )
                with st.expander("Rejected wording (for transparency)"):
                    st.write(run.rejected_narrative)
            st.markdown(run.answer or "_no answer_")
            if g and not g.ok:
                st.warning(
                    "Numbers not found in any tool result (do not rely on them): "
                    + ", ".join(g.ungrounded[:10])
                )
            if run.overclaims:
                st.warning("Over-confident wording detected: " + ", ".join(run.overclaims))
        with right_a:
            st.markdown("#### Verified statements (written by code from tool results)")
            if run.statements:
                st.markdown("\n".join(f"- {s_}" for s_ in run.statements))
            else:
                st.caption("No plan in this run; see the tool results below.")
        st.markdown("#### What the agent did")
        for i, s in enumerate(run.steps, 1):
            icon = {"read": "🔎", "propose": "📝", "action": "⚡"}.get(s.privilege, "•")
            err = isinstance(s.result, dict) and "error" in s.result
            with st.expander(
                f"{i}. {icon} {s.tool}  ·  {s.seconds:.2f} s" + ("  ·  ERROR" if err else "")
            ):
                st.caption("arguments")
                st.json(s.args, expanded=True)
                st.caption("result")
                st.json(s.result, expanded=False)

        drafts = next(
            (
                s.result
                for s in reversed(run.steps)
                if s.tool == "draft_messages" and "messages" in s.result
            ),
            None,
        )
        if drafts:
            st.markdown("#### Personalised messages (one per RFM segment)")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Segment": seg_,
                            "Customers": m["customers"],
                            "Message": m["message"],
                            "Chars": m["characters"],
                            "Written by": m["written_by"],
                            "Passed checks": "yes" if m["passed_checks"] else "NO",
                        }
                        for seg_, m in drafts["messages"].items()
                    ]
                ),
                hide_index=True,
                use_container_width=True,
            )

        pid = run.pending_approval or (run.plan_ids[-1] if run.plan_ids else None)
        if pid and pid in eng.plans:
            st.markdown("#### Human checkpoint")
            status = eng.approval_status(pid)
            sp = eng.plans[pid]
            st.write(
                f"Plan `{pid}`: contact **{sp.summary['customers_to_contact']:,}** customers, "
                f"expected spend **{money(sp.summary['expected_spend'], cur)}**. Status: **{status}**."
            )
            if status in ("pending", "not_requested"):
                name = st.text_input("Approver name (required)")
                ok_col, no_col = st.columns(2)
                if ok_col.button("✅ Approve plan", disabled=not name.strip()):
                    if status == "not_requested":
                        eng.request_approval(pid)
                    eng.human_approve(pid, name)
                    agent.audit.write(
                        run.run_id, "approval", plan_id=pid, approver=name, decision="approved"
                    )
                    st.rerun()
                if no_col.button("❌ Reject plan", disabled=not name.strip()):
                    eng.human_reject(pid, name)
                    agent.audit.write(
                        run.run_id, "approval", plan_id=pid, approver=name, decision="rejected"
                    )
                    st.rerun()
            elif status == "approved":
                share = st.slider("Random hold-out for measurement", 0.0, 0.5, 0.1, 0.01)
                if st.button("⚡ Export audience file"):
                    try:
                        res = toolbox.call(
                            "export_audience", {"plan_id": pid, "holdout_share": share}
                        )
                        agent.audit.write(run.run_id, "export", **res)
                        st.session_state["export"] = res
                    except ApprovalRequired as exc:  # pragma: no cover - defensive
                        st.error(str(exc))
                res = st.session_state.get("export")
                if res and res.get("plan_id") == pid and "file" in res:
                    st.success(
                        f"Exported {res['customers_to_send']:,} customers to send and "
                        f"{res['customers_in_holdout']:,} in the hold-out. Approved by "
                        f"{res['approved_by']}."
                    )
                    data = Path(res["file"]).read_bytes()
                    st.download_button("Download audience.csv", data, "audience.csv", "text/csv")
                    st.dataframe(
                        pd.read_csv(res["file"]).head(8), hide_index=True, use_container_width=True
                    )
            else:
                st.error("Plan rejected. Nothing was exported.")

# ===================================================================== 6. ETHICS
with tabs[5]:
    st.markdown("### Is it wise? Controls that are built in, and their current status")
    lp = st.session_state.get("last_plan_params", {})
    _, _, fair_now = cached_plan(
        dataset,
        lp.get("margin", d.margin),
        lp.get("contact_cost", d.contact_cost),
        lp.get("discount", d.discount),
        lp.get("budget"),
        (),
        False,
    )
    st.caption(
        f"Audit of the plan currently set in the Optimizer tab "
        f"({lp.get('contact_cost', d.contact_cost):g} {cur} per message, margin "
        f"{lp.get('margin', d.margin):.0%}). Line = uplift measured for each group in the past "
        "experiment: a gap in who is contacted should be backed by a gap in real effect."
    )
    cols = st.columns(2)
    for col, key, title in zip(cols, ("gender", "age_band"), ("gender", "age band"), strict=True):
        if key not in fair_now:
            col.info(f"No {title} information in this dataset.")
            continue
        f = fair_now[key]
        rates = f["selection_rate_by_group"]
        fig = go.Figure(
            go.Bar(
                x=list(rates),
                y=[v * 100 for v in rates.values()],
                marker_color=VIOLET,
                text=[f"{v:.1%}" for v in rates.values()],
                textposition="outside",
                name="Share contacted (%)",
            )
        )
        up = f.get("measured_uplift_by_group_in_past_test") or {}
        if up:
            fig.add_scatter(
                x=list(up),
                y=[v * 100 for v in up.values()],
                yaxis="y2",
                mode="lines+markers",
                name="Measured uplift (points)",
                line={"color": AMBER, "width": 3},
            )
        fig.update_layout(
            title=f"Share contacted by {title}",
            yaxis={"range": [0, max(rates.values()) * 135 + 1], "title": "% contacted"},
            yaxis2={
                "overlaying": "y",
                "side": "right",
                "showgrid": False,
                "range": [0, 8],
                "title": "uplift, points",
            },
        )
        col.plotly_chart(style(fig, 320), use_container_width=True)
        ratio = f["lowest_over_highest_rate"]
        col.markdown(
            pill(
                "REVIEW" if f["flag_for_review"] else "OK", "bad" if f["flag_for_review"] else "ok"
            )
            + f"lowest ÷ highest rate = <b>{ratio:.2f}</b> (flag under 0.80)"
            if ratio is not None
            else pill("n/a", "info"),
            unsafe_allow_html=True,
        )

    st.markdown("#### Guardrails")
    plan0 = eng.plan()
    removed = plan0["removed_by_rule"]
    eng.plans.pop(plan0["plan_id"], None)
    guard = [
        ("Age and gender are not model inputs", "audited after every plan (charts above)", "ok"),
        (
            "Opt-outs are never contacted",
            f"{removed.get('opted_out', 0):,} removed by the suppression list",
            "ok",
        ),
        (
            "Minors are never contacted",
            f"{removed.get('under_18', 0):,} customers under 18 removed",
            "ok",
        ),
        (
            "No contact when no positive effect is expected",
            f"{removed.get('no_expected_effect', 0):,} customers left in peace",
            "ok",
        ),
        (
            "A human approves before anything is exported",
            "export tool refuses without approval; the agent cannot approve itself",
            "ok",
        ),
        (
            "Every stated number must come from a tool",
            "numeric grounding check on each answer",
            "ok",
        ),
        (
            "Copy is checked by code, not by the model",
            f"{len(PRESSURE_PATTERNS)} pressure / sensitive-attribute patterns, length, opt-out, "
            "no invented numbers",
            "ok",
        ),
        (
            "Every campaign keeps a random hold-out",
            "so the real effect is measured, not assumed",
            "ok",
        ),
        (
            "Customer data stays on this machine",
            "local model; live feeds send no customer data",
            "ok",
        ),
    ]
    st.dataframe(
        pd.DataFrame(guard, columns=["Control", "Status now", "_"]).drop(columns="_"),
        hide_index=True,
        use_container_width=True,
    )

    st.markdown("#### Limits you should know")
    st.markdown(
        "- The measured effect is small and its interval is wide: decisions are probabilistic.\n"
        f"- {profile['note'] or 'Revenue is observed directly in this dataset.'}\n"
        "- The experiment is one campaign in one period; behaviour drifts, so every new "
        "campaign keeps a hold-out and the model is re-checked.\n"
        "- Leaving loyal customers out of a discount can feel unfair to them; the plan shows "
        "this trade-off instead of hiding it."
    )

    st.markdown("#### Audit log (latest events)")
    log = AuditLog().read(60)
    if log:
        ldf = pd.DataFrame(log)[::-1]
        keep = [
            c2
            for c2 in (
                "ts",
                "run_id",
                "event",
                "tool",
                "privilege",
                "seconds",
                "result_sha256",
                "decision",
                "approver",
                "ungrounded",
            )
            if c2 in ldf.columns
        ]
        st.dataframe(ldf[keep], hide_index=True, use_container_width=True, height=280)
    else:
        st.caption("No agent runs yet.")
    with st.expander("Raw evaluation report (JSON)"):
        st.json(json.loads((eng.dir / "report.json").read_text()), expanded=False)
