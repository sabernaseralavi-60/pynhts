# Adversarial review of pynhts 0.7.0 and what was done (fixed in 0.7.1)

An independent reviewer (a separate model instance with read-only instructions, real data of all four waves) tried to break
the 0.7.0 modules after release. It reported 4 P0, 7 P1 and 15 P2 findings, each reproduced by code, and listed 34 statements it verified as true
(feature counts, the roster percentages, the equality of member counts with `WRKCOUNT`/`DRVRCNT` in complete rosters, Box-Cox and
Yeo-Johnson lambdas against a grid search, weighted fits equal to row replication, mode shares equal to a manual computation, the
documented sampling-frame and collection-mode facts). Every finding below was re-checked by a regression test (`tests/unit/test_review_070.py`,
`tests/data/test_features_real.py`) or documented.

| Id | Finding | Fate in 0.7.1 |
|---|---|---|
| P0-1 | skip code `-1` summed as a mile (2001: 21 trips, 2009: 181) in `aggregate`, `p_miles`, `hh_miles`, `hh_vmt` | **fixed**: table sources load with `skip="auto"`; numeric validity uses `valid()` (negative numbers are skips or non-answers, never quantities) |
| P0-2 | `trip_shares("purpose")` read `WHYTRP1S` and applied the `WHYTO` crosswalk (home 70.6 % instead of 34.6 %) | **fixed**: `purpose` uses `WHYTO`, `purpose_summary` uses `WHYTRP1S` |
| P0-3 | weighted Spearman: tie mid-rank wrong with unequal weights | **fixed** (cumulative weight minus half the tie group's weight) |
| P0-4 | `compare_groups` standardised difference used the overall sd, not the documented pooled within-group sd | **fixed** |
| P1-1 | education universe differs by wave (youngest respondent 16 in 2001, 18 in 2009, 14 in 2017/2022) while docs said "adults" | **fixed**: universe is persons aged 18+; younger respondents are `not_applicable` |
| P1-2 | count features turned unknown inputs into 0 while the registry said NaN | **fixed**: unknown companions `hh_n_vehicles_age_unknown`, `hh_trips_unknown_purpose`, `p_trips_unknown_purpose`; registry states the real rule |
| P1-3 | `first`/`last` on a user frame followed the frame's row order | **fixed**: frames are put in trip-number order; an order column is required |
| P1-4 | `empty="auto"` turned rows a user had filtered out into zeros | **fixed**: default `empty="nan"` for frames, `"auto"` for table names; features pass `"auto"` for their complete frames |
| P1-5 | duplicate rows in a user frame were counted twice silently | **fixed**: raises unless `allow_duplicates=True` |
| P1-6 | `trends.pool` stacked 2001 children 0-4, kept raw codes, only warned for unmapped coded columns | **fixed**: `min_age=5`, raw codes renamed `<col>_raw`, unmapped coded columns raise unless `allow_raw_codes=True` |
| P1-7 | `hh_vmt` is 0.983 (2009), 0.999 (2017), 0.9995 (2022) of the official `VMT_MILE`; the registry gave the wrong reason | **documented**: the group excludes driver trips in other trucks and RVs which `VMT_MILE` includes |
| P2-1 | `~Where` turned NA rows into matches | **fixed** |
| P2-2 | integers on coded columns matched nothing silently | **fixed**: codes compare unpadded (1, "1", "01"); type mismatches raise |
| P2-3 | `empty="nan"` inconsistent between `n` and `sum` | **documented** in the docstring |
| P2-4 | `hh_n_age_unknown` missing from the registry | **fixed** |
| P2-5 | `hh_n_unlisted` is not only children under 5 | **fixed** (description) |
| P2-6 | `YOUNGCHILD` does not exist in 2001/2009 | **fixed** (docstring) |
| P2-7 | Kendall subsampling note incomplete | **fixed** |
| P2-8 | `split_by_household` depended on row order | **fixed** (sorted ids) |
| P2-9 | `sample_characteristics` counted skip codes as answers | **fixed** |
| P2-10 | `histogram` clipped by an unweighted quantile and mis-stated the clipped share | **fixed** (weighted quantile; share of weight reported) |
| P2-11 | `bar_share` without n printed "n = 0" | **fixed** |
| P2-12 | `trip_shares(min_age)` drops trips of persons with unknown age silently | **documented** |
| P2-13 | distance statement in the generated harmonization page wrong in direction and numbers | **fixed** (the 2017 routed distances are about 10 % shorter than self-reports, yet the mean rises; `TRPMILAD` scales up) |
| P2-14 | the `WKFTPT` example numbers did not reproduce on the full file | **fixed** (308,619 non-missing, 138,786 real answers) |
| P2-15 | research landscape overstated what was read and what was reproduced | **fixed** |

Lessons recorded in the research-kit ledger (PKG-20261022-09..10). Not independently checked by the author after the fix: the reviewer's
one session covered the new modules and their docs, not the whole package; a second fact-check of the corrected documentation was not run.
