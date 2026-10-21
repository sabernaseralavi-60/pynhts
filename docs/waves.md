# Working with two waves: 2017 and 2022

`pynhts.load(2017)` and `pynhts.load(2022)` return the same kind of object, `NHTSData`, with the
same methods. What differs is stated by the data, not hidden by the library.

```python
import pynhts
d17, d22 = pynhts.load(2017), pynhts.load(2022)

d17.variance_method, d22.variance_method         # ('jkn', 'taylor')
d22.tables       # ('household', 'person', 'trip', 'vehicle', 'longdist')   2017 has no 'longdist'
d22.key("trip")  # ('HOUSEID', 'PERSONID', 'TRIPID')   2017: ('HOUSEID', 'PERSONID', 'TDTRPNUM')

d22.survey("trip", ["TRPMILES"]).mean("TRPMILES")               # Taylor-series SE, df per domain
d22.survey("household", ["HHSIZE"], weights="weekday").total()  # weekday weight set (5D)
```

## What changed between the waves (and what pynhts does about it)

| | 2017 | 2022 | In pynhts |
|---|---|---|---|
| Households / persons / trips | 129,696 / 264,234 / 923,572 | 7,893 / 16,997 / 31,074 | |
| Standard errors | 98 jackknife replicates | none: Taylor series with `STRATUMID` and `HOUSEID` | `Survey` / `TaylorSurvey` |
| Weight sets | one | seven-day, weekday, weekend | `weights=` |
| Trip weight | constant within a person-day | varies by trip | handled per row |
| Trip counts | as reported | adjusted for web-only, no travel log | **not** corrected (see below) |
| Population | includes group quarters | excludes them (about -2.5 %) | documented |
| Tables | household, person, trip, vehicle | + long-distance (one row per person) | `longdist` |
| Geography | state, CBSA | census division only | `HHSTATE`, `HH_CBSA` absent |

## Same name, different meaning

`pynhts.harmonize.compare_waves()` compares every variable name of the two codebooks (253
variable names are in only one wave: 111 only in 2017, 142 only in 2022):

| status | meaning | variables |
|---|---|---:|
| `identical` | same label, type and coded values | 19 |
| `relabelled` | same coded values, other wording | 34 |
| `review_labels` | same codes, labels share under a third of their words (often a false alarm: `Yes` against `Worker`) | 33 |
| `codes_changed` | the set of coded values differs; **do not pool the raw column** | 47 |

```python
from pynhts import harmonize
cmp = harmonize.compare_waves()
cmp[cmp.variable == "TRPTRANS"]           # codes_changed
```

`TRPTRANS` is the example: code `02` is a bicycle in 2017 and a van in 2022; `03` is a car and an
SUV; `20` is a boat and walking.

## Harmonizing trip purpose and mode

`harmonize.crosswalk("purpose")` and `harmonize.crosswalk("mode")` list every code of both waves
with its shared category and a status: `exact`, `merge` (several codes of one wave collapse into
the category), `approximate` (the waves do not define the category identically) or `only_here`.
The alignment is the one in Appendix 2 of the 2022 User Guide, checked against the codebooks and
against ORNL's own derived variables.

```python
trips17 = d17.trips(["TRPTRANS", "WHYTO"], missing="keep")
trips22 = d22.trips(["TRPTRANS", "WHYTO"], missing="keep")
trips17["mode"] = harmonize.apply(trips17["TRPTRANS"], "mode", wave=2017)
trips22["mode"] = harmonize.apply(trips22["TRPTRANS"], "mode", wave=2022)

harmonize.category_report("mode")        # which categories are comparable, and why not
harmonize.apply(trips22["TRPTRANS"], "mode", wave=2022, level="summary")   # guide's summary modes
```

`category_report` marks a category `comparable` only if it exists in both waves and every code in
it is `exact`. In the trip-purpose crosswalk 14 of 18 categories are comparable; the others
(work-related trips, care, shopping, other) need a decision from you, and the report says what
differs. In the mode crosswalk 13 of 20 are comparable.

Missing codes (-9, -8, -7) and codes the crosswalk does not list become NA. Nothing is imputed.

### Two places where the official documents disagree

* The guide prints trip-purpose codes 18 (religious) and 19 (rest or relaxation); the codebook
  and ORNL's `WHYTRP1S` say 18 is rest or relaxation and 19 is religious. pynhts follows the
  codebook.
* The guide groups recreational vehicles under "Other Vehicle"; ORNL's 2022 `TRIPMODE` counts them
  as private-vehicle trips. The `summary` level follows the guide.

## What is not harmonized

* **Trip rates.** The 2022 trip weights contain a methods adjustment (about 10-12 % more trips)
  that the 2017 weights do not. Comparing trips per person between the waves mixes real change
  with that adjustment. pynhts does not try to undo it.
* **Distances.** 2017 `TRPMILES` is shortest-path distance (use `TRPMILAD` to compare with older
  surveys); check the 2022 compatibility document before pooling distances.
* **Geography, vehicle models, state add-ons** exist in 2017 only.
* Weighted levels (`WTHHFIN`, ...) carry different population baselines; compare shares and
  rates, not totals, and never pool the two files into one weighted sample.

## Sources

2022 NHTS Data User Guide (V2.0.1), Appendix 2; 2022 NextGen NHTS Compatibility with Prior Data
(V2.1); 2017 NHTS Compatibility with Prior NHTS Data; the two codebooks. All are pinned by hash
in the registry and downloaded with `pynhts docs --wave 2017|2022`.
