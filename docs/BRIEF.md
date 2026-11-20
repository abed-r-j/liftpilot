# LiftPilot: authoring brief (single source of truth for every document)

Read this file, then `docs/RESULTS.md` (generated numbers) before writing anything.

## What the project is

Course project, "AI in Business and Marketing", Saint Joseph University of Beirut (USJ),
instructor Dr. Katia Raya. Group 10: **Abed El Rahmane Jaafir** and **Ghandi Mahdmoud**.
Official topic: *AI-Powered Marketing Campaign Optimizer: Using Uplift Modeling & AI to Maximize
Incremental Profit*. Presented on campus on 25 November 2026 by Abed alone, 15 minutes including
a live demo. Judging criteria: Technical, Ethics, Communication, Concept, Metrics, AI integration.
Audience: computer-engineering students and a marketing-and-AI instructor. English only.

**LiftPilot** is an AI campaign agent that spends marketing budget only where it changes customer
behaviour. One-line pitch: *"Most marketing AI finds people who will buy. LiftPilot finds people
who will buy BECAUSE you contacted them, proves it on a real experiment, and asks a human before
anything is sent."*

## The story, in the order the evidence supports it

1. **Problem.** A real grocery chain (X5, 400,162 loyalty customers, 45.8 M receipt lines) sent a
   communication at random to half of 200,039 customers. 63.65% of contacted customers bought;
   60.33% of held-out customers bought anyway. The campaign caused +3.32 points. About 95 of every
   100 "campaign purchases" would have happened without it. Dashboards and platform ROAS count all of them.
2. **RFM shows who is persuadable.** Computed from raw receipts. Champions buy 88% of the time
   with no message and gain +1.2 points; Hibernating and New customers gain +4.6 and +5.6.
   "Reward your best customers" wastes budget. The more often a customer already buys, the less a message adds.
3. **A likely-buyer (response) model is the wrong tool.** Its Qini is negative: ranking by
   purchase probability is no better than random at finding persuadable customers. Uplift learners
   (S, T, X, DR, class transformation, ensemble; gradient-boosted trees) have a small but
   significant Qini, and their top decile reacts about three times the average.
4. **Profit rule.** Contact customer i only if `margin x basket_i x uplift_i > message cost +
   discount x basket_i x P(buy | contacted)_i`. Break-even uplift = (c + d V p1) / (m V).
   Uplift scores are calibrated (isotonic regression on a separate split) before the rule is applied.
5. **Evidence by replay.** Because contact was random, any targeting rule can be evaluated on
   held-out customers without running it (self-normalised inverse-propensity estimator, bootstrap 95% intervals).
6. **Honest headline.** Targeting is worth what contact costs. At 2 RUB per message, contacting
   almost everyone is right and LiftPilot matches it with about 30% less spend (difference not
   significant). At 6 RUB, or with a 3% discount, contacting everyone loses money while LiftPilot
   stays around break-even to positive, and the difference versus contacting everyone IS significant.
   LiftPilot's own profit interval crosses zero in the costly scenarios: say so.
7. **The agent.** A local 8B language model (Qwen3 through Ollama, on the laptop GPU, no cloud,
   0 USD) drives 16 tools. It is a utility-based agent (course taxonomy: "where the next 100 goes").
   Design lessons from testing, each now a control: the model invented arguments -> strict
   argument rule and validation; it skipped steps -> a runtime checklist forces evidence, fairness
   audit and an approval request for every plan; it misdescribed figures -> facts are written by
   code as "verified statements" and the model only narrates them; it mistyped numbers -> numeric
   grounding check; over-confident wording -> over-claim check; if the narrative still fails, it is
   discarded and the verified statements are shown. Copy is drafted per RFM segment and checked by
   code (length, opt-out, no invented numbers, no pressure tactics, no sensitive attributes).
   Export of the audience file is impossible until a human approves; the agent cannot approve itself.
