# pynhts

![status](https://img.shields.io/badge/status-pre--alpha-orange)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-BSD--3--Clause-green)

> **Work in progress / pre-alpha.** This library is under active development. The API will change
> without notice, nothing is released on PyPI yet, and results have **not** yet been validated
> against published NHTS tables. Do not use it for publications until a tagged release says otherwise.

Typed, survey-weight-aware Python access to US National Household Travel Survey (NHTS) microdata.
Phase 1 covers the NHTS **2017** wave only.

## What works today
- `pynhts.io.fetch()`: hash-verified download of the official 2017 files into a local cache
  (offline mode supported); `pynhts.io.register_local()` adopts files you already have, after
  proving they are the official ones.
- `pynhts.io.convert()`: deterministic, idempotent conversion to typed Parquet (original survey
  codes kept; replicate weights in separate float32 files).
- `pynhts.load(2017)`: lazy, validated access. Request any column from any table and it is
  joined from the table that owns it (many-to-one, no orphans, row order kept), with
  `missing="nan"|"keep"` and `skip="keep"|"nan"` control over the survey codes:

  ```python
  import pynhts
  data = pynhts.load(2017)                      # downloads + converts on first use
  trips = data.trips(["TRPMILES", "TRPTRANS", "HHFAMINC", "R_AGE"])
  ```
- `data.survey(table, columns)`: totals, means, proportions and ratios with **JKn standard
  errors, 95 % margins of error and confidence intervals** from the 98 replicate weights
  (variance = 6/7 * sum of squared replicate deviations; MOE = t(0.975, 98) * SE, as FHWA).
  Trip estimates run on person-day replicates, so 923,572 trips need no trips x 98 matrix.

  ```python
  s = data.survey("person", ["R_AGE_IMP", "DRIVER"])
  s.total(domain=s.rows["DRIVER"] == "01")        # 223,277 thousand drivers, MOE 827
  trips = data.survey("trip", ["TRPMILES"])
  trips.mean("TRPMILES")                          # 10.70 miles, MOE 0.40
  ```
- `data.decode_labels(df, table=...)`: replace codes by the codebook's labels.
- Golden tests: the loader reproduces all 3,811 code frequencies (counts and weighted totals) of
  the official codebook, and the 2017 *Summary of Travel Trends* Table 1 totals for households,
  persons by age, drivers and workers, **including their published margins of error**, and the
  Table 3 travel rates (trips and miles per person and per household). Two small gaps are documented
  openly in `tests/golden/stt2017_table1.yaml` (printed total of persons; MOE of miles per person).
- `pynhts.core.schema`: typed column schema generated from the official codebook
  (dtypes, missing-value codes, owner table of each column).

## Planned
`pynhts.recipes` replication of published
tables (first target: FHWA *Summary of Travel Trends: 2017 NHTS*), `pynhts.ml` array/tensor export.

## Data
The NHTS microdata are public data of the US Federal Highway Administration
(<https://nhts.ornl.gov>). They are **never** bundled with or committed to this repository.

## Development
```
uv venv && uv pip install -e ".[dev]"
pytest              # unit tests (no data needed)
pytest -m data      # needs the real files in the pynhts cache
pytest -m network -o addopts=-ra   # live ORNL download (~80 MB), manual only
```

License: BSD-3-Clause.
