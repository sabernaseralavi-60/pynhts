# Analysis plan (pre-registration-lite) - Paper 02: Design-aware re-estimation of the NHTS research literature

**Date written: 2026-10-23.** Written after the data-reproduction audit of 22 studies (docs/paper_data_audit) and after the
first three model reproductions (P01 Yang 2011, P03 Quinn 2016, P18 Jiao 2020) had been run during engine development; those
results were seen before this plan was frozen and are marked "seen" below. Everything else (P02, P06/P17, P11, P13-P15, P20,
P21, P22) was specified before its results existed.

Idea register: I-03 (docs/idea_register.md) is widened from "typology of unstated rules" to a quantitative question; the user
asked for it on 2026-10-23 ("reproduce the data of all papers, then the methods in general, then theorise"). I-02 (state-level
heterogeneity) stays a separate paper and its models are NOT run here.

## Question
Do the conclusions of published NHTS studies survive (a) a faithful rebuild of their data and models from the public file,
(b) the survey design the NHTS prescribes (weights and replicate-weight variance), and (c) a leakage-free validation design
for the machine-learning studies?

## Estimands
For every reproduced model: the published headline coefficient(s) or score(s) (E0), the same quantity under the paper's own stated
or inferred estimator (E1 = "paper-style"), and under the design-aware estimator (E2). Shifts are reported as: relative change
of the point estimate E2 vs E1, ratio of standard errors (design effect on the SE scale), sign flips, and changes of significance
at the 5 % level.

## Ladder (grades per study)
L0 sample rebuilt (audit); L1 descriptive tables rebuilt (audit); L2 model reproduced (published coefficient/score within the
printed precision = EXACT, <=5 % relative = CLOSE, otherwise GAP; no tuning of rules to reach a number); L3 design-aware
re-estimate computed. A study that cannot reach L2 stops at the highest level reached and the reason is recorded (external data,
unstated rule, model not specified).

## Models and regimes
* Logit, OLS, Poisson: IRLS; NB2 and ZINB: weighted maximum likelihood with analytic scores.
* Regimes: naive (unweighted, model-based SE), weighted (survey-weighted point estimate, household-clustered sandwich SE), design
  (weighted, wave's replicate-weight variance: JKn 98 replicates 2017, JK2 100 replicates 2009, delete-one 99 replicates 2001).
  Replicate estimates of NB/ZINB by Newton/chord steps from the full-sample optimum (validated against exact refits, tests/).
* Weights are scaled to the sample size for point estimation; replicate variance is scale-free.
* Machine learning: random-row split (the studies' design) versus split by household (and by state for the household-level
  regression); resampling (SMOTE) before versus after the split; survey-weighted scores; 3 seeds (a second seed set is the
  stability repeat required by the civil-engineering ML standard).

## Hypotheses and decision rules (fixed here)
H1 Point estimates of weighted published models are reproduced (L2 EXACT/CLOSE) when the paper used weights; fail otherwise.
H2 Design-aware standard errors are larger than model-based ones by a median ratio above 1.5 across all reproduced coefficients.
H3 At least 10 % of coefficients that are significant under paper-style inference are not significant under design-aware inference.
H4 For the classification papers the published AUC is reproduced only under a pipeline in which resampled copies can reach the test
   set; under a household split AUC drops by more than 0.15.
Each hypothesis is reported as supported/not supported with the numbers; no threshold is changed after seeing results.

## Multiverse
Unstated sample rules are NOT explored here (they were in the audit). Within the model step the multiverse is: weights (none /
person / replicate), variance (model-based / sandwich / replicate), validation design (random / household / state), resampling order.

## Uncertainty
Replicate-weight variance; ML seeds 0-2 (mean and range); no multiplicity correction because the aim is descriptive across
studies; the share of flipped verdicts is reported with an exact binomial interval.

## Excluded (stated in the manuscript)
P04 (South Africa, not NHTS), P05/P16/P23 (variables from restricted or external files), P07, P09, P10, P19 (descriptive or
simulation studies without a regression to compare), P12 (sample not recovered), P24 (reserved for I-02), duplicates P08.

## Deviations from this plan
Logged 2026-10-23 after the external adversarial review of the draft (review items 3, 4, 13, 16, 17):
1. **Order of work.** P01 (Yang), P03 (Quinn) and P18 (Jiao) were run during engine development, before this plan was frozen; they hold 154 of the 310 coefficients and all three headline examples (stated in the manuscript).
2. **Grading tolerance.** The plan said ACCEPTABLE <= 5 %; the manuscript additionally gives a floor of two units of the last printed digit. Printed decimals are now stored per study (trailing zeros had been lost in the first grading; fixed).
3. **H3 reference estimator.** H3 is evaluated against each study's own declared inference (unweighted model-based for six studies, weighted with household-clustered errors for one); the study that itself used the jackknife (P03) is excluded. The first draft pooled all coefficients against the unweighted fit; both versions are reported. An exact binomial interval (promised in the plan) is added.
4. **H4 reformulated.** The plan said "the published AUC is reproduced only in a leaky pipeline". The result is that the printed value (0.924) is not reproduced by either pipeline (leaky 0.99, honest 0.64); what holds is the inflation (> 0.15 for three of five models). Reported as such.
5. **Seeds.** The tuned run uses two master seeds (plan: three); the default run uses three.
6. **Additional diagnostics not in the plan** (added because the review showed the first interpretation was wrong): decomposition of the standard-error ratio into weights, household clustering and the replicate formula; an unweighted household-clustered fit; a comparison of Newton and exact replicate refits on one real model.
7. **Targets of P13 and P15** (headline percentages from abstracts) cannot be mapped onto zero-inflated coefficients; they are no longer graded and these two models are re-estimated for design effects only.
