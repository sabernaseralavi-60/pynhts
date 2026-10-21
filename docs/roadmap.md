# Roadmap

## Done in 0.4.0: NHTS 2009 and 2001

* Both waves: hash-pinned download (including the separate replicate archives), schema read from the
  PDF codebooks (`tools/build_schema_pdf.py`; 3,435 and 6,327 code frequencies reproduce, gaps
  documented), typed Parquet, 100 and 99 jackknife replicate weights with the factor and
  degrees of freedom of each wave.
* Recipes `stt2009` (40 figures of the 2009 *Summary of Travel Trends*: 35 reproduced, 5 with a
  margin-of-error convention difference) and `stt2001` (47 figures: 40 reproduced, 7 within
  one unit or from an older data version).
* `harmonize`: crosswalks of mode and of the summary purpose `WHYTRP1S` over all four waves;
  `compare_waves` ignores zero padding of codes.

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

* **The 1995 and earlier waves** (NPTS). The registry, schema and variance design are per wave, so a
  wave adds files (and a crosswalk), not code paths. 2001 and 2009 are now available to validate the
  tour-chaining rule against FHWA's tables (`chain_ids` is still unvalidated, and `pynhts.tours` is
  2017-only).
* Detailed purpose (`WHYTO`) crosswalk for 2001 and 2009; the official documents align 2017 and
  2022 only.
* Crosswalks beyond trip purpose and mode (income, education, urban/rural, vehicle type) and a
  harmonized pooled-analysis helper that carries the loss report along.
* Tours for 2022 (`pynhts.tours` is 2017-only: it relies on `TDTRPNUM`).
* Variance of regression coefficients (refit once per replicate weight).
* More recipes: other tables of the Summary of Travel Trends and seminal NHTS papers.
* A hosted documentation site.
* Explaining the four documented gaps (see [validation](validation.md)); reports from users
  who can are welcome.
