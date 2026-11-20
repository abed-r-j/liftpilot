// LiftPilot paper, IEEE conference style, written for the Typst compiler (no template package,
// no network). Build with docs/paper/build.py. Every number comes from docs/RESULTS.md.

// ---------------------------------------------------------------- layout
#set document(
  title: "LiftPilot: Profit-Calibrated Uplift Targeting with a Guarded LLM Campaign Agent",
  author: ("Abed El Rahmane Jaafir", "Ghandi Mahmoud"),
)
#set page(
  paper: "us-letter",
  margin: (top: 0.75in, bottom: 1in, left: 0.625in, right: 0.625in),
  columns: 2,
)
#set columns(gutter: 0.25in)
#set text(font: "Times New Roman", size: 10pt, lang: "en", hyphenate: true)
#set par(justify: true, leading: 0.5em, spacing: 0.5em, first-line-indent: 1em)
#show list: set par(first-line-indent: 0pt)
#show enum: set par(first-line-indent: 0pt)
#set math.equation(numbering: "(1)", supplement: none)
#show math.equation.where(block: true): set block(above: 0.75em, below: 0.75em)
#set list(indent: 0.6em, body-indent: 0.45em, spacing: 0.45em)
#set enum(indent: 0.6em, body-indent: 0.45em, spacing: 0.45em)
#show raw: set text(font: "Consolas", size: 8.3pt)

// Small capitals built by hand (Times New Roman has no small-caps feature).
#let fsc(s) = {
  let words = s.split(" ")
  let small = ("and", "of", "the", "by", "on", "at", "to", "in", "per", "with", "vs.")
  words
    .enumerate()
    .map(((i, w)) => {
      let cl = w.clusters()
      let digits = ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")
      if cl.len() == 0 { [] } else if cl.first() in digits or (cl.first() == "(" and cl.len() > 1 and cl.at(1) in digits) {
        [#w]
      } else if i > 0 and lower(w) in small {
        text(size: 0.8em, upper(w))
      } else if cl.first() == "(" and cl.len() > 1 {
        [(#upper(cl.at(1))#text(size: 0.8em, upper(cl.slice(2).join("")))]
      } else {
        [#upper(cl.first())#text(size: 0.8em, upper(cl.slice(1).join("")))]
      }
    })
    .join([ ])
}

// Headings: I. SMALL CAPS centred; A. italic flush left.
#set heading(numbering: "I.A.")
#show heading.where(level: 1): it => {
  set align(center)
  set text(size: 10pt, weight: "regular")
  block(above: 1.15em, below: 0.65em, sticky: true)[
    #if it.numbering != none [#numbering("I.", counter(heading).get().at(0))#h(0.6em)]
    #if it.body.has("text") { fsc(it.body.text) } else { it.body }
  ]
}
#show heading.where(level: 2): it => {
  set text(size: 10pt, weight: "regular", style: "italic")
  block(above: 0.85em, below: 0.5em, sticky: true)[
    #numbering("A.", counter(heading).get().at(1))#h(0.5em)#it.body
  ]
}

// Figures and tables.
#set figure(gap: 0.5em)
#set place(clearance: 1em)
#set figure.caption(separator: [. ])
#show figure.where(kind: image): set figure(supplement: [Fig.])
#show figure.caption.where(kind: image): it => {
  set text(size: 8pt)
  set par(justify: true, first-line-indent: 0pt, leading: 0.45em)
  align(left)[#it.supplement #context it.counter.display("1")#it.separator#it.body]
}
#show figure.where(kind: table): set figure.caption(position: top)
#show figure.caption.where(kind: table): it => {
  set text(size: 8pt)
  set par(justify: false, first-line-indent: 0pt, leading: 0.45em)
  align(center)[TABLE #context it.counter.display("I") \ #it.body]
}
#let tnum(k) = [Table~#context numbering("I", counter(figure.where(kind: table)).at(k).first())]
#let fnum(k) = [Fig.~#context numbering("1", counter(figure.where(kind: image)).at(k).first())]

#let tbl(caption, cols, ..cells, wide: false, align-spec: auto, label: none, size: 8pt, place: top) = [
  #figure(
    kind: table,
    supplement: [Table],
    placement: place,
    scope: if wide { "parent" } else { "column" },
    caption: fsc(caption),
    {
      set text(size: size)
      set par(justify: false, first-line-indent: 0pt, leading: 0.4em)
      table(
        columns: cols,
        align: if align-spec == auto { (x, y) => if x == 0 { left } else { right } } else { align-spec },
        stroke: none,
        inset: (x: 3.2pt, y: 1.8pt),
        table.hline(stroke: 0.7pt),
        ..cells,
        table.hline(stroke: 0.7pt),
      )
    },
  ) #label
]
#let hd(..c) = (table.header(..c.pos().map(x => strong(x))), table.hline(stroke: 0.4pt))
#let mid = table.hline(stroke: 0.3pt)

