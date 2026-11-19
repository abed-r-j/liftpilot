"""Uplift (conditional average treatment effect) learners.

Every learner answers the same question for one customer with features ``x``:

    tau(x) = P(buy | contacted, x) - P(buy | not contacted, x)

Implemented from the original papers, on top of gradient-boosted trees:

* ``SLearner``, ``TLearner``, ``XLearner``  - Kunzel et al., PNAS 2019
* ``DRLearner``                              - Kennedy, Electron. J. Stat. 2023
* ``ClassTransformation``                    - Jaskowski & Jaroszewicz, 2012
* ``ResponseModel``                          - the conventional "who is likely to
  buy" model, kept as the baseline that uplift modeling is meant to beat.

The data come from a randomised experiment, so the propensity ``e = P(T = 1)``
is a known constant and is not modelled.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor
from numpy.typing import NDArray
from sklearn.model_selection import StratifiedKFold

FloatArray = NDArray[np.float64]

DEFAULT_PARAMS: dict[str, Any] = {
    "n_estimators": 300,
    "learning_rate": 0.03,
    "num_leaves": 15,
    "min_child_samples": 200,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "reg_lambda": 5.0,
    "verbose": -1,
    "n_jobs": 4,
}


def _clf(seed: int, params: dict[str, Any] | None) -> LGBMClassifier:
    return LGBMClassifier(**{**DEFAULT_PARAMS, **(params or {}), "random_state": seed})


def _reg(seed: int, params: dict[str, Any] | None) -> LGBMRegressor:
    return LGBMRegressor(**{**DEFAULT_PARAMS, **(params or {}), "random_state": seed})


def _check(X: pd.DataFrame, t: Any, y: Any) -> tuple[pd.DataFrame, NDArray[np.int64], FloatArray]:
    t_arr = np.asarray(t).astype(np.int64).ravel()
    y_arr = np.asarray(y, dtype=np.float64).ravel()
    if len(X) != len(t_arr) or len(X) != len(y_arr):
        raise ValueError("X, t and y must have the same number of rows")
    if set(np.unique(t_arr)) != {0, 1}:
        raise ValueError("t must contain both 0 and 1 and nothing else")
    return X.reset_index(drop=True), t_arr, y_arr


class UpliftLearner(ABC):
    """Common interface: ``fit(X, t, y)`` then ``predict(X)`` -> uplift per row."""

    name: str = "base"

    def __init__(self, seed: int = 0, params: dict[str, Any] | None = None) -> None:
        self.seed = seed
        self.params = params
        self.propensity_: float = 0.5

    @abstractmethod
    def fit(self, X: pd.DataFrame, t: Any, y: Any) -> UpliftLearner: ...

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> FloatArray: ...


class ResponseModel(UpliftLearner):
    """Baseline: P(buy | contacted). Ranks likely buyers, not persuadable ones."""

    name = "response"

    def fit(self, X: pd.DataFrame, t: Any, y: Any) -> ResponseModel:
        X, t_arr, y_arr = _check(X, t, y)
        self.model_ = _clf(self.seed, self.params).fit(X[t_arr == 1], y_arr[t_arr == 1])
        return self

    def predict(self, X: pd.DataFrame) -> FloatArray:
        return np.asarray(self.model_.predict_proba(X)[:, 1], dtype=np.float64)


class SLearner(UpliftLearner):
    """One model with the treatment flag as a feature."""

    name = "s_learner"

    def fit(self, X: pd.DataFrame, t: Any, y: Any) -> SLearner:
        X, t_arr, y_arr = _check(X, t, y)
        self.propensity_ = float(t_arr.mean())
        self.model_ = _clf(self.seed, self.params).fit(X.assign(_treatment=t_arr), y_arr)
        return self

    def predict(self, X: pd.DataFrame) -> FloatArray:
        p1 = self.model_.predict_proba(X.assign(_treatment=1))[:, 1]
        p0 = self.model_.predict_proba(X.assign(_treatment=0))[:, 1]
        return np.asarray(p1 - p0, dtype=np.float64)


class TLearner(UpliftLearner):
    """Two models: one on contacted customers, one on held-out customers."""

    name = "t_learner"

    def fit(self, X: pd.DataFrame, t: Any, y: Any) -> TLearner:
        X, t_arr, y_arr = _check(X, t, y)
        self.propensity_ = float(t_arr.mean())
        self.model1_ = _clf(self.seed, self.params).fit(X[t_arr == 1], y_arr[t_arr == 1])
        self.model0_ = _clf(self.seed + 1, self.params).fit(X[t_arr == 0], y_arr[t_arr == 0])
        return self

    def predict_outcomes(self, X: pd.DataFrame) -> tuple[FloatArray, FloatArray]:
        """(P(buy | not contacted), P(buy | contacted))."""
        p0 = np.asarray(self.model0_.predict_proba(X)[:, 1], dtype=np.float64)
        p1 = np.asarray(self.model1_.predict_proba(X)[:, 1], dtype=np.float64)
        return p0, p1

    def predict(self, X: pd.DataFrame) -> FloatArray:
        p0, p1 = self.predict_outcomes(X)
        return p1 - p0


class XLearner(UpliftLearner):
    """X-learner: impute individual effects, then regress them on features."""

    name = "x_learner"

    def fit(self, X: pd.DataFrame, t: Any, y: Any) -> XLearner:
        X, t_arr, y_arr = _check(X, t, y)
        self.propensity_ = float(t_arr.mean())
        X1, X0 = X[t_arr == 1], X[t_arr == 0]
        y1, y0 = y_arr[t_arr == 1], y_arr[t_arr == 0]
        mu1 = _clf(self.seed, self.params).fit(X1, y1)
        mu0 = _clf(self.seed + 1, self.params).fit(X0, y0)
        d1 = y1 - mu0.predict_proba(X1)[:, 1]
        d0 = mu1.predict_proba(X0)[:, 1] - y0
        self.tau1_ = _reg(self.seed + 2, self.params).fit(X1, d1)
        self.tau0_ = _reg(self.seed + 3, self.params).fit(X0, d0)
        return self

    def predict(self, X: pd.DataFrame) -> FloatArray:
        g = self.propensity_
        tau = g * self.tau0_.predict(X) + (1.0 - g) * self.tau1_.predict(X)
        return np.asarray(tau, dtype=np.float64)


class DRLearner(UpliftLearner):
    """Doubly robust learner with cross-fitting.

    Pseudo-outcome (AIPW score) for each customer:

        phi = mu1(x) - mu0(x) + T (Y - mu1(x)) / e - (1 - T) (Y - mu0(x)) / (1 - e)

    whose conditional mean is the uplift. The nuisance models ``mu0``, ``mu1``
    are fitted on other folds than the one they score.
    """

    name = "dr_learner"

    def __init__(
        self, seed: int = 0, params: dict[str, Any] | None = None, n_folds: int = 3
    ) -> None:
        super().__init__(seed, params)
        self.n_folds = n_folds

    def fit(self, X: pd.DataFrame, t: Any, y: Any) -> DRLearner:
        X, t_arr, y_arr = _check(X, t, y)
        e = float(t_arr.mean())
        self.propensity_ = e
        mu0 = np.zeros(len(X))
        mu1 = np.zeros(len(X))
        strata = t_arr * 2 + (y_arr > 0).astype(np.int64)
        folds = StratifiedKFold(self.n_folds, shuffle=True, random_state=self.seed)
        for k, (fit_idx, score_idx) in enumerate(folds.split(X, strata)):
            Xf, tf, yf = X.iloc[fit_idx], t_arr[fit_idx], y_arr[fit_idx]
            m1 = _clf(self.seed + 10 * k, self.params).fit(Xf[tf == 1], yf[tf == 1])
            m0 = _clf(self.seed + 10 * k + 1, self.params).fit(Xf[tf == 0], yf[tf == 0])
            mu1[score_idx] = m1.predict_proba(X.iloc[score_idx])[:, 1]
            mu0[score_idx] = m0.predict_proba(X.iloc[score_idx])[:, 1]
        phi = mu1 - mu0 + t_arr * (y_arr - mu1) / e - (1 - t_arr) * (y_arr - mu0) / (1.0 - e)
        self.pseudo_outcome_mean_ = float(phi.mean())
        self.model_ = _reg(self.seed + 99, self.params).fit(X, phi)
        return self

    def predict(self, X: pd.DataFrame) -> FloatArray:
        return np.asarray(self.model_.predict(X), dtype=np.float64)


class ClassTransformation(UpliftLearner):
    """Class-variable transformation: Z = Y T + (1 - Y)(1 - T).

    With propensity ``e`` the uplift is recovered through sample weights
    ``1/e`` for treated and ``1/(1-e)`` for control rows, which reduces to
    ``tau = 2 P(Z = 1 | x) - 1`` when ``e = 0.5``.
    """

    name = "class_transformation"

    def fit(self, X: pd.DataFrame, t: Any, y: Any) -> ClassTransformation:
        X, t_arr, y_arr = _check(X, t, y)
        if not np.isin(y_arr, (0.0, 1.0)).all():
            raise ValueError("class transformation needs a binary outcome")
        e = float(t_arr.mean())
        self.propensity_ = e
        z = (y_arr * t_arr + (1 - y_arr) * (1 - t_arr)).astype(np.int64)
        w = np.where(t_arr == 1, 0.5 / e, 0.5 / (1.0 - e))
        self.model_ = _clf(self.seed, self.params).fit(X, z, sample_weight=w)
        return self

    def predict(self, X: pd.DataFrame) -> FloatArray:
        return np.asarray(2.0 * self.model_.predict_proba(X)[:, 1] - 1.0, dtype=np.float64)


class Ensemble(UpliftLearner):
    """Average of already-fitted uplift learners, each put on a common scale.

    Individual learners disagree customer by customer (their rank correlation
    on real data is only moderate), so averaging cancels part of their noise.
    Scores are standardised with the mean and spread seen on the training data.
    """

    name = "ensemble"

    def __init__(self, members: dict[str, UpliftLearner]) -> None:
        super().__init__()
        if not members:
            raise ValueError("an ensemble needs at least one member")
        self.members = members

    def fit(self, X: pd.DataFrame, t: Any = None, y: Any = None) -> Ensemble:
        """Members are already fitted; this only learns their score scales."""
        self.scale_ = {}
        for name, model in self.members.items():
            s = model.predict(X)
            self.scale_[name] = (float(s.mean()), float(s.std()) or 1.0)
        return self

    def predict(self, X: pd.DataFrame) -> FloatArray:
        parts = [
            (model.predict(X) - self.scale_[name][0]) / self.scale_[name][1]
            for name, model in self.members.items()
        ]
        return np.asarray(np.mean(parts, axis=0), dtype=np.float64)


LEARNERS: dict[str, type[UpliftLearner]] = {
    cls.name: cls
    for cls in (ResponseModel, SLearner, TLearner, XLearner, DRLearner, ClassTransformation)
}


def make_learner(name: str, seed: int = 0, params: dict[str, Any] | None = None) -> UpliftLearner:
    if name not in LEARNERS:
        raise KeyError(f"unknown learner '{name}'; choose from {sorted(LEARNERS)}")
    return LEARNERS[name](seed=seed, params=params)
