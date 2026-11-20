# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-11-25

First release, prepared for the course presentation at Saint Joseph University of Beirut on
that date. Until the release is tagged, the package metadata (`pyproject.toml` and
`liftpilot.__version__`) still reads 0.1.0.

### Added

- **Data.** `liftpilot download` for the X5 RetailHero and Hillstrom datasets with SHA-256
  verification; receipt aggregation with DuckDB; a customer table with 33 behaviour features
  and a leakage guard on redemption dates.
- **RFM.** Recency, Frequency and Monetary quintile scores, eight named segments, a weighted RFM
  score and a shrunk expected basket per customer.
- **Uplift learners.** Response-model baseline; S-, T-, X- and DR-learner; class
  transformation; ensemble. All on gradient-boosted trees.
- **Evaluation.** Qini curve and coefficient, uplift in the top share of a ranking, bootstrap
  95% intervals, repeated-split stability check, feature ablation.
- **Calibration.** Isotonic calibration of the champion's score on a separate split.
- **Profit rule.** Per-customer incremental profit and break-even uplift; allocation under an
  optional budget.
- **Replay evaluation.** Real incremental profit of any targeting rule on held-out randomised
  customers, with a paired bootstrap for the comparison of two rules; three money scenarios per
  dataset.
- **Campaign engine.** Planning, replay evidence, sensitivity analysis, hold-out design,
  per-customer explanation, eligibility rules (opt-outs, minors), human approval and audience
  export.
- **Fairness.** Selection-rate audit by age band and gender with a review flag; a "fair mode"
  that values every customer at the average basket.
- **Agent.** A local language model (Qwen3 8B through Ollama) driving 16 tools; scripted
  fallback without a model; audit log.
- **Agent controls.** Argument rule, runtime checklist, verified statements written by code,
  numeric grounding check, over-claim check, discard of a failing narrative, copy guard with
  pre-approved templates, human approval gate.
- **Agent benchmark.** `liftpilot agent-eval` with 13 fixed requests (7 campaign requests, 3
  questions, 3 safety probes); results in section 10 of `docs/RESULTS.md`.
- **Live context.** Exchange rates and public holidays with timeouts and an offline cache.
- **Results and figures.** `liftpilot results` writes `docs/RESULTS.md` and `docs/figures/`
  from the saved artifacts.
- **Dashboard.** `liftpilot app`, a Streamlit demo with six tabs.
- **Documentation.** README, explainer, model card, datasheet, ethics statement, contribution
  guide, `CITATION.cff`.
- **Quality.** Test suite on synthetic data with a known answer, ruff, mypy settings,
  pre-commit hooks, CI on Ubuntu and Windows.

### Known limitations

- Purchase amounts after the X5 campaign are not in the data; money figures value a purchase at
  the customer's average basket. Margin, contact cost and discount are scenario assumptions.
- Targeting does not beat contacting everyone when contact is cheap, and LiftPilot's own profit
  interval includes zero in the costly scenarios.
- Fair mode does not close the measured age gap.
- The age band labelled "18-24" holds ages 14 to 24, and customers under 18 are excluded from
  contact but counted in the band, so the fairness ratio for that band is lowered by
  construction. See `docs/ETHICS.md`, section 3.
- A full campaign plan with the language model takes two to three minutes on the development
  laptop (median 149 s in the agent benchmark).
- See `README.md` (Limitations) and `docs/ETHICS.md` (Open questions).
