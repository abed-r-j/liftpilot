"""Who gets the offer? Audit of a targeting decision across customer groups.

The model never sees age or gender. That alone does not make it fair: purchase
behaviour can act as a proxy. So after every plan we measure, per group,

* the selection rate (share of the group that is contacted),
* the group's real uplift measured in the experiment (was the difference in
  treatment justified by a difference in effect?),

and the disparate-impact ratio = lowest selection rate / highest selection
rate. Values under 0.8 are flagged for human review (the "four-fifths" rule
of thumb from US employment-selection guidelines, used here as a screening
heuristic and not as a legal test for marketing).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

FOUR_FIFTHS = 0.8


def audit_groups(
    groups: pd.Series,
    selected: Any,
    t: Any | None = None,
    y: Any | None = None,
    min_group: int = 200,
) -> pd.DataFrame:
    sel = np.asarray(selected, dtype=bool)
    df = pd.DataFrame({"group": groups.to_numpy(), "selected": sel})
    if t is not None and y is not None:
        df["t"] = np.asarray(t, dtype=float)
        df["y"] = np.asarray(y, dtype=float)
    rows = []
    for name, part in df.groupby("group", observed=True):
        row: dict[str, Any] = {
            "group": name,
            "customers": len(part),
            "selected": int(part["selected"].sum()),
            "selection_rate": float(part["selected"].mean()),
            "small_group": len(part) < min_group,
        }
        if "t" in part and part["t"].notna().any():
            lab = part[part["t"].notna()]
            yt, yc = lab.loc[lab["t"] == 1, "y"], lab.loc[lab["t"] == 0, "y"]
            if len(yt) > 1 and len(yc) > 1:
                row["observed_uplift"] = float(yt.mean() - yc.mean())
                row["uplift_se"] = float(
                    np.sqrt(yt.var(ddof=1) / len(yt) + yc.var(ddof=1) / len(yc))
                )
        rows.append(row)
    out = pd.DataFrame(rows).set_index("group")
    overall = float(sel.mean())
    out["rate_vs_overall"] = out["selection_rate"] / overall if overall > 0 else np.nan
    return out


def disparate_impact(table: pd.DataFrame, ignore: tuple[str, ...] = ("unknown",)) -> dict[str, Any]:
    """Lowest / highest selection rate among known, large-enough groups."""
    use = table[~table.index.isin(ignore) & ~table["small_group"]]
    if len(use) < 2 or use["selection_rate"].max() == 0:
        return {"ratio": None, "flag": False, "lowest": None, "highest": None}
    lo, hi = use["selection_rate"].idxmin(), use["selection_rate"].idxmax()
    ratio = float(use.loc[lo, "selection_rate"] / use.loc[hi, "selection_rate"])
    return {"ratio": ratio, "flag": ratio < FOUR_FIFTHS, "lowest": str(lo), "highest": str(hi)}
