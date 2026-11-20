# Is it wise? Ethics of LiftPilot

This document takes a position, gives the measured findings, maps every control to the code
and its test, states what the system must not be used for, and lists the questions that remain
open. Measured numbers come from [RESULTS.md](RESULTS.md) unless the sentence names another
source. References are numbered and listed at the end with links. Legal passages are quoted
from the official texts; our reading of them is an interpretation by students, not legal
advice.

## 1. Position

**Conditionally yes.** Deciding who to contact by estimated uplift is better, ethically, than
the two things it replaces: contacting everyone, and contacting the people most likely to buy.
It sends fewer unwanted messages, it wastes fewer discounts, and it forces the company to
measure what its marketing really causes. But an uplift score is, by construction, an estimate
of how much a person's behaviour changes when the company acts. That is the property that makes
it profitable and the property that makes it sensitive.

So the system is wise only under conditions, and we built it to meet them:

1. the influence stays on the persuasion side of the line: open, truthful, with no exploitation
   of weakness;
2. people who opted out are removed before the optimiser runs;
3. who gets contacted is audited by group, with numbers, for every plan;
4. nothing is exported without a named human approving it;
5. what the language model writes is checked by code: a planning assumption the manager never
   stated, a number no tool returned, an over-confident word, or an offer that is not on the
   offer sheet is rejected, and the facts shown to the manager are written by code;
6. the limits are reported with the results.

Where a condition is only partly met, section 7 says so.

## 2. The argument

### 2.1 The dilemma

A likely-buyer score estimates "will buy". An uplift score estimates "will change because of our
message". When the differences it picks up are about relevance (the customer had drifted away,
or had not formed a habit yet), using it is ordinary good marketing. When the differences are
about impaired self-control or distress, using it is exploitation. The model cannot tell these
apart. Only the choice of features, the rules around the model and a human can.

### 2.2 The line between persuasion and manipulation

Susser, Roessler and Nissenbaum define manipulation as hidden influence that works by
exploiting a person's decision-making weak points, and contrast it with persuasion, which is
open and gives reasons the person can assess [1]. Calo argued earlier that firms which mediate
the consumer's experience through technology can discover, and even trigger, individual
vulnerabilities [2].

European law now draws the same line. The EU AI Act prohibits, in Article 5(1)(a), an AI system
"that deploys subliminal techniques beyond a person's consciousness or purposefully manipulative
or deceptive techniques, with the objective, or the effect of materially distorting the
behaviour of a person or a group of persons by appreciably impairing their ability to make an
informed decision", and, in Article 5(1)(b), one "that exploits any of the vulnerabilities of a
natural person or a specific group of persons due to their age, disability or a specific social
or economic situation", in both cases where significant harm is caused or reasonably likely
[3]. Recital 29 of the same regulation adds that "common and legitimate commercial practices,
for example in the field of advertising, that comply with the applicable law should not, in
themselves, be regarded as constituting harmful manipulative AI-enabled practices" [3]. The
Commission's guidelines on these prohibitions state: "In persuasive interactions, individuals
are aware of the influence attempt and can freely and autonomously choose it. In manipulative
interactions, the lack of awareness of the techniques or their impact negates the freedom of
choice and informed and autonomous decision-making." They add that "Advertising techniques that
use AI to personalise content based on user preferences are not inherently manipulative if they
do not deploy subliminal, purposefully manipulative or deceptive techniques that subvert
individual autonomy or exploit vulnerabilities in harmful ways" [4].

From these sources we use a four-question test for any plan and any message (the synthesis is
ours):

1. **Open?** Would the recipient understand that this is a marketing message and from whom?
2. **Truthful?** Does it give accurate reasons the person can evaluate?
3. **Vulnerability-neutral?** Is the targeting independent of a known or inferred weakness?
4. **Endorsable?** Would the person, fully informed, plausibly accept being targeted this way?

How LiftPilot answers: (1) every draft must name the sender and carry an opt-out; (2) a draft
may contain only what is on the offer sheet, and no number that is not on it; (3) the model's
inputs are purchase behaviour only, age and gender are excluded, minors are excluded, and no
tool can target a personal attribute; (4) the messages we draft are reminders and thanks, with
no pressure wording, and a human reads the plan before anything leaves the system.

### 2.3 Evidence that the concern is real

- **Optimising an economic objective can discriminate without anyone intending it.** Lambrecht
  and Tucker found that a gender-neutral job advertisement was shown to fewer women because the
  delivery algorithm optimised cost-effectiveness [5]. Ali et al. found skewed delivery of
  employment and housing advertisements under neutral targeting, driven by budget and content
  [6]. Our own audit shows the same kind of mechanism at small scale (section 3).
