# Changelog

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
