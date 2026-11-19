"""End-to-end training and evaluation pipeline.

    raw files -> customer table -> RFM -> uplift learners -> champion ->
    calibration -> profit rule -> off-policy evaluation -> audit -> artifacts

Three disjoint parts of the experiment keep the numbers honest:

* **train**        fits the models,
* **calibration**  picks the champion learner and calibrates its scores,
* **test**         is touched once, to report results.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from liftpilot import fairness
from liftpilot.data.prepare import Experiment, assign_splits, describe
from liftpilot.policy.economics import Economics, break_even_uplift, incremental_profit
from liftpilot.policy.evaluation import compare_policies, evaluate_policy, profit_curve
from liftpilot.policy.optimizer import allocate, top_k
from liftpilot.uplift import metrics
from liftpilot.uplift.calibration import UpliftCalibrator
from liftpilot.uplift.learners import LEARNERS, Ensemble, TLearner, make_learner

UPLIFT_LEARNERS = [n for n in LEARNERS if n != "response"]
ALL_SCORES = [*LEARNERS, "ensemble"]
CHAMPION_CANDIDATES = [*UPLIFT_LEARNERS, "ensemble"]

DEFAULT_SCENARIOS: dict[str, dict[str, Economics]] = {
    "x5": {
        "A. Text reminder (2 RUB per message)": Economics(
            margin=0.25, contact_cost=2.0, discount=0.0, currency="RUB"
        ),
        "B. Costlier channel (6 RUB per contact)": Economics(
            margin=0.25, contact_cost=6.0, discount=0.0, currency="RUB"
        ),
        "C. Reminder + 3% basket discount": Economics(
            margin=0.25, contact_cost=2.0, discount=0.03, currency="RUB"
        ),
    },
    "hillstrom": {
        "A. E-mail (0.10 USD all-in)": Economics(
            margin=0.40, contact_cost=0.10, discount=0.0, currency="USD"
        ),
        "B. Printed mailer (0.60 USD)": Economics(
            margin=0.40, contact_cost=0.60, discount=0.0, currency="USD"
        ),
        "C. E-mail + 10% discount": Economics(
            margin=0.40, contact_cost=0.10, discount=0.10, currency="USD"
        ),
    },
}

DEFAULT_ECONOMICS: dict[str, Economics] = {
    "x5": Economics(margin=0.25, contact_cost=2.0, discount=0.0, currency="RUB"),
    "hillstrom": Economics(margin=0.40, contact_cost=0.10, discount=0.0, currency="USD"),
}


def _xy(df: pd.DataFrame, features: list[str]) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    return df[features], df["t"].to_numpy().astype(int), df["y"].to_numpy().astype(float)


def _json_default(o: Any) -> Any:
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return None if np.isnan(o) else float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, pd.Timestamp):
        return str(o)
    raise TypeError(f"not JSON serialisable: {type(o)}")


def _thin(curve: metrics.Curve, points: int = 201) -> dict[str, list[float]]:
    idx = np.unique(np.linspace(0, len(curve.x) - 1, points).round().astype(int))
    return {"fraction": curve.fraction[idx].tolist(), "value": curve.y[idx].tolist()}


def benchmark(
    exp: Experiment, seed: int, n_boot: int, params: dict[str, Any] | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fit every learner on train; score calibration and test; report metrics."""
    Xtr, ttr, ytr = _xy(exp.part("train"), exp.features)
    Xca, tca, yca = _xy(exp.part("calibration"), exp.features)
    Xte, tte, yte = _xy(exp.part("test"), exp.features)
    models: dict[str, Any] = {}
    rows: dict[str, Any] = {}

    def add(name: str, model: Any, seconds: float) -> None:
        s_ca, s_te = model.predict(Xca), model.predict(Xte)
        models[name] = model
        rows[name] = {
            "fit_seconds": round(seconds, 2),
            "qini_calibration": metrics.qini_coefficient(yca, tca, s_ca),
            "qini_test": metrics.bootstrap_metric(
                metrics.qini_coefficient, yte, tte, s_te, n_boot=n_boot, seed=seed
            ),
            "auuc_test": metrics.auuc(yte, tte, s_te),
            "uplift_at_10": metrics.uplift_at_k(yte, tte, s_te, k=0.10),
            "uplift_at_30": metrics.uplift_at_k(yte, tte, s_te, k=0.30),
            "uplift_bottom_30": metrics.uplift_at_k(yte, tte, -s_te, k=0.30),
        }

    for name in LEARNERS:
        start = time.perf_counter()
        model = make_learner(name, seed=seed, params=params).fit(Xtr, ttr, ytr)
        add(name, model, time.perf_counter() - start)
    start = time.perf_counter()
    ensemble = Ensemble({n: models[n] for n in UPLIFT_LEARNERS}).fit(Xtr)
    add("ensemble", ensemble, time.perf_counter() - start)
    return models, rows


