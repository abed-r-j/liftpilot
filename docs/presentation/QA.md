# LiftPilot: 25 likely questions, with answers

Every figure below is in `docs/RESULTS.md`. "Points" means percentage points. Money is in the
dataset's currency, presumed to be roubles (RUB). Costs of 2 or 6 RUB, the 3% discount and the
25% margin are our scenario assumptions, not facts about X5.

How to answer: give the first sentence, stop, and add the rest only if the person wants more.
If you do not know, say so: "I do not have that number; it is not something we measured."

## A. Is the effect real?

**1. How do you know the campaign caused 3.3 points and it is not noise?**
Contact was assigned at random: 99,981 customers were contacted and 100,058 were held out. The
purchase rates were 63.65% and 60.33%, a difference of +3.32 points with a 95% interval of +2.90
to +3.75. The z statistic is 15.3, so the p-value is far below 0.001. Because of the random
assignment, the only systematic difference between the two groups is the message.

**2. Where does "95 of every 100" come from?**
It is 60.33 divided by 63.65, which is 94.8%. Among contacted customers who bought, that share
would have bought without the message, because the held-out group bought at 60.33% with no
contact. Only the remaining 5% or so of purchases were caused by the campaign.

**3. The uplift models have a Qini of 0.009. Is that not almost nothing?**
It is small, and we say so. It is still significantly above zero: the champion's 95% interval is
+0.0021 to +0.0156, and the result holds over five re-splits (+0.0143 ± 0.0030). What matters for
the business is the top of the ranking: the top 10% of customers react by +9.9 points against
+3.3 on average. Below the top the ranking is noisy.

**4. Did you find customers who buy less when contacted, the "sleeping dogs"?**
No, and we do not claim it. The group that the model scores as having no positive effect had a
real measured effect of +1.7 points, with an interval from -0.1 to +3.5. So the honest statement
is that these customers react little, not that the message harms.

**5. Your own profit interval crosses zero. So does LiftPilot make money or not?**
At 6 RUB per message the plan's real incremental profit is 204,762 RUB, with a 95% interval from
-206,450 to 598,342 and an 84% probability of being positive. So it is around break-even to
positive, not guaranteed. What is statistically clear is the comparison: it is 1,049,514 RUB
better than contacting everyone (interval 633,841 to 1,427,149), because contacting everyone
loses 844,752 RUB (interval -1,391,002 to -223,432).

## B. Method and models

**6. What is uplift modeling, in one sentence, and how is it different from a normal prediction model?**
A normal response model predicts who will buy; an uplift model predicts how much the probability
of buying changes because of the message. It can only be trained on data where contact was
random, because it must compare similar customers with and without contact. On our test set the
response model had a negative Qini (-0.0052): it finds buyers, not persuadable customers.

**7. What is Qini?**
Rank customers from the highest score to the lowest and contact them in that order. The Qini
curve counts the extra purchases caused as you go down the list, and the Qini value is the area
between that curve and the straight line you would get with random targeting. Above zero means
the ranking finds persuadable customers faster than chance.

**8. Which models did you use, and how did you choose the final one?**
Five uplift learners built on gradient-boosted trees (S, T, X, DR, class transformation) plus
their ensemble, and a response model as the baseline. That makes seven models in the table. The data was split once into train (120,023),
calibration (40,008) and test (40,008). The champion, the S-learner, was chosen by Qini on the
calibration split, before looking at the test results. The intervals of the uplift learners
overlap, so we do not claim that one of them beats the others.

**9. How can you state the profit of a plan that was never run?**
Because contact in the past campaign was random, any targeting rule can be replayed on held-out
customers: we look only at customers whose random assignment happens to agree with what the rule
would have done. The estimator is a self-normalised inverse-propensity estimator, and the 95%
intervals come from the bootstrap. This is a replay on historical data, which is why a real
deployment still keeps a random hold-out in every campaign.

**10. Why calibrate the uplift scores?**
The profit rule compares the uplift with a break-even value, so the score must mean what it says:
a score of 6 points has to correspond to about 6 points of real effect. Raw model scores rank well
but are not on that scale. We fit an isotonic regression on the separate calibration split and
apply the rule to the calibrated scores.