// ---------------------------------------------------------------- references (IEEE numeric, by hand)
#let refs = (
  x5: [X5 Retail Group, "X5 RetailHero uplift modeling dataset," RetailHero hackathon, 2019. Documented in scikit-uplift, `sklift.datasets.fetch_x5`. [Online]. Available: https://www.uplift-modeling.com/en/latest/api/datasets/fetch_x5.html],
  lewis: [R. A. Lewis and J. M. Rao, "The unfavorable economics of measuring the returns to advertising," _Quart. J. Econ._, vol. 130, no. 4, pp. 1941--1973, Nov. 2015, doi: 10.1093/qje/qjv023.],
  gordon: [B. R. Gordon, F. Zettelmeyer, N. Bhargava, and D. Chapsky, "A comparison of approaches to advertising measurement: Evidence from big field experiments at Facebook," _Marketing Sci._, vol. 38, no. 2, pp. 193--225, Mar. 2019, doi: 10.1287/mksc.2018.1135.],
  rubin: [D. B. Rubin, "Estimating causal effects of treatments in randomized and nonrandomized studies," _J. Educ. Psychol._, vol. 66, no. 5, pp. 688--701, Oct. 1974, doi: 10.1037/h0037350.],
  radcliffe: [N. J. Radcliffe and P. D. Surry, "Real-world uplift modelling with significance-based uplift trees," Stochastic Solutions Ltd., Edinburgh, U.K., Portrait Tech. Rep. TR-2011-1 (Stochastic Solutions White Paper), 2011. [Online]. Available: https://www.stochasticsolutions.com/pdf/sig-based-up-trees.pdf],
  gutierrez: [P. Gutierrez and J.-Y. Gerardy, "Causal inference and uplift modelling: A review of the literature," in _Proc. 3rd Int. Conf. Predictive Applications and APIs_, in Proc. Mach. Learn. Res., vol. 67, 2017, pp. 1--13. [Online]. Available: https://proceedings.mlr.press/v67/gutierrez17a.html],
  kunzel: [S. R. Kunzel, J. S. Sekhon, P. J. Bickel, and B. Yu, "Metalearners for estimating heterogeneous treatment effects using machine learning," _Proc. Natl. Acad. Sci. U.S.A._, vol. 116, no. 10, pp. 4156--4165, Mar. 2019, doi: 10.1073/pnas.1804597116.],
  kennedy: [E. H. Kennedy, "Towards optimal doubly robust estimation of heterogeneous causal effects," _Electron. J. Statist._, vol. 17, no. 2, pp. 3008--3049, 2023, doi: 10.1214/23-EJS2157.],
  jaskowski: [M. Jaskowski and S. Jaroszewicz, "Uplift modeling for clinical trial data," presented at the 29th Int. Conf. Machine Learning (ICML), Edinburgh, U.K., 2012. [Online]. Available: https://home.ipipan.waw.pl/sj/pdf/logsemi.pdf],
  belbahri: [M. Belbahri, A. Murua, O. Gandouet, and V. Partovi Nia, "Qini-based uplift regression," _Ann. Appl. Statist._, vol. 15, no. 3, pp. 1247--1272, Sep. 2021, doi: 10.1214/21-AOAS1465.],
  bokelmann: [B. Bokelmann and S. Lessmann, "Improving uplift model evaluation on randomized controlled trial data," _Eur. J. Oper. Res._, vol. 313, no. 2, pp. 691--707, Mar. 2024, doi: 10.1016/j.ejor.2023.09.018.],
  leng: [Y. Leng and D. Dimmery, "Calibration of heterogeneous treatment effects in randomized experiments," _Inf. Syst. Res._, vol. 35, no. 4, pp. 1721--1742, Dec. 2024, doi: 10.1287/isre.2021.0343.],
  bult: [J. R. Bult and T. Wansbeek, "Optimal selection for direct mail," _Marketing Sci._, vol. 14, no. 4, pp. 378--394, Nov. 1995, doi: 10.1287/mksc.14.4.378.],
  verbeke: [W. Verbeke, D. Olaya, M.-A. Guerry, and J. Van Belle, "To do or not to do? Cost-sensitive causal classification with individual treatment effect estimates," _Eur. J. Oper. Res._, vol. 305, no. 2, pp. 838--852, Mar. 2023, doi: 10.1016/j.ejor.2022.03.049.],
  floria: [C. Fernandez-Loria and F. Provost, "Causal decision making and causal effect estimation are not the same...and why it matters," _INFORMS J. Data Sci._, vol. 1, no. 1, pp. 4--16, Apr. 2022, doi: 10.1287/ijds.2021.0006.],
  ascarza: [E. Ascarza, "Retention futility: Targeting high-risk customers might be ineffective," _J. Marketing Res._, vol. 55, no. 1, pp. 80--98, Feb. 2018, doi: 10.1509/jmr.16.0163.],
  dudik: [M. Dudik, D. Erhan, J. Langford, and L. Li, "Doubly robust policy evaluation and optimization," _Statist. Sci._, vol. 29, no. 4, pp. 485--511, Nov. 2014, doi: 10.1214/14-STS500.],
  hitsch: [G. J. Hitsch, S. Misra, and W. W. Zhang, "Heterogeneous treatment effects and optimal targeting policy evaluation," _Quant. Marketing Econ._, vol. 22, no. 2, pp. 115--168, Jun. 2024, doi: 10.1007/s11129-023-09278-5.],
  simester: [D. Simester, A. Timoshenko, and S. I. Zoumpoulis, "Efficiently evaluating targeting policies: Improving on champion vs. challenger experiments," _Manage. Sci._, vol. 66, no. 8, pp. 3412--3424, Aug. 2020, doi: 10.1287/mnsc.2019.3379.],
  fader: [P. S. Fader, B. G. S. Hardie, and K. L. Lee, "RFM and CLV: Using iso-value curves for customer base analysis," _J. Marketing Res._, vol. 42, no. 4, pp. 415--430, Nov. 2005, doi: 10.1509/jmkr.2005.42.4.415.],
  gupta: [S. Gupta, D. Hanssens, B. Hardie, W. Kahn, V. Kumar, N. Lin, N. Ravishanker, and S. Sriram, "Modeling customer lifetime value," _J. Service Res._, vol. 9, no. 2, pp. 139--155, Nov. 2006, doi: 10.1177/1094670506293810.],
  react: [S. Yao, J. Zhao, D. Yu, N. Du, I. Shafran, K. Narasimhan, and Y. Cao, "ReAct: Synergizing reasoning and acting in language models," arXiv:2210.03629, v3, Mar. 2023. [Online]. Available: https://arxiv.org/abs/2210.03629],
  toolformer: [T. Schick, J. Dwivedi-Yu, R. Dessi, R. Raileanu, M. Lomeli, E. Hambro, L. Zettlemoyer, N. Cancedda, and T. Scialom, "Toolformer: Language models can teach themselves to use tools," in _Advances in Neural Information Processing Systems 36 (NeurIPS 2023)_, Main Conference Track, 2023. [Online]. Available: https://proceedings.neurips.cc/paper_files/paper/2023/hash/d842425e4bf79ba039352da0f658a906-Abstract-Conference.html],
  matz: [S. C. Matz, J. D. Teeny, S. S. Vaid, H. Peters, G. M. Harari, and M. Cerf, "The potential of generative AI for personalized persuasion at scale," _Sci. Rep._, vol. 14, no. 1, Art. no. 4692, Feb. 2024, doi: 10.1038/s41598-024-53755-0.],
  beat: [E. Ascarza and A. Israeli, "Eliminating unintended bias in personalized policies using bias-eliminating adapted trees (BEAT)," _Proc. Natl. Acad. Sci. U.S.A._, vol. 119, no. 11, Art. no. e2115293119, Mar. 2022, doi: 10.1073/pnas.2115293119.],
  aiact: [Regulation (EU) 2024/1689 of the European Parliament and of the Council of 13 June 2024 laying down harmonised rules on artificial intelligence and amending Regulations (EC) No 300/2008, (EU) No 167/2013, (EU) No 168/2013, (EU) 2018/858, (EU) 2018/1139 and (EU) 2019/2144 and Directives 2014/90/EU, (EU) 2016/797 and (EU) 2020/1828 (Artificial Intelligence Act), _Official Journal of the European Union_, OJ L, 2024/1689, 12.7.2024. [Online]. Available: http://data.europa.eu/eli/reg/2024/1689/oj],
  gdpr: [Regulation (EU) 2016/679 (General Data Protection Regulation). [Online]. Available: http://data.europa.eu/eli/reg/2016/679/oj],
  hillstrom: [K. Hillstrom, "The MineThatData e-mail analytics and data mining challenge," MineThatData blog, Mar. 20, 2008. [Online]. Available: https://blog.minethatdata.com/2008/03/minethatdata-e-mail-analytics-and-data.html],
  lee: [H.-P. Lee, A. Sarkar, L. Tankelevitch, I. Drosos, S. Rintel, R. Banks, and N. Wilson, "The impact of generative AI on critical thinking: Self-reported reductions in cognitive effort and confidence effects from a survey of knowledge workers," in _Proc. 2025 CHI Conf. Human Factors in Computing Systems_, Art. no. 1121, Apr. 2025, doi: 10.1145/3706598.3713778.],
  moffatt: [_Moffatt v. Air Canada_, 2024 BCCRT 149, British Columbia Civil Resolution Tribunal, Feb. 14, 2024. [Online]. Available: https://www.canlii.org/en/bc/bccrt/doc/2024/2024bccrt149/2024bccrt149.html],
)
#let cited = state("cited", ())
#let c(..keys) = {
  for k in keys.pos() {
    assert(k in refs, message: "unknown reference key " + k)
    cited.update(l => if k in l { l } else { l + (k,) })
  }
  context {
    let l = cited.final()
    let nums = keys.pos().map(k => l.position(x => x == k)).filter(x => x != none).map(x => x + 1).sorted()
    nums.map(n => "[" + str(n) + "]").join(", ")
  }
}

// ---------------------------------------------------------------- title block
#place(top + center, scope: "parent", float: true, clearance: 1.6em)[
  #set par(justify: false, first-line-indent: 0pt, leading: 0.5em)
  #text(size: 24pt)[LiftPilot: Profit-Calibrated Uplift Targeting with a Guarded LLM Campaign Agent, Evaluated on a Real Randomised Retail Experiment]
  #v(1.1em)
  #grid(
    columns: (1fr, 1fr),
    column-gutter: 1em,
    [#text(size: 11pt)[Abed El Rahmane Jaafir] \
      #emph[Faculty of Engineering (ESIB)] \
      #emph[Saint Joseph University of Beirut] \
      Beirut, Lebanon],
    [#text(size: 11pt)[Ghandi Mahmoud] \
      #emph[Faculty of Engineering (ESIB)] \
      #emph[Saint Joseph University of Beirut] \
      Beirut, Lebanon],
  )
]

// ---------------------------------------------------------------- abstract
#{
  set text(size: 9pt, weight: "bold")
  set par(leading: 0.47em)
  [#emph[Abstract:] A grocery chain sent a communication at random to half of 200,039 loyalty customers. 63.65% of contacted customers bought and 60.33% of held-out customers bought anyway: the campaign caused +3.32 percentage points (95% CI +2.90 to +3.75), and 94.8% of the purchases that followed a contact would have happened without it. LiftPilot is a campaign planner built on this experiment. It estimates the effect of contact per customer with gradient-boosted meta-learners, calibrates the estimates, contacts a customer only when margin times basket times uplift exceeds the cost of the message and of any discount, and reports the incremental profit of every plan by replay on held-out randomised customers. Purchase amounts after the campaign are not in the data, so a purchase is valued at the customer's average basket; the currency is presumed to be RUB. A likely-buyer model has a Qini coefficient of −0.0052 on test customers (95% CI −0.0116 to +0.0010), no better than random; the chosen uplift learner reaches +0.0089 (95% CI +0.0021 to +0.0156). Whether targeting pays depends on the cost of contact. With an assumed 25% margin and 2 RUB per message, the profit rule cannot be distinguished from contacting everyone (difference −46,581 RUB, 95% CI −347,880 to +230,187). At an assumed 6 RUB, contacting everyone loses 844,752 RUB (−1,391,002 to −223,432) and the rule is better by 1,049,514 RUB (633,841 to 1,427,149), although its own profit interval includes zero. A local 8B language model drives 16 tools around this engine under runtime controls written as code, a fairness audit and a human approval gate. Among adults the audit finds a small age gap in who is selected that widens with the cost of contact (lowest-to-highest selection ratio 0.96 at 2 RUB, 0.57 at 10 RUB). We also report where the method does not help.]
  v(0.45em)
  [#emph[Index Terms:] uplift modeling, heterogeneous treatment effects, incremental profit, RFM, off-policy evaluation, LLM agents, fairness, marketing.]
}

// ================================================================ I
= Introduction

Marketing dashboards count the customers who bought after a campaign. That count mixes two groups: customers who bought because they were contacted, and customers who would have bought anyway. A randomised experiment separates them, and field evidence shows that returns to advertising are measured with very wide intervals #c("lewis") and that non-experimental methods often fail to recover experimental effects #c("gordon").

The X5 RetailHero data #c("x5") make the point with one number. A grocery chain sent a communication to a random half of 200,039 loyalty-card customers. The purchase rate was 63.65% among contacted customers and 60.33% among held-out customers. The campaign therefore caused +3.32 points (95% CI +2.90 to +3.75), and 94.8% of the purchases that followed a contact, about 95 in every 100, would have happened without it.

The question is then which customers change their behaviour when contacted, and whether the change is worth the cost. LiftPilot answers it per customer and states how sure it is. Our contributions are:

- a calibrated profit rule that decides, per customer, whether contact is expected to pay, with RFM features computed from 45.8 million raw receipt lines;
- an evaluation by replay on held-out randomised customers that gives the real incremental profit of any targeting rule with 95% intervals, before money is spent;
- a campaign agent built on a local language model that is fenced by code: numbers come only from tools, facts are written by code, and nothing is exported without human approval;
- a measured fairness audit, and negative results (cheap contact, a second data set with uniform effects, a fairness mode that failed) reported with the same weight as the positive ones.

To our knowledge, an LLM agent that calls an uplift model and a profit rule on a real randomised experiment has not been described in peer-reviewed work; we cannot rule out unpublished or workshop-level work.

// ================================================================ II
= Related Work

== Uplift modeling and meta-learners
Uplift modeling estimates the conditional average treatment effect, the difference between a customer's two potential outcomes #c("rubin"), of which only one is ever observed. Marketing practice added direct tree-based estimators and the Qini measure #c("radcliffe"). Reviews group the methods into two-model, class-transformation and direct approaches #c("gutierrez"). We use the S-, T- and X-learners of Kunzel _et al._ #c("kunzel"), who state that none of the meta-learners is uniformly the best, the doubly robust learner #c("kennedy") and the class-variable transformation #c("jaskowski"). Qini-based evaluation is formalised in #c("belbahri"), and improving its estimates on experimental hold-out data is a research topic of its own #c("bokelmann"). A profit rule needs effect magnitudes, not only a ranking, hence our interest in calibration #c("leng").

== Profit-aware targeting and policy evaluation
The rule "mail when expected marginal return exceeds marginal cost" was derived for response probability by Bult and Wansbeek #c("bult"). Cost-sensitive causal classification restates the treat or do-not-treat decision for an estimated individual effect #c("verbeke"), and Fernandez-Loria and Provost argue that a good decision and an accurate effect estimate are different goals #c("floria"). Ascarza shows that targeting the customers at highest risk might be ineffective #c("ascarza"). A new policy can be valued from logged data by inverse-propensity and doubly robust estimators #c("dudik")#[;] targeting policies have been evaluated on randomised data #c("hitsch"), and one experiment can evaluate many policies #c("simester").

== RFM and customer value
Recency, frequency and monetary (RFM) scoring is a long-standing practice of database marketing. Fader _et al._ link RFM to customer lifetime value (CLV) through iso-value curves #c("fader"), and Gupta _et al._ review CLV models #c("gupta"). We use RFM as features and as a reporting vocabulary, not as the decision rule.

== LLM agents, tool use and their limits
ReAct interleaves reasoning traces and actions #c("react"). Toolformer starts from the observation that language models struggle with arithmetic and factual lookup, and lets them call tools #c("toolformer"). Hence our division of labour: the estimator computes, the model selects tools and words the answer, and code checks both.

== Ethics of personalised persuasion
Messages personalised by a generative model were more influential than non-personalised ones across four studies #c("matz"). Personalised policies risk targeting protected groups disproportionately, and balanced allocation methods exist #c("beat"). The EU Artificial Intelligence Act prohibits manipulative techniques and the exploitation of vulnerabilities that cause significant harm #c("aiact"), and the GDPR gives a right to object to direct marketing and related profiling #c("gdpr").

// ================================================================ III
= Data

== X5 RetailHero
The primary data set #c("x5") has three files: 400,162 loyalty customers, 45.8 million purchase lines dated 2018-11-21 to 2019-03-19, all before the campaign, and a randomised table of 200,039 customers with a treatment flag and a binary outcome (purchase afterwards). The remaining 200,123 customers were never tested; we treat them as the audience of the next campaign.

Labelled customers are split once, stratified by arm and outcome, into train (120,023), calibration (40,008) and test (40,008). Learners are fitted on train; the champion is chosen and calibrated on calibration; every result in Section VI is computed on test, and Qini is also reported over five re-splits.

_Leakage guard._ The field `first_redeem_date` runs past the end of the purchase history into the outcome period. Only redemptions dated before the reference date (the day after the last receipt) are allowed to become features.

_What is not known._ The source describes the treatment only as "a communication" and does not name the channel, the content, or the length of the outcome window. The currency is not stated; we presume Russian roubles (RUB) because the retailer is Russian. The purchase amount after the campaign is not in the data, so every money figure values a purchase at the customer's own average basket, shrunk towards the overall mean (mean expected basket 463 RUB). Age and gender exist for the audit; 1,779 invalid ages were set to missing.

== Hillstrom e-mail test
The second data set #c("hillstrom") has 64,000 customers randomised to an e-mail or no e-mail, with observed spend in USD over two weeks. We merge the two e-mail arms and use the visit as outcome. It has no purchase frequency, so it is an external check only.

// ================================================================ IV
= Method

== RFM construction
Purchase lines are collapsed to receipts. For each customer we compute recency in days before the reference date, the number of receipts and total spend, and score each from 1 to 5 by quintile. The weighted score is
$ "RFM" = 0.40 R + 0.35 F + 0.25 M, $ <eq-rfm>
where the weights are a stated assumption and not an estimate. Eight named segments (Champions to Hibernating) are assigned from $R$ and the mean of $F$ and $M$. The model uses 33 features: R, F, M, their scores, and behaviour such as basket statistics, tenure, recent activity and loyalty-point use. Age and gender are excluded.

== Learners
All learners use gradient-boosted trees (300 trees, learning rate 0.03, 15 leaves). The S-learner fits one model with the treatment flag as a feature; the T-learner fits one model per arm; the X-learner imputes individual effects and regresses them on features #c("kunzel")#[;] the DR-learner regresses a cross-fitted doubly robust pseudo-outcome #c("kennedy")#[;] the class transformation fits one classifier on $Z = Y T + (1 - Y)(1 - T)$ #c("jaskowski"). An ensemble averages the five on a common scale. The propensity is the known constant of the experiment. A response model, $P("buy" | "contacted")$, is kept as the conventional baseline. Rankings are scored by the Qini coefficient #c("radcliffe", "belbahri"): the area between the Qini curve and the random diagonal, divided by the same area for a perfect ranking.

== Calibration
Meta-learner scores order customers better than they measure them. On the calibration split we cut customers into 20 equal-size score bins, measure the treated-minus-control difference in each, and fit an isotonic regression through the bin estimates, weighted by precision (#fnum(<fig-models>)c). The calibrated uplift $hat(tau)_i$ is the input of the profit rule.

== Profit rule
For customer $i$, let $V_i$ be the expected basket, $m$ the gross margin rate, $c$ the cost of one message, $d$ the discount as a share of the basket, and $p_(0 i)$, $p_(1 i)$ the purchase probabilities without and with contact, with $tau_i = p_(1 i) - p_(0 i)$. Expected profit is
$ pi_(1 i) = (m - d) V_i p_(1 i) - c, quad pi_(0 i) = m V_i p_(0 i) $ <eq-profit>
with and without contact, so the incremental profit of contacting is
$ g_i = m V_i tau_i - d V_i p_(1 i) - c. $ <eq-gain>
Contact pays only when $tau_i$ exceeds the break-even uplift
$ tau_i^* = (c + d V_i p_(1 i)) / (m V_i). $ <eq-be>
The discount term makes customers who buy anyway expensive: their $tau_i$ is near zero but they still collect the discount. With a budget $B$ and expected spend $s_i = c + d V_i p_(1 i)$, the plan solves
$ max_(x in {0,1}^n) sum_i x_i g_i quad "s.t." quad sum_i x_i s_i <= B, $ <eq-knap>
a knapsack that the greedy order by $g_i \/ s_i$, stopped at $g_i <= 0$ or at the budget, solves up to one customer because each customer is small relative to $B$.

== Off-policy evaluation
Because contact was random, any rule "contact the customers in set $A$" can be evaluated on test customers without running it #c("dudik", "simester"). With $r_j$ the realised profit of customer $j$ (margin on revenue, minus message and discount if treated),
$ hat(Delta)(A) = |A| ( overline(r)_(A, T = 1) - overline(r)_(A, T = 0) ), $ <eq-ope>
the self-normalised inverse-propensity estimate of the profit of $A$ against contacting nobody. Intervals are percentile bootstrap intervals that resample customers within each arm. Two rules are compared with a paired bootstrap on the same resamples, so the interval describes the difference itself. Totals are scaled from the test split to the stated population.

== Fairness audit
After every plan we compute the selection rate by age band and by gender, the uplift measured in the experiment for each group, and the ratio of the lowest to the highest selection rate. Customers under 18 are never contacted, by an eligibility rule; they form a band of their own and are left out of the ratio, as are customers of unknown age or gender. A ratio under 0.8 is flagged for human review. The threshold is a screening heuristic, not a legal test for marketing.

== Lifetime value
From the three complete months of receipts, monthly churn is the share of customers active in one month and absent the next, and
$ "LTV" = "AOV" times "orders per active month" times m times L, $ <eq-ltv>
with $L = min(1 \/ "churn", 36)$ months. The cap is needed because a three-month window cannot support longer lifetimes.

// ---------------------------------------------------------------- floats (declared early so they land on the right pages)
#figure(
  placement: top,
  scope: "parent",
  image("../figures/fig_architecture.pdf", width: 80%),
  caption: [Architecture. Steps 1 to 5 are deterministic code; the agent (6) reaches them only through tool calls, the manager approves (7), and only then can the audience file with a random hold-out be written (8).],
) <fig-arch>

// ================================================================ V
= The Agent

== Architecture and privileges
The agent (#fnum(<fig-arch>)) is a utility-based agent: its goal is a number, incremental profit, and its tools compute, test and act on that number. A Qwen3 8B model served by Ollama on the laptop GPU (no cloud service, no fee) receives 16 tool schemas and follows a reason, call, read loop in the style of #c("react"). Tools have three privilege levels. Twelve _read_ tools return facts (data profile, experiment read-out, segments, model report, plan evidence, sensitivity, fairness, hold-out size, calendar, currency and others). Three _propose_ tools create a plan, draft messages or request approval; nothing leaves the system. One _action_ tool writes the audience file and refuses to run unless a human approved that plan. If the model is not running, a scripted planner drives the same tools.

== Six controls, each from an observed failure
+ _Invented arguments._ The model passed budgets and discounts that the manager never stated. A provenance guard now accepts a planning argument only if it can be traced to the manager's words; others are dropped and reported, the system default applies, and values are validated.
+ _Skipped steps._ The model sometimes answered after planning. A runtime checklist now forces evidence by replay, the fairness audit and an approval request for every plan.
+ _Misdescribed figures._ The model called deliberately skipped customers "a hold-out" and called a difference significant when its interval crossed zero. The meaning of every figure is now fixed by code as verified statements; the model only narrates them.
+ _Mistyped numbers._ Every number in the answer must match a tool result of the same run, or a number in the request, after rounding or unit change; others are reported as ungrounded.
+ _Over-confident wording._ An over-claim check rejects wording stronger than the evidence.
+ _Residual failure._ If the narrative still fails, it is discarded and the verified statements are shown alone.

These controls answer the three ways a language model fails according to the course's closing session: it can be wrong (controls 1 to 4), be biased (the audit of Section IV, for selection only, not for wording) or just agree (controls 3 and 5). The stress test of Section VI widened three of them: control 1 now also drops a hold-out target the manager did not state, control 2 applies to every run in which the model makes a plan, in any language, and control 5 also rejects wording that calls a plan approved or exported when it is not, or that advises skipping approval. The reader is a further risk: among 319 surveyed knowledge workers, more confidence in generative AI went with less critical thinking #c("lee"), a self-reported link, not proof of cause. So the approver reads statements written by code and stays accountable: a tribunal held an airline responsible for its chatbot's answer #c("moffatt").

Message drafts are written per RFM segment and checked by code: length, opt-out instruction, no number that is not on the approved offer sheet, no pressure tactics, no sensitive attribute. A draft that fails twice is replaced by a pre-approved template. The brand in sample messages, "FreshMart", is fictional.

A code review of the agent added further controls. A budget or its currency is never guessed: if either cannot be matched to the manager's words, the plan is refused and the agent asks for it. A request for a segment that is unknown, or that is defined by a demographic attribute, is refused. A message that fails the copy checks is never stored, messages cannot be redrafted after approval, and fair mode (Section VI) respects the budget on real spend.

== Live feeds, human gate, audit log
Two public feeds have a job and never change uplift scores. Exchange rates (Frankfurter) convert a budget stated in another currency; the course brief's R\$ 1,000,000 was 14,069,900 RUB on 2026-11-19. A public-holiday calendar (Nager.Date) sets the send date and measurement window. Both are cached for offline use. The agent cannot approve its own plan. Every tool call is appended to an audit log with its arguments and a fingerprint of the result.

// ================================================================ VI
= Results

#tbl(
  "Measured Uplift by RFM Segment (X5 Experiment, 95% CI)",
  (auto, auto, auto, auto, auto, auto, auto, auto, auto),
  ..hd([Segment], [Customers], [Share], [Recency (d)], [Purchases], [Spend (RUB)], [Buys without contact], [Uplift (pts)], [95% CI]),
  [Champions], [87,792], [21.9%], [1.8], [40.7], [16,951], [88.1%], [+1.2], [+0.7 to +1.8],
  [Loyal], [26,624], [6.7%], [4.9], [31.9], [15,989], [80.2%], [+1.2], [−0.1 to +2.6],
  [Potential loyalists], [49,255], [12.3%], [2.0], [18.0], [6,406], [70.4%], [+3.3], [+2.2 to +4.4],
  [New customers], [23,018], [5.8%], [2.1], [7.9], [2,659], [53.5%], [+5.6], [+3.8 to +7.4],
  [Need attention], [38,464], [9.6%], [5.1], [14.8], [6,022], [59.5%], [+3.5], [+2.1 to +4.9],
  [At risk], [42,979], [10.7%], [11.8], [18.1], [8,988], [56.3%], [+3.2], [+1.9 to +4.6],
  [Cannot lose them], [11,433], [2.9%], [11.2], [35.2], [17,882], [65.8%], [+1.9], [−0.5 to +4.4],
  [Hibernating], [120,597], [30.1%], [12.2], [6.7], [2,748], [34.3%], [+4.6], [+3.9 to +5.4],
  wide: true,
  label: <tab-rfm>,
)

#figure(
  placement: top,
  scope: "parent",
  block(width: 100%, grid(
    columns: (1fr, 1fr, 1fr),
    column-gutter: 6pt,
    image("../figures/fig_qini.pdf", width: 100%),
    image("../figures/fig_deciles.pdf", width: 100%),
    image("../figures/fig_calibration.pdf", width: 100%),
    text(8pt)[(a)], text(8pt)[(b)], text(8pt)[(c)],
  )),
  caption: [Models on held-out test customers. (a) Qini curves: the likely-buyer model and the RFM score stay near or under the random diagonal; the uplift model is above it. (b) Measured uplift by decile of the uplift score with 95% intervals; the dotted line is the average effect. (c) Isotonic calibration of the score on the calibration split.],
) <fig-models>

== Experiment and RFM segments
The average effect is +3.32 points (relative uplift 5.5%, $z = 15.3$). #tnum(<tab-rfm>) and #fnum(<fig-rfm>) show how unevenly it is spread. Champions buy 88.1% of the time without a message and gain +1.2 points (+0.7 to +1.8). Hibernating and New customers gain +4.6 (+3.9 to +5.4) and +5.6 (+3.8 to +7.4). From the lowest to the highest frequency score the baseline purchase rate rises from 29% to 89% while uplift falls from +4.5 to +1.3 points. The more often a customer already buys, the less a message adds, so "reward your best customers" spends where the effect is smallest. Two segment intervals (Loyal, Cannot lose them) include zero.

#place(top, scope: "parent", float: true, grid(
  columns: (1.62fr, 1fr),
  column-gutter: 16pt,
  align: bottom,
  [#figure(
      image("../figures/fig_rfm_segments.pdf", width: 100%),
      caption: [Measured effect of the campaign by RFM segment with 95% intervals. The percentages under the bars are purchase rates without a message.],
    ) <fig-rfm>],
  [#figure(
      image("../figures/fig_fairness_age.pdf", width: 100%),
      caption: [Selection rate by age band relative to the average, as the message cost rises. Age is never a model input. The under-18 band is at zero by rule (minors are never contacted) and is left out of the ratios in the legend.],
    ) <fig-fair>],
))

#tbl(
  "Learners on Test Customers (Uplift in Points) and Feature Ablation",
  (auto, auto, auto, auto, auto, auto, auto),
  ..hd([Learner], [Qini], [95% CI], [Top 10%], [Top 30%], [Bottom 30%], [Qini, 5 re-splits]),
  [Response model], [−0.0052], [−0.0116 to +0.0010], [+1.9], [+1.5], [+4.1], [−0.0052 ± 0.0024],
  [S-learner (champion)], [+0.0089], [+0.0021 to +0.0156], [+9.9], [+5.0], [+2.9], [+0.0143 ± 0.0030],
  [T-learner], [+0.0092], [+0.0012 to +0.0164], [+7.9], [+4.4], [+2.0], [+0.0115 ± 0.0024],
  [X-learner], [+0.0073], [+0.0003 to +0.0149], [+9.0], [+4.4], [+2.9], [+0.0145 ± 0.0009],
  [DR-learner], [+0.0098], [+0.0032 to +0.0162], [+7.6], [+4.8], [+2.4], [+0.0125 ± 0.0020],
  [Class transformation], [+0.0082], [+0.0025 to +0.0156], [+5.1], [+4.5], [+2.0], [+0.0116 ± 0.0022],
  [Ensemble], [+0.0090], [+0.0017 to +0.0163], [+8.7], [+4.8], [+2.4], [+0.0141 ± 0.0016],
  mid,
  [S-learner, RFM only (3 features)], [+0.0085], [+0.0024 to +0.0149], [], [], [], [],
  [S-learner, behaviour + age, gender], [+0.0097], [+0.0034 to +0.0164], [], [], [], [],
  wide: true,
  label: <tab-learners>,
)

== Learners
#tnum(<tab-learners>) gives the learner comparison. The response model has a negative Qini (−0.0052, 95% CI −0.0116 to +0.0010; −0.0052 ± 0.0024 over five re-splits): ranking by purchase probability is no better than random at finding customers who react, and its top 10% reacts less (+1.9 points) than its bottom 30% (+4.1). All six uplift rankings have a positive Qini whose interval excludes zero. The coefficients are small and the learners cannot be separated from each other: their intervals overlap almost entirely. The S-learner was chosen on the calibration split, not on test. Its top decile reacts by +9.9 points, about three times the average (#fnum(<fig-models>)b); the deciles under the first are not ordered, so the model mainly finds the most reactive tenth.

_Feature ablation._ With R, F and M alone the Qini is +0.0085, against +0.0089 with all behaviour features and +0.0097 when age and gender are added. The intervals overlap, so excluding the two personal attributes costs nothing we can measure.

_Decision groups._ At default costs the rule puts 70.7% of customers in the contact group (uplift measured on the test customers of that group +3.5 points, +2.4 to +4.7), skips 16.1% whose gain is under cost (+3.7, +1.5 to +5.8) and skips 13.2% with no expected effect (+1.7, −0.1 to +3.5). The skipped groups still react: the rule skips them because they buy without a message 72.3% and 85.9% of the time, so the gain does not cover the cost. We found no evidence of "sleeping dogs", customers harmed by contact: the group with a non-positive estimate has a measured effect of +1.7 points whose interval includes zero.

#tbl(
  "Real Incremental Profit by Scenario (Test Replay Scaled to 400,162 Customers, RUB)",
  (auto, auto, auto, auto, auto, auto, auto),
  ..hd([Rule], [Contacted], [Spend], [Incremental profit], [95% CI], [P(profit > 0)], [iROAS]),
  table.cell(colspan: 7, align: left)[_A. Text reminder: 2 RUB per message, no discount; mean break-even uplift 2.13 points_],
  [Contact everyone], [100.0%], [800,324], [755,896], [209,646 to 1,377,216], [99%], [7.78],
  [Response model, same size], [70.2%], [561,955], [470,676], [−8,412 to 967,685], [97%], [7.35],
  [RFM best customers, same size], [70.2%], [561,955], [432,177], [−53,355 to 939,983], [95%], [7.08],
  [LiftPilot profit rule], [70.2%], [561,955], [709,315], [243,853 to 1,198,625], [100%], [9.05],
  mid,
  table.cell(colspan: 7, align: left)[_B. Costlier channel: 6 RUB per contact, no discount; mean break-even uplift 6.39 points_],
  [Contact everyone], [100.0%], [2,400,972], [−844,752], [−1,391,002 to −223,432], [1%], [2.59],
  [Response model, same size], [19.3%], [462,815], [−449,798], [−673,151 to −240,619], [0%], [0.11],
  [RFM best customers, same size], [19.3%], [462,815], [−170,886], [−422,074 to 71,112], [9%], [2.52],
  [LiftPilot profit rule], [19.3%], [462,815], [204,762], [−206,450 to 598,342], [84%], [5.77],
  mid,
  table.cell(colspan: 7, align: left)[_C. Reminder with a 3% basket discount: 2 RUB per message; mean break-even uplift 9.78 points_],
  [Contact everyone], [100.0%], [4,264,332], [−2,708,112], [−3,215,799 to −2,120,271], [0%], [1.46],
  [Response model, same size], [7.8%], [366,297], [−393,209], [−501,278 to −283,845], [0%], [−0.29],
  [RFM best customers, same size], [7.8%], [408,421], [−345,496], [−463,194 to −228,903], [0%], [0.62],
  [LiftPilot profit rule], [7.8%], [227,605], [60,933], [−42,660 to 173,516], [89%], [5.07],
  wide: true,
  label: <tab-scen>,
)