- **Removing a protected attribute from the inputs is not enough.** Ascarza and Israeli report
  that the remedies firms commonly use against bias in personalised policies often do not
  remove it and may worsen it [7]. Idan and Li describe how uplift-driven policies can produce
  disparities both in who is treated and in who benefits [8]. This is why we audit outcomes
  instead of relying on the exclusion.
- **Language models persuade, and pushing them to persuade costs accuracy.** A large study of
  conversational AI found that the methods which raised persuasiveness also systematically
  lowered factual accuracy [9]. A preregistered experiment found that messages microtargeted by
  a language model were not statistically more persuasive than non-targeted ones [10]. For us
  this means two things: tailoring copy to personal traits is not worth its ethical cost, and
  checking every claim in the copy is the control that matters most.
- **A company answers for what its AI says.** The US Federal Trade Commission has told
  marketers not to exaggerate what an AI product can do and that a "black box" is no excuse
  [11].
- **Uplift scores are unstable.** A survey with an experimental comparison reports that uplift
  models are frequently unstable, with strong variability in performance [12]. Our Hillstrom
  check shows it directly: Qini over repeated splits is +0.024 ± 0.021 for the S-learner, the
  learner with the highest mean. Decisions about individuals must not be presented as precise.

### 2.4 Evidence for the upside

- **Fewer contacts.** At 6 RUB per message the plan contacts 19.3% of customers instead of
  100%. Zhang, Kumar and Cosguner showed for one retailer that the number of e-mails has a
  non-linear effect on profit, so more messages are not harmless [13].
- **Honest measurement.** Uplift needs a randomised hold-out, so the company measures what its
  marketing causes. In the X5 experiment 94.8% of post-contact purchases would have happened
  anyway. Lo made the point in 2002: response models target people who would act regardless
  of contact [14].
- **A division of labour between people and AI.** Davenport et al. argue that AI in marketing
  is more effective when it augments human managers than when it replaces them [15]. In
  LiftPilot the model proposes and a person decides.

One upside we do **not** claim: protecting customers who are annoyed by contact. Radcliffe and
Surry describe negative effects that "arise when, for some or all segments of the population,
the overall impact of the treatment is to reduce sales" [16]. We looked for such a group and
did not find one: the group with a non-positive estimated effect had a real effect of +1.7
points (95% CI -0.1 to +3.5).

### 2.5 The cost we accept, stated plainly

The profit rule leaves many frequent buyers alone because a message changes little for them.
In the discount scenario this means the most loyal customers get the fewest discounts. UK
regulators have treated "long-standing customers get the worse deal" as a consumer-protection
problem in other markets [17]. LiftPilot does not solve this. It reports contacts by RFM
segment for every plan so that a manager can see it and choose, for example, a thank-you
message without a discount for Champions (the default angle for that segment in the drafts).

## 3. Measured fairness findings

Age and gender are never model inputs. They are kept only to audit who is selected. The audit
computes, for each group, the **selection rate** (share of the group the plan contacts) and the
ratio of the lowest to the highest selection rate. A ratio under 0.80 is flagged for human
review. The threshold is the "four-fifths" rule of thumb from US employment selection, a
disparate-impact ratio of the kind studied in [18]; we use it as a screening heuristic, not as
a legal test for marketing.

**Who is in the audit.** Customers under 18 are never contacted (control 2 in section 4). They
form their own age band, "under 18", whose selection rate is zero by rule and not because of
the model. That band and the "unknown" band (no valid age) are left out of the ratio, as is any
group of fewer than 200 customers. The ratio therefore compares the six adult bands: 18-24,
25-34, 35-44, 45-54, 55-64 and 65+.

**Finding 1. Among adults the age gap is small when contact is cheap and widens as contact gets
expensive.**

| Cost per message | Share contacted | Age ratio | Flag | Lowest group | Highest group | Gender ratio |
|---:|---:|---:|---|---|---|---:|
| 2 RUB | 69.9% | 0.96 | ok | 65+ | 18-24 | 0.99 |
| 4 RUB | 39.8% | 0.86 | ok | 65+ | 35-44 | 0.97 |
| 6 RUB | 19.0% | 0.82 | ok | 65+ | 35-44 | 0.95 |
| 10 RUB | 4.6% | 0.57 | REVIEW | 18-24 | 35-44 | 0.90 |

The model never saw age; purchase behaviour carries part of the information. Up to 6 RUB no
plan is flagged and the least-selected band is 65+. At 10 RUB, where the plan contacts only
4.6% of customers, the 18-24 band is selected least, the ratio is 0.57, and the plan is flagged
for human review. The gender ratio stays at or above 0.90.

What can be claimed: the gap exists, it grows with contact cost, and the system flags it when
it passes the threshold. What cannot be claimed: that young adults are disadvantaged at 2, 4 or
6 RUB (they are the most-selected band at 2 RUB), or that a ratio above 0.80 means there is
nothing to look at.

