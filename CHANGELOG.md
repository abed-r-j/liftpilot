# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Work done after the course published its closing session, "Thinking Critically with AI". No
version number was changed.

### Added

- **Stress suite.** `liftpilot agent-stress` runs 10 cases built from the closing session (the
  same request three times, opposite opinions, a leading request, three known answers, two
  hidden instructions, a swap of sender name and role, a swap of language) and writes
  `artifacts/agent_stress.json`; `--case <id>` runs one case. Results in section 12 of
  `docs/RESULTS.md`, from one full run of all ten cases on the final code: 9 of 9 gated cases
  passed over 17 agent runs, 241 of 241 numbers matched to a tool result or to a number in the
  request, 1 narrative rejected by the guards. The language swap is reported and not gated;
  the French and the Arabic request each matched the English plan and completed the checklist.
- **Guards found by the stress suite.** The runtime ignores a hold-out detection target the
  manager did not state; wording that says something was approved or exported is rejected while
  nothing is; advice to go ahead without approval is rejected; a run the model does not finish
  cannot pass a stress case. The two wording checks are pattern lists: a paraphrase that avoids
  the listed words passes them. Export itself does not depend on wording.
- **Checklist in any language.** A run in which the model itself made a plan must complete the
  whole campaign checklist, whatever the language of the request. English keywords are only a
  second trigger.
- **CHECK block.** The dashboard shows "Before you approve: CHECK" above the approver name
  field: five lines (Claims, Hunt the source, Evidence and numbers, Cross-check, Keep a human
  sign-off) written by code from the run's tool results. It adds no click. When a run made a
  plan but did not finish the checklist, the block names the steps not done and says not to
  approve before they are done.
- **Stress suite bookkeeping.** Every saved case carries a fingerprint of the code that
  produced it; the result file is written whole and a broken file stops the run; an empty
  answer or a step-limit answer fails a case; the agent run records the reminders it got, the
  steps the runtime ran itself and what was matched in its first draft. Section 12 of the
  results sheet lists the earlier runs, the guards that acted and the guards that did not.
- **Critical-thinking mapping.** `docs/CRITICAL_THINKING.md` maps the closing session to the
  product, control by control, with the evidence and the gap for each, and lists how the
  session's eight references were checked.
- **Results sheet.** `liftpilot results --sheet-only` rewrites `docs/RESULTS.md` from the saved
  artifacts without recomputing or refetching anything.
- **Quick-start guide.** `docs/QUICKSTART.md`: how to start the dashboard and what to do in
  each tab.
- **Fallback screenshots.** Six screenshots of the dashboard in `docs/presentation/fallback/`,
  for a presentation without a working demo.

### Fixed

- **Approval.** A new approval request no longer resets a plan that a person already approved
  (found by a review after the last stress run; `engine.py`, unit test only).
- **CHECK block.** It counts only the steps of the last plan of a run, and an interval of
  missing values is no longer read as an interval.
- **Dark theme.** Dashboard colours are readable in the dark theme.
- **Tab titles.** Tab titles are no longer clipped.
- **Arabic request stopped early.** In an earlier stress run an Arabic request got a plan but
  no hold-out design, no send date, no drafts and no approval request, because the runtime
  recognised a campaign request by English keywords. See "Checklist in any language" above.
- **"Approved" check switched off after any approval.** The check on false "approved or
  exported" wording, and the check on advice to skip approval, now look only at the plans of
  the run itself. An approval given to another plan earlier in the session no longer excuses
  the wording. Once a plan of the run really is approved, neither check is applied to that run.
- **A denial anywhere excused the whole sentence.** A denial or a condition now excuses a
  status phrase only when it stands just before it, in the same clause. More phrasings count
  as a claim ("export is complete", "approval has been granted").
- **Hold-out guard was too loose.** A detection target is kept only if it is a fraction
  between 0 and 1 that the manager wrote next to detection wording. A number written for
  something else, such as a cost or a margin, no longer counts. The wording is matched in
  English only.
- **Export slider.** The slider "Random hold-out for measurement" started at 10% while the
  briefing stated the designed share. It now starts at the share designed in the run, else at
  10%, with a caption that says which.
- **CHECK block.** The Claims line now says "matched to a tool result or to a number in the
  request", which is what the check does. Malformed values in a run give a plain row and no
  error on the approval screen.
- **Stress scoring.** The hidden-instruction cases could pass with an empty answer. The French
  test sentence began with "Planifie", which contains the English keyword "plan"; it was
  replaced by a sentence with no English keyword, and a test checks this. The checks for
  agreement and for a guaranteed result read only the words around the phrase.

### Known limitations

- Four earlier runs of the stress suite each scored 9 of 9 under a weaker rule and each hid a
  problem (section 12 of `docs/RESULTS.md`). The final figures come from one run of all ten
  cases on the final code: one model, one seed, one run per variant.
- The over-claim list does not read denials. In the final stress run it matched "messages
  sent" inside "No messages sent yet.", and one correct briefing was replaced by the verified
  statements. The first draft was sent back for a rewrite in 16 of 17 runs. Not fixed.
- Some guards did not have to act in the final stress run, so only unit tests show that they
  work: dropping an invented planning argument, the runtime running missing steps itself,
  blocking an export attempt, and sending a draft back for an ungrounded number or for advice
  to skip approval.
- The dashboard still shows the Approve button for a plan whose run did not finish the
  checklist. The CHECK block warns; it does not stop.
- Languages other than English were tested with one French and one Arabic request, one run
  each. The wording of the drafts was not compared.
- The agent benchmark of section 10 was produced before these guards and was not run again.

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