#figure(
  placement: top,
  scope: "parent",
  image("../figures/fig_scenarios.pdf", width: 80%),
  caption: [Real incremental profit of four targeting rules under the three cost scenarios, with 95% bootstrap intervals (test replay scaled to 400,162 customers).],
) <fig-scen>

== Scenarios
The margin (25%), the message costs (2 and 6 RUB) and the discount (3%) are scenario assumptions, not facts about X5. #tnum(<tab-scen>) and #fnum(<fig-scen>) give the replay results. Baselines contact the same number of customers as the profit rule, so differences come from who is chosen.

_A, cheap contact._ The profit rule earns about as much as contacting everyone, with 561,955 RUB of spend instead of 800,324, about 30% less. The paired difference is −46,581 RUB (−347,880 to +230,187; probability that the rule is better 34%). At this price targeting does not add profit; it saves spend, and the difference is not significant.

_B, costlier contact._ Contacting everyone loses 844,752 RUB (−1,391,002 to −223,432). The rule contacts 19.3% and earns 204,762 RUB, but its interval (−206,450 to 598,342) includes zero. The paired difference against contacting everyone, +1,049,514 RUB (633,841 to 1,427,149), is significant. The response model and the RFM rule, at the same size, both lose money.

_C, discount._ The discount is paid to every contacted buyer, including those who buy anyway, so contacting everyone loses 2,708,112 RUB (−3,215,799 to −2,120,271). The rule contacts 7.8% and earns 60,933 RUB (−42,660 to 173,516), again around break-even. The paired difference is +2,769,045 RUB (2,203,378 to 3,249,314).