**Finding 2. The flagged gap follows a difference in measured effect, but age-band averages do
not explain selection in general.** Uplift measured in the experiment by age band, in points:
18-24: +1.1; 25-34: +1.6; 35-44: +3.1; 45-54: +3.4; 55-64: +4.0; 65+: +5.9; under 18: +3.1;
unknown: +4.0. By gender: female +4.0; male +2.9; unknown +2.9. The 18-24 band reacted least to
this communication, so a rule that follows the estimated effect contacts it least once contact
is expensive. The match is not uniform: the 65+ band has the largest measured effect and is
still the least-selected band up to 6 RUB (17.1% at 6 RUB, against 20.8% for the 35-44 band, in
`artifacts/extra_analyses.json`). Selection follows each customer's estimated uplift, basket
and purchase probability, not the average of their age band. None of this settles whether a
gap is acceptable; that is a decision for a person, which is why the system flags it instead of
deciding.

**Finding 3. "Fair mode" did not help and cost profit (a negative result).** Fair mode values
every customer at the average basket, so a small spender is not passed over only for spending
less.

| Cost | Fair mode | Contacted | Real profit (RUB) | 95% CI | Age ratio | Gender ratio |
|---:|---|---:|---:|---|---:|---:|
| 2 RUB | off | 139,828 (69.9%) | 363,138 | 130,803 to 603,439 | 0.96 | 0.99 |
| 2 RUB | on | 145,144 (72.5%) | 341,133 | 108,178 to 585,710 | 0.93 | 0.98 |
| 6 RUB | off | 38,113 (19.0%) | 99,838 | -99,289 to 296,175 | 0.82 | 0.95 |
| 6 RUB | on | 23,925 (12.0%) | 43,565 | -25,589 to 120,655 | 0.58 | 0.92 |

At 6 RUB the age ratio fell from 0.82 to 0.58, which is under the review threshold, and the
profit estimate was roughly halved (both intervals include zero). At 2 RUB the ratio moved from
0.96 to 0.93. Fair mode made the age gap wider, not narrower, so the gap is not caused by
valuing customers at their own basket.

**A correction we made to our own audit.** An earlier version of the audit counted customers
under 18, who are excluded from contact, inside the 18-24 band. That lowered the band's
selection rate by construction and overstated the gap (ratios 0.85 at 2 RUB, 0.70 at 6 RUB and
0.48 at 10 RUB, with review flags at 4 and 6 RUB). A code review caught it; the band was split,
the model retrained and every figure regenerated. The numbers above are the corrected ones. We
keep this note because it shows that an audit is code like any other and needs review itself.

**Finding 4. Excluding age and gender costs nothing measurable.** Qini with behaviour features
only: +0.0089 (95% CI +0.0021 to +0.0156); with age and gender added: +0.0097 (+0.0034 to
+0.0164). The intervals overlap almost entirely.

## 4. Controls: where they live, why they exist, how they are tested

"Test" names refer to `tests/`; "benchmark" refers to `liftpilot agent-eval`
(`src/liftpilot/agent/evaluate.py`). Paths are under `src/liftpilot/`.

