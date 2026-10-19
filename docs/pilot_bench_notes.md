# Pilot: survey-design-aware benchmark for synthetic activity schedules (NHTS 2017)

Status 2026-10-19: feasibility sprint, NOT peer reviewed, NOT released. Code `tools/pilot_bench/`, results `paper/pilot/`,
literature pass `docs/lit/`. Decision recorded: conditional GO (see "Go/no-go").

## Protocol
Households are split 50/50 at random (5 splits, seeds 1000..1004). Models are fitted on the train half and generate one day per
held-out person given that person's covariates (age band, worker, vehicles, weekend). For a statistic,
z = (model - test) / sqrt(se_test^2 + se_train^2) with JKn standard errors of the two half-sample domain estimates.
Split-half reference (real train half vs real test half): mean z^2 = 0.97, so z is calibrated.
Schedules are compared at activity level (travel time absorbed into the destination activity; the format caveat/acteval use).

## Results
Split 0, all models (5 splits for resample and CART):
| model | mean z^2 | C2ST pMSE (real-vs-real null 0.0032 +- 0.0009, 25 runs) | AUC | MIA advantage |
|---|---|---|---|---|
| weighted resample, fine cells | 0.92 (0.48-1.11 over 5 splits) | 0.0072 (0.0069-0.0074) | 0.60 | 0.256 (0.252-0.267): copies train days |
| CART, weighted donors | 2.34 (0.76-2.34) | 0.0108 (0.0108-0.0121) | 0.63 | 0.019 (0.009-0.019) |
| Markov + duration | 7.12 | 0.0502 | 0.80 | 0.008 |
| caveat, paper-scale (4x256 CVAEContLSTMCP, Colab, 6211 s) | 16.60 | 0.0717 | 0.91 | 0.006 |
| caveat, small CPU config | 60.0 | 0.0833 | 0.92 | -0.001 |
| caveat, first mis-configured run | 233.3 | 0.1076 | 0.94 | 0.012 |
Caveat days are home-based by construction, ours are not always, so `ends_at_home` / `home_at_23` penalise it (data mismatch, not model quality).

## Frame effect (EMD distance / real-vs-real floor, mean over 5 splits; min-max in brackets)
| | frame | resample | CART | caveat (split 0 only) |
|---|---|---|---|---|
| participations | unweighted | 2.9 (1.3-5.3) | 3.5 (1.7-5.9) | 3.3 |
| | weighted | 1.1 (0.9-1.6) | 1.4 (1.0-1.8) | 1.3 |
| timing | unweighted | 2.2 (2.0-2.6) | 2.6 (2.2-3.1) | 7.3 |
| | weighted | 1.1 (1.1-1.2) | 1.2 (1.1-1.3) | 3.1 |
| transitions | unweighted | 2.8 (2.6-3.1) | 3.8 (3.6-3.9) | 4.8 |
| | weighted | 1.1 (1.0-1.2) | 1.4 (1.1-1.6) | 2.6 |
The floor itself is about 2-3x larger in the weighted frame. On participations (split 0 for caveat) the caveat-vs-resample order flips between frames:
caveat 3.3 vs resample 4.4 in the unweighted frame (caveat better), caveat 1.3 vs resample 1.0 in the weighted frame (caveat worse). Caveat is ahead of
CART on participations in both frames (3.3 vs 5.1; 1.3 vs 1.5), so the CART order does not flip there. One split only: UNCONFIRMED.

## Effect size of ignoring the weights (`paper/pilot/sample_vs_population.csv`)
Unweighted sample vs survey-weighted population: trips/person +3.5% (6.6 SE), minutes at work -4.0% (3.8 SE), maintenance +7.7% (5.3 SE),
leisure +4.3%, school -26.3% (15.6 SE). A model trained and scored unweighted reproduces the sample, not the population.

## Literature status (docs/lit, first pass only)
Keyword scans of the full text of Shone & Hillel, DeepAM, Kim & Bansal, Borysov et al., Abbasi et al. found no use of survey weights or survey
sampling error in the evaluation; two treat the sample as the population. NOT a systematic proof. Closest neighbours: Mensah et al. 2025
(bootstrap CIs for population-synthesis robustness; full text NOT read) and Snoke et al. 2018 (pMSE with analytic null). Novelty claim: to verify.

## Go/no-go
Conditional GO as (a) a pynhts evaluation module + software paper (safest) and (b) a methods/benchmark paper only if: the rank-flip is confirmed on
>= 5 splits with a second trained model or a weighted caveat, Mensah et al. is read, and a second wave (2022) is added.

## Limits
One survey wave; one deep model trained once at paper scale; C2ST/MIA from one synthetic draw; schedule-level (no travel state) comparison;
caveat data mismatch (home-based); weights ignore JKn dependence between the two halves (calibration supports this); EMD floors from acteval
are unweighted by construction, the weighted frame is built by person re-draws.