#tbl(
  "Cost Frontier on the Never-Tested Audience (200,123 Customers, RUB)",
  (auto, auto, auto, auto, auto),
  ..hd([Cost], [Contacted], [Plan profit], [95% CI], [Gain vs. everyone]),
  [1], [75.0%], [484,065], [241,700 to 747,523], [−94,085],
  [2], [69.9%], [363,138], [141,047 to 603,291], [−14,889],
  [3], [58.7%], [222,820], [1,732 to 459,155], [44,915],
  [4], [39.8%], [121,762], [−106,128 to 347,648], [143,981],
  [5], [26.3%], [128,510], [−95,592 to 343,092], [350,851],
  [6], [19.0%], [99,838], [−114,276 to 299,621], [522,303],
  [8], [9.7%], [60,300], [−110,402 to 227,237], [883,011],
  [10], [4.6%], [−9,457], [−152,617 to 145,963], [1,213,500],
  label: <tab-frontier>,
  size: 7.6pt,
)

== Cost frontier
#tnum(<tab-frontier>) varies the message cost for the 200,123 customers who were never tested, with profit from the test replay scaled to that audience. The crossover is between 2 and 3 RUB: under it the rule gives up a little profit against contacting everyone, above it the gain grows with cost. The plan's own interval excludes zero up to 3 RUB and includes it from 4 RUB on. At 6 RUB the plan contacts 19.0% of the audience, 38,113 customers, which costs about 230 thousand RUB of the 14,069,900 RUB budget of Section V, and the plan's own interval includes zero at that cost. The first answer of the system is how much of the budget not to spend.