def repeated_split_qini(
    exp: Experiment, repeats: int, seed: int, params: dict[str, Any] | None = None
) -> dict[str, dict[str, float]]:
    """Stability check: re-split and re-train several times, report mean and SD."""
    scores: dict[str, list[float]] = {n: [] for n in ALL_SCORES}
    lab = exp.labelled
    for r in range(repeats):
        split = assign_splits(lab, seed=seed + 100 + r)
        train, test = lab[split.isin(["train", "calibration"])], lab[split == "test"]
        Xtr, ttr, ytr = _xy(train, exp.features)
        Xte, tte, yte = _xy(test, exp.features)
        fitted = {}
        for name in LEARNERS:
            fitted[name] = make_learner(name, seed=seed + r, params=params).fit(Xtr, ttr, ytr)
        fitted["ensemble"] = Ensemble({n: fitted[n] for n in UPLIFT_LEARNERS}).fit(Xtr)
        for name, model in fitted.items():
            scores[name].append(metrics.qini_coefficient(yte, tte, model.predict(Xte)))
    return {
        n: {"mean": float(np.mean(v)), "sd": float(np.std(v, ddof=1)), "runs": len(v)}
        for n, v in scores.items()
    }


CONTACT = "contact"
SKIP_COST = "skip: gain below cost"
SKIP_NO_EFFECT = "skip: no expected effect"


def decision_groups(tau: np.ndarray, gain: np.ndarray) -> np.ndarray:
    """Three decision groups under the given money assumptions.

    The textbook picture has four customer types (persuadables, sure things,
    lost causes, sleeping dogs). Types are not observable for an individual,
    and on the X5 test data the group with a non-positive estimated effect
    turned out to have a small positive real effect, not a negative one. The
    labels therefore describe the decision and its reason, not a personality.
    """
    out = np.full(len(tau), SKIP_COST, dtype=object)
    out[gain > 0] = CONTACT
    out[tau <= 0] = SKIP_NO_EFFECT
    return out


