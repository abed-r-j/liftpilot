# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-11-25

First release, prepared for the course presentation at Saint Joseph University of Beirut on
that date. The package metadata (`pyproject.toml` and `liftpilot.__version__`) and
`CITATION.cff` read 1.0.0.

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
  per-customer explanation, eligibility rules (opt-outs, minors), restriction to RFM segments
  only (an unknown or demographic segment name is refused), human approval by a named person
  and audience export.
- **Fairness.** Selection-rate audit by age band and gender with a review flag; customers under
  18 form their own band and are kept out of the ratio; a "fair mode" that values every customer
  at the average basket and holds a budget on real expected spend.
- **Agent.** A local language model (Qwen3 8B through Ollama) driving 16 tools; scripted
  fallback without a model; audit log.
- **Agent controls.** Provenance guard (a planning argument must be traceable to the manager's
  words), runtime checklist, verified statements written by code, numeric grounding check,
  over-claim check, discard of a failing narrative, copy guard with pre-approved templates,
  human approval gate.
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

### Fixed before release (code review of the release candidate)

- **Fairness audit.** Customers under 18, who are never contacted, were counted inside the
  "18-24" age band, which lowered that band's selection rate by construction and overstated the
  age gap (ratios 0.85 / 0.70 / 0.48 at 2 / 6 / 10 RUB). There is now a separate "under 18" band
  that is left out of the ratio. Corrected ratios: 0.96 / 0.86 / 0.82 / 0.57 at 2 / 4 / 6 / 10
  RUB, flagged only at 10 RUB. The model was retrained and every number, figure and the agent
  benchmark were regenerated.
- **Budget provenance.** A budget or its currency is never guessed: when the amount or the
  currency cannot be matched to the manager's words, the plan is refused instead of being made
  on a reinterpreted figure.
- **Copy guard.** The offer wording is checked before drafting, and a message that fails the
  copy checks is never stored on the plan, so it cannot reach an export.
- **Approval.** Messages cannot be redrafted after a plan is approved.
- **Fair mode.** A budget is respected on real expected spend, not on the equal-basket spend
  used for the decision.
- **Verified statements.** A plan whose replay estimate is not clearly positive is no longer
  described as "more likely than not" profitable.
- **Numeric grounding.** The rounding tolerance is capped at 2% of the value, so "30%" is not
  accepted for 25%.
- **Without a model.** A request that states costs or a budget is not planned on default costs
  when the language model is unavailable; the answer says that no plan was made.

### Known limitations

- Purchase amounts after the X5 campaign are not in the data; money figures value a purchase at
  the customer's average basket. Margin, contact cost and discount are scenario assumptions.
- Targeting does not beat contacting everyone when contact is cheap, and LiftPilot's own profit
  interval includes zero in the costly scenarios.
- Among adult age bands the selection ratio falls to 0.57 at 10 RUB per message (flagged for
  human review). Fair mode does not help: at 6 RUB it lowers the ratio from 0.82 to 0.58 and
  roughly halves the profit estimate.
- A full campaign plan with the language model took 40 to 161 seconds on the development laptop
  (median 136 s in the agent benchmark): about 50 seconds on a cool laptop, two minutes or more
  when the GPU is hot or shared.
- See `README.md` (Limitations) and `docs/ETHICS.md` (Open questions).