**11. Why RFM, if the model has 33 features?**
RFM is the language marketers already use, so it is how we explain and segment, and how messages
are written. It also carries most of the signal: with only the three RFM features the Qini is
+0.0085, against +0.0089 with all behaviour features. The weights of the RFM score (0.40, 0.35,
0.25) are a stated assumption; the uplift model, not that score, decides who is contacted.

## C. Metrics and money

**12. Why not simply report ROAS, as the platforms do?**
Platform ROAS divides all revenue from contacted customers by the spend, including the 95% of
purchases that would have happened anyway. We report incremental ROAS: only the extra revenue
caused by the message, divided by the spend. The break-even is one divided by the margin, so 4.0
at a 25% margin. At 6 RUB, contacting everyone has an incremental ROAS of 2.59, which loses
money, and the LiftPilot plan has 5.77.

**13. Walk me through the calculation for one customer.**
Take a margin of 25%, a basket of 400 RUB, a message cost of 6 RUB, and a customer who buys 40%
of the time without a message and 48% with one. Extra margin is 0.25 x 400 x 0.08 = 8 RUB, the
cost is 6 RUB, so the expected profit is +2 RUB and we contact. Her break-even uplift is
6 / (0.25 x 400) = 6 points. With a 3% discount the cost becomes 6 + 0.03 x 400 x 0.48 = 11.76
RUB, which is more than 8, so we skip. This customer is an illustration with round numbers, not
a row of the data.

**14. Where do the 25% margin and the 2 and 6 RUB costs come from?**
They are scenario assumptions, and the slides say so. X5 does not publish its margin or its
contact cost. That is why we show three scenarios and a cost frontier from 1 to 10 RUB, and why
the demo has sliders: a real retailer would enter its own numbers.

**15. How did you compute retention and lifetime value, and how far can we trust them?**
With the course formulas on the real receipts: monthly churn from month-to-month transitions,
retention = 1 - churn, lifetime = 1 / churn capped at 36 months, and LTV = average order value x
orders per month x margin x lifetime. Overall churn is 7.7% a month and LTV is 8,142 RUB of gross profit. The limit
is the horizon: we have three complete months and two transitions, and lifetime is capped at 36
months, so these are orders of magnitude.

**16. What is the answer to the R$ 1 million question?**
At the reference rate of 19 November 2026, R$ 1,000,000 is 14,073,400 RUB (the figure on the
results sheet; the app converts at the rate of the day). At 6 RUB per message, the plan for the
never-tested audience contacts 19% of 200,123 customers, which costs about 230 thousand RUB.
Its expected profit is 99,838 RUB, with a 95% interval from -114,276 to 299,621. So the first
recommendation is to not spend most of the budget on contact, and the system says so instead of
finding ways to spend it.

## D. The agent and AI integration

**17. Why not just use ChatGPT?**
Three reasons. A general chatbot cannot know the causal effect of a message on these customers;
that comes from the experiment and the uplift models, not from language. Second, we do not let
the language model produce numbers at all: every number comes from a tool, facts are written by
code, and a grounding check rejects text with numbers that no tool returned. Third, the model
runs locally (Qwen3 8B through Ollama), so no customer data leaves the laptop and the cost is
0 USD.

**18. What exactly does the language model do, then?**
It reads the manager's request, chooses which of the 16 tools to call and with which arguments,
narrates the verified statements in plain English, and drafts one message per RFM segment. It
does not estimate uplift, decide who is contacted, compute profit, or approve anything. Those are
done by machine learning, by rules, by statistics and by a human.

**19. What happens when the model hallucinates?**
We saw it in testing, and each failure became a control. Invented arguments are blocked by a
strict argument rule and validation. Skipped steps are forced by a runtime checklist. Wrong
numbers are caught by the numeric grounding check, and over-confident wording by an over-claim
check. If the narrative still fails, it is discarded and the verified statements written by code
are shown instead.

**20. Why is it a "utility-based" agent, and what are the privilege levels?**
In the course taxonomy a utility-based agent chooses the action with the best expected outcome;
here the utility is expected incremental profit, the question of where the next 100 goes. The 16
tools have three privilege levels: 12 read tools for facts and analysis, 3 propose tools (plan,
drafts, approval request), and 1 action tool, the export. The export refuses to run until a named
human has approved, and the agent cannot approve itself.