def run(
    exp: Experiment,
    out_dir: Path,
    econ: Economics | None = None,
    seed: int = 0,
    n_boot: int = 300,
    repeats: int = 5,
    params: dict[str, Any] | None = None,
    extra_feature_sets: dict[str, list[str]] | None = None,
    scenarios: dict[str, Economics] | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    econ = econ or DEFAULT_ECONOMICS[exp.name]
    report: dict[str, Any] = {
        "dataset": describe(exp),
        "economics": econ.model_dump(),
        "seed": seed,
    }

    lab = exp.labelled
    report["experiment_readout"] = metrics.average_treatment_effect(lab["y"], lab["t"])

    # 1. benchmark -----------------------------------------------------------------
    models, table = benchmark(exp, seed, n_boot, params)
    report["learners"] = table
    if repeats > 0:
        report["learners_repeated"] = repeated_split_qini(exp, repeats, seed, params)

    # 2. champion = best Qini on the calibration part (never on test) -----------------
    champion = max(CHAMPION_CANDIDATES, key=lambda n: table[n]["qini_calibration"])
    report["champion"] = champion

    cal, test = exp.part("calibration"), exp.part("test")
    Xca, tca, yca = _xy(cal, exp.features)
    _, tte, yte = _xy(test, exp.features)
    calibrator = UpliftCalibrator().fit(models[champion].predict(Xca), tca, yca)
    report["calibration"] = {
        "informative": calibrator.is_informative(),
        "bin_score": calibrator.bin_score_.tolist(),
        "bin_uplift_observed": calibrator.bin_uplift_.tolist(),
        "bin_uplift_fitted": calibrator.predict(calibrator.bin_score_).tolist(),
    }

    # 3. score every customer --------------------------------------------------------
    frame = exp.frame.copy()
    X_all = frame[exp.features]
    t_model: TLearner = models["t_learner"]
    p0, p1 = t_model.predict_outcomes(X_all)
    frame["p0"], frame["p1"] = p0, p1
    for name, model in models.items():
        frame[f"score_{name}"] = model.predict(X_all)
    frame["uplift_score"] = frame[f"score_{champion}"]
    frame["uplift"] = calibrator.predict(frame["uplift_score"])
    frame["break_even_uplift"] = break_even_uplift(econ, frame["value"], frame["p1"])
    frame["gain"] = incremental_profit(econ, frame["value"], frame["uplift"], frame["p1"])
    frame["type"] = decision_groups(frame["uplift"].to_numpy(), frame["gain"].to_numpy())

    te = frame.loc[test.index]
    scale = len(frame) / len(te)
    report["scale_to_base"] = scale

    # 4. curves on test --------------------------------------------------------------
    curves: dict[str, Any] = {"qini": {}, "profit": {}}
    for name in ALL_SCORES:
        curves["qini"][name] = _thin(metrics.qini_curve(yte, tte, te[f"score_{name}"]))
        curves["profit"][name] = {
            k: v.tolist()
            for k, v in profit_curve(
                econ, te[f"score_{name}"], tte, yte, te["revenue"], scale=scale
            ).items()
        }
    curves["qini"]["rfm"] = (
        _thin(metrics.qini_curve(yte, tte, te["rfm_score"])) if ("rfm_score" in te) else None
    )
    curves["profit"]["liftpilot"] = {
        k: v.tolist()
        for k, v in profit_curve(econ, te["gain"], tte, yte, te["revenue"], scale=scale).items()
    }
    curves["qini"]["perfect_end"] = float(metrics.qini_curve(yte, tte, te["uplift"]).y[-1])
    curves["deciles"] = {
        k: v.tolist() for k, v in metrics.uplift_by_bin(yte, tte, te["uplift_score"], 10).items()
    }
    curves["deciles_calibrated_mean"] = [
        float(np.mean(chunk))
        for chunk in np.array_split(
            te["uplift"].to_numpy()[np.argsort(-te["uplift_score"].to_numpy(), kind="stable")], 10
        )
    ]

    # 5. policies, evaluated on what really happened in the test part ----------------
    plan = allocate(econ, te["value"], te["uplift"], te["p1"])
    k = plan.n_selected
    rng = np.random.default_rng(seed)
    random_sel = np.zeros(len(te), dtype=bool)
    random_sel[rng.choice(len(te), k, replace=False)] = True
    policies: dict[str, np.ndarray] = {
        "Contact everyone": np.ones(len(te), dtype=bool),
        "Random, same size": random_sel,
        "Response model, same size": top_k(te["score_response"], k),
        f"Uplift ranking ({champion}), same size": top_k(te["uplift_score"], k),
        "LiftPilot profit rule": plan.selected,
    }
    if "rfm_score" in te:
        policies["RFM best customers, same size"] = top_k(te["rfm_score"], k)
        policies["RFM at-risk segments"] = (
            te["rfm_segment"].isin(["At risk", "Cannot lose them", "Need attention"]).to_numpy()
        )
    report["policies"] = {
        name: evaluate_policy(
            name, econ, sel, tte, yte, te["revenue"], scale=scale, n_boot=n_boot, seed=seed
        ).as_dict()
        for name, sel in policies.items()
    }
    report["plan_expected"] = plan.summary()
    report["liftpilot_vs_everyone"] = compare_policies(
        econ,
        plan.selected,
        np.ones(len(te), dtype=bool),
        tte,
        yte,
        te["revenue"],
        scale=scale,
        n_boot=n_boot,
        seed=seed,
    )

    # 5b. the same comparison under other money assumptions --------------------------------
    scen_out: dict[str, Any] = {}
    for label, e in (scenarios or DEFAULT_SCENARIOS.get(exp.name, {})).items():
        p = allocate(e, te["value"], te["uplift"], te["p1"])
        everyone = np.ones(len(te), dtype=bool)
        rules = {
            "Contact everyone": everyone,
            "Response model, same size": top_k(te["score_response"], p.n_selected),
            "LiftPilot profit rule": p.selected,
        }
        if "rfm_score" in te:
            rules["RFM best customers, same size"] = top_k(te["rfm_score"], p.n_selected)
        scen_out[label] = {
            "economics": e.model_dump(),
            "mean_break_even_uplift": float(break_even_uplift(e, te["value"], te["p1"]).mean()),
            "policies": {
                name: evaluate_policy(
                    name, e, sel, tte, yte, te["revenue"], scale=scale, n_boot=n_boot, seed=seed
                ).as_dict()
                for name, sel in rules.items()
            },
            "liftpilot_vs_everyone": compare_policies(
                e,
                p.selected,
                everyone,
                tte,
                yte,
                te["revenue"],
                scale=scale,
                n_boot=n_boot,
                seed=seed,
            ),
        }
    report["scenarios"] = scen_out

    # 6. who is who ------------------------------------------------------------------
    report["types"] = {
        str(k): {"customers": int(v), "share": float(v / len(frame))}
        for k, v in frame["type"].value_counts().items()
    }
    # Do the model's types hold on customers it never saw? Real uplift per type, test part.
    for name, part in te.groupby("type"):
        if part["t"].nunique() == 2 and len(part) > 50:
            ate = metrics.average_treatment_effect(part["y"], part["t"])
            report["types"][str(name)].update(
                test_customers=len(part),
                test_uplift=ate["ate"],
                test_uplift_ci=[ate["ci_low"], ate["ci_high"]],
                test_rate_control=ate["rate_control"],
            )
    if "r_score" in frame:
        by_score: dict[str, Any] = {}
        for dim in ("r_score", "f_score", "m_score"):
            if dim not in frame:
                continue
            by_score[dim] = {}
            for score, part in lab.assign(**{dim: frame.loc[lab.index, dim]}).groupby(dim):
                ate = metrics.average_treatment_effect(part["y"], part["t"])
                by_score[dim][str(int(score))] = {
                    "customers": len(part),
                    "rate_control": ate["rate_control"],
                    "uplift": ate["ate"],
                    "ci_low": ate["ci_low"],
                    "ci_high": ate["ci_high"],
                }
        report["uplift_by_rfm_score"] = by_score
    if "rfm_segment" in frame:
        seg_rows = {}
        for seg, part in frame.groupby("rfm_segment", observed=True):
            pl = part[part["split"] != "new"]
            ate = metrics.average_treatment_effect(pl["y"], pl["t"])
            seg_rows[str(seg)] = {
                "customers": len(part),
                "share": len(part) / len(frame),
                "recency_days": float(part["recency_days"].mean()),
                "frequency": float(part["frequency"].mean()),
                "monetary": float(part["monetary"].mean()),
                "avg_basket": float(part["value"].mean()),
                "conversion_control": ate["rate_control"],
                "observed_uplift": ate["ate"],
                "uplift_ci_low": ate["ci_low"],
                "uplift_ci_high": ate["ci_high"],
                "predicted_uplift": float(part["uplift"].mean()),
                "share_selected": float((part["gain"] > 0).mean()),
            }
        report["rfm_segments"] = seg_rows

    # 7. fairness audit of the test-part plan ------------------------------------------
    audit: dict[str, Any] = {}
    for col in exp.audit_cols:
        tab = fairness.audit_groups(te[col], plan.selected, tte, yte)
        audit[col] = {
            "groups": json.loads(tab.reset_index().to_json(orient="records")),
            "disparate_impact": fairness.disparate_impact(tab),
        }
    report["fairness"] = audit

    # 8. ablations: what do extra feature sets buy? --------------------------------------
    if extra_feature_sets:
        abl = {}
        _, ttr, ytr = _xy(exp.part("train"), exp.features)
        base_learner = champion if champion in LEARNERS else "x_learner"
        for label, feats in extra_feature_sets.items():
            m = make_learner(base_learner, seed=seed, params=params).fit(
                exp.part("train")[feats], ttr, ytr
            )
            abl[label] = {
                "n_features": len(feats),
                "qini_test": metrics.bootstrap_metric(
                    metrics.qini_coefficient,
                    yte,
                    tte,
                    m.predict(test[feats]),
                    n_boot=n_boot,
                    seed=seed,
                ),
            }
        report["ablation"] = abl

    # 9. feature importance of the champion (gain share) ---------------------------------
    # The X-learner's effect model regresses imputed individual effects on the
    # features, so its split gains describe what drives uplift (not purchase).
    booster = getattr(models["x_learner"], "tau1_", None)
    if booster is not None and hasattr(booster, "booster_"):
        names = booster.booster_.feature_name()
        gains = booster.booster_.feature_importance(importance_type="gain")
        total = float(gains.sum()) or 1.0
        order = np.argsort(-gains)[:15]
        report["feature_importance"] = {names[i]: float(gains[i] / total) for i in order}

    # 10. save ------------------------------------------------------------------------------
    keep = [
        *exp.features,
        "t",
        "y",
        "revenue",
        "value",
        "split",
        "p0",
        "p1",
        "uplift_score",
        "uplift",
        "break_even_uplift",
        "gain",
        "type",
        *exp.audit_cols,
        *[
            c
            for c in ("rfm_score", "rfm_segment", "rfm_cell", "recency_days", "monetary", "age")
            if c in frame.columns
        ],
        *[f"score_{n}" for n in ALL_SCORES],
    ]
    keep = list(dict.fromkeys(keep))
    scored = frame[keep].copy()
    if "rfm_segment" in scored:
        scored["rfm_segment"] = scored["rfm_segment"].astype(str)
    scored.to_parquet(out_dir / "customers.parquet")
    joblib.dump(
        {
            "models": models,
            "calibrator": calibrator,
            "champion": champion,
            "features": exp.features,
        },
        out_dir / "models.joblib",
        compress=3,
    )
    (out_dir / "curves.json").write_text(json.dumps(curves, default=_json_default))
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, default=_json_default))
    return report
