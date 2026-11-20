# Datasheet for the datasets used by LiftPilot

This datasheet follows the question groups of "Datasheets for datasets" (Gebru et al., 2021)
[1]: motivation, composition, collection, preprocessing, uses, distribution, maintenance.

We did not create either dataset. We describe them **as used here**, and we separate three
kinds of statement:

- **Source**: stated by the data provider on a page we opened (URL given);
- **Measured**: computed by us from the files;
- **Unknown**: not stated by the source and not measurable from the files. Unknowns are listed
  as unknown, not filled with guesses.

Sources were opened and re-checked on 2026-11-20. Counts in the "Measured" rows that also appear
in [RESULTS.md](RESULTS.md) are taken from there.

---

## 1. X5 RetailHero uplift data (main dataset)

### 1.1 Motivation

| Question | Answer | Kind |
|---|---|---|
| Who created it and for what? | Provided by X5 Retail Group, a Russian grocery retailer, for the RetailHero hackathon hosted in winter 2019; the uplift-modeling competition was hosted on ODS.ai [2], [3] | Source |
| What task was it built for? | Uplift modeling: deciding which customers should receive a communication | Source |
| Who funded it? | Unknown | Unknown |

### 1.2 Composition

| Question | Answer | Kind |
|---|---|---|
| What does a row represent? | `clients`: one loyalty-card customer. `purchases`: one product line of one receipt. `uplift_train`: one customer in the experiment | Source, checked on the files |
| How many rows? | `clients` 400,162; `purchases` 45,786,568; `uplift_train` 200,039 [2] | Source; the 200,039 was recounted |
| Columns | `uplift_train`: `client_id, treatment_flg, target`. `clients`: `client_id, first_issue_date, first_redeem_date, age, gender`. `purchases`: `client_id, transaction_id, transaction_datetime, regular_points_received, express_points_received, regular_points_spent, express_points_spent, purchase_sum, store_id, product_id, product_quantity, trn_sum_from_iss, trn_sum_from_red` | Measured (file headers) |
| Treatment | `treatment_flg` "indicates if there was a communication" [3]. The page frames the decision as whether "we should send a text to the client" and does not name a channel | Source |
| Outcome | `target` "shows if there was a purchase afterward" (yes or no) [3] | Source |
| Group sizes and rates | 99,981 contacted and 100,058 held out; purchase rate 63.65% versus 60.33%; difference +3.32 points (95% CI +2.90 to +3.75) | Measured |
| Is there a monetary outcome? | No. Amounts exist only in the purchase history before the campaign (`purchase_sum`) | Measured |
| Time span of the purchase history | First receipt 2018-11-21, last receipt 2019-03-18. RESULTS.md prints the window as 2018-11-21 to 2019-03-19 because its second date is the reference date for recency, the day after the last receipt. Purchases are the "purchase history prior to communication" [3] | Measured; Source |
| Sub-populations | Age and gender are present. Gender is coded `M`, `F`, `U` (unknown). 1,779 customers have no valid age (outside 14 to 100) | Measured |
| Missing data | `first_redeem_date` is empty for some customers; 200,123 of the 400,162 customers have no treatment flag in the files we use | Measured |
| Does it identify people? | Customers appear under an opaque `client_id`. The files contain no names or contact details. Age, gender and a detailed purchase history are present | Measured |
| Sensitive attributes | Age and gender | Measured |
| Size on disk | 647 MB compressed, 4.17 GB uncompressed according to the scikit-uplift documentation [2]; the compressed purchase file alone is about 670 MB | Source; Measured |

### 1.3 Collection process

| Question | Answer | Kind |
|---|---|---|
| How was the treatment assigned? | The data are distributed as a treatment-and-control benchmark for uplift modeling, and we treat the treatment flag as assigned at random. What the files let us check: the two groups are almost equal in size (99,981 and 100,058). The assignment procedure itself is not documented | Source; Measured |
| Which channel was used? | Unknown. The source says "a communication" and "send a text to the client"; the word SMS does not appear | Unknown |
| What did the communication say? Did it carry an offer? | Unknown | Unknown |
| How long after the communication was a purchase counted? | Unknown (not stated on the page) | Unknown |
| When was the campaign run? | Unknown; the purchase history ends on 2019-03-18 | Unknown |
| Were customers informed or did they consent to this use? | Unknown | Unknown |
| Was there an ethical review? | Unknown | Unknown |
| How were the customers in the files chosen from the retailer's customer base? | Unknown | Unknown |

### 1.4 Preprocessing done in this project

All steps are in `src/liftpilot/data/x5.py` and `src/liftpilot/data/prepare.py`.

