# Changelog

## Unreleased

(nothing yet)

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
