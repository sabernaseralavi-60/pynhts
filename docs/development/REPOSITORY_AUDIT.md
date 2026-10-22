# Repository audit (2026-10-22, at pynhts 0.6.1; result of the 0.7.0 work in section 8)

Scope: the working tree of `NHTS/02_tools` on 2026-10-22, read before any code was changed. Facts below were
checked in the repository or by running it; items that were not checked are in section 7.

## 1. Current architecture (0.6.1)

| Layer | Modules | Role |
|---|---|---|
| io | `io.fetcher`, `io.registry`, `io.converter` | SHA-256-pinned download (ranged, parallel), offline mode, CSV to Parquet (deterministic, idempotent) |
| core | `core.schema`, `core.data` (`NHTSData`), `core.cache`, `core.flags`, `core.dictionary` | codebook-derived typed schema, lazy column loading, validated many-to-one joins parent -> child, missing/skip masking, top-code and national-only flags |
| stats | `stats.survey`, `stats.jackknife`, `stats.taylor`, `stats.distributions` | design-based totals, means, proportions, ratios: delete-one jackknife (2001, 2009, 2017; per-wave factor and df as registry data), Taylor series (2022); Student t without SciPy |
| rates | `rates` | daily trip/mile rates by the documented weight route |
| harmonize / concepts | `harmonize`, `concepts` | crosswalks (mode, purpose, income, education, fuel, vehicle type...) and the concept dictionary (38 concepts x 4 waves, comparability C/H/N, pitfalls with evidence) |
| recipes | `recipes.*` | reproduction of published tables (stt2001/2009/2017, ug2022, McNally and Rafiq 2021) with statuses |
| tours / viz / ml / tables / cli | `tours`, `viz.diary`, `ml`, `tables`, `cli` | tours (2017 only, by design), activity-diary figure, arrays and tensors, LaTeX/Markdown tables, `pynhts fetch|register|info|validate|docs` |

Dependencies: numpy, pandas, pyarrow, pooch, platformdirs, pyyaml (no SciPy by design). Python >= 3.10; CI Ubuntu and Windows x Python 3.10 and 3.13.
Size: about 5,400 lines of source at 0.6.1. Data: raw CSV and Parquet stay in the user cache (never in git).

## 2. Existing public API (0.6.1)

`pynhts.load`, `NHTSData` (`households/persons/trips/vehicles/longdist`, `table`, `survey`, `survey_rows`, `tours`, `labels`, `decode_labels`, `schema`, `columns`, `key`, `weight_column`, `replicate_weights`), `pynhts.dictionary`, `describe`, `concepts.{names,get,table,find,to_json}`, `harmonize.{concepts,crosswalk,apply,apply_column,category_report,age_bands,compare_waves}`, `rates.daily_rate`, `stats.{Survey,TaylorSurvey,ratio_across,...}`, `recipes.{run,to_markdown}`, `tables.{Row,build,note,to_latex,to_markdown}`, `tours.*`, `viz.*`, `ml.*`.

## 3. Supported datasets and waves

2001 (5 tables incl. long-distance trips; 99 delete-one replicates), 2009 (4 tables; 100 replicates), 2017 (4 tables; 98 replicates in 14 strata x 7), 2022 NextGen V2.1 (5 tables; no replicate weights: Taylor series with `STRATUMID` and household clusters). Only these four waves; nothing earlier by user decision.

## 4. What existed and worked