- Receipt lines are collapsed to one row per receipt. The receipt total `purchase_sum` is
  repeated on every line of a receipt, so it is taken once per receipt.
- One row of 33 behaviour features per customer: recency, frequency, monetary value, basket
  statistics, activity in the last 7, 30 and 31 to 60 days, stores visited, loyalty points
  received and spent, card age, and R, F, M scores.
- Recency is counted from the day after the last purchase date in the data.
- Leakage guard: `first_redeem_date` can fall after the end of the purchase history, so only
  redemptions dated before the reference date become features.
- Ages outside 14 to 100 are set to missing (1,779 customers without a valid age). Age is
  grouped into bands for auditing only. The band labelled "18-24" holds every valid age under
  25, that is ages 14 to 24. Customers under 18 are never eligible for contact but are still
  counted in that band, which matters when reading the fairness audit
  (see [ETHICS.md](ETHICS.md), section 3).
- Age and gender are **not** model inputs. They are kept only to audit who is selected.
- Revenue of a buyer is **imputed**: the purchase amount after the campaign is not in the data,
  so a purchase is valued at that customer's own average basket, shrunk towards the overall mean
  for customers with few purchases (mean 463 in the data's currency).
- The 200,039 labelled customers are split, stratified on treatment and outcome, into train
  120,023, calibration 40,008 and test 40,008. The 200,123 customers without a treatment flag
  are kept as the "next audience" to plan for; they are never used for training.
- The raw files are kept unchanged in `data/raw/x5/`; derived tables go to `data/interim/` and
  `artifacts/x5/`.

### 1.5 Uses

| Question | Answer |
|---|---|
| What is it used for here? | Training and evaluating uplift learners, RFM analysis, replay evaluation of targeting rules, fairness audit, retention and lifetime-value tables |
| What should it not be used for? | Claims about the retailer's real margins, costs or revenue; claims about the channel; conclusions about named individuals; any attempt to re-identify customers |
| What could affect future use? | The outcome is yes or no, so money figures depend on an imputed basket; the data are from one retailer and one period (2018 to 2019); the currency and the outcome window are undocumented |

### 1.6 Distribution

| Question | Answer | Kind |
|---|---|---|
| Where do we get it? | `https://sklift.s3.eu-west-2.amazonaws.com/{uplift_train,clients,purchases}.csv.gz`, the mirror used by the scikit-uplift library [2] | Source |
| Licence | **None stated** on the competition data page or in the scikit-uplift documentation | Source |
| How we handle that | The raw files are not committed to this repository. `liftpilot download` fetches them from the public location, and `data/checksums.sha256` records their SHA-256 so a changed file is detected. We cite the source and do not redistribute | Project decision |
| Currency of `purchase_sum` | Not stated by the source. We presume Russian roubles (RUB) because the retailer is Russian | Unknown; presumed |

### 1.7 Maintenance

| Question | Answer | Kind |
|---|---|---|
| Who maintains it? | Unknown. The competition archive and the scikit-uplift mirror both answered on 2026-11-20 | Unknown; Measured |
| Will it be updated? | Unknown. scikit-uplift's last release is 0.5.1 (2022-08-11) | Unknown; Source |
| Erratum or contact | Unknown | Unknown |

### 1.8 Unknowns, in one list

- the channel of the communication and its content;
- whether the communication carried an offer or a discount;
- the length of the outcome window and the date of the campaign;
- the currency of the amounts (presumed RUB);
- the purchase amount after the campaign (not in the data);
- the exact randomisation procedure;
- how the customers were sampled from the retailer's base;
- whether customers consented to this use, and whether any ethical review took place;
- the licence;
- the contents of two files in the original competition archive that we do not use
  (`products.csv` and `uplift_test.csv`): their columns, row counts and whether test labels were
  published.

---

## 2. Hillstrom MineThatData e-mail test (external check)

### 2.1 Motivation

| Question | Answer | Kind |
|---|---|---|
| Who created it and for what? | Kevin Hillstrom published it on the MineThatData blog on 20 March 2008 as an e-mail analytics and data mining challenge [4] | Source |
| Who funded it? | Unknown | Unknown |

### 2.2 Composition

| Question | Answer | Kind |
|---|---|---|
| What does a row represent? | One customer of an online retailer; "64,000 customers who last purchased within twelve months" [4] | Source |
| How many rows? | 64,000 | Source; recounted |
| Columns | `recency` (months since last purchase), `history_segment`, `history` (USD spent in the past year), `mens`, `womens`, `zip_code` (Urban, Surburban [sic], Rural), `newbie`, `channel` (Phone, Web, Multichannel), `segment` (the treatment), `visit`, `conversion`, `spend` | Source for definitions; Measured for values |
| Treatment | Three groups assigned at random, one third each: a men's e-mail, a women's e-mail, no e-mail [4] | Source |
| Outcomes | `visit` (yes or no), `conversion` (yes or no), `spend` (USD), tracked "during a period of two weeks following the e-mail campaign" [4] | Source |
| Group sizes | No e-mail 21,306; men's e-mail 21,307; women's e-mail 21,387 | Measured |
| Is there a monetary outcome? | Yes: `spend` in USD | Source |
| Raw transactions? | No. Recency and past-year spend are given; purchase frequency is not | Measured |
| Does it identify people? | No identifiers are in the file; we number the rows ourselves | Measured |
| Sensitive attributes | The file has no age column and no gender column. We run no group audit on this dataset | Measured |

### 2.3 Collection process

| Question | Answer | Kind |
|---|---|---|
| How was the treatment assigned? | At random, per the blog post [4] | Source |
| Which retailer, which products, which e-mail content? | Unknown | Unknown |
| When was the campaign run? | Unknown; the post is dated March 2008 | Unknown |
| Consent and ethical review | Unknown | Unknown |

### 2.4 Preprocessing done in this project

In `src/liftpilot/data/prepare.py` (`load_hillstrom`):

- Both e-mail versions count as "contacted"; the no-e-mail group is the control. This makes the
  treated share about two thirds.
- The outcome the learners predict is `visit`. Money comes from the observed `spend`.
- 9 features: `recency`, `history`, `mens`, `womens`, `newbie`, two indicators from `zip_code`
  (urban, rural), two from `channel` (web, phone).
- The value of one visit is the average spend per visit measured on the training part only.
- Same stratified train / calibration / test split as for X5.
- Scenario assumptions for the profit rule (40% margin; 0.10 or 0.60 USD per contact; 10%
  discount) are set in `src/liftpilot/pipeline.py`. They are assumptions, not facts about the
  retailer.

Measured on the data as we use it: visit rate 16.70% for e-mailed customers and 10.62% for the
others, a difference of +6.09 points (95% CI +5.54 to +6.63).

### 2.5 Uses

| Question | Answer |
|---|---|
| What is it used for here? | An external check: does the method behave sensibly on a different retailer, channel, country and decade, with observed spend |
| What should it not be used for? | Conclusions about today's e-mail marketing; it is 2008 data with few, coarse features |
| What could affect future use? | Fewer than 1.3% of customers convert in any group, so `spend` is zero for almost everyone and money estimates are noisy |

### 2.6 Distribution

| Question | Answer | Kind |
|---|---|---|
| Where do we get it? | The original CSV on `minethatdata.com` (URL in `src/liftpilot/data/prepare.py`); it is also mirrored by scikit-uplift | Source |
| Licence | **None stated** on the blog post | Source |
| How we handle that | Not committed to this repository; downloaded by `liftpilot download` and checked against `data/checksums.sha256`. We cite the blog | Project decision |

### 2.7 Maintenance

| Question | Answer | Kind |
|---|---|---|
| Who maintains it? | The file is hosted on the author's site and answered on 2026-11-20. No maintenance policy is stated | Measured; Unknown |

### 2.8 Unknowns, in one list

- the retailer, the products and the content of the two e-mails;
- the date of the campaign;
- how the 64,000 customers were chosen beyond "last purchased within twelve months";
- consent and ethical review;
- the licence.

---

## 3. Live context data (not training data)

Two public feeds supply context to the planner. They never enter the models.

| Feed | Used for | Notes |
|---|---|---|
| Frankfurter exchange rates [5] | converting a budget stated in another currency | The site states that no API key is needed and that rates are reference rates from central banks and official sources. A second public source (`open.er-api.com`) is tried if it does not answer |
| Nager.Date public holidays | choosing a send date and listing holidays inside the measurement window | Terms of use and rate limits were not checked: unknown |

Both are cached under `data/cache/` (not committed) so the system works offline.

---

## References

[1] T. Gebru et al., "Datasheets for datasets," *Communications of the ACM*, vol. 64, no. 12,
pp. 86-92, 2021. https://doi.org/10.1145/3458723

[2] scikit-uplift documentation, page for the `fetch_x5` data loader (X5 RetailHero data).
https://www.uplift-modeling.com/en/latest/api/datasets/fetch_x5.html

[3] ODS.ai, data page of the X5 RetailHero uplift modeling competition.
https://ods.ai/competitions/x5-retailhero-uplift-modeling/data

[4] K. Hillstrom, MineThatData blog post announcing the e-mail analytics and data mining
challenge, 20 March 2008.
https://blog.minethatdata.com/2008/03/minethatdata-e-mail-analytics-and-data.html

[5] Frankfurter, exchange rates API. https://frankfurter.dev/
