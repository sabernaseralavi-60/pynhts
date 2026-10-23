# AGENTS.md: using pynhts correctly (for AI agents and for humans in a hurry)

`pynhts` gives typed, survey-weighted access to the US National Household Travel Survey: waves **2001,
2009, 2017, 2022**. Nothing earlier is supported. Read this page before writing analysis code; every rule
below was a real silent error found in the data (see `docs/guards.md`, `docs/opus_review_0.4.0.md`).

## Ask the package before you assume

```python
import pynhts
pynhts.concepts.find("VEHAGE", 2009)     # what the variable means, top-code, national-only, comparability
pynhts.describe("TRPTRANS", 2017)        # codebook facts + top-code + the concepts that use it
pynhts.concepts.table()                  # the 44 concepts x 4 waves (grade C / H / N)
pynhts.harmonize.compare_waves(2009, 2017)   # which same-name variables really are the same
```

## The twelve rules

1. **Use `data.survey(...)`, never a plain mean of rows.** It applies the weights and the wave's variance
   design (jackknife 2001/2009/2017, Taylor 2022). Subpopulations: `domain=`, never drop rows.
2. **Totals from trip weights are ANNUAL.** `WTTRDFIN` = 365 x the person weight (2001-2017). For daily rates use
   `pynhts.rates.daily_rate(data, "trips" | "miles", per="person" | "household")`. 2022 trip weights include a
   +10 % methods adjustment: 2.275 trips per person and day, not 2.078.
3. **Raw codes are not comparable across waves.** The same code means different things (`TRPTRANS` 08 =
   airplane, golf cart, motorcycle, bus; `URBAN` 1/2 swapped in 2001; `WHYTRP1S` has two numbering systems). Map with
   `pynhts.harmonize.apply_column(frame, "TRPTRANS", "mode")`; it reads the wave from the frame and refuses a wrong one.
   Available concepts: `harmonize.concepts()`. Check `category_report` for `comparable`.
   Race is not a non-Hispanic variable in any wave (Hispanic respondents sit inside White and the other groups):
   `harmonize.race_ethnicity(frame)` combines race with the separate Hispanic-origin question.
4. **Never pool weights across waves.** Compare shares, rates and distributions per wave; totals have
   different population bases (2022 excludes group quarters; 2001 includes children 0-4).
5. **2001 contains children aged 0-4; the other waves start at 5.** Use `min_age=5` or `harmonize.age_bands`.
6. **Top-coded values are not numbers**: age (88 = 85+ in 2001, 92 = 89+ later), vehicle age (35 = 25+ in 2009,
   40 = 33+ otherwise), vehicle year. Use bands. The estimators warn (`PynhtsWarning`); do not silence it.
7. **2001 national-sample-only columns** (`BESTMILE`, fuel economy, travel-period counts, the whole long-distance
   file) cannot be weighted with the full-sample weight without bias; pynhts warns.
8. **Defaults protect you; changing them is on you.** `skip="auto"` makes the skip code -1 NA in numeric columns;
   `missing="nan"` masks every non-answer code. `skip="keep"`/`missing="keep"` return raw codes.
9. **Universes differ** (education 16+/18+/14+, worker/driver ages, 2022 `PRMACT` non-workers only).
   `pynhts.concepts.get(name)["universe"]` says who is in.
10. **Say what you computed.** Every result frame carries `result.attrs["pynhts"]` (wave, table, weight, variance
    design, unit). Put the design sentence in a methods footnote (`pynhts.tables.note`) instead of writing your own.
11. **Fit regressions with the design, not around it.** `pynhts.models.fit(..., regime="design")` (or `compare_regimes`) gives weighted estimates
    with the wave's own variance; state which estimand you mean (respondents or population). Over 310 re-estimated coefficients of 8 published studies the
    design-aware standard error was a median 2.2 times the unweighted one, mostly from the unequal weights (see `docs/models.md`, `papers/02-nhts-ladder`).
12. **Score ML models without leakage.** NHTS rows of one household are dependent and SMOTE invents rows from neighbours: split by household and resample
    the training part only (`pynhts.validate.audit_classifier` reports how much a random-row, resample-first score is inflated).

## Canonical recipes

```python
d = pynhts.load(2009, replicates=True)                       # downloads/verifies on first use
s = d.survey("person", ["R_AGE", "WORKER"])
s.total(domain=(s.rows["R_AGE"] >= 16))                      # persons 16+, SE and MOE
pynhts.rates.daily_rate(d, "trips", per="person")            # 3.79 daily person trips per person
t = d.trips(["TRPTRANS"])                                    # frame knows its wave
t["mode"] = pynhts.harmonize.apply_column(t, "TRPTRANS", "mode")
pynhts.recipes.run("stt2009", d)                             # reproduce the published tables, with gaps reported
```

## Building analysis tables (0.7.0)

- Collapse trips to persons or households with `pynhts.aggregate.aggregate(...)` or `pynhts.features.create_*_features(...)`, never with a
  hand-written `groupby` plus a merge: they report orphans, missing inputs and the weight of the target table. Household features use the
  **household** weight; trip features the trip weight.
- `notna()` is not validity in coded columns (`-1` is a skip, `-7/-8/-9` non-answers): use `pynhts.valid(series)`.
- Member counts from the person file are lower bounds when `hh_n_unlisted > 0`; the official `WRKCOUNT`, `DRVRCNT`, `NUMADLT` are exact.
- To go from a research statement (sample rules, variables, weighting) to data, a sample-flow table, a Table 1 and figures in one step use
  `pynhts.study.Study(...).run(data)` (docs/study.md); `Complete(skip="ok")` keeps a skip (-1), the default removes it. `study.compare` grades against a
  paper's printed numbers; never adjust a rule to reach one.
- Split train and test **by household** (`transform.split_by_household`); fit transformations on training rows only.
- Compare waves with `pynhts.trends` (per-wave estimates); pool only with `trends.pool`, which refuses non-comparable concepts. Trip distance,
  trip counts and trip weights are not comparable across waves.

## Prior literature (0.10.0)

- Before modelling a topic, ask what earlier NHTS studies did and what the audit measured: `print(pynhts.compendium.advise("EV adoption"))`
  (a topic, an analysis mode such as `"classification"`/`"ZINB"`, or words). It reports the waves named, the model families, how many modelling abstracts name
  survey weights or a variance estimator, and the design pitfalls with numbers from the 22-study audit (SE inflation, lost significance, sign flips, SMOTE leakage).
- Find and cite: `compendium.search("bikeshare", wave=2017, model="logit")`, `compendium.to_bibtex(hits)`; `compendium.register()` lists the audited studies (P01-P24).
- The tags describe **abstracts**, not analyses: "does not name weights" never means "did not use weights". The compendium is the official list, not the literature
  (it includes grid-optimisation and news items, and most entries do not name the NHTS in their text). Read `docs/compendium.md` before quoting a count.


## What not to do

- Do not add waves before 2001, mask "suspicious" sentinel values without documentation, undo the 2022 trip
  adjustment, impute distances, or extend `pynhts.tours` beyond 2017 (it raises on other waves on purpose).
- Do not report a standard error from `survey_rows` of tours as if the tours were a sample: they share the
  person-day weight (that is the correct design, but say so).
- Margins of error use the convention of the published tables (`convention="fhwa"`); the textbook one is
  `convention="design"` (2009: multiplier 1 and 99 df; differences are about 0.5 %).

## Check yourself

`python agent_eval/grade.py --reference` prints the reference answers of 14 tasks that contain the traps above;
`python agent_eval/grade.py answers.json` grades an answers file (id -> number).