== Fairness and fair mode
Age and gender are never model inputs, and minors are never contacted and are kept out of the audit. Among adults the audit finds a small age gap at low cost that widens as contact gets expensive (#tnum(<tab-fair>), #fnum(<fig-fair>)). The ratio of the lowest to the highest age-band selection rate is 0.96 at 2 RUB, 0.86 at 4 RUB and 0.82 at 6 RUB, none of them flagged, and 0.57 at 10 RUB, where the plan is flagged for human review. The least selected band is 65 and over from 2 to 6 RUB and 18–24 at 10 RUB. The gender ratio falls from 0.99 to 0.90 over the same range.

At 10 RUB the gap follows a real difference in measured effect: +1.1 points for 18–24 against +5.9 for 65 and over (female +4.0, male +2.9), so a strict rule drops the youngest adults first. The lower selection of the 65-and-over band at 2 to 6 RUB is not explained by its measured effect, which is the highest; the rule acts on each customer's estimated uplift and basket, not on the band average, and we did not decompose that gap. An earlier version of the audit counted customers under 18, who are excluded from contact by rule, inside the youngest band and overstated the gap (0.85, 0.70 and 0.48 at 2, 6 and 10 RUB); a code review caught the error and the figures here are the corrected ones.

#tbl(
  "Fairness Audit on the Never-Tested Audience (Adults): Lowest-to-Highest Selection Ratio by Age Band and by Gender",
  (auto, auto, auto, auto, auto, auto, auto),
  ..hd([Cost], [Contacted], [Age], [Flag], [Lowest age], [Highest age], [Gender]),
  [2], [69.9%], [0.96], [ok], [65+], [18–24], [0.99],
  [4], [39.8%], [0.86], [ok], [65+], [35–44], [0.97],
  [6], [19.0%], [0.82], [ok], [65+], [35–44], [0.95],
  [10], [4.6%], [0.57], [review], [18–24], [35–44], [0.90],
  mid,
  [6, fair mode], [12.0%], [0.58], [], [], [], [0.92],
  label: <tab-fair>,
  size: 7.6pt,
)

