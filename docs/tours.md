# Tours (`pynhts.tours`)

Tour formation and trip chaining for the NHTS 2017 trip table. *Status: first version; validated
against one study (McNally & Rafiq 2021, see [validation](validation.md)).*

## Quick start

```python
import pynhts
from pynhts import tours

data = pynhts.load(2017, replicates=True)
trips = data.trips(["WHYFROM", "WHYTO", "TRPMILES", "TRPTRANS"], weight=False, missing="keep")

result = tours.build_tours(trips)                      # default: work-from-home counts as home
result.tours["tour_class"].value_counts()              # HBW / HBO / NHB
result.trips[["HOUSEID", "PERSONID", "tour", "trip_in_tour", "activity"]].head()

# design-correct weighted estimates for tours (all tours of a person-day share one weight)
s = data.survey_rows(result.tours, "trip")
s.proportion(result.tours["tour_class"] == "HBW")      # share of tours that are work tours, with MOE
s.total(by="tour_class")                               # annual number of tours, with MOE
```

## What a tour is

Each trip that **arrives at home** closes the tour it belongs to. A tour is *complete* when its first
trip leaves home and its last trip arrives home; the *day* is complete when the first trip of the
day leaves home and the last one arrives home. Destinations are typed `H` (home), `W` (work) or
`N` (anything else).

| Column (tours) | Meaning |
|---|---|
| `tour_class` | `HBW` complete tour with work, `HBO` complete tour without work, `NHB` tour that does not start and end at home |
| `activities` | destination types in order, e.g. `WNH` |
| `n_work`, `n_before`, `n_after`, `n_during` | work stops, other stops before the first work stop, after the last, and between work stops |
| `pattern` | McNally & Rafiq's 3-tuple `(before,after,during)` for tours with work |
| `work_type` | `simple`, `complex` (stops before or after work), `work_based` (stops between work stops), `multi_work` (several work stops, no other stop) |
| `complete`, `day_complete`, `has_invalid` | completeness flags and whether a purpose code was missing |

## Parameters (`TourConfig`)

| Parameter | Default | Why it is a parameter |
|---|---|---|
| `home_codes` | `{"01", "02"}` | `02` (work from home) takes place at home. McNally & Rafiq's work-tour count is closer with `01` only (2,456 against 2,454) than with both (2,471) |
| `day_home_codes` | same as `home_codes` | their transit-user sample matches *exactly* only when `02` counts as home at the day level |
| `work_codes` | `{"03"}` | adding `04` (work-related meeting) moves their count to 2,535 |
| `dwell_threshold` | `None` | minutes; used by `chain_ids` (FHWA's 2001 chained-trip file uses 30) |
| `drop_invalid` | `False` | drop tours with a missing or coded purpose |

`TourConfig.mcnally_rafiq()` bundles the combination that reproduces their sample.

## Chains

`tours.chain_ids(trips, TourConfig.fhwa_chained())` numbers FHWA-style chains: travel between
anchors (home or work) in which stops of at most 30 minutes stay inside the chain. This follows the
description in FHWA's note on the 2001 chained-trip file and has **not** been validated against a
published table yet.

## Limits

* Only the 2017 trip file is supported. Purposes come from `WHYFROM`/`WHYTO`, which have no location,
  so two work stops cannot be told apart from one workplace visited twice.
* Tours that extend past the single travel day recorded for each person are cut at its end.
* The default home rule is a choice, not a fact about the data; see the table above.