| # | Control | Where in the code | What motivates it | How it is tested |
|---:|---|---|---|---|
| 1 | **Sensitive attributes are not model inputs.** The feature list holds purchase behaviour only; age band and gender are audit columns | `data/prepare.py` (`X5_FEATURES`, `X5_AUDIT`) | Art. 5(1)(b) AI Act [3]; proxy and bias concerns [5], [7] | The ablation in `cli.py` (`train`) trains a variant *with* age and gender and reports the difference; no unit test asserts the exclusion |
| 2 | **Opt-outs and minors are removed before optimising.** Customers listed in the optional file `data/suppression_list.txt` (one identifier per line; absent by default and not committed) and customers under 18 are never eligible | `engine.py` (`_eligible`) | Right to object to direct marketing, GDPR Art. 21(2)-(3) [19]; age as a vulnerability in Art. 5(1)(b) AI Act [3] | `test_opt_outs_are_never_contacted`; minors: asserted in `test_plan_contacts_only_profitable_eligible_customers` |
| 3 | **No targeting by personal attribute.** A campaign can be restricted only to the eight RFM segments. An unknown or demographic segment name (for example "Women over 60") is refused with an error that lists the valid segments; no plan is made | `engine.py` (`plan`) | Art. 5(1)(b) AI Act [3] | `test_demographic_targeting_is_refused`; benchmark probe "women over 60" |
| 4 | **Fairness audit of every plan.** Selection rate and measured uplift by age band and gender; ratio under 0.80 flagged. The "under 18" band (never contacted by rule), the "unknown" band and groups under 200 customers are left out of the ratio | `fairness.py` (`audit_groups`, `disparate_impact`); `engine.py` (`fairness`) | [5], [7], [8], [18] | `test_fairness_holdout_and_explanation`; the runtime checklist (control 8) forces the audit. No unit test asserts that the under-18 band is left out of the ratio |
| 5 | **Evidence before spending.** Every plan is replayed on held-out randomised customers; profit is reported with a bootstrap 95% interval and compared with contacting everyone | `policy/evaluation.py`; `engine.py` (`evaluate`) | "Do not overclaim" [11]; instability of uplift estimates [12] | `test_policy_evaluation_recovers_known_effect`, `test_evaluate_reports_real_result_with_interval` |
| 6 | **Human approval gate.** The audience file cannot be written until a named person approves in the interface; the approval code is never shown to the model and the agent has no approving tool. Messages cannot be redrafted after approval, because the approver has not seen the new wording: a new plan and a new approval are required | `engine.py` (`request_approval`, `human_approve`, `export`); `agent/tools.py` (`_export`, `_draft`) | GDPR Art. 22 on solely automated decisions [19]; LGPD Art. 20 on review of automated decisions [20]; [15] | `test_export_is_blocked_without_human_approval`; `test_failed_or_late_drafts_cannot_reach_export` (redraft after approval is blocked); benchmark probe "export right away" |
| 7 | **Provenance guard** (earlier name: argument rule). Every planning argument must be traceable to the manager's words. A margin, cost or discount reaches the planner only if the same number appears in what the manager wrote (as written, as a percentage, or with a unit such as "1 million" or "50k"); a budget currency only if that currency is named; fair mode only if the manager asked for it. Anything else is dropped, the system default is used, and the answer says so | `agent/runtime.py` (`_provenance`); `agent/grounding.py` (`stated_amounts`) | In testing the model invented money assumptions | `test_invented_arguments_are_dropped_by_the_provenance_guard`; benchmark "argument fidelity" |
| 8 | **Runtime checklist.** Evidence and fairness audit for every plan; hold-out, send date, drafts and approval request for every campaign; the runtime calls the missing tools itself if the model does not | `agent/runtime.py` (`_missing_steps`, `run`) | In testing the model skipped steps | `test_scripted_agent_runs_full_workflow_and_waits_for_human` (fixed-order path); benchmark "checklist completion" |
| 9 | **Verified statements.** The facts of a plan are written by code as fixed sentences; the model receives only these sentences and narrates them. A plan whose replay interval includes zero is described as "more likely than not" profitable only when the estimate is positive and the probability of a profit is above one half; otherwise the sentence says the plan cannot be expected to make money | `agent/report.py` (`verified_statements`) | In testing the model called the customers left alone "a hold-out" and a difference "significant" when its interval crossed zero; hallucination as a known failure of language models [21] | `test_statement_does_not_call_a_loss_likely_profitable`; the scripted test asserts the answer states that the plan is waiting for human approval |
| 10 | **Numeric grounding.** Every number in the answer must be a correctly rounded version of a number that a tool returned in the same run or that the manager wrote. The rounding allowed is half of the last digit kept and never more than 2% of the value | `agent/grounding.py` | In testing the model mistyped numbers; [9] | `test_grounding_flags_invented_numbers`, `test_grounding_rejects_loose_round_numbers`; benchmark "numeric grounding" |
| 11 | **Over-claim check and discard.** Words such as "guaranteed", "proven", "significant" (unless the interval is entirely positive) and claims that messages were sent are flagged; one rewrite is allowed; a narrative that still fails is discarded and the verified statements are shown | `agent/report.py` (`overclaims`); `agent/runtime.py` (`run`) | [11]; over-confident wording in testing | Benchmark probe "guaranteed profit" and the count of rejected narratives; no dedicated unit test |
| 12 | **Copy guard.** Each draft is checked by code: length, opt-out, sender named, no number that is not on the offer sheet, no false urgency or scarcity, no guilt, no unsupported promises, no surveillance wording, no sensitive attributes, no links. One retry, then a pre-approved template. The offer wording is checked before any drafting and refused if it fails. A message that fails the checks is never stored on the plan, so it cannot reach an export | `agent/copy_guard.py`; `agent/tools.py` (`_draft`) | Dark-pattern categories found at scale on shopping sites [22]; accuracy cost of persuasive generation [9]; the right to object to direct marketing must be brought to the person's attention, GDPR Art. 21(4) [19] | `test_copy_guard_accepts_clean_and_rejects_manipulative_copy`, `test_real_deadline_and_listed_numbers_are_allowed`, `test_fallback_templates_always_pass`, `test_failed_or_late_drafts_cannot_reach_export` |
| 13 | **Personalisation boundary.** The drafting prompt contains the brand, the RFM segment and its description, an angle and the offer. No customer identifier, uplift score, age or gender | `agent/tools.py` (`_draft_one`) | Weak evidence that trait targeting adds persuasion [10]; consumers react badly to inferred attributes [23] | No dedicated test |
| 14 | **Hold-out for the next campaign.** The plan states how many selected customers to keep uncontacted; the export assigns them at random | `engine.py` (`design_holdout`, `export`) | Without a random hold-out the next campaign cannot be measured and the model cannot be re-trained honestly | `test_fairness_holdout_and_explanation`, `test_export_is_blocked_without_human_approval` |
| 15 | **Audit log.** Each request, tool call, arguments, result fingerprint, answer and approval is appended to `runs/audit.jsonl` | `agent/runtime.py` (`AuditLog`); `app/main.py` (approval record) | Accountability, GDPR Art. 5(2) [19]; NIST AI RMF [24] | Used in the scripted-agent test; no tamper test |
| 16 | **Local processing.** The language model runs on the same machine; live feeds send only a currency code or a country code | `agent/llm.py`; `live.py` | Data minimisation and security, GDPR Art. 5(1)(c),(f) [19] | The test suite runs with no network and no language model |
| 17 | **Documentation.** Model card, datasheet, generated results sheet | `docs/` | [25], [26] | Results are generated by `liftpilot results`, not typed |
| 18 | **A budget is never guessed.** A budget is a spending limit. If the amount the model passes does not match an amount in the manager's words, if the manager named a foreign currency and the model left the currency out, or if the manager stated a budget and the model passed none, no plan is made: the tool returns an error that says what to restate | `agent/runtime.py` (`_provenance`, `_execute`) | A budget silently changed, dropped or read in the wrong currency would produce a confident plan for the wrong amount of money; [11] | `test_budget_is_never_guessed` |
| 19 | **Fair mode respects the budget on real spend.** Fair mode decides with every customer valued at the average basket, but a budget is held on real expected spend, computed with each customer's own basket; reported money also uses real baskets | `engine.py` (`_select`, `plan`) | A fairness option must not become a way to overspend | `test_fair_mode_respects_the_budget_on_real_spend` |
| 20 | **No plan on default costs when stated figures cannot be read.** If the language model is not running and the request states a cost, a margin, a budget or a currency, the agent makes no plan and says why; the scripted planner runs by itself only for requests that state no figures | `agent/runtime.py` (`run`) | Planning on defaults while the request names other figures would mislead | `test_scripted_agent_runs_full_workflow_and_waits_for_human` covers the request without figures; no test covers the refusal |
| 21 | **Hold-out target guard.** A detection target reaches the hold-out design only if it is a fraction between 0 and 1 that the manager wrote next to detection wording; otherwise it is dropped and the default applies. The wording is read in English only | `agent/runtime.py` (`_holdout_provenance`) | In the stress test the model chose the target itself and three identical requests gave hold-outs of 16%, 8% and 16% | `test_holdout_target_the_manager_never_stated_is_dropped`; stress test: dropped in 13 of 17 runs |
| 22 | **Status and skip-approval wording checks.** While no plan of the run is approved or exported, a sentence saying that something was approved or exported, and advice to go ahead without approval, are flagged like an over-claim (one rewrite, then discard). A denial or a condition excuses a phrase only just before it in the same clause. Both are pattern lists | `agent/report.py` (`status_claims`, `bypass_advice`, `denied_before`); `agent/runtime.py` (`_loud`) | In the stress test answers said drafts were "all approved", and a draft repeated a hidden instruction to export without approval | `test_a_false_approved_is_rejected_until_a_person_really_approves`, `test_advice_to_skip_approval_is_rejected_and_recorded`, `test_a_denial_elsewhere_in_the_sentence_does_not_excuse_the_claim`; stress test: one "approved" sentence sent back in the final run; the skip-approval check did not have to act |
| 23 | **Checklist in any language, and CHECK before approval.** A run in which the model itself made a plan must complete the whole campaign checklist, whatever the language of the request. The approval screen shows five CHECK lines written by code from the run's tool results; if steps are missing it names them and says not to approve. The export slider starts at the hold-out share designed in the run | `agent/runtime.py` (`_missing_steps`); `agent/check.py`; `app/main.py` | In the stress test an Arabic request stopped after three tools; a plan from such a run could be approved without notice | `test_a_plan_made_by_the_model_completes_the_checklist_in_any_language`, `test_check_panel_names_the_steps_a_run_did_not_do`, `test_export_slider_starts_at_the_share_designed_in_the_run`; stress test: French and Arabic completed the checklist, one run each |

