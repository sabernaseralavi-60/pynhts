# pynhts

[![ci](https://github.com/sabernaseralavi-60/pynhts/actions/workflows/ci.yml/badge.svg)](https://github.com/sabernaseralavi-60/pynhts/actions/workflows/ci.yml)
![status](https://img.shields.io/badge/status-alpha-orange)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-BSD--3--Clause-green)

Typed, survey-weight-aware Python access to US National Household Travel Survey (NHTS)
microdata.

> **Scope and status (0.3.0, alpha).** The **2017** and **2022** (NextGen) waves are supported.
> The API may still change. Results are validated against published tables: for 2017, 31 of 37
> figures of FHWA's *Summary of Travel Trends* reproduce completely (3 more reproduce the estimate
> but not the margin of error, 3 are gaps); for 2022, 15 of 18 control totals of the User Guide,
> and the Taylor-series errors equal R's `survey` package. Every gap is reported openly in
> [docs/validation.md](https://github.com/sabernaseralavi-60/pynhts/blob/main/docs/validation.md) (tours: 21 of 33).

## Install

```
pip install pynhts
pynhts fetch --replicates        # download, verify (SHA-256) and convert; about 0.4 GB of Parquet, plus 1.8 GB of raw CSV that you may delete afterwards
```

`pynhts fetch --wave 2022` needs no replicate weights (4.5 MB). Already have the NHTS CSV files?
`pynhts register <folder> [--wave 2022]` adopts them after checking their hashes, and
`pynhts docs --wave 2017|2022` downloads the official documents (also hash-checked).

## What it does

```python
import pynhts
data = pynhts.load(2017)

# lazy, validated tables: columns are joined from the table that owns them
trips = data.trips(["TRPMILES", "TRPTRANS", "HHFAMINC", "R_AGE"])

# weighted statistics with jackknife (JKn) standard errors and 95 % margins of error
s = data.survey("person", ["R_AGE_IMP", "DRIVER"])
s.total(domain=s.rows["DRIVER"] == "01")        # 223,277 thousand drivers, MOE 827 thousand
data.survey("trip", ["TRPMILES"]).mean("TRPMILES")   # 10.70 miles, MOE 0.40

# replicate a published table and see every gap
from pynhts import recipes
print(recipes.to_markdown(recipes.run("stt2017", data)))

# machine-learning bridge
from pynhts import ml
arr = ml.to_arrays(trips, ["TRPMILES", "R_AGE"], target="TRPTRANS", weight="WTTRDFIN")

# NHTS 2022: same interface, Taylor-series errors (strata + households) instead of replicates
d22 = pynhts.load(2022)
d22.survey("trip", ["TRPMILES"]).mean("TRPMILES")          # weights="weekday" | "weekend" too

# the waves use different codes: compare and harmonize explicitly (TRPTRANS 02 is a bike in 2017, a van in 2022)
from pynhts import harmonize
harmonize.compare_waves()                                   # 386 variable names: 19 identical, 47 with changed codes
trips22 = d22.trips(["TRPTRANS"], missing="keep")
trips22["mode"] = harmonize.apply(trips22["TRPTRANS"], "mode", wave=2022)
pynhts.dictionary(2022)                                     # every variable with owner table, type, codes
```

| Module | Purpose |
|---|---|
| `pynhts.io` | verified download, offline mode, deterministic Parquet cache |
| `pynhts.core` | codebook-derived schema, `NHTSData` loader, missing-code handling |
| `pynhts.stats` | totals, means, proportions, ratios with JKn (2017) or Taylor-series (2022) errors and margins of error |
| `pynhts.harmonize` | variable inventory of two waves; validated 2017 <-> 2022 crosswalks of trip purpose and mode |
| `pynhts.recipes` | replication of published tables with honest status per figure |
| `pynhts.tours` | tour formation (HBW/HBO/NHB, work-tour patterns), FHWA-style chains; flexible home/work rules |
| `pynhts.ml` | NumPy / PyTorch / graph export (PyTorch optional) |

## Why a library

Correct NHTS analysis has many silent traps (a data server that returns HTTP 200 for missing
files, string codes with leading zeros, `-1` skips that are not missing data, 107 copied
parent columns in the child tables, a vehicle `PERSONID` that is not the person key, ...).
They are documented in [docs/data_notes.md](https://github.com/sabernaseralavi-60/pynhts/blob/main/docs/data_notes.md) and each is covered by a test.

## Validation

* All coded values of the official codebooks (counts and weighted totals) reproduce: 3,807 in
  2017 and 2,639 in 2022.
* 37 figures from Tables 1 and 3 of FHWA's *Summary of Travel Trends: 2017 NHTS*, including the
  adjusted-distance rows and the annual totals, with margins of error: 31 reproduce completely, 3
  reproduce the estimate but not the margin of error, 3 do not reproduce.
* 2022: 15 of the 18 control totals of the V2.x User Guide (Tables 10 and 11); the 3 that do not
  reproduce are documented. Estimates, standard errors and degrees of freedom of 24 estimands
  equal R's `survey` package to 1e-9.
* The transit-user sample of McNally & Rafiq's tour study (4,994 persons, 20,222 trips, 10,011
  transit trips) exactly, plus 33 of their figures in all: 21 reproduce, 12 gaps are documented
  (`pynhts.tours`). See [docs/validation.md](https://github.com/sabernaseralavi-60/pynhts/blob/main/docs/validation.md).

## Documentation

[Comparing waves](https://github.com/sabernaseralavi-60/pynhts/blob/main/docs/waves.md) · [Methods](https://github.com/sabernaseralavi-60/pynhts/blob/main/docs/methods.md) · [Data notes](https://github.com/sabernaseralavi-60/pynhts/blob/main/docs/data_notes.md) · [Validation](https://github.com/sabernaseralavi-60/pynhts/blob/main/docs/validation.md)
· [Roadmap](https://github.com/sabernaseralavi-60/pynhts/blob/main/docs/roadmap.md) · [Contributing](https://github.com/sabernaseralavi-60/pynhts/blob/main/CONTRIBUTING.md) · [Changelog](https://github.com/sabernaseralavi-60/pynhts/blob/main/CHANGELOG.md)

## Data

The NHTS microdata are public data of the US Federal Highway Administration
(<https://nhts.ornl.gov>). They are **never** bundled with or committed to this repository.

## Development

```
uv venv && uv pip install -e ".[dev]"
pytest                             # unit tests, no data needed
pytest -m data                     # real-data tests (files registered in the pynhts cache)
pytest -m network -o addopts=-ra   # live ORNL download, manual only
```

## Citation

See [CITATION.cff](https://github.com/sabernaseralavi-60/pynhts/blob/main/CITATION.cff). License: BSD-3-Clause.
