# Changelog

## 0.9.0 (2026-10-23)

* **`pynhts.models`: design-aware regression.** `fit(data, rows, y, X, family=..., regime=...)` fits OLS (`gaussian`), logit (`binomial`), Poisson and negative binomial (`nb`, needs SciPy) under four regimes: `naive` (unweighted, model-based), `clustered` (unweighted, household-clustered sandwich), `weighted` (weighted, household-clustered sandwich; `cluster="none"` treats every observation as its own cluster) and `design` (the wave's variance: replicate-weight jackknife for 2001, 2009 and 2017, Taylor linearisation over strata and households for 2022). `compare_regimes` returns the four fits side by side with the standard-error ratios, sign flips and significance changes and warns when the design-aware fit changes a verdict. Never drops rows silently. Validated against R `survey::svyglm` (tools/validate_models_r.R, tools/validate_models_taylor_r.R; golden files in tests/golden): coefficients agree to 1e-5 and standard errors to 0.2 % (2017 jackknife) and 0.5 % (2022 Taylor); the negative binomial replicate variance (Newton/chord steps) is checked against exact refits.
* **`pynhts.validate`: leakage audit of classifiers.** `audit_classifier` scores a model under four pipelines (oversample before or after the split, rows or households, weighted AUC) and warns when the leaky one inflates AUC; `group_split`, `smote`, `weighted_auc` are available separately (NumPy only).
* **Evidence.** Paper 02 (`papers/02-nhts-ladder`) re-estimated 8 published regression studies (310 coefficients) and re-scored 5 classifiers of vehicle adoption: the design-aware standard error is a median 2.19 times the unweighted one, almost entirely because of the unequal weights; oversampling before splitting inflates the AUC of a random forest by 0.35. AGENTS.md rules 11 and 12, docs/models.md.
* New optional dependency group `models` (SciPy); `dev` now includes SciPy and scipy-stubs. 25 new tests.

## 0.8.1 (2026-10-22)

* **Release for citation and journal submission; no change to the package code.** Archived on Zenodo as 10.5281/zenodo.23575312 (all versions: 10.5281/zenodo.23573454). `LICENSE.txt` added (a copy of `LICENSE`, the name journals look for).

* **Zenodo DOI.** Version 0.8.0 is archived (10.5281/zenodo.23573455); the all-versions DOI is 10.5281/zenodo.23573454 (in `CITATION.cff` and the README). `.zenodo.json` holds the record metadata.

* **Paper audit re-check with the 0.8.0 Study and crosswalks** (`tools/paper_audit/recheck_p01/p02/p10_*.py`; docs only, no package change). Lidbe 2021: 262 of 280
  cells EXACT (Table 3 base = trips of persons with a valid `MEDCOND` answer; Table 4 weekend = `TRAVDAY` Saturday+Sunday, duration = `TRVLCMIN`, 72 of 72 condition-item
  cells via `condition_effect`); Yang 2011 sample reproduced as a `Study`; Zhou & Wang 2014 still partial. Conventions A-25..A-32.

## 0.8.0 (2026-10-22)

* **`pynhts.study`: from a research statement to data, tables and figures.** A `Study` (wave, unit, ordered sample rules `Keep`/`Drop`/`Complete`,
  variables, weight or explicitly none, stated assumptions; as objects, a dictionary or YAML) runs to a `StudyResult` with the analysis frame, the
  **sample-flow table**, a descriptive table (mean, sd, min, max, share; per group with the difference), `count_distribution` (zeros and users by band),
  a methods paragraph, a Markdown report, figures (flow, outcome distribution with its share of zeros, shares by group) and `compare`/`grade` against
  published numbers (EXACT / CLOSE / ACCEPTABLE / GAP). The skip code is not a non-answer (`Complete(skip=...)`); a variable may not share a raw column's
  name; the wave is checked. Docs: `docs/study.md`, example `docs/examples/ridesharing_35_states.yaml` (reproduces Zhang & Zhang 2018's sample to 0.09 %).
* **Cap flags** found in the paper audit: `PTUSED` is capped at 30 in 2017 (1,194 persons) and 2022 (42), `NWALKTRP` at 99 in 2009 (138); estimators and
  `quality.report` now warn about them. `concepts` `transit_use` states it.
* **Paper audit extended to 21 US papers** (`tools/paper_audit/p13..p23`, 11 new: sample flows, Table 1 and distributions rebuilt with pynhts and graded
  against the printed numbers; 9 of 21 SUFFICIENT; 9 recovered unwritten conventions in `docs/paper_data_audit/recovered_conventions.md`).
* **Race and Hispanic-origin crosswalks** (4 new `harmonize` concepts: `race_household`, `hispanic_household` for all four waves, `race_person`,
  `hispanic_person` for 2017 and 2022) and `harmonize.race_ethnicity(frame, level=)`, which combines race with the separate Hispanic-origin
  question into `hispanic` / `nh_white` / `nh_black` / ... because the race groups are not non-Hispanic in any wave. The statuses rest on a
  cross-tabulation of race against Hispanic origin in the four files: 2001 code 06 and 2009 code 07 ("Hispanic/Mexican") are 99.7 % and 98.7 %
  Hispanic, and the later waves file such respondents under "Some other race" (82 % Hispanic in 2017, 67 % in 2022). Consequence: `other` is
  comparable only from 2017 on; 2001 White, Black and American Indian absorb the "& Hispanic" codes (approximate); Black, Asian, American Indian,
  Pacific Islander and `multiple` are exact from 2009 on, **White only from 2017 on** (the independent review found that 2009's Hispanic race answer
  files 47.8 % of the Hispanic households under White against 69.0 % in 2017).
* `harmonize.variable_of(concept, wave)` and the `variable_by_wave` key of `concept_info`: some concepts have another column name in one wave
  (2001 `HHR_RACE`, `HHR_HISP`); `crosswalk()["variable"]` is now per wave. Existing concepts are unchanged.
* `concepts`: `race_household` is now grade H (was N, no crosswalk); new `hispanic_household`, `race_person`, `hispanic_person` (41 concepts; 44 with the medical-condition ones below).
* 8 new unit tests and 3 real-data tests (every quoted percentage is re-checked on the files).
* **Medical-condition crosswalks** (3 new `harmonize` concepts, all four waves): `medical_condition` (`MEDCOND`), `condition_duration` (`MEDCOND6`: six
  bands of 2001/2009 and three of 2017/2022 into `up_to_6_months` / `over_6_months` / `lifelong`) and `condition_effect` (`CONDTRAV`, `CONDNIGH`,
  `CONDPUB`, `CONDRIDE`, `CONDRIVE`, `CONDSPEC`). Cross-tabulation of the four files shows: `MEDCOND` is asked of ages 16+ in 2001 and 2009 and of everybody
  aged 5+ later (the 0.4.0 review table said 15+ for 2001 and 2009; the data say 16+); 2022 has 5.4 % non-answers among adults against 0.04 to 0.14 %
  before, so 2022 is `approximate` (the yes share of 18+ is 8.8, 10.5, 10.0, 7.5 %); the effect items are asked of every person aged 80+ in 2017 and
  2022 whatever `MEDCOND` says, 2022 is a select-all list, and the yes share falls on all six items from 2009 to 2017 with unchanged codes (cause
  undocumented), so only 2001 to 2009 are comparable. `concepts`: `medical_condition` and `condition_duration` grade H, `condition_effect` grade N (44 concepts).
  Docs: `docs/waves.md`, "Medical condition that makes travel difficult".
* 4 new unit tests and 4 real-data tests.
* **Independent adversarial review of this release** (`docs/review_0.8.0.md`, 3 P0, 3 P1, 10 P2, all reproduced on the real files; fixed here):
  * **P0 `pynhts.study`** variables and `Keep`/`Drop` rules read raw codes: the 2009 `PTUSED` hidden missing code 99 raised a mean from 1.467 to 1.814;
    `Drop(R_AGE < 18)` removed 496 refused ages and `Keep(TIMETOWK <= 60)` kept 259,474 person rows of which 157,774 are skips or non-answers (101,700 are real minutes); `kind="binary"` of a raw column gave a
    "share" of 120 %. Now variables and rules read a masked view (skip, non-answers and hidden codes missing; `raw=True` on a step selects the codes),
    and a binary column that is not 0/1 raises. Studies written before may select different rows (a refused age is no longer "under 18"); the
    Zhang & Zhang 2018 example still reproduces to 0.09 %.
  * **P1** 2009 White is `approximate` (Hispanic respondents are filed under White in 47.8 % of the Hispanic households in 2009, 69.0 % in 2017, 71.0 % in 2022);
    `StudyResult.figures()`/`save()` crashed for a count outcome; the study dropped the top-code and cap warnings.
  * **P2** the 2001 `MEDCOND` yes share is 8.8 % (not 8.7 %); `compare` matched category "1" to "10 ..." by prefix, graded a missing group against the first group and
    lost the printed precision (`grade("5.10", 5.14)`); `Keep` on a study variable failed; the name-clash guard checked only loaded columns; trip studies
    kept no trip key in 2022; a test that could not fail (race fallback: it fires for 15 households in 2009); `NWALKTRP` is flagged as capped in 2017 too
    (364 persons at 99); README said 16 crosswalks.
* 12 new unit tests and 4 new real-data tests for the review fixes.

## 0.7.1 (2026-10-22)

Fixes from an independent adversarial review of 0.7.0 (`docs/review_0.7.0.md`: 4 P0, 7 P1, 15 P2, all reproduced). **0.7.0 gave wrong numbers
in two places; upgrade:**

* **P0** The skip code `-1` was summed as a mile by `aggregate` and by `p_miles`, `hh_miles`, `hh_vmt` in 2001 and 2009 (now unknown, NaN).
  `trends.trip_shares("purpose")` read the wrong variable (now `WHYTO`). Weighted Spearman tie ranks and the `compare_groups` effect size corrected.
* **P1** Education universe is adults 18+; unknown-input companion counts added; `first`/`last` and duplicate rows on user frames guarded; frames default
  to `empty="nan"`; `trends.pool` drops 2001 children, renames raw codes and refuses unmapped coded columns; `hh_vmt` scope documented.
* **P2** `Where` compares codes unpadded and refuses type mismatches, `~Where` no longer matches NA; Kendall note; `split_by_household` independent of
  row order; `sample_characteristics` and plots corrected; four documentation statements corrected.
* 9 new unit tests and 4 real-data tests (one per fixed finding group).

## 0.7.0 (2026-10-22)

From access to analysis. No existing behaviour changed; new modules and helpers only.

* `pynhts.aggregate`: `aggregate(data, source, target, specs)` collapses trips, persons or vehicles onto persons or households with
  one result row per target row, orphan and unique-key checks, an explicit missing-value policy (`propagate` or `skip`), true zeros
  for targets without child rows, the target table's weight, and a diagnostics report in `attrs["pynhts_aggregate"]`. Declarative
  conditions (`Where`, `&`, `|`, `~`, `Custom`) and 14 functions (`n, count, sum, mean, median, min, max, std, quantile, nunique, any, share, first, last`).
* `pynhts.features`: registry of 89 features (person 19, household 56, trip 11, vehicle 3) with scientific meaning, sources, formula,
  eligibility, missing rule, denominator, weight and waves; creators for four levels; lineage in `attrs["pynhts_features"]`.
  Member counts equal the survey's own `WRKCOUNT` and `DRVRCNT` in all complete-roster households of all four waves. The person file is
  not always a complete roster (`hh_n_unlisted`: 14.5 % of 2001, 19.8 % of 2009, 7.0 % of 2017, 9.1 % of 2022 households).
* `pynhts.valid` and `answer_status`: real answers versus skip (-1) and non-answer codes (`notna()` is not validity in coded columns).
* `pynhts.eda`: `missing_report`, `describe`, weighted quantiles, `correlation_matrix` (Pearson, Spearman, Kendall; refuses nominal columns; no
  interval for weighted data), `cramers_v`, `association_matrix`, `compare_groups`, `compare_distributions`.
* `pynhts.quality.report`: key uniqueness, referential integrity, weight sanity and top-coded shares per table.
* `pynhts.transform`: `Transformer` (log, log1p, sqrt, Box-Cox, Yeo-Johnson, standardize, robust, winsorize, bins; fit on training rows, JSON
  parameters), `diagnostics`, `split_by_household`, `recommend`.
* `pynhts.trends`: `trip_shares`, `wave_means` (warns for non-comparable concepts), `pool` (refuses non-comparable concepts, requires explicit crosswalks, within-wave weights, always warns).
* `pynhts.tables`: `sample_characteristics`, `to_html`, `to_csv`, `to_excel`. `pynhts.viz.plots`: histogram, bar_share, wave_trend, corr_heatmap, save;
  every figure states weighting and sample size.
* Docs: `docs/analysis.md`, generated `docs/data/{FEATURES,VARIABLE_REGISTRY,CROSSWAVE_HARMONIZATION}.md`, `docs/development/REPOSITORY_AUDIT.md`,
  `docs/research/NHTS_RESEARCH_LANDSCAPE.md` with an evidence table, and `docs/paper_data_audit/` (ten published NHTS papers rebuilt from the public files).

## 0.6.1 (2026-10-22)

Corrections from an independent fact-check of the 0.6.0 documentation (`docs/factcheck_0.6.0.md`: about
263 statements checked, 10 false, 44 imprecise).

* **Crosswalk statuses that overstated equivalence:** `trip_class` HBW and HBO are `approximate` (2001 and
  2009 file work-related business trips under HBO, 2017 and 2022 under HBW: weighted HBW share 10.6, 11.6,
  13.7, 17.9 percent); `fuel` gasoline and alternative fuel are `approximate` (hybrids are gasoline in
  2001/2009 and code 03 in 2017); `purpose_1990` "other", "school_church" and "family_personal" are
  `approximate` (2017/2022 put change-of-mode segments in "other"; child care moves between classes);
  2017 `FUELTYPE` 97 is `only_here`; `urban_rural` is grade H (the delineation is dated differently and URBAN
  code 03 changes side).
* **New flags:** mileage variables are capped at 200,000 in every wave (kind `cap`), 2001 `VEHYEAR` and `YRTOUS`
  bottom codes; a column that is both capped and national-only warns about both.
* **Variance:** the 2017 `design` degrees of freedom is 97 (R's `svrepdesign(type="JKn")`, was the
  unverified 84); documentation states which numbers are R's and which are choices (the 2001 guide's
  example uses 2 x SE, so 99 df is ours).
* **Documentation:** Hispanic is a separate variable in all four waves; WHYTRP1S has two numbering systems,
  not three; -4 means "did not work at the usual workplace"; 2022 age imputation is documented in the
  Weighting Memo; the 2001 worker/driver universe, PRMACT universe, HHVEHCNT, trip distance in 2022, the
  fieldwork period of 2001, item non-response wording, the suspected-sentinel list (extended) and the
  unmasked suppression codes; `purpose_summary` has nine categories.
* **Agent tasks:** T14 states the multiplier and its trap is corrected (a naive standard error is 131
  thousand, larger, not smaller); T04, T10, T12, T13 name the denominator or definition and carry measured
  careless values.

## 0.6.0 (2026-10-21)

Added value for researchers and AI agents, from the plan of the adversarial review.

* **`pynhts.concepts`**: a machine-readable dictionary of 38 analysis concepts x 4 waves (variable of each
  wave, universe, unit, comparability grade C/H/N, harmonization, pitfalls, evidence);
  `concepts.find(variable, wave)`, `table()`, `get()`, `to_json()`; `describe()` now adds `topcode`,
  `national_only` and the concepts that use the variable. Tests check every variable against the schemas and
  the checkable statements against the real files (`tests/data/test_concepts_real.py`).
* **9 new crosswalk concepts** (`income`, `education`, `urban_area`, `urban_rural`, `density`,
  `vehicle_type`, `fuel`, `trip_class`, `purpose_1990`), status `nested` for exact collapses, `age_bands`
  that end at 85+; `harmonize.apply` accepts numeric codes and ignores zero padding.
  `WHYTRP90` 98/99 and the suppression codes `HHSTATE` "XX", `HH_CBSA` "XXXXX" are masked
  (`_schema/missing_overrides.yaml`).
* **`pynhts.rates.daily_rate`**: daily person trips or miles per person or household by the official route,
  with the unit in the result.
* **Variance conventions** (`convention="fhwa"` or `"design"`) for the jackknife waves, equal to R's `survey`
  package (`tools/validate_jackknife_r.R`, golden files `tests/golden/jackknife_2001_r.csv`, `..._2009_r.csv`).
* **AGENTS.md, llms.txt and an agent task harness** (`agent_eval/`): 14 questions with an oracle and a trap;
  `python agent_eval/grade.py --reference` / `answers.json`.
* Scheduled real-data workflow for NHTS 2022 (`.github/workflows/data.yml`); the visualization test skips
  without matplotlib.

## 0.5.0 (2026-10-21)

Guards and corrections from an adversarial review of 0.4.0 (`docs/opus_review_0.4.0.md`).
**Behaviour changes** (hence the minor version): `skip="auto"` is the new default and the 2001 and
2009 schemas mask more codes.

* **Safe skip default.** `skip="auto"` turns the appropriate-skip code -1 into NA in numeric columns
  (where it is never a quantity) and keeps it in coded columns. Before, `survey("trip",
  ["VMT_MILE"])` gave a mean of 5.36 in 2009 instead of 9.72 and total VMT 7 % low.
  `skip="keep"` restores the old behaviour.
* **More non-answer codes masked (2001, 2009).** Every labelled negative code (-3 no contact, -4 and
  -5 did not work last week, -6 odometer broken) is now a missing code of its own kind; 2009 mean commute time
  was 23.34 instead of 24.21 minutes. Schemas regenerated; the codebook-frequency tests still pass.
* **Top-codes and national-only columns** (`pynhts.core.flags`, `_schema/column_flags.yaml`): age
  (88 = 85+ in 2001, 92 = 89+ later), vehicle age (35 = 25+ in 2009, 40 = 33+ in the others), vehicle
  year, and the 2001 columns that exist only for the national sample (`BESTMILE`, fuel block,
  travel-period counts, the long-distance file). Estimators issue a `PynhtsWarning`.
* **Results know where they come from:** `DataFrame.attrs["pynhts"]` holds wave, table, weight,
  variance design and the unit of a total ("annual person trips", ...); `tables.note` writes the
  design of the wave (it said "delete-a-group jackknife, 98 replicates" for every wave);
  `harmonize.apply` raises when the frame came from another wave; `harmonize.apply_column`.
* `compare_waves`: new status `codes_permuted` (`URBAN` 2001/2009, `R_RELAT`, `WHYTO`, `WHYFROM`
  2017/2022), found by comparing labels with symbols kept.
* Crosswalks corrected against ORNL's own variables: Amtrak (2001, 2009) is "other transit" like
  the 2022 guide (summary `public_transit` now equals `PUBTRANS` for every trip of 2009, 2017,
  2022); 2001 `WHYTRP1S` 13 is `approximate` (39.7 % of those trips are school or religious).
* `data.tours()` raises unless the wave is 2017 or a `TourConfig` is passed (the 2017 purpose codes
  found no home-based-work tour in 2001 and 2009).
* `ratio_across` raises across different replicate systems or waves (2001 long-distance replicates
  belong to the national sample).
* 2009 travel-day weights of persons without trips (45,967) are filled with 365 x the person
  weights (registry `fill_from`), so person-day analyses can include non-travelers.
* **Documentation corrections:** the 45,967 persons without a 2009 `DAYWGT` are exactly the persons
  without trips (the 0.4.0 text said "no complete travel day"); 2001 children 0-4 were collected,
  not computed; top-codes exist in all four waves; the 2001 long-distance weight is the national
  weight x 365/28; new pages [Defaults and guards](docs/guards.md) and units in
  [Methods](docs/methods.md).
* Tests: unit `test_guards.py`; real-data `test_four_wave_guards.py` (negative codes, top-codes, national-only
  columns, defaults, wave tags, summary mode against `PUBTRANS`, replicate structure of all waves).

## 0.4.0 (2026-10-21)

Adds the **2009** and **2001** waves.

* **NHTS 2009** (release 2.1) and **NHTS 2001**: hash-pinned download of the data archives and of
  the separate replicate-weight archives (`Ascii.zip` holds CSV files; 2009 keeps them in the folder
  `Ascii/`), typed Parquet, `pynhts.load(2009)` / `load(2001)`, `pynhts fetch|info|register|docs
  --wave`. 2009 has four tables; 2001 adds `longdist` (one row per long-distance trip).
* **Schemas read from the PDF codebooks** (`tools/build_schema_pdf.py`; the 2009 data dictionary
  `.xls` has no codes and the 2001 codebook is Appendix B of the User's Guide). 3,435 (2009) and
  6,327 (2001) printed code frequencies reproduce, unweighted and weighted. Documented codebook
  problems: a control character in `MAKECODE` 35 (repaired by the data), a hidden missing code `99`
  in 2009 `PTUSED`, and printed `VEHTYPE` frequencies that do not match the file.
* **Jackknife for any replicate design:** the number of replicates, the multiplier (99/100 in
  2009, 98/99 in 2001, 6/7 in 2017), the degrees of freedom, the weight and stem names of each
  replicate file (renamed keys, zero-padded stems, SAS missing values) are registry data
  (`Registry.n_replicates`, `jackknife_factor`, `replicate_jobs`). Units without a weight
  (45,967 persons without a travel-day weight in 2009) are zeroed; a row that belongs to such a
  unit raises an error.
* Recipes `stt2009` (40 figures: 35 reproduced, 5 with a different margin-of-error convention)
  and `stt2001` (47 figures: 40 reproduced, 7 within one unit or from an older data version).
  Definitions reverse-engineered from the printed numbers are documented in `docs/data_notes.md`
  (household vehicles are types 01-07, golf-cart trips are not vehicle trips; the 2001 Table 3 rates).
* `harmonize`: `mode` crosswalk over all four waves, new `purpose_summary` concept (`WHYTRP1S` has
  three different code systems), `category_report(concept, wave_a, wave_b)` for any pair,
  `compare_waves` ignores zero padding of codes (`padding_differs`).
* `Registry.weight_for`, `NHTSData.replicate_weights` and `survey` work for the 2001 long-distance
  file (person replicates); `table_key("longdist", 2001)`.

## 0.3.0 (2026-10-21)

Adds the **2022 NextGen NHTS**, completes the 2017 wave and compares the two.

* **NHTS 2022** (public release V2.1): hash-pinned download of `csv.zip` (4.5 MB), codebook-derived
  schema for five tables (household, person, trip, vehicle and the new person-level `longdist`),
  all 2,639 codebook code frequencies reproduce (unweighted and weighted). `pynhts.load(2022)`,
  `pynhts fetch|info|register --wave 2022`.
* **Taylor-series variance** (`pynhts.stats.TaylorSurvey`, `taylor_variance`) for waves without
  replicate weights: strata `STRATUMID`, clusters `HOUSEID`, degrees of freedom per domain as in
  `survey::degf`. `data.survey(...)` picks the design from the wave; `clusters="all"|"observed"`,
  `weights="all"|"weekday"|"weekend"`. Estimates, standard errors and df equal R's `survey` package
  to 1e-9 for 24 estimands (`tools/validate_taylor_r.R`, `tests/golden/taylor_2022_r.csv`).
* Recipe `ug2022`: the control totals of the 2022 User Guide (Tables 10 and 11): 15 of 18 reproduce;
  vehicle-trip weight, VMT cases and VMT weight do not (documented, not tuned).
* **2017 completed:** recipe `stt2017` grows from 24 to 37 targets with the report's "2017 adj."
  rows (`TRPMILAD`, version 1.2 adjusted trip miles) and the 2017 rows of its Table 1d (annual
  totals with margins of error): 31 reproduce completely, 3 reproduce only the estimate, 3 do not.
  The unexplained printed total of persons is traced to the report's Census control total.
* **Official documents** are pinned in the registry and downloadable with `fetch_docs` /
  `pynhts docs --wave 2017|2022` (codebooks, user guides, derived variables, release notes,
  compatibility notes, weighting documents). The 2022 registry pins the current V2.x guide; the
  site still links the V1 guide whose control totals no longer match the data.
* `pynhts.dictionary(wave)` and `pynhts.describe(variable, wave)`.
* **`pynhts.harmonize`:** `compare_waves` (386 variable names: 19 identical, 34 relabelled, 33 to
  review, 47 with changed codes, 253 in one wave only) and crosswalks of trip purpose and trip
  mode (`crosswalk`, `apply`, `category_report`) with a status per code, validated against the
  codebooks and ORNL's derived variables (`WHYTRP1S`, `TRIPMODE`). Documents that the User Guide
  and the 2022 codebook disagree on purpose codes 18/19.
* Conversion downloads each zip once (several tables share one archive).
* Registry members carry their table; `Registry.variance`, `Registry.tables`.
* Breaking for code that imported `pynhts.io.converter.CORE_TABLES` (now in the registry).

## 0.2.1 (2026-10-20)

Memory fix found by running the full real-data test suite on a free 13 GB Colab runtime.

* String columns are now loaded as Arrow-backed `string[pyarrow]` instead of Python-object strings.
  Measured on Colab (same tests, 2026-10-20): loading all columns of `person` peaked at 1.4 GB instead of
  4.8 GB, and the all-columns `trip` loader test peaked at 4.1 GB instead of being killed (out of memory
  above 11.4 GB). Values, `pd.NA` semantics and codes are unchanged; `.dtype.storage` is now `"pyarrow"`.
* Derived frames (`tours()`, `NHTSData.tours`) get the same Arrow-backed `string` columns whether they are
  built fresh or read back from the cache (pandas would restore Python storage from Parquet);
  `object` columns are unchanged.
* New regression test `test_string_columns_are_arrow_backed`.
* Full suite (155 tests including all real-data and network tests) passes on Windows / Python 3.13 and the
  non-data suite (103) on Linux / Python 3.13 (Colab).

## 0.2.0 (2026-10-19)

Adds the tours module, a derived-data cache, activity-diary plots and a table exporter. Scope is still NHTS **2017** only.

* `NHTSData.tours(config, columns, force_rebuild=False)`: tours cached as Parquet in
  `<cache>/<wave>/derived/` (key = hash of parameters + source files; 11 s -> 0.9 s on 923,572 trips).
* `pynhts.viz` (optional `matplotlib`, extra `pynhts[viz]`): `activity_profile` (weighted minute-by-minute
  activity shares over the 04:00-03:59 diary day) and `plot_activity_diary` / `plot_profile` (stacked areas).
* `pynhts.tables`: `Row`, `build`, `to_latex` (booktabs), `to_markdown` for estimate +/- MoE, SE or CI tables.
* `tools/make_replication_artifacts.py`: Figure 1 and Table 1 of the McNally-Rafiq replication.
* `pynhts.tours`: `TourConfig`, `build_tours` (tour numbering, completeness, HBW/HBO/NHB classes, work-tour
  patterns and types) and `chain_ids` (FHWA-style chains, 30-minute rule).
* `NHTSData.survey_rows`: bind any rows keyed by household or person-day (e.g. tours) to the replicate
  weights for design-correct margins of error.
* New recipe `mcnally_rafiq2021` (33 targets): the 4,994-person transit-user sample reproduces exactly;
  12 figures are documented gaps. `docs/validation.md` now covers every recipe.

## 0.1.1 (2026-10-17)

First version published on PyPI (0.1.0 exists only as a GitHub release). README links made absolute so
that they work on the PyPI page; no code changes.

## 0.1.0 (2026-10-17)

First release. Scope: NHTS **2017** only.

* `pynhts.io`: SHA-256-pinned download of the official archives, offline mode, adoption of local
  files, deterministic and idempotent CSV to Parquet conversion, replicate weights as float32.
* `pynhts.core`: codebook-derived typed schema (hierarchical, label-aware column ownership);
  `NHTSData` loader with lazy columns, validated many-to-one joins and per-column masking of
  survey codes (`missing="nan"|"keep"`, `skip="keep"|"nan"`); `decode_labels`.
* `pynhts.stats`: stratified jackknife (JKn, 98 replicates) totals, means, proportions and ratios
  with standard error, margin of error, confidence interval, domains and groups;
  `ratio_across` for rates built from two weight systems; Student-t quantile without SciPy.
* `pynhts.recipes`: replication of 24 figures of FHWA's *Summary of Travel Trends: 2017 NHTS*
  (20 reproduced, 2 estimate-only, 2 not reproduced; gaps documented, none tuned away).
* `pynhts.ml`: NumPy arrays with sample weights, PyTorch tensors, household graph edges.
* Command line: `pynhts fetch | register | info | validate`.
* Documentation: methods, data pitfalls, generated validation report. JOSS paper draft.
