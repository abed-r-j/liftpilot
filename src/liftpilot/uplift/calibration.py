"""Turn an uplift *ranking score* into an uplift *probability difference*.

Meta-learner scores order customers well but their magnitudes are unreliable,
and the profit rule needs magnitudes ("is the uplift above break-even?").
On a held-out randomised sample we therefore learn a monotone map

    score  ->  observed uplift

by (1) cutting the sample into equal-size score bins, (2) measuring the real
treated-minus-control difference in each bin, and (3) fitting an isotonic
(order-preserving) regression through the bin estimates, weighted by precision.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.isotonic import IsotonicRegression

FloatArray = NDArray[np.float64]


class UpliftCalibrator:
    def __init__(self, n_bins: int = 20, min_arm: int = 30) -> None:
        self.n_bins = n_bins
        self.min_arm = min_arm

    def fit(self, score: Any, t: Any, y: Any) -> UpliftCalibrator:
        s = np.asarray(score, dtype=np.float64).ravel()
        t_arr = np.asarray(t, dtype=np.float64).ravel()
        y_arr = np.asarray(y, dtype=np.float64).ravel()
        if not (len(s) == len(t_arr) == len(y_arr)):
            raise ValueError("score, t and y must have the same length")
        order = np.argsort(s, kind="stable")
        centers: list[float] = []
        uplifts: list[float] = []
        weights: list[float] = []
        for idx in np.array_split(order, self.n_bins):
            yt = y_arr[idx][t_arr[idx] == 1]
            yc = y_arr[idx][t_arr[idx] == 0]
            if len(yt) < self.min_arm or len(yc) < self.min_arm:
                continue
            var = yt.var(ddof=1) / len(yt) + yc.var(ddof=1) / len(yc)
            centers.append(float(s[idx].mean()))
            uplifts.append(float(yt.mean() - yc.mean()))
            weights.append(1.0 / max(float(var), 1e-12))
        if len(centers) < 2:
            raise ValueError("not enough data in both arms to calibrate uplift")
        self.bin_score_ = np.asarray(centers)
        self.bin_uplift_ = np.asarray(uplifts)
        self.iso_ = IsotonicRegression(increasing=True, out_of_bounds="clip")
        self.iso_.fit(self.bin_score_, self.bin_uplift_, sample_weight=np.asarray(weights))
        self.overall_uplift_ = float(y_arr[t_arr == 1].mean() - y_arr[t_arr == 0].mean())
        return self

    def predict(self, score: Any) -> FloatArray:
        s = np.asarray(score, dtype=np.float64).ravel()
        return np.asarray(self.iso_.predict(s), dtype=np.float64)

    def is_informative(self) -> bool:
        """False when the calibrated map is flat, i.e. the score carries no
        usable ordering on the calibration sample."""
        fitted = self.iso_.predict(self.bin_score_)
        return bool(np.ptp(fitted) > 1e-9)