**21. How did you test the agent itself?**
With a fixed benchmark of 13 requests: seven campaign plans, three questions and three safety
probes (export without approval, target only women over 60, promise a guaranteed profit). For
each run we record whether the planner received exactly the stated assumptions, whether the
mandatory checklist was completed, the share of numbers grounded in a tool result, and whether
the probe was refused. The results, from section 10 of `docs/RESULTS.md`: argument fidelity 100%
after the provenance guard, which had to drop invented assumptions in 1 run; checklist completed
in 100% of runs; 100% of 203 numbers grounded; 1 narrative rejected by the guards and replaced
by the verified statements; 56 of 56 message drafts passed the copy checks; 3 of 3 safety probes
passed. The median time for a full plan was 149 seconds on the laptop GPU. This is 13 requests
on one model, so it is a regression check, not a proof. If the benchmark is run again, read the
new numbers from the results sheet and rebuild the deck.

## E. Ethics

**22. You do not use age, yet young customers are selected less. Is that discrimination?**
Age and gender are never model inputs, but removing an attribute does not remove its correlation
with behaviour. Our audit found that the selection ratio for 18-24 year-olds falls from 0.85 at
2 RUB to 0.70 at 6 RUB and 0.48 at 10 RUB. It follows a real difference in measured effect: +1.4
points for 18-24 against +5.9 for 65 and over. The system does not decide whether that is
acceptable; it flags any ratio under 0.80 for human review.

**23. Why did the fair mode fail, and why do you report it?**
Fair mode values every customer at the average basket, so small spenders are not passed over for
spending less. At 6 RUB the age ratio went from 0.70 to 0.65, so it did not close the gap, and
profit fell from 99,838 RUB (95% interval -99,289 to 296,175) to 43,565 RUB (-25,589 to
120,655). The gap comes from the difference in measured effect,
not from basket size. We report it because a negative result is information: this fix does not
work, and a business should not believe it does.

**24. Is this legal, and is it manipulation?**
We designed against the texts we could read in the original. GDPR Article 21(2) and (3) give an
unconditional right to object to direct marketing and the related profiling, so opt-outs are
never contacted. GDPR Article 22 and Brazil's LGPD Article 20 concern decisions taken solely by
automated processing: Article 22 includes a right to obtain human intervention, and LGPD
Article 20 a right to request a review. That is one reason a human approves every plan. The EU AI Act Article
5(1)(b) prohibits exploiting vulnerability due to age, so minors are excluded and the copy check
rejects pressure tactics. This is our reading as engineers, not legal advice.

## F. Business, data and limits

**25. What if a company has never run a randomised campaign? And when does this not help at all?**
Then uplift cannot be learned or checked, and we would not deploy. The 12-week pilot starts
there: between week 2 and week 5 it designs and runs one baseline campaign with a random
hold-out, which only requires leaving a random group of customers uncontacted. It does not help
when contact is nearly free: at 2 RUB, contacting almost everyone is right, and LiftPilot only
saves about 30% of the spend. It also does not help
when everyone reacts the same: on the Hillstrom e-mail test the right answer was all or nothing.

## Short answers for data questions that may come up

- **Is the data real?** Yes. X5 RetailHero is a public dataset from a grocery chain: 400,162
  customers with purchase history and 45.8 million receipt lines. Hillstrom is a public e-mail
  test with 64,000 customers.
- **Was the message an SMS?** We do not know. The source says only "a communication".
- **Is the currency roubles?** Presumed. The source does not state it.
- **Do you observe how much people spent after the campaign?** No. We know whether they bought.
  Money figures value a purchase at that customer's own average basket (463 RUB on average).
- **Is "FreshMart" a real brand?** No. It is a fictional name used in the sample messages.
- **Does live data change who is contacted?** No. Exchange rates only convert a budget stated in
  another currency, and the holiday calendar only sets the send date. Both are cached offline.
- **Why does the agent take more than two minutes?** It is an 8-billion-parameter model on a
  laptop GPU, and one plan needs seven tool calls, and the model also writes one message draft
  per segment. The median was 149
  seconds in the benchmark. A campaign decision does not need a faster answer, and in exchange
  no customer data leaves the machine.
- **Is this the first system of its kind?** We do not claim that. To our knowledge, the
  combination of a per-customer profit rule, replay evidence and a fenced local agent is not
  common in class projects, and that is all we say.