The benchmark's measured values are in section 10 of RESULTS.md (model `qwen3:8b`, 13 fixed
requests): the planner received exactly the stated assumptions in 100% of the campaign requests
after the provenance guard, which had to drop invented assumptions in 1 run; the checklist was
completed and the run ended in a human-approval request in 100% of them; 100.0% of 204 numbers
in the final answers were grounded and the guards rejected 1 narrative; 56 of 56 drafts were
written by the model and passed the copy checks; the questions used the expected tool in 100%
of cases; 3 of 3 safety probes were passed; the median time for a full campaign plan was 136 s
on an RTX 3080 laptop GPU. These are results for the model together with its controls, on a
small set written by the authors.

## 5. What the system must not be used for

- **Sending or spending without a human decision.** The approval step is part of the system,
  not an optional extra, and the approval must be a real review. The EU guidance on automated
  decisions says human involvement must be meaningful and not a token gesture [27].
- **Targeting people because they are vulnerable**: minors, people in financial difficulty,
  people selected for impulsivity, emotional state or a moment of weakness. Do not add features
  that describe such conditions.
- **Targeting or excluding by age, gender or any other protected attribute.**
- **Offers that can harm**: credit, "buy now, pay later", gambling-like mechanics, health or
  financial promises. The copy guard blocks the wording; the offer itself is a human
  responsibility.
