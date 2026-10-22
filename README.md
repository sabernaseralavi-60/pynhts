# pynhts

[![ci](https://github.com/sabernaseralavi-60/pynhts/actions/workflows/ci.yml/badge.svg)](https://github.com/sabernaseralavi-60/pynhts/actions/workflows/ci.yml)
![status](https://img.shields.io/badge/status-alpha-orange)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-BSD--3--Clause-green)

Typed, survey-weight-aware Python access to US National Household Travel Survey (NHTS)
microdata.

> **Scope and status (0.8.1, alpha).** The **2001**, **2009**, **2017** and **2022** (NextGen)
> waves are supported. The API may still change. Results are validated against published tables:
> for 2009, 35 of 40 figures of the *Summary of Travel Trends* reproduce completely (the other 5
> reproduce the estimate; the report's margin of error uses another multiplier), for 2001 40 of
> 47 (the 7 others are within one unit or come from an older data version); for 2017, 31 of 37
> figures of FHWA's *Summary of Travel Trends* reproduce completely (3 more reproduce the estimate
> but not the margin of error, 3 are gaps); for 2022, 15 of 18 control totals of the User Guide,
> and the Taylor-series errors equal R's `survey` package. Every gap is reported openly in
> [docs/validation.md](https://github.com/sabernaseralavi-60/pynhts/blob/main/docs/validation.md) (tours: 21 of 33).

## Install

```
pip install pynhts
pynhts fetch --replicates        # download, verify (SHA-256) and convert; about 0.4 GB of Parquet, plus 1.8 GB of raw CSV that you may delete afterwards
```

`pynhts fetch --wave 2022` needs no replicate weights (4.5 MB); 2009 and 2001 need a separate
replicate archive (400 and 440 MB) for standard errors. Already have the NHTS CSV files?
`pynhts register <folder> [--wave 2022]` adopts them after checking their hashes, and
`pynhts docs --wave 2001|2009|2017|2022` downloads the official documents (also hash-checked).

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

# 2009 and 2001: 100 and 99 jackknife replicates, same interface (children 0-4 are in the 2001 file)
d09 = pynhts.load(2009, replicates=True)
d09.survey("person", ["R_AGE"]).total()                     # 283,054 thousand persons

# daily rates by the official route, with the unit in the result
from pynhts import rates
rates.daily_rate(d09, "trips", per="person")                # 3.79 person trips per person and day

# what a variable means in each wave, and what to watch for
pynhts.concepts.find("VEHAGE", 2009)                        # top-coded (35 = 25+), grade H, pitfalls
pynhts.concepts.table()                                     # concepts x 4 waves, grade C / H / N

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
| `pynhts.stats` | totals, means, proportions, ratios with jackknife (2001, 2009, 2017) or Taylor-series (2022) errors and margins of error |
| `pynhts.harmonize` | variable inventory of two waves; 19 crosswalk concepts (mode, three trip-purpose schemes, trip class, income, education, race, Hispanic origin, medical condition, urban area, density, vehicle type, fuel ...) with a status per code; `race_ethnicity` combines race and Hispanic origin |
| `pynhts.concepts` | machine-readable dictionary: variable, universe, unit, comparability and pitfalls of each concept in each wave |
| `pynhts.rates` | daily trips and miles per person or household by the official route, with units |
| `pynhts.recipes` | replication of published tables with honest status per figure |
| `pynhts.tours` | tour formation (HBW/HBO/NHB, work-tour patterns), FHWA-style chains; flexible home/work rules |
| `pynhts.ml` | NumPy / PyTorch / graph export (PyTorch optional) |
| `pynhts.study` | a research statement (wave, sample rules, variables, weighting) to data + sample-flow table + Table 1 + figures + methods text; `compare` grades the result against a paper's printed numbers |
| `pynhts.aggregate` | trips to persons, persons to households: no row multiplication, stated missing-value policy, true zeros, diagnostics report |
| `pynhts.features` | 93 documented person, household, trip and vehicle features (formula, eligibility, denominator, weight, waves) with lineage |
| `pynhts.eda`, `pynhts.quality` | missing-value reasons, weighted descriptives, correlation that refuses nominal columns, key and weight integrity report |
| `pynhts.transform` | leakage-safe transformations (fit on training rows, JSON parameters, split by household) |
| `pynhts.trends` | per-wave harmonized estimates; guarded pooled workflow that refuses non-comparable concepts |

```python
# 0.7.0: from trips to a documented household table, with diagnostics (see docs/analysis.md)
from pynhts import features, aggregate as A, valid
hh = features.create_household_features(d, groups=["composition", "travel", "modes"])
hh.attrs["pynhts_features"]            # lineage: sources, formula, missing rule per feature
```

## Why a library

Correct NHTS analysis has many silent traps (a data server that returns HTTP 200 for missing
files, string codes with leading zeros, `-1` skips that are not missing data, 107 copied
parent columns in the child tables, a vehicle `PERSONID` that is not the person key, ...).
They are documented in [docs/data_notes.md](https://github.com/sabernaseralavi-60/pynhts/blob/main/docs/data_notes.md) and each is covered by a test.

## Validation

* All coded values of the official codebooks (counts and weighted totals) reproduce: 3,807 in
  2017, 2,639 in 2022, 3,435 in 2009 and 6,327 in 2001 (three documented codebook errors in 2009).
* 37 figures from Tables 1 and 3 of FHWA's *Summary of Travel Trends: 2017 NHTS*, including the
  adjusted-distance rows and the annual totals, with margins of error: 31 reproduce completely, 3
  reproduce the estimate but not the margin of error, 3 do not reproduce.
* 2022: 15 of the 18 control totals of the V2.x User Guide (Tables 10 and 11); the 3 that do not
  reproduce are documented. Estimates, standard errors and degrees of freedom of 24 estimands
  equal R's `survey` package to 1e-9.
* 2009: 40 figures of the *Summary of Travel Trends* (35 reproduce completely; all 27 printed
  margins of error of its Table 1 match t(0.975, 100) x the jackknife standard error to rounding).
  2001: 47 figures (40 reproduce; the 2004 report's per-person rates are reproduced only with its
  own definition, documented). The 2001 User's Guide worked example (202,586,200 vehicles, SE
  672,072) reproduces.
* The transit-user sample of McNally & Rafiq's tour study (4,994 persons, 20,222 trips, 10,011
  transit trips) exactly, plus 33 of their figures in all: 21 reproduce, 12 gaps are documented
  (`pynhts.tours`). See [docs/validation.md](https://github.com/sabernaseralavi-60/pynhts/blob/main/docs/validation.md).

* **Independent evidence (2026-10-22, `docs/paper_data_audit`):** the analysis data of ten published NHTS papers
  that pynhts was never tuned on were rebuilt from the public files. The national totals and rates of Lidbe et al.
  (2021) for 2001 and 2017, Tables 1 to 4 of Alberini et al. (2021) and the 130,222-person sample with 21 odds
  ratios of Yang et al. (2011) reproduce; where papers do not reproduce, the cause is an unstated sample rule or an
  inconsistency in the paper (documented per paper, none tuned away). In every household whose person file is a
  complete roster, the worker and driver counts of `pynhts.features` equal the survey's own `WRKCOUNT` and `DRVRCNT`
  in all four waves.

## Documentation

[Analysis toolkit](https://github.com/sabernaseralavi-60/pynhts/blob/main/docs/analysis.md) · [Feature registry](https://github.com/sabernaseralavi-60/pynhts/blob/main/docs/data/FEATURES.md) · [Research landscape](https://github.com/sabernaseralavi-60/pynhts/blob/main/docs/research/NHTS_RESEARCH_LANDSCAPE.md) · [Comparing waves](https://github.com/sabernaseralavi-60/pynhts/blob/main/docs/waves.md) · [Defaults and guards](https://github.com/sabernaseralavi-60/pynhts/blob/main/docs/guards.md) · [AGENTS.md](https://github.com/sabernaseralavi-60/pynhts/blob/main/AGENTS.md) · [Methods](https://github.com/sabernaseralavi-60/pynhts/blob/main/docs/methods.md) · [Data notes](https://github.com/sabernaseralavi-60/pynhts/blob/main/docs/data_notes.md) · [Validation](https://github.com/sabernaseralavi-60/pynhts/blob/main/docs/validation.md)
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

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23573454.svg)](https://doi.org/10.5281/zenodo.23573454)

Cite the software with the Zenodo DOI [10.5281/zenodo.23573454](https://doi.org/10.5281/zenodo.23573454) (all versions; version 0.8.1 is 10.5281/zenodo.23575312; version 0.8.0 is 10.5281/zenodo.23573455), see [CITATION.cff](https://github.com/sabernaseralavi-60/pynhts/blob/main/CITATION.cff). License: BSD-3-Clause.
