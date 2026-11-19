"""Turn raw files into an ``Experiment``: a clean, model-ready randomised dataset."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from liftpilot import rfm
from liftpilot.data import x5

X5_FEATURES = [
    "recency_days",
    "frequency",
    "monetary",
    "avg_basket",
    "std_basket",
    "max_basket",
    "median_basket",
    "tenure_days",
    "active_days",
    "active_weeks",
    "n_stores",
    "avg_lines",
    "avg_units",
    "points_received",
    "express_received",
    "points_spent",
    "express_spent",
    "share_tx_redeeming",
    "share_weekend",
    "share_evening",
    "frequency_30d",
    "monetary_30d",
    "frequency_31_60d",
    "monetary_31_60d",
    "frequency_7d",
    "avg_gap_days",
    "frequency_trend",
    "card_age_days",
    "redeemed_before",
    "days_since_first_redeem",
    "r_score",
    "f_score",
    "m_score",
]

# Never used as model inputs; kept only to audit who ends up being targeted.
X5_AUDIT = ["age_band", "gender"]

AGE_BINS = [0, 25, 35, 45, 55, 65, 200]
AGE_LABELS = ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]


@dataclass
class Experiment:
    """A randomised marketing experiment, one row per customer.

    ``frame`` columns: the ``features``, ``t`` (1 = contacted), ``y`` (1 =
    converted), ``revenue`` (revenue in the outcome window), ``value``
    (expected revenue of one conversion), ``split`` (train / calibration /
    test, or ``new`` for customers outside the experiment) and audit columns.
    """

    name: str
    frame: pd.DataFrame
    features: list[str]
    currency: str
    revenue_observed: bool
    description: str
    audit_cols: list[str] = field(default_factory=list)
    notes: dict[str, object] = field(default_factory=dict)

    def part(self, split: str) -> pd.DataFrame:
        return self.frame[self.frame["split"] == split]

    @property
    def labelled(self) -> pd.DataFrame:
        return self.frame[self.frame["split"] != "new"]


def assign_splits(
    df: pd.DataFrame, seed: int = 0, calibration: float = 0.2, test: float = 0.2
) -> pd.Series:
    """Stratified train / calibration / test split of the labelled customers.

    Stratification on (treatment, outcome) keeps both experimental arms and
    the conversion rate identical across the three parts.
    """
    labelled = df["t"].notna().to_numpy()
    pos = np.flatnonzero(labelled)
    strata = df["t"].to_numpy()[pos].astype(int) * 2 + (df["y"].to_numpy()[pos] > 0).astype(int)
    rest, test_pos, strata_rest, _ = train_test_split(
        pos, strata, test_size=test, random_state=seed, stratify=strata
    )
    train_pos, cal_pos = train_test_split(
        rest,
        test_size=calibration / (1.0 - test),
        random_state=seed + 1,
        stratify=strata_rest,
    )
    labels = np.full(len(df), "new", dtype=object)
    labels[train_pos] = "train"
    labels[cal_pos] = "calibration"
    labels[test_pos] = "test"
    return pd.Series(labels, index=df.index, dtype=object)


def clean_age(age: pd.Series) -> pd.Series:
    """Ages outside 14-100 are data-entry errors: set them to missing."""
    out = age.astype("float64")
    return out.where((out >= 14) & (out <= 100))


def load_x5(raw_dir: Path, interim_dir: Path, seed: int = 0, rebuild: bool = False) -> Experiment:
    cache = interim_dir / "x5_customers.parquet"
    if cache.exists() and not rebuild:
        df = pd.read_parquet(cache)
    else:
        df = x5.build_customer_table(raw_dir, interim_dir, rebuild=rebuild)
        interim_dir.mkdir(parents=True, exist_ok=True)
        df.to_parquet(cache)

    df = rfm.add_rfm(df)
    df["value"] = rfm.shrunk_basket(df["avg_basket"], df["frequency"])
    df["age"] = clean_age(df["age_raw"])
    df["age_band"] = pd.cut(df["age"], AGE_BINS, labels=AGE_LABELS, right=False).astype(object)
    df["age_band"] = df["age_band"].fillna("unknown")
    df["gender"] = df["gender"].map({"M": "male", "F": "female", "U": "unknown"}).fillna("unknown")
    # The public file records whether a purchase happened, not its amount.
    # Revenue of a converter is therefore imputed with that customer's own
    # expected basket; every money figure built on it is labelled as such.
    df["revenue"] = df["y"] * df["value"]
    df["split"] = assign_splits(df, seed=seed)
    for col in X5_FEATURES:
        df[col] = df[col].astype("float64")

    notes = {
        "reference_date": str(pd.Timestamp(df["reference_date"].iloc[0]).date()),
        "history_start": str(pd.Timestamp(df["history_start"].iloc[0]).date()),
        "invalid_ages_set_missing": int(df["age"].isna().sum()),
        "source": x5.BASE_URL,
    }
    return Experiment(
        name="x5",
        frame=df,
        features=list(X5_FEATURES),
        currency="RUB",
        revenue_observed=False,
        description=(
            "X5 Retail Group (RetailHero 2019): a marketing communication sent at random to "
            "half of the loyalty-card holders of a grocery chain; outcome = purchase afterwards."
        ),
        audit_cols=list(X5_AUDIT),
        notes=notes,
    )


HILLSTROM_URL = (
    "http://www.minethatdata.com/"
    "Kevin_Hillstrom_MineThatData_E-MailAnalytics_DataMiningChallenge_2008.03.20.csv"
)


def load_hillstrom(raw_dir: Path, seed: int = 0, outcome: str = "visit") -> Experiment:
    """Hillstrom MineThatData e-mail test: 64,000 customers, real spend in USD.

    Two e-mail versions and a no-e-mail control were assigned at random. Here
    both e-mails count as "contacted". ``outcome`` is the binary result the
    model learns (``visit`` or ``conversion``); money comes from ``spend``.
    """
    df = pd.read_csv(raw_dir / "hillstrom.csv")
    df.index = pd.Index([f"h{i:05d}" for i in range(len(df))], name="client_id")
    df["t"] = (df["segment"] != "No E-Mail").astype(float)
    df["y"] = df[outcome].astype(float)
    df["revenue"] = df["spend"].astype(float)
    df["zip_urban"] = (df["zip_code"] == "Urban").astype(float)
    df["zip_rural"] = (df["zip_code"] == "Rural").astype(float)
    df["channel_web"] = df["channel"].isin(["Web", "Multichannel"]).astype(float)
    df["channel_phone"] = df["channel"].isin(["Phone", "Multichannel"]).astype(float)
    df["recency_days"] = df["recency"] * 30.0
    df["monetary"] = df["history"]
    features = [
        "recency",
        "history",
        "mens",
        "womens",
        "newbie",
        "zip_urban",
        "zip_rural",
        "channel_web",
        "channel_phone",
    ]
    for col in features:
        df[col] = df[col].astype("float64")
    df["split"] = assign_splits(df, seed=seed)
    train = df[df["split"] == "train"]
    # Expected revenue per positive outcome, measured on the training part only.
    df["value"] = float(train["revenue"].sum() / max(train["y"].sum(), 1.0))
    df["r_score"] = rfm.quintile_score(df["recency"], higher_is_better=False)
    df["m_score"] = rfm.quintile_score(df["history"], higher_is_better=True)
    return Experiment(
        name="hillstrom",
        frame=df,
        features=features,
        currency="USD",
        revenue_observed=True,
        description=(
            "Hillstrom MineThatData (2008): randomised e-mail campaign of an online "
            f"retailer; outcome = {outcome} within two weeks; revenue = observed spend."
        ),
        audit_cols=[],
        notes={"source": HILLSTROM_URL, "outcome": outcome, "arms": "any e-mail vs no e-mail"},
    )


def describe(exp: Experiment) -> dict[str, object]:
    lab = exp.labelled
    t, y = lab["t"].to_numpy(), lab["y"].to_numpy()
    return {
        "name": exp.name,
        "description": exp.description,
        "currency": exp.currency,
        "customers_total": len(exp.frame),
        "customers_in_experiment": len(lab),
        "treated_share": float(t.mean()),
        "conversion_treated": float(y[t == 1].mean()),
        "conversion_control": float(y[t == 0].mean()),
        "splits": {k: int(v) for k, v in exp.frame["split"].value_counts().items()},
        "n_features": len(exp.features),
        "revenue_observed": exp.revenue_observed,
        "mean_value": float(np.mean(lab["value"])),
        **exp.notes,
    }