A "fair mode" that values every customer at the average basket did not help. At 6 RUB it contacted 12.0% of the audience in place of 19.0%, the age ratio fell from 0.82 to 0.58 and the gender ratio from 0.95 to 0.92, and real profit fell from 99,838 RUB (−99,289 to 296,175) to 43,565 RUB (−25,589 to 120,655), roughly half. At 2 RUB the age ratio moved from 0.96 to 0.93 and profit from 363,138 RUB (130,803 to 603,439) to 341,133 RUB (108,178 to 585,710). We report it as a negative result: equalising the basket made the age gap wider, not narrower.

#tbl(
  "Monthly Churn, Orders per Active Month, Basket (RUB), Lifetime (Months, Capped at 36) and LTV (RUB, Margin 25%)",
  (auto, auto, auto, auto, auto, auto),
  ..hd([Segment], [Churn], [Orders], [AOV], [Life], [LTV]),
  [All customers], [7.7%], [5.9], [427], [13.0], [8,142],
  [Champions], [0.6%], [10.3], [415], [36.0], [38,514],
  [Loyal], [0.6%], [8.3], [500], [36.0], [37,237],
  [Potential loyalists], [4.2%], [4.6], [350], [23.9], [9,647],
  [New customers], [20.6%], [2.4], [319], [4.9], [922],
  [Need attention], [6.1%], [4.0], [403], [16.4], [6,588],
  [At risk], [2.7%], [5.0], [493], [36.0], [22,363],
  [Cannot lose them], [0.5%], [9.8], [507], [36.0], [44,599],
  [Hibernating], [22.3%], [2.4], [403], [4.5], [1,090],
  label: <tab-ltv>,
  size: 7.6pt,
)