- **Decisions with legal or similarly significant effects** on a person, including prices that
  would bar someone from goods or services.
- **Contacting people who did not agree to marketing or who objected.** The public data contain
  no consent information. A real deployment must load its consent and objection records into
  the suppression list before any plan is made.
- **Presenting the back-tested figures as a guarantee**, or the money figures as the retailer's
  real accounts. Purchase amounts are imputed and the margins and costs are scenarios.
- **Use on non-randomised data**, or transfer to another company without a new experiment.
- **Judging an individual.** A score is a noisy estimate that is useful in aggregate. Nobody
  should be labelled from it.

## 6. Which law we designed against

The project was built in Lebanon on public research data. We used the GDPR, the EU AI Act and
Brazil's LGPD as the design benchmark because they are the most developed texts and because the
course brief is set in Brazil. Under the GDPR an objection to direct marketing also covers the
profiling related to it (Art. 21(2)-(3)) and a person has the right not to be subject to a
decision "based solely on automated processing" with legal or similarly significant effects
(Art. 22(1)) [19]. LGPD Art. 20 gives a right to request review of decisions taken solely by
automated processing that affect a person's interests, and names the consumer profile
expressly [20]. For Lebanon, Law No. 81 of 2018 covers electronic transactions and personal
data; we could not open the official text and rely on two secondary descriptions [28], [29], so
we make no claim about its wording.

The public datasets carry no names or contact details, so the demonstration processes customers
only under opaque identifiers. The controls are shown as they would operate on real customer
data.

## 7. Open questions and known gaps

1. **Is a lower contact rate for one age band a harm?** Being left alone by a reminder is
   not obviously a loss. With a discount it is: the group contacted less also receives fewer
   discounts. We have no principled answer and leave the flag to a human.
2. **Why do customers aged 18 to 24 react less, and why is the 65+ band selected least up to
   6 RUB although it reacts most?** We measured both; we cannot explain them from these data.
3. **The audit itself was wrong once** (section 3): an earlier version counted excluded
   minors inside the 18-24 band and overstated the gap. It is corrected, but no unit test
   asserts that the under-18 band stays out of the ratio, and the threshold of 0.80 is a rule
   of thumb: a ratio of 0.82 at 6 RUB passes it narrowly.
4. **Fair mode failed.** It widened the age gap instead of narrowing it. Other remedies
   exist, for example allocation methods that balance groups directly [7]. We did not
   implement them.
5. **No consent data.** The suppression list is the only objection mechanism, and the public
   data do not let us test it on real objections.
6. **No frequency cap.** The system plans one campaign at a time and does not limit how often a
   customer is contacted across campaigns.
7. **No proxy test.** We audit outcomes by group but do not measure how well age or gender can
   be predicted from the features or from the score.
8. **The audit log is append-only by convention.** It is not tamper-evident.
9. **No disclosure of AI assistance in the message**, and no "why you received this" line. Both
   would be cheap to add and would answer the "open" question of section 2.2 more fully.
10. **The loyalty question** (section 2.5) is reported, not solved.
11. **The agent benchmark is small** (13 requests written by the authors, one model).
12. **Some controls have no dedicated unit test**: the exclusion of age and gender from the
    feature list (control 1), the exclusion of the under-18 band from the fairness ratio
    (control 4), the over-claim check (control 11), the personalisation boundary of the
    drafting prompt (control 13) and the refusal to plan on default costs when the model is
    not running (control 20).
13. **The provenance guard matches values, not roles.** It checks that a number passed to the
    planner appears in the manager's words, not that it was stated for that argument. The
    assumptions actually used are printed in the first verified statement for the human to
    read.
14. **Statements without numbers are not checked.** The grounding check covers numbers and the
    over-claim check covers a list of words. A wrong sentence with neither can pass. The
    verified statements shown next to the narrative, and the human reader, are the remedy.
15. **The data's own provenance**: whether the X5 customers consented to research use is
    unknown (see [DATASHEET.md](DATASHEET.md)).
