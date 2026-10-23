# Paper 02 (I-03 widened): design-aware re-estimation of the NHTS literature - working state

Started 2026-10-23 (user: "reproduce data of all papers, then methods, then theorise about package + narrative").
Idea register: I-03 (docs/idea_register.md) is the paper; user request of 2026-10-23 is the decision to start it.

## Environment (changed 2026-10-23)
* scipy/statsmodels/sklearn/xgboost/semopy now INSTALL (network recovered). Scratch venv: `%TEMP%/ml310` (python 3.13, pynhts editable).
  Run studies with `PYTHONUTF8=1 OMP_NUM_THREADS=6 %TEMP%/ml310/Scripts/python.exe papers/02-nhts-ladder/src/studies/pNN_*.py`.
* If `import yaml/packaging/pygments` breaks after a uv install: `uv pip install --reinstall <pkg>`.

## Engine (src/engine.py, src/countmodels.py)
Three regimes per model: `naive` (unweighted, model-based SE), `weighted` (weighted, cluster-robust SE),
`design` (weighted + replicate-weight jackknife SE of the wave). Logit/OLS/Poisson by IRLS (warm-start replicate refits);
NB2/ZINB by weighted analytic-score L-BFGS; replicate SEs of NB/ZINB by Newton/chord steps from the full-sample optimum
(`replicate_newton`, tests in tests/test_countmodels.py). BUG fixed 2026-10-23: full-sample optimum must be fitted on
sample-scaled weights, otherwise the replicate SEs are inflated 10-20x (first P18 run).

## Studies (src/studies/pNN_*.py -> results/tables/pNN_models.csv)
| id | paper | model | status |
|---|---|---|---|
| P01 | Yang 2011 | weighted logit ORs by age group | done; weighted ORs = published to 2 decimals; naive ORs differ (Midwest 0.83 vs 0.67) |
| P03 | Quinn 2016 | 4 logits (walk/bike x transport/commute) | done; weighted commute ORs = published; naive flips signs (bike commute edu GR 1.71 vs 0.41) |
| P18 | Jiao 2020 | NB weekday/weekend | rerun after bug fix |
| P14 | Zhang 2018 | ZINB ridesharing ~ vehicles (ll naive -82,622.9 vs published -82,654.8, n 218,831 vs 219,026) | rerun |
| P11 | Alberini 2021 | OLS ln miles ~ ln price/mile + FE | running |
| P20 | Shirgaokar 2021 | NB social trips | running |
| todo | P13,P15 (ZINB), P02/P12 (SEM), P05 (ZINB, external vars missing), P06/P17 (ML AFV/EV), P21 (GBM online shopping), P22 (PSM), P16, P23 (motifs), P24 (own 2025 ML), P07/P09/P10/P19 descriptive only |

## Published targets already read (keep)
* P22 PSM: matched drivers-with-access mean daily VMT freq 24.82, occ 25.86, non 25.41; non-driver/no access freq 6.25, occ 5.03, non 4.37; veh ownership diffs -0.065/-0.125/-0.190; matched triples 5,161; net +7.8 M VMT/day at alpha 0.6.
* P21 GBM R2 test 0.72 (2009) / 0.71 (2017); RF 0.66/0.65; SVM 0.59/0.56; LR 0.11/0.11; RMSE GBM 2.78/2.93 (16 vars of 48 by RFE).
* P02 SEM Table 4: prop_purchase<-prop_shoptrp 0.125, prop_shoptrp<-prop_purchase 0.214 (standardised, n 85,663).

## 2026-10-23 closing
Package 0.9.0 released (v0.9.0, PyPI). Paper commit 5f513ee. Remaining: AUTHOR-TODOs (co-authors, funding, competing interests), Zenodo new version, journal choice, I-02.