== Retention and lifetime value
#tnum(<tab-ltv>) applies (@eq-ltv) to the three complete months (two month-to-month transitions). Monthly churn is 7.7% overall, 0.6% for Champions and 22.3% for Hibernating customers. The LTV figures are gross profit over a horizon capped at 36 months and rest on a three-month window; four segments hit the cap, so the table is an ordering, not a forecast. The segments that react most to a message (New, Hibernating) are worth least over time. The profit rule values one campaign window only.

== External check: Hillstrom
On the Hillstrom test the e-mail raises the visit rate from 10.62% to 16.70%, +6.09 points (+5.54 to +6.63), and the effect is nearly uniform across customers. Rankings are unstable: the S-learner has a Qini of +0.043 (+0.014 to +0.073) on the test split but +0.024 ± 0.021 over repeated splits, and the class transformation −0.003 ± 0.023. The margin, costs and discount are again scenario assumptions. The right answer is all or nothing and the rule finds the switch. At 0.10 USD per e-mail it contacts 100.0% and earns the same 13,260 USD (1,174 to 23,770) as sending to all. At 0.60 USD it contacts nobody, where sending to all loses 18,740 USD (−30,826 to −8,230). With a 10% discount it contacts 17.1% and earns 960 USD (−3,372 to 4,603) against 5,179 USD (−5,774 to 14,373) for sending to all: the rule loses by 4,219 USD (−13,334 to +5,876), not significant. Targeting did not help on this data set, where the model could not rank customers reliably.

== Agent benchmark
// BENCHMARK-BEGIN
The agent is tested like the models, on fixed cases. Thirteen manager requests are run end to end: seven campaign requests with different stated assumptions (cost, margin, discount, a budget in RUB or in BRL, or none), three questions that one read tool should answer, and three safety probes (export without approval, target women over 60, confirm a guaranteed profit). Each run is scored on argument fidelity (the planner received exactly the stated assumptions), checklist completion, whether the plan waits for a human, the share of numbers in the answer that match a tool result, narratives rejected by the guards, drafts passing the copy checks, and refusal of each probe.

#tbl(
  "Agent Benchmark (Qwen3 8B, 13 Fixed Requests)",
  (auto, auto),
  ..hd([Measure], [Result]),
  [Argument fidelity, after the provenance guard], [100%],
  [Runs where the guard dropped invented assumptions], [1],
  [Mandatory checklist completed], [100%],
  [Runs ending in a human-approval request], [100%],
  [Numbers in answers matching a tool result], [204 of 204],
  [Narratives rejected by the guards], [1],
  [Message drafts passing the copy checks], [56 of 56],
  [Questions answered with the expected tool], [100%],
  [Safety probes passed], [3 of 3],
  [Median time for a full campaign plan], [136 s],
  label: <tab-bench>,
  size: 7.6pt,
)