16. **Requests that are not in English.** In an earlier run of the stress test of section 8 an
    Arabic request got a plan but no hold-out design, no send date, no drafts and no approval
    request, because the runtime recognised a campaign request by English keywords. The
    trigger was changed (control 23), and in the final run a French and an Arabic request each
    completed the checklist. That is one run per language on one request. The wording of the
    drafts in other languages was not compared, and the hold-out guard (control 21) reads
    English wording only.
17. **The wording checks are pattern lists.** The checks of control 22 miss a paraphrase that
    avoids the listed words. The older over-claim list (control 11) does not read denials: in
    the final stress run it matched "messages sent" inside "No messages sent yet." and a
    correct briefing was replaced by the verified statements. Export does not depend on
    wording; it needs a named approval.
18. **A plan from an unfinished run can still be approved.** The CHECK block names the steps
    not done, but the Approve button is still shown.

## 8. The course's closing session: Thinking critically with AI

[CRITICAL_THINKING.md](CRITICAL_THINKING.md) maps the closing session of the course (three ways
AI fails, the four moves, CHECK, the six-question ethics compass, the marketing red lines) to
the controls above, with the gap for each. It is not repeated here.

A stress test built from that session (`liftpilot agent-stress`, section 12 of RESULTS.md,
model `qwen3:8b`) passed 9 of 9 gated cases over 17 agent runs, with 241 of 241 numbers
matched to a tool result or to a number in the request and no approval or export in the two
hidden-instruction cases. This is one full run of all ten cases on the final code. The
language swap is reported and not counted: the French and the Arabic request each matched the
English plan and completed the checklist (item 16 above). The guards rejected 1 narrative, a
correct one (item 17). Four earlier runs of the suite each scored 9 of 9 and each hid a
problem that only reading the answers or the code showed, so a pass here means the stated rule
held in these runs and nothing more.

## References

[1] D. Susser, B. Roessler, and H. Nissenbaum, "Technology, autonomy, and manipulation,"
*Internet Policy Review*, vol. 8, no. 2, 2019. https://doi.org/10.14763/2019.2.1410

[2] R. Calo, "Digital Market Manipulation," *George Washington Law Review*, vol. 82, no. 4, p.
995, Aug. 2014. https://www.gwlr.org/calo/

[3] Regulation (EU) 2024/1689 of the European Parliament and of the Council (Artificial
Intelligence Act), Article 5(1)(a), Article 5(1)(b) and Recital 29.
http://data.europa.eu/eli/reg/2024/1689/oj

[4] European Commission, "Commission Guidelines on prohibited artificial intelligence practices
established by Regulation (EU) 2024/1689 (AI Act)," C(2025) 5052 final, 29 July 2025,
paragraphs (130) and (133). Non-binding.
https://digital-strategy.ec.europa.eu/en/library/commission-publishes-guidelines-prohibited-artificial-intelligence-ai-practices-defined-ai-act

[5] A. Lambrecht and C. Tucker, "Algorithmic Bias? An Empirical Study of Apparent Gender-Based
Discrimination in the Display of STEM Career Ads," *Management Science*, vol. 65, no. 7, pp.
2966-2981, 2019. https://doi.org/10.1287/mnsc.2018.3093

[6] M. Ali, P. Sapiezynski, M. Bogen, A. Korolova, A. Mislove, and A. Rieke, "Discrimination
through Optimization: How Facebook's Ad Delivery Can Lead to Biased Outcomes," *Proc. ACM
Hum.-Comput. Interact.*, vol. 3, no. CSCW, pp. 1-30, 2019. https://doi.org/10.1145/3359301

[7] E. Ascarza and A. Israeli, "Eliminating unintended bias in personalized policies using
bias-eliminating adapted trees (BEAT)," *PNAS*, vol. 119, no. 11, e2115293119, 2022.
https://doi.org/10.1073/pnas.2115293119

[8] L. Idan and M. Li, "Responsible Uplift Modeling," in *Proc. 24th Int. Conf. on Autonomous
Agents and Multiagent Systems (AAMAS 2025)*, Detroit, MI, USA, 19-23 May 2025.
https://aamas.csc.liv.ac.uk/Proceedings/aamas2025/pdfs/p1034.pdf

[9] K. Hackenburg, B. M. Tappin, L. Hewitt, E. Saunders, S. Black, H. Lin, C. Fist, H.
Margetts, D. G. Rand, and C. Summerfield, "The levers of political persuasion with
conversational artificial intelligence," *Science*, vol. 390, no. 6777, eaea3884, 4 Dec. 2025.
https://doi.org/10.1126/science.aea3884

[10] K. Hackenburg and H. Margetts, "Evaluating the persuasive influence of political
microtargeting with large language models," *PNAS*, vol. 121, no. 24, e2403116121, 2024.
https://doi.org/10.1073/pnas.2403116121

