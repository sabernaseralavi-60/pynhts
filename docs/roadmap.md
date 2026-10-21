# Roadmap

## Done in 0.3.0: NHTS 2022 and cross-wave tools

* NHTS 2022 (NextGen, V2.1): hash-pinned download, codebook-derived schema (2,639 code frequencies
  reproduce), five tables including the long-distance file, weekday/weekend weights.
* Taylor-series variance for waves without replicate weights, validated against R's `survey`.
* Recipe `ug2022` (control totals of the 2022 User Guide): 15 of 18 reproduce, 3 gaps documented.
* 2017 completed: the report's adjusted-distance rows (`TRPMILAD`) and annual totals of its Table
  1d are reproduced (37 targets: 31 reproduce); the official documents are pinned and
  downloadable (`pynhts docs`); `pynhts.dictionary` / `describe`.
* `pynhts.harmonize`: variable inventory of two waves and validated 2017 <-> 2022 crosswalks of trip
  purpose and mode.

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

* **Other waves** (2009, 2001, 1995). The registry, schema and variance design are per wave, so a
  wave adds files (and a crosswalk), not code paths. 2001 is also needed to validate the
  tour-chaining rule against FHWA's tables.
* Crosswalks beyond trip purpose and mode (income, education, urban/rural, vehicle type) and a
  harmonized pooled-analysis helper that carries the loss report along.
* Tours for 2022 (`pynhts.tours` is 2017-only: it relies on `TDTRPNUM`).
* Variance of regression coefficients (refit once per replicate weight).
* More recipes: other tables of the Summary of Travel Trends and seminal NHTS papers.
* A hosted documentation site.
* Explaining the four documented gaps (see [validation](validation.md)); reports from users
  who can are welcome.
