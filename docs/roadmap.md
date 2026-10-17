# Roadmap

## Done (version 0.1.0, NHTS 2017)

* Hash-pinned download, offline mode, adoption of local files (`pynhts.io`).
* Codebook-derived typed schema, deterministic idempotent Parquet cache with float32 replicate
  weights (`pynhts.io`, `pynhts.core.schema`).
* `NHTSData` loader with lazy columns, validated joins and per-column missing-code masking
  (`pynhts.core`).
* Jackknife estimators with margins of error and a cross-survey ratio (`pynhts.stats`).
* Recipe that reproduces 24 figures of FHWA's *Summary of Travel Trends: 2017 NHTS*
  (`pynhts.recipes`); 20 reproduce completely, 4 gaps are documented.
* Arrays, PyTorch tensors and household graph edges (`pynhts.ml`); command line interface.

## In progress: `pynhts.tours`

First version done (tour formation, work-tour patterns, FHWA-style chains, weighted tour estimates),
built by paper-driven development against McNally & Rafiq's 2017 transit-tour study: their user sample
reproduces exactly. See [tours](tours.md) and [design notes](tours_design_notes.md). Still open: the
rules behind the remaining gaps, validation of the chained-trip definition, and the replication paper.

## Not done yet

* **Other waves** (2022 NextGen, 2009, 2001, 1995). Deliberately postponed until the 2017
  schema, merge logic and weighting were validated. The registry and schema layers are
  per-wave, so a new wave adds files, not code paths.
* Variance of regression coefficients (refit once per replicate weight).
* More recipes: other tables of the Summary of Travel Trends and seminal NHTS papers.
* A hosted documentation site and a PyPI release.
* Explaining the four documented gaps (see [validation](validation.md)); reports from users
  who can are welcome.