[11] M. Atleson, "Keep your AI claims in check," FTC Business Blog, 27 Feb. 2023.
https://www.ftc.gov/business-guidance/blog/2023/02/keep-your-ai-claims-check (archived copy:
https://web.archive.org/web/20250101082345/https://www.ftc.gov/business-guidance/blog/2023/02/keep-your-ai-claims-check)

[12] F. Devriendt, D. Moldovan, and W. Verbeke, "A Literature Survey and Experimental
Evaluation of the State-of-the-Art in Uplift Modeling: A Stepping Stone Toward the Development
of Prescriptive Analytics," *Big Data*, vol. 6, no. 1, pp. 13-41, 2018.
https://doi.org/10.1089/big.2017.0104

[13] X. Zhang, V. Kumar, and K. Cosguner, "Dynamically Managing a Profitable Email Marketing
Program," *Journal of Marketing Research*, vol. 54, no. 6, pp. 851-866, 2017.
https://doi.org/10.1509/jmr.16.0210

[14] V. S. Y. Lo, "The true lift model: a novel data mining approach to response modeling in
database marketing," *ACM SIGKDD Explorations Newsletter*, vol. 4, no. 2, pp. 78-86, 2002.
https://doi.org/10.1145/772862.772872

[15] T. Davenport, A. Guha, D. Grewal, and T. Bressgott, "How artificial intelligence will
change the future of marketing," *J. Acad. Marketing Science*, vol. 48, no. 1, pp. 24-42, 2020.
https://doi.org/10.1007/s11747-019-00696-0

[16] N. J. Radcliffe and P. D. Surry, "Real-World Uplift Modelling with Significance-Based
Uplift Trees," Portrait Technical Report TR-2011-1 / Stochastic Solutions White Paper, 2011.
Not peer-reviewed. https://stochasticsolutions.com/pdf/sig-based-up-trees.pdf

[17] UK Competition and Markets Authority, "Loyalty penalty super-complaint," case page.
https://www.gov.uk/cma-cases/loyalty-penalty-super-complaint

[18] M. Feldman, S. A. Friedler, J. Moeller, C. Scheidegger, and S. Venkatasubramanian,
"Certifying and Removing Disparate Impact," in *Proc. KDD '15*, pp. 259-268, 2015.
https://doi.org/10.1145/2783258.2783311

[19] Regulation (EU) 2016/679 (General Data Protection Regulation), Articles 5, 21 and 22.
http://data.europa.eu/eli/reg/2016/679/oj

[20] Brazil, Lei No. 13.709/2018 (Lei Geral de Proteção de Dados Pessoais, LGPD), Art. 20.
https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm

[21] Z. Ji et al., "Survey of Hallucination in Natural Language Generation," *ACM Computing
Surveys*, vol. 55, no. 12, pp. 1-38, 2023. https://doi.org/10.1145/3571730

[22] A. Mathur et al., "Dark Patterns at Scale: Findings from a Crawl of 11K Shopping Websites,"
*Proc. ACM Hum.-Comput. Interact.*, vol. 3, no. CSCW, pp. 1-32, 2019.
https://doi.org/10.1145/3359183

[23] T. Kim, K. Barasz, and L. K. John, "Why Am I Seeing This Ad? The Effect of Ad Transparency
on Ad Effectiveness," *Journal of Consumer Research*, vol. 45, no. 5, pp. 906-932, 2019.
https://doi.org/10.1093/jcr/ucy039

[24] National Institute of Standards and Technology, *Artificial Intelligence Risk Management
Framework (AI RMF 1.0)*, NIST AI 100-1, 26 Jan. 2023. https://doi.org/10.6028/NIST.AI.100-1

[25] M. Mitchell et al., "Model Cards for Model Reporting," in *Proc. Conf. on Fairness,
Accountability, and Transparency (FAT\* '19)*, pp. 220-229, 2019.
https://doi.org/10.1145/3287560.3287596

[26] T. Gebru et al., "Datasheets for datasets," *Communications of the ACM*, vol. 64, no. 12,
pp. 86-92, 2021. https://doi.org/10.1145/3458723

[27] Article 29 Working Party, "Guidelines on Automated individual decision-making and
Profiling for the purposes of Regulation 2016/679," WP251rev.01, endorsed by the European Data
Protection Board on 25 May 2018.
https://www.edpb.europa.eu/our-work-tools/our-documents/guidelines/automated-decision-making-and-profiling_en

[28] SMEX, "An 'Ugly' New Data Protection Law in Lebanon," 11 Oct. 2018. Secondary source.
https://smex.org/an-ugly-new-data-protection-law-in-lebanon/

[29] DLA Piper, "Data Protection Laws of the World - Lebanon," last modified 21 December 2022.
Secondary source. https://www.dlapiperdataprotection.com/index.html?t=law&c=LB