8. **Live data with a real job.** Exchange rates (Frankfurter) convert a budget stated in another
   currency (the course brief's R$ 1 million) into the data's currency; a public-holiday calendar
   (Nager.Date) sets the send date and measurement window. Both are cached for offline use. Live
   feeds never change the uplift scores.
9. **Ethics, measured.** Age and gender are never model inputs. Minors are never contacted (rule)
   and are kept out of the audit. Among adults the fairness audit finds a small age gap at low cost
   that widens as contact gets expensive: lowest-to-highest selection ratio 0.96 at 2 RUB, 0.86 at
   4 RUB, 0.82 at 6 RUB (none flagged) and 0.57 at 10 RUB, where 18-24 year-olds are selected least
   and the plan is flagged for human review. The gap follows a real difference in measured effect
   (+1.1 points for 18-24 versus +5.9 for 65+). A "fair mode" (value every customer at the average
   basket) did not help: at 6 RUB it lowered the ratio to 0.58 and roughly halved profit. Reported
   as a negative result. An earlier version of the audit counted excluded minors inside the 18-24
   band and overstated the gap (0.85 / 0.70 / 0.48); a code review caught it. Say this if asked: it
   is a good example of why the audit itself needs review.
   Agent benchmark (final code): see section 10 of RESULTS.md. A full plan takes about 50 seconds
   on a cool laptop and two minutes or more when the GPU is hot or shared (benchmark median 136 s).
10. **External check.** On the Hillstrom e-mail test (64,000 customers, real spend in USD) the
    effect is nearly uniform across customers, uplift rankings are unstable, and the right answer
    is all-or-nothing; the profit rule finds the switch (send to all at 0.10 USD, to nobody at
    0.60 USD) but loses to "send to all" in the discount scenario (not significant). Targeting
    only helps where effects really differ between customers.
11. **The R$ 1 million "AI consultant" question.** The honest answer the system gives: at 6 RUB
    per message the profitable campaign needs only about 230 thousand RUB of the 14 million RUB
    budget. The first job of the AI is to say how much NOT to spend.

## Rules for every document

- Every number must come from `docs/RESULTS.md` (or be a trivial restatement of one). Never
  round in a way that changes meaning; always give the 95% interval next to a profit figure.
- Never claim: that the X5 channel was SMS (the source says only "a communication" / "send a text
  to the client"), that the currency is certainly RUB (presumed), that post-campaign purchase
  amounts are observed (they are imputed with each customer's average basket), that "sleeping
  dogs" (negative effect) were found (the group with non-positive estimated effect had a real
  effect of +1.7 points, interval -0.1 to +3.5), that results are guaranteed, or that this is the
  first system of its kind (say "to our knowledge" at most).
- Money assumptions (25% gross margin, 2 / 6 RUB per contact, 3% discount) are scenario
  assumptions, not facts about X5. Say so.
- The brand in sample messages, "FreshMart", is fictional.
- Lifetime value figures are capped at a 36-month horizon and rest on a three-month window.
- References: use only entries marked `[verified: ...]` in the research files
  (`C:\Users\abedr\AppData\Local\Temp\claude\9bd729568ee9ca7b\bf62ae74-a7fc-4e23-9e0e-7060b62a5983\scratchpad\research\01_literature.md`,
  `...\03_ethics.md`, `...\02_data.md`). Copy citation data exactly. Do not cite anything else.
  Radcliffe & Surry (2011) does NOT contain the four customer-type names; do not attribute them to it.
- Plain, direct English. No hype words, no em dashes, no "revolutionary". Define a term once.
- Honest limits belong in the text, not in a footnote.

## Differentiation from the other groups (for the Concept criterion)

Other groups cover: causal measurement of promotion effectiveness (PromoGuard), churn
prediction with RFM and profit-based recommendations, personalised retail marketing, customer
intelligence dashboards, cold outreach, market intelligence, synthetic customer panels.
LiftPilot differs on four points: (1) it decides who NOT to contact, per customer, with a
calibrated profit rule; (2) every plan is proven by replay on a real randomised experiment with
intervals, before spending; (3) the agent is fenced: numbers only from tools, facts written by
code, human approval gate, audit log, all measured in an agent benchmark; (4) it reports where it
does not help (cheap contact, uniform effects, fair mode).

## Where things are

- Code: `src/liftpilot/` (see module docstrings). CLI: `liftpilot download | train | results | agent | agent-eval | app`.
- Numbers: `docs/RESULTS.md`, `artifacts/x5/report.json`, `artifacts/extra_analyses.json`, `artifacts/agent_eval.json`.
- Figures (PNG and PDF): `docs/figures/` (fig_architecture, fig_rfm_segments, fig_qini,
  fig_deciles, fig_calibration, fig_scenarios, fig_scenarios_hillstrom, fig_fairness_age, fig_gantt).
- Environment: Windows 11, PowerShell (not Bash), run Python as `.\.venv\Scripts\python.exe`;
  write scripts to files rather than `python -c`. PowerPoint and Chrome are installed. No LaTeX:
  the paper is built with the `typst` Python package (`typst.compile(src, output=pdf)`), which
  also renders PNG pages (`format="png"`, output `page-{n}.png`) for visual checks.
- Do not commit, do not push, do not touch files outside the repository except your own scratch files.
