from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture(scope="session")
def synthetic_rct() -> dict[str, object]:
    """A randomised experiment with a known uplift structure.

    x0 drives the baseline purchase rate (sure things vs lost causes);
    x1 drives the uplift (persuadables have x1 > 0, sleeping dogs x1 < -1).
    """
    rng = np.random.default_rng(42)
    n = 24_000
    X = pd.DataFrame(rng.normal(size=(n, 5)), columns=[f"x{i}" for i in range(5)])
    base = 1 / (1 + np.exp(-(X["x0"] - 0.5)))
    tau = np.where(X["x1"] > 0, 0.15, np.where(X["x1"] < -1, -0.08, 0.0))
    t = rng.integers(0, 2, n)
    p = np.clip(base * 0.6 + 0.1 + t * tau, 0.01, 0.99)
    y = (rng.random(n) < p).astype(int)
    value = np.exp(rng.normal(6.0, 0.4, n))
    return {"X": X, "t": t, "y": y, "tau": tau, "value": value, "base": np.asarray(base)}


@pytest.fixture(scope="session")
def tiny_experiment():
    """A small synthetic shop with RFM columns, audit columns and unlabelled customers."""
    from liftpilot import rfm
    from liftpilot.data.prepare import Experiment, assign_splits

    rng = np.random.default_rng(7)
    n = 30_000
    df = pd.DataFrame(
        {
            "recency_days": rng.integers(1, 120, n).astype(float),
            "frequency": rng.integers(1, 40, n).astype(float),
            "avg_basket": np.exp(rng.normal(6.0, 0.4, n)),
            "x_noise": rng.normal(size=n),
        },
        index=pd.Index([f"c{i:05d}" for i in range(n)], name="client_id"),
    )
    df["monetary"] = df["frequency"] * df["avg_basket"]
    df = rfm.add_rfm(df)
    df["value"] = rfm.shrunk_basket(df["avg_basket"], df["frequency"])
    base = 1 / (1 + np.exp(-(df["frequency"] - 20) / 8))
    tau = np.where(df["recency_days"] > 60, 0.20, 0.0)  # lapsed customers are persuadable
    df["true_tau"] = tau
    t = rng.integers(0, 2, n).astype(float)
    y = (rng.random(n) < np.clip(0.15 + 0.6 * base + t * tau, 0, 0.98)).astype(float)
    labelled = rng.random(n) < 0.7
    df["t"] = np.where(labelled, t, np.nan)
    df["y"] = np.where(labelled, y, np.nan)
    df["revenue"] = df["y"] * df["value"]
    df["age"] = rng.integers(16, 80, n).astype(float)
    df["age_band"] = pd.cut(
        df["age"], [0, 35, 55, 200], labels=["young", "middle", "senior"]
    ).astype(str)
    df["gender"] = rng.choice(["female", "male", "unknown"], n)
    df["split"] = assign_splits(df, seed=0)
    return Experiment(
        name="tiny",
        frame=df,
        features=["recency_days", "frequency", "monetary", "avg_basket", "x_noise"],
        currency="RUB",
        revenue_observed=False,
        description="synthetic test shop",
        audit_cols=["age_band", "gender"],
        notes={"reference_date": "2019-03-19", "history_start": "2018-11-21"},
    )


@pytest.fixture(scope="session")
def tiny_artifacts(tiny_experiment, tmp_path_factory):
    from liftpilot import pipeline
    from liftpilot.policy.economics import Economics

    out = tmp_path_factory.mktemp("artifacts")
    report = pipeline.run(
        tiny_experiment,
        out,
        econ=Economics(margin=0.25, contact_cost=2.0),
        n_boot=20,
        repeats=0,
        params={"n_estimators": 60, "min_child_samples": 40},
        scenarios={"costly": Economics(margin=0.25, contact_cost=8.0)},
    )
    return out, report


@pytest.fixture
def engine(tiny_artifacts, tmp_path, monkeypatch):
    from liftpilot.engine import CampaignEngine

    monkeypatch.setenv("LIFTPILOT_HOME", str(tmp_path))
    return CampaignEngine("tiny", artifacts=tiny_artifacts[0])