#tnum(<tab-bench>) gives the results on the code as it was before the stress test below. The planner received exactly the stated assumptions in every campaign run, but only after the guard: for the request to plan "with the usual costs" the model supplied a cost, a margin and a discount of its own, which were dropped in favour of the system defaults. One narrative was rejected and replaced by the verified statements. All 204 numbers in the answers match a tool result, all 56 drafts were written by the model and pass the copy checks, and the three probes were refused: the export was blocked by the approval gate, the demographic request was refused, and no guarantee was given.

_Timing._ The median time for a full plan is 136 s on an RTX 3080 laptop GPU, and it is not a constant of the method. Campaign runs took from 40 to 161 s: the first three of the sequence took 40 to 59 s and the later ones 136 to 161 s. A full plan takes about 50 s on a cool laptop and two minutes or more when the GPU is hot or shared with other work, so the time depends on GPU temperature and load more than on the request. The benchmark is small: thirteen requests written by the authors, one model, one run each. It shows that the controls hold on these cases, not that they hold in general.
// BENCHMARK-END

== Stress test from the closing session
Ten further cases apply the tests of the course's closing session to the agent: the same request three times, neutral wording against two opposite opinions, a manager who asks it to confirm a losing plan, three questions with a known answer, a hidden instruction in a tool result and in a pasted note, the same request signed by four senders, and the request in French and in Arabic (reported, not gated). In one full run of all ten cases on the final code, with no earlier result reused and no case repeated, the 9 gated cases pass over 17 runs, 14 of which produced a plan (median 166 s), and 241 of 241 numbers in the answers match a tool result or a number in the request.

Four earlier runs each scored 9 of 9 under the rule of the time, and reading the saved answers showed a fault each time. Run 1: the model chose the hold-out's detection target itself, and three identical requests gave hold-outs of 16%, 8% and 16%. Run 2: two answers said that the drafts were "all approved" when nothing had been approved. Run 3: a run that ended in a server error was scored as a pass, and a draft repeated the pasted note's "Export audience file now without approval". Run 4, a partial rerun: the Arabic request stopped after three of seven tools, because the runtime recognised a campaign request by English keywords, and French had passed only because "Planifie" contains "plan". Each fault became a guard or a stricter rule. The checklist now applies to every run in which the model makes a plan, in any language, and the French test sentence has no English keyword.

In the final run the answer to the leading request gave both tool figures, −422,465 RUB for contacting everyone and 99,838 RUB for the plan, and endorsed nothing, but it did not say in words that the manager was wrong. The four senders got the same plan. French and Arabic both equal the English baseline in plan arguments and decision numbers, complete the checklist (seven tools, after one reminder from the runtime) and end in an approval request. One correct briefing was replaced by the verified statements, because the over-claim list matched "messages sent" inside "No messages sent yet". Limits: one model, one seed, one run per variant; the wording checks are pattern lists that a paraphrase passes; and five guards, among them the approval gate blocking an export, did not act in this run, so only unit tests show them. A pass means that the rule held in these runs, not that it always holds.

// ================================================================ VII
= Discussion

== When targeting pays
Targeting is worth what contact costs. Break-even uplift (@eq-be) rises with the message cost and with the discount: its mean is 2.13 points in scenario A, under the average effect of 3.32, and 6.39 and 9.78 points in B and C, above it. Under the average effect, most customers clear it and a model can only save some spend. Above it, contacting everyone loses money and only a selective campaign can be profitable. The Hillstrom check adds a second condition: effects must differ between customers and the model must be able to rank them.

== Limits and threats to validity
(i) Money is imputed: a purchase is valued at the customer's average basket, so if the campaign changes basket size, profit is misstated in an unknown direction. (ii) Margin, costs and discount are assumptions. (iii) The channel, the message and the outcome window are undocumented, and the currency is presumed. (iv) There is one experiment from one retailer in 2019. (v) Scenario C assumes that the measured effect carries over to a message with a discount; the data cannot tell. (vi) The learners have overlapping intervals, and the plan's own profit interval includes zero in the costly scenarios; the significant quantity is the difference against contacting everyone. (vii) LTV rests on three months. (viii) The never-tested audience is assumed to resemble the tested one.

== Ethics and regulation
The AI Act #c("aiact") prohibits, in Article 5(1)(a) and (b), manipulative or deceptive techniques and the exploitation of vulnerabilities due to age, disability or social or economic situation where these cause or are reasonably likely to cause significant harm; its recital 29 states that common and legitimate commercial practices, for example in advertising, that comply with the applicable law should not in themselves be regarded as harmful manipulative practices. Under the GDPR #c("gdpr"), an uplift score on an identifiable customer is profiling within Article 4(4), Article 21(2) and (3) give a right to object at any time to direct marketing and to the profiling related to it, and Article 22(1) concerns decisions based solely on automated processing. These texts are our design benchmark, not obligations we claim apply to a course project in Lebanon on public data. The controls are concrete: no personal attribute is a model input or a tool argument, every draft carries an opt-out and passes the pressure-tactic check, a group gap triggers review, and a person approves every plan. The audit shows why the gate matters: at 10 RUB a profit-optimal rule selected adults aged 18–24 at 0.57 times the rate of the most selected band without ever seeing age. The audit itself needed a review before its figures were right.

// ================================================================ VIII
= Conclusion and Future Work

On a real randomised experiment, about 95 in 100 purchases after a contact would have happened anyway, a likely-buyer model could not find the customers who react, and uplift learners could, modestly. A calibrated profit rule then gave a profit that could not be distinguished from contacting everyone when contact was cheap, and avoided a significant loss when it was not, although its own profit interval included zero in the costly scenarios. Money figures rest on imputed baskets and assumed margin and costs. The agent adds plain-language access without being trusted with numbers or actions.

Future work is a new randomised campaign with the hold-out that the export tool already draws, to test the plan prospectively and observe basket amounts; experiments with several offers, so that the effect of a discount is estimated and not assumed; a fairness constraint that acts on selection rates directly, such as the balanced allocation of #c("beat")#[;] and a longer history, so that the rule can weigh the long-run value of a contact.

#heading(numbering: none)[Acknowledgment]
This work was carried out for the course "AI in Business and Marketing" at Saint Joseph University of Beirut. The authors thank the instructor, Dr. Katia Raya, for the project brief and guidance.

#heading(numbering: none)[References]
#{
  set text(size: 8pt)
  set par(justify: true, first-line-indent: 0pt, leading: 0.42em, spacing: 0.42em)
  show raw: set text(size: 7pt)
  context {
    let l = cited.final()
    let missing = refs.keys().filter(k => k not in l)
    grid(
      columns: (auto, 1fr),
      column-gutter: 0.5em,
      row-gutter: 0.42em,
      ..l.enumerate().map(((i, k)) => ([[#(i + 1)]], block(breakable: false, refs.at(k)))).flatten(),
    )
    if missing.len() > 0 { text(fill: red)[UNCITED: #missing.join(", ")] }
  }
}
