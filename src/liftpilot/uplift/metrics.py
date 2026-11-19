"""Evaluation of uplift rankings on randomised (treatment / control) data.

All functions take three aligned arrays:

* ``y``      - observed outcome (binary conversion or a monetary amount),
* ``t``      - treatment indicator (1 = contacted, 0 = held out),
* ``score``  - model score; higher means "contact this customer first".

The Qini curve follows Radcliffe (2007): after contacting the best ``k``
customers, the cumulative incremental outcome is

    Q(k) = Y_T(k) - Y_C(k) * N_T(k) / N_C(k)

where ``Y_T`` / ``Y_C`` are outcome sums and ``N_T`` / ``N_C`` are head counts of
treated / control customers among the first ``k``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


def _prepare(
    y: ArrayLike, t: ArrayLike, score: ArrayLike
) -> tuple[FloatArray, FloatArray, FloatArray]:
    y_arr = np.asarray(y, dtype=np.float64).ravel()
    t_arr = np.asarray(t, dtype=np.float64).ravel()
    s_arr = np.asarray(score, dtype=np.float64).ravel()
    if not (len(y_arr) == len(t_arr) == len(s_arr)):
        raise ValueError("y, t and score must have the same length")
    if len(y_arr) == 0:
        raise ValueError("empty input")
    if not np.isin(t_arr, (0.0, 1.0)).all():
        raise ValueError("t must contain only 0 and 1")
    if t_arr.sum() == 0 or t_arr.sum() == len(t_arr):
        raise ValueError("both treated and control customers are required")
    if not np.isfinite(s_arr).all():
        raise ValueError("score contains NaN or infinite values")
    return y_arr, t_arr, s_arr


def _order(score: FloatArray) -> NDArray[np.intp]:
    # Stable sort so that ties keep input order: results are reproducible.
    return np.argsort(-score, kind="stable")


@dataclass(frozen=True)
class Curve:
    """A cumulative curve: ``x`` customers contacted -> ``y`` incremental outcome."""

    x: FloatArray
    y: FloatArray

    @property
    def fraction(self) -> FloatArray:
        return self.x / self.x[-1]

    def area(self) -> float:
        return float(np.trapezoid(self.y, self.x))


def qini_curve(y: ArrayLike, t: ArrayLike, score: ArrayLike) -> Curve:
    """Qini curve: cumulative incremental outcome, in outcome units."""
    y_arr, t_arr, s_arr = _prepare(y, t, score)
    order = _order(s_arr)
    y_o, t_o = y_arr[order], t_arr[order]
    n_t = np.cumsum(t_o)
    n_c = np.cumsum(1.0 - t_o)
    y_t = np.cumsum(y_o * t_o)
    y_c = np.cumsum(y_o * (1.0 - t_o))
    ratio = np.divide(n_t, n_c, out=np.zeros_like(n_t), where=n_c > 0)
    q = y_t - y_c * ratio
    x = np.arange(1, len(y_o) + 1, dtype=np.float64)
    return Curve(np.concatenate([[0.0], x]), np.concatenate([[0.0], q]))


def uplift_curve(y: ArrayLike, t: ArrayLike, score: ArrayLike) -> Curve:
    """Uplift curve: (mean treated - mean control) among the first k, times k."""
    y_arr, t_arr, s_arr = _prepare(y, t, score)
    order = _order(s_arr)
    y_o, t_o = y_arr[order], t_arr[order]
    n_t = np.cumsum(t_o)
    n_c = np.cumsum(1.0 - t_o)
    y_t = np.cumsum(y_o * t_o)
    y_c = np.cumsum(y_o * (1.0 - t_o))
    mean_t = np.divide(y_t, n_t, out=np.zeros_like(y_t), where=n_t > 0)
    mean_c = np.divide(y_c, n_c, out=np.zeros_like(y_c), where=n_c > 0)
    x = np.arange(1, len(y_o) + 1, dtype=np.float64)
    u = (mean_t - mean_c) * x
    return Curve(np.concatenate([[0.0], x]), np.concatenate([[0.0], u]))


def perfect_qini_curve(y: ArrayLike, t: ArrayLike) -> Curve:
    """Best achievable Qini curve for a binary outcome.

    Order: treated responders first, then non-responders of both groups, then
    control responders last (the "no negative effect" optimum used by
    scikit-uplift, which lets the two implementations be cross-checked).
    """
    y_arr = np.asarray(y, dtype=np.float64).ravel()
    t_arr = np.asarray(t, dtype=np.float64).ravel()
    ideal = y_arr * t_arr - y_arr * (1.0 - t_arr)
    return qini_curve(y_arr, t_arr, ideal)


def qini_coefficient(y: ArrayLike, t: ArrayLike, score: ArrayLike) -> float:
    """Normalised Qini coefficient in roughly [-1, 1]; 0 = random targeting."""
    curve = qini_curve(y, t, score)
    random_area = 0.5 * curve.x[-1] * curve.y[-1]
    perfect = perfect_qini_curve(y, t)
    denom = perfect.area() - random_area
    if denom <= 0:
        return 0.0
    return float((curve.area() - random_area) / denom)


def qini_area(y: ArrayLike, t: ArrayLike, score: ArrayLike) -> float:
    """Un-normalised area between the Qini curve and the random diagonal,
    divided by n^2 so that it does not grow with the sample size."""
    curve = qini_curve(y, t, score)
    n = curve.x[-1]
    random_area = 0.5 * n * curve.y[-1]
    return float((curve.area() - random_area) / (n * n))


def auuc(y: ArrayLike, t: ArrayLike, score: ArrayLike) -> float:
    """Area under the uplift curve, normalised by n^2 (mean uplift scale)."""
    curve = uplift_curve(y, t, score)
    n = curve.x[-1]
    return float(curve.area() / (n * n))


def uplift_at_k(y: ArrayLike, t: ArrayLike, score: ArrayLike, k: float = 0.3) -> float:
    """Observed uplift (treated mean - control mean) in the top ``k`` share."""
    if not 0 < k <= 1:
        raise ValueError("k must be in (0, 1]")
    y_arr, t_arr, s_arr = _prepare(y, t, score)
    order = _order(s_arr)
    n_top = max(1, round(k * len(y_arr)))
    y_o, t_o = y_arr[order][:n_top], t_arr[order][:n_top]
    if t_o.sum() == 0 or t_o.sum() == len(t_o):
        return float("nan")
    return float(y_o[t_o == 1].mean() - y_o[t_o == 0].mean())


def uplift_by_bin(
    y: ArrayLike, t: ArrayLike, score: ArrayLike, bins: int = 10
) -> dict[str, FloatArray]:
    """Observed uplift per score quantile bin (bin 0 = highest scores)."""
    y_arr, t_arr, s_arr = _prepare(y, t, score)
    order = _order(s_arr)
    chunks = np.array_split(order, bins)
    out: dict[str, list[float]] = {
        "bin": [],
        "n": [],
        "n_treated": [],
        "n_control": [],
        "rate_treated": [],
        "rate_control": [],
        "uplift": [],
        "se": [],
        "mean_score": [],
    }
    for i, idx in enumerate(chunks):
        yt = y_arr[idx][t_arr[idx] == 1]
        yc = y_arr[idx][t_arr[idx] == 0]
        out["bin"].append(float(i))
        out["n"].append(float(len(idx)))
        out["n_treated"].append(float(len(yt)))
        out["n_control"].append(float(len(yc)))
        rt = float(yt.mean()) if len(yt) else float("nan")
        rc = float(yc.mean()) if len(yc) else float("nan")
        out["rate_treated"].append(rt)
        out["rate_control"].append(rc)
        out["uplift"].append(rt - rc)
        var = (yt.var(ddof=1) / len(yt) if len(yt) > 1 else np.nan) + (
            yc.var(ddof=1) / len(yc) if len(yc) > 1 else np.nan
        )
        out["se"].append(float(np.sqrt(var)))
        out["mean_score"].append(float(s_arr[idx].mean()))
    return {k: np.asarray(v, dtype=np.float64) for k, v in out.items()}


def average_treatment_effect(y: ArrayLike, t: ArrayLike) -> dict[str, float]:
    """Difference in means with a two-sided z-test (the classic A/B read-out)."""
    from scipy import stats

    y_arr = np.asarray(y, dtype=np.float64).ravel()
    t_arr = np.asarray(t, dtype=np.float64).ravel()
    yt, yc = y_arr[t_arr == 1], y_arr[t_arr == 0]
    diff = float(yt.mean() - yc.mean())
    se = float(np.sqrt(yt.var(ddof=1) / len(yt) + yc.var(ddof=1) / len(yc)))
    z = diff / se if se > 0 else float("nan")
    p = float(2 * (1 - stats.norm.cdf(abs(z)))) if se > 0 else float("nan")
    return {
        "rate_treated": float(yt.mean()),
        "rate_control": float(yc.mean()),
        "ate": diff,
        "relative_uplift": diff / float(yc.mean()) if yc.mean() != 0 else float("nan"),
        "se": se,
        "ci_low": diff - 1.96 * se,
        "ci_high": diff + 1.96 * se,
        "z": z,
        "p_value": p,
        "n_treated": float(len(yt)),
        "n_control": float(len(yc)),
    }


def bootstrap_metric(
    metric: object,
    y: ArrayLike,
    t: ArrayLike,
    score: ArrayLike,
    n_boot: int = 200,
    seed: int = 0,
    **kwargs: float,
) -> dict[str, float]:
    """Percentile bootstrap (stratified by treatment arm) for any metric above."""
    y_arr, t_arr, s_arr = _prepare(y, t, score)
    rng = np.random.default_rng(seed)
    idx_t = np.flatnonzero(t_arr == 1)
    idx_c = np.flatnonzero(t_arr == 0)
    point = float(metric(y_arr, t_arr, s_arr, **kwargs))  # type: ignore[operator]
    draws = np.empty(n_boot, dtype=np.float64)
    for b in range(n_boot):
        idx = np.concatenate(
            [
                rng.choice(idx_t, len(idx_t), replace=True),
                rng.choice(idx_c, len(idx_c), replace=True),
            ]
        )
        draws[b] = metric(y_arr[idx], t_arr[idx], s_arr[idx], **kwargs)  # type: ignore[operator]
    low, high = np.nanpercentile(draws, [2.5, 97.5])
    return {
        "value": point,
        "ci_low": float(low),
        "ci_high": float(high),
        "se": float(np.nanstd(draws)),
    }
