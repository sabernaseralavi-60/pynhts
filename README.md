# pynhts

[![ci](https://github.com/sabernaseralavi-60/pynhts/actions/workflows/ci.yml/badge.svg)](https://github.com/sabernaseralavi-60/pynhts/actions/workflows/ci.yml)
![status](https://img.shields.io/badge/status-alpha-orange)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-BSD--3--Clause-green)

Typed, survey-weight-aware Python access to US National Household Travel Survey (NHTS)
microdata.

> **Scope and status (0.1.0, alpha).** Only the **2017** wave is supported; other waves come
> after this one is solid. The API may still change. Not yet on PyPI. Results are validated
> against FHWA's published tables: 20 of 24 figures reproduce completely and 4 gaps are reported
> openly in [docs/validation.md](docs/validation.md).

## Install

```
pip install git+https://github.com/sabernaseralavi-60/pynhts.git
pynhts fetch --replicates        # download, verify (SHA-256) and convert; about 0.4 GB of Parquet, plus 1.8 GB of raw CSV that you may delete afterwards
```

Already have the NHTS 2017 CSV files? `pynhts register <folder>` adopts them after checking
their hashes.

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
```

| Module | Purpose |
|---|---|
| `pynhts.io` | verified download, offline mode, deterministic Parquet cache |
| `pynhts.core` | codebook-derived schema, `NHTSData` loader, missing-code handling |
| `pynhts.stats` | JKn totals, means, proportions, ratios; margins of error |
| `pynhts.recipes` | replication of published tables with honest status per figure |
| `pynhts.ml` | NumPy / PyTorch / graph export (PyTorch optional) |

## Why a library

Correct NHTS analysis has many silent traps (a data server that returns HTTP 200 for missing
files, string codes with leading zeros, `-1` skips that are not missing data, 107 copied
parent columns in the child tables, a vehicle `PERSONID` that is not the person key, ...).
They are documented in [docs/data_notes.md](docs/data_notes.md) and each is covered by a test.

## Validation

* All 3,807 coded values of the official codebook (counts and weighted totals) reproduce.
* 24 figures from Tables 1 and 3 of FHWA's *Summary of Travel Trends: 2017 NHTS*, with margins
  of error: 20 reproduce completely, 2 reproduce the estimate but not the margin of error,
  2 do not reproduce. See [docs/validation.md](docs/validation.md).

## Documentation

[Methods](docs/methods.md) · [Data notes](docs/data_notes.md) · [Validation](docs/validation.md)
· [Roadmap](docs/roadmap.md) · [Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)

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

See [CITATION.cff](CITATION.cff). License: BSD-3-Clause.
