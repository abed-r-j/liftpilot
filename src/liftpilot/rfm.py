"""RFM: Recency, Frequency, Monetary - the classic behavioural segmentation.

Each customer gets three scores from 1 (worst) to 5 (best), by quintile:

* **R** - how recently they bought (fewer days = better),
* **F** - how often they bought,
* **M** - how much they spent.

The scores are combined into the named segments marketers already use
("Champions", "At risk", ...). The weighted RFM score uses explicit weights so
the trade-off is visible and can be changed. The defaults put recency first,
then frequency, then monetary value - the usual ordering in RFM practice. They
are a stated assumption, not an estimate: the uplift model, not this score,
decides who is contacted.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_WEIGHTS: dict[str, float] = {"recency": 0.40, "frequency": 0.35, "monetary": 0.25}

SEGMENT_ORDER = [
    "Champions",
    "Loyal",
    "Potential loyalists",
    "New customers",
    "Need attention",
    "At risk",
    "Cannot lose them",
    "Hibernating",
]

SEGMENT_DESCRIPTION = {
    "Champions": "Bought very recently, buy often, spend the most.",
    "Loyal": "Buy regularly and recently; the stable core of revenue.",
    "Potential loyalists": "Recent customers with average frequency; can become loyal.",
    "New customers": "Bought recently but only a few times so far.",
    "Need attention": "Average on every score; drifting without a reason to come back.",
    "At risk": "Used to buy often, have not bought for a while.",
    "Cannot lose them": "Were among the best customers, now inactive.",
    "Hibernating": "Low on every score; last purchase long ago.",
}


def quintile_score(values: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """Score 1-5 by quintile. Ties are broken by rank so groups stay equal-sized."""
    ranks = values.rank(method="first", ascending=higher_is_better)
    scores = pd.qcut(ranks, 5, labels=[1, 2, 3, 4, 5])
    return scores.astype(int)


def _segment(r: int, fm: float) -> str:
    if r >= 4 and fm >= 4:
        return "Champions"
    if r >= 3 and fm >= 4:
        return "Loyal"
    if r >= 4 and fm >= 2.5:
        return "Potential loyalists"
    if r >= 4:
        return "New customers"
    if r == 3 and fm >= 2:
        return "Need attention"
    if r <= 2 and fm >= 4.5:
        return "Cannot lose them"
    if r <= 2 and fm >= 3:
        return "At risk"
    return "Hibernating"


def add_rfm(
    df: pd.DataFrame,
    recency: str = "recency_days",
    frequency: str = "frequency",
    monetary: str = "monetary",
    weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Return a copy of ``df`` with R, F, M scores, weighted score and segment."""
    w = weights or DEFAULT_WEIGHTS
    total = sum(w.values())
    if total <= 0 or any(v < 0 for v in w.values()):
        raise ValueError("RFM weights must be non-negative and not all zero")
    out = df.copy()
    out["r_score"] = quintile_score(out[recency], higher_is_better=False)
    out["f_score"] = quintile_score(out[frequency], higher_is_better=True)
    out["m_score"] = quintile_score(out[monetary], higher_is_better=True)
    out["rfm_score"] = (
        w["recency"] * out["r_score"]
        + w["frequency"] * out["f_score"]
        + w["monetary"] * out["m_score"]
    ) / total
    out["rfm_cell"] = (
        out["r_score"].astype(str) + out["f_score"].astype(str) + out["m_score"].astype(str)
    )
    fm = (out["f_score"] + out["m_score"]) / 2.0
    out["rfm_segment"] = pd.Categorical(
        [_segment(int(r), float(v)) for r, v in zip(out["r_score"], fm, strict=True)],
        categories=SEGMENT_ORDER,
    )
    return out


def segment_table(df: pd.DataFrame, value_cols: dict[str, str] | None = None) -> pd.DataFrame:
    """Size and average behaviour of each RFM segment."""
    cols = {
        "recency_days": "mean",
        "frequency": "mean",
        "monetary": "mean",
        "rfm_score": "mean",
        **(value_cols or {}),
    }
    cols = {k: v for k, v in cols.items() if k in df.columns}
    table = df.groupby("rfm_segment", observed=True).agg(
        customers=("rfm_score", "size"), **{k: (k, v) for k, v in cols.items()}
    )
    table["share"] = table["customers"] / table["customers"].sum()
    return table.reindex([s for s in SEGMENT_ORDER if s in table.index])


def shrunk_basket(
    avg_basket: pd.Series, frequency: pd.Series, prior_strength: float = 5.0
) -> pd.Series:
    """Expected basket value per customer, shrunk towards the overall mean.

    A customer seen twice does not have a reliable personal average, so the
    estimate is ``(n * own average + k * global average) / (n + k)``.
    """
    global_mean = float(np.average(avg_basket, weights=frequency))
    return (frequency * avg_basket + prior_strength * global_mean) / (frequency + prior_strength)