* Hash-pinned data acquisition and Parquet cache; every codebook frequency reproduces from the data.
* Correct design-based variance for four waves, validated against R `survey` (to 1e-9 for the Taylor path) and against the published tables (FHWA Summary of Travel Trends for 2001, 2009, 2017; the 2022 User's Guide).
* Guards for silent errors: `skip="auto"`, masked non-answer codes, top-codes, national-only columns, wave tags on frames, refusal to apply a crosswalk of another wave.
* Cross-wave dictionary of meaning and comparability; an agent task harness (`agent_eval`) and `AGENTS.md`.
* Independent evidence in this session (docs/paper_data_audit): national totals, rates and tables of papers it was not tuned on reproduce exactly (Lidbe 2021, Alberini 2021, Yang 2011).

## 5. Limitations and gaps found

1. **No relational aggregation layer.** Collapsing trips to persons or persons to households was rewritten by hand in 6 of 10 audited papers; the only help was the parent-to-child join of the loader. A hand-written `groupby` has no row-multiplication guard, no stated missing-value policy and no zero-versus-missing rule.
2. **No documented derived features** beyond official columns; no lineage for user-created variables.
3. **A usability trap:** with `skip="keep"` (and by default in coded columns) `-1` stays a valid-looking string, so `.notna()` is not a validity test (2009 `WKFTPT`: 262,694 "valid" values, 128,726 real answers).
4. **The person file is not a complete roster** (2001: 14.5 % of households have fewer listed persons than `HHSIZE`; 2009: 19.8 %; 2017: 7.0 %; 2022: 9.1 %). Member counts built from it are lower bounds; the official household counts (`WRKCOUNT`, `DRVRCNT`) are exact. Nothing in 0.6.1 said so.
5. **No exploratory layer** (missing-value reasons, weighted descriptives, correlation that refuses nominal variables), no transformation helper, no leakage-safe split by household, no quality report, no table export beyond LaTeX/Markdown, only one figure type.
6. **Cross-wave comparison was a manual job**: `compare_waves` compares variable definitions, not estimates; nothing stopped pooled stacking of non-comparable concepts.
7. Not covered by design or by data: ACS/block-group variables (need the restricted block-group ID), the write-in "scooter/skateboard" mode of 2017, state GDP and similar external joins.
8. Models, regression variance (refit per replicate) and GIS are out of scope; no regression-result tables.

## 6. Potential breaking changes

None were made. 0.7.0 only adds modules and one top-level helper (`pynhts.valid`, `pynhts.answer_status`); `tables` gained functions; `viz` gained `plots`. The mypy configuration gained a per-module `warn_return_any = false` for the new modules (pandas-stubs noise) and ruff ignores `D105` and line length in documentation-heavy modules.

## 7. Claims that require further verification (not verified)

* That the 2009 release 2.1 in the registry is the release behind every 2009-based paper (two audited papers cite "the second release, November 2010").
* The cause of the 2001 medical-condition gap in Lidbe 2021 Table 3 (4.40 % of trips in the data against 5.49 % printed).
* The under-5 population in the 2017 Summary of Travel Trends (Census control total, API key needed).
* Whether the 2022 trip-weight adjustment affects shares equally across modes (shares are compared, but the adjustment factor varies by purpose, 1.03 to 1.19).
* Literature claims in `docs/research/NHTS_RESEARCH_LANDSCAPE.md` for studies marked "abstract only": the abstract was read, the full text was not.
* No external review of the 0.7.0 modules has been done yet (the two earlier releases each had an adversarial review and a fact-check; see PKG-20261021-11 and PKG-20261022-01).

## 8. What 0.7.0 adds in response (priority order)

1. `pynhts.aggregate`: explicit, diagnosed aggregation (keys, orphans, missing policy, true zeros, weight of the target table).
2. `pynhts.features`: 89 documented features at four levels with a registry, eligibility rules and lineage; validated against the survey's own counts in every wave.
3. `pynhts.valid` / `answer_status`.
4. `pynhts.eda`, `pynhts.quality`: missing-value reasons, weighted descriptives and quantiles, correlation that refuses nominal columns, Cramér's V, distribution comparison, key and weight integrity report.
5. `pynhts.transform`: leakage-safe transformations (fit on training rows, JSON parameters, split by household) with diagnostics.
6. `pynhts.trends`: harmonized per-wave estimates and a guarded pooled workflow.
7. `tables.sample_characteristics`, HTML/CSV/Excel export; `viz.plots` with weighting and sample size on every figure.
8. Docs generated from the machine-readable sources (`docs/data/`), a literature evidence table (`docs/research/`).

Not done and why: regression-result tables and model-performance tables (no model layer by design); geographic maps (the public file gives state and tract-level categories only); GIS and block-group joins (restricted ID); automatic annualisation (never automatic: it is a decision).
