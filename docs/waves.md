# Working with four waves: 2001, 2009, 2017 and 2022

`pynhts.load(2001)`, `load(2009)`, `load(2017)` and `load(2022)` return the same kind of object,
`NHTSData`, with the same methods. What differs is stated by the data, not hidden by the library.

| | 2001 | 2009 | 2017 | 2022 |
|---|---:|---:|---:|---:|
| Households | 69,817 | 150,147 | 129,696 | 7,893 |
| Persons | 160,758 | 308,901 | 264,234 | 16,997 |
| Trips | 642,292 | 1,167,321 | 923,572 | 31,074 |
| Tables | + long trips | | | + long distance (per person) |
| Variance | 99 jackknife replicates, 98/99 | 100 replicates, 99/100 | 98 replicates, 6/7 | Taylor series |
| t degrees of freedom | 99 | 100 | 98 | by domain |
| Children 0-4 | in the file (collected) | not in the file | not in the file | not in the file |
| Yes/no and sex codes | `"1"`, `"2"` | `"01"`, `"02"` | `"01"`, `"02"` | `"01"`, `"02"` |

```python
import pynhts
d01, d09 = pynhts.load(2001, replicates=True), pynhts.load(2009, replicates=True)
d09.survey("trip", ["TRPMILES"]).mean("TRPMILES")     # jackknife SE with the 100 replicates
d01.key("longdist")       # ('HOUSEID', 'PERSONID', 'TPTRPNUM')  one row per long trip
```

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
| `review_labels` | same codes, labels share under a third of their words (often a false alarm: `Yes` against `Worker`) | 30 |
| `codes_permuted` | same codes, but the meaning of some moved to another code (`R_RELAT`: 01 is "self" in 2017 and 07 in 2022; `URBAN` between 2001 and 2009) | 3 |
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

## 2001 and 2009: the same name, other codes

`harmonize.compare_waves(2001, 2009)` finds 41 variables whose codes changed and 11 whose type
changed; `harmonize.compare_waves(2009, 2017)` finds 37 and 4. Code padding is ignored when codes
are compared (`"1"` and `"01"` are the same answer; the column `padding_differs` says where it
happened, 50 variables for 2001 and 2009). Two examples that would corrupt a pooled analysis:

* `TRPTRANS` (mode): 08 is a commercial airplane in 2001, a golf cart in 2009, a motorcycle in
  2017 and a bus in 2022; 19 is a cruise ship, a taxi, an airplane and an e-scooter in the same
  four waves.
* `WHYTRP1S` (summary purpose): 2001 uses 01 = to work ... 13 = other; 2009, 2017 and 2022 use 01 =
  home, 10 = work, 20 = school/daycare/religious. The 2009 category 60 ("family personal
  business") has no code from 2017 on; in the 2017 data those trips (WHYTO "other general
  errands", "buy goods" and "buy services") all have `WHYTRP1S` 40.

19 crosswalk concepts are available (`harmonize.concepts()`): `mode`, `purpose_summary`
(`WHYTRP1S`), `purpose_1990` (`WHYTRP90`, ORNL's own cross-wave purpose), `trip_class` (`TRIPPURP`),
`income` (eight nominal bands that nest exactly in all four waves), `education` (five levels), `race_household`, `race_person`,
`hispanic_household`, `hispanic_person` (see below), `medical_condition`, `condition_duration`, `condition_effect` (see below), `urban_area`
(`URBAN`, codes swapped in 2001), `urban_rural`, `density` (`HBHUR`), `vehicle_type`, `fuel`, and the
detailed `purpose` (2017/2022). Status `nested` means several codes collapse exactly into the category,
so the category is comparable. `harmonize.age_bands` ends at 85+ whatever the top-code;
`crosswalk("mode")` covers all four waves; `crosswalk("purpose_summary")` maps `WHYTRP1S` of all four
waves to nine categories; the detailed `crosswalk("purpose")` (WHYTO) stays 2017/2022 because the
2001/2009 detail codes (11 go to work, 41 buy goods, ...) have no official alignment to the 2017
scheme. `category_report(concept, wave_a, wave_b)` compares any two waves.

```python
harmonize.apply(trips["TRPTRANS"], "mode", wave=2009)
harmonize.category_report("mode", 2001, 2009)       # walk, bike, car, SUV, ... are comparable
```

### Race and Hispanic origin

Race is the answer of one person per household (the household respondent); only 2017 and 2022 also ask each person
(`R_RACE`, `R_HISP`). Three things make a raw `HH_RACE` comparison wrong, all found in the data (households, unweighted):

* **The column is renamed in 2001** (`HHR_RACE`, `HHR_HISP`). `harmonize.variable_of("race_household", 2001)` returns the name of the wave.
* **Hispanic origin is a race code in 2001 and 2009.** 2001 codes 06 and 10-12 and 2009 code 07 name Hispanic origin; 99.7 % (2001 code 06) and
  98.7 % (2009 code 07) of those respondents also answer "Hispanic: yes". The later waves have no such code: 82 % (2017) and 67 % (2022) of the
  respondents who choose "Some other race" are Hispanic. The crosswalk files those codes under `other` as `approximate`, so `other` is not comparable
  before 2017, and 2001 White, Black and American Indian (which absorb "White & Hispanic" and similar codes) are not comparable with later waves.
  From 2009 on the five single-race groups and `multiple` are exact; Asian and Pacific Islander are exact in all four waves.
* **The race groups are not non-Hispanic.** Hispanic respondents sit inside White (5.7 % of 2017 White households) and the other groups in every wave.

For non-Hispanic groups use `harmonize.race_ethnicity(frame)`: a respondent who answers "Hispanic" is `hispanic`, the others are `nh_white`,
`nh_black`, `nh_asian`, `nh_aian`, `nh_nhpi`, `nh_multiple` or `nh_other`; the dedicated Hispanic question decides, and a Hispanic race code only
when the question is unanswered. Unknown origin or race stays missing (0 to 0.9 % of households). In the real files the household respondent is
Hispanic in 5.4 % (2001), 6.9 % (2009), 7.0 % (2017) and 7.7 % (2022) of the households that could be classified (unweighted; use the household weight for population shares).

```python
hh = pynhts.load(2001).households(["HHR_RACE", "HHR_HISP"])
hh["race_eth"] = harmonize.race_ethnicity(hh)       # same call and same categories in 2009, 2017, 2022
harmonize.category_report("race_household", 2009, 2017)   # white ... nhpi, multiple: comparable
```

### Medical condition that makes travel difficult

`MEDCOND` is a yes/no in all four waves and the codes mean the same, but three things make a naive comparison wrong (person file,
cross-tabulated against age, `MEDCOND6` and the effect items; the numbers are re-checked by `tests/data/test_four_wave_guards.py`):

* **The universe changes.** Ages 16+ answer in 2001 and 2009 (15 and younger carry the skip `-1`; 6 adults are skipped in 2009), everybody aged 5+ in
  2017 and 2022. Compare adults (18+).
* **2022 has 5.4 % non-answers** among adults (weighted; 0.04 to 0.14 % in 2001 to 2017) and asks about a "condition or disability". The yes share among
  the valid answers of 18+ is 8.7 % (2001), 10.5 % (2009), 10.0 % (2017) and 7.5 % (2022). The crosswalk marks 2022 `approximate`, so
  `category_report("medical_condition", 2017, 2022)` says not comparable: do not report the fall as a trend.
* **The effect items (`condition_effect`: `CONDTRAV`, `CONDNIGH`, `CONDPUB`, `CONDRIDE`, `CONDRIVE`, `CONDSPEC`) are asked of different people.**
  2001 and 2009: only of those who answered yes to `MEDCOND`; 2017 and 2022: also of every person aged 80+ whatever they answered (9,291 and 382
  persons with `MEDCOND` = no; nobody younger). 2022 turns the items into a select-all list, so "Not Selected" is not a "no". And the share answering yes
  among persons with a condition falls on every item from 2009 to 2017 although the codes are identical (`CONDNIGH` 46 % to 27 %, `CONDRIDE`
  55 % to 40 %, `CONDTRAV` 83 % to 72 %); the cause is not documented. Only 2001 to 2009 are marked comparable. Restrict to `MEDCOND` = yes to keep one definition.

`condition_duration` (`MEDCOND6`, asked of the yes answers only) collapses the six bands of 2001/2009 and the three of 2017/2022 into `up_to_6_months`,
`over_6_months` and `lifelong`; only the six-month boundary is inexact (the first band is 7.2 %, 6.9 %, 7.8 % and 7.0 % of the yes answers, so it moves little).

## What is not harmonized

* **Trip rates.** The 2022 trip weights contain a methods adjustment (about 10-12 % more trips)
  that the 2017 weights do not. Comparing trips per person between the waves mixes real change
  with that adjustment. pynhts does not try to undo it.
* **Distances.** 2017 `TRPMILES` is shortest-path distance (use `TRPMILAD` to compare with older
  surveys); check the 2022 compatibility document before pooling distances.
* **Geography** (`HHSTATE`; 2001 hides the state of some households as "XX", 2009 and 2017 hide
  small CBSAs as "XXXXX"), vehicle make and model (`MAKECODE`, `MODLCODE`) and the state add-on
  samples exist in 2001, 2009 and 2017; 2022 is a national sample without them. Suppression codes
  are values of these columns, not states.
* Weighted levels (`WTHHFIN`, ...) carry different population baselines; compare shares and
  rates, not totals, and never pool the two files into one weighted sample.

## Sources

2022 NHTS Data User Guide (V2.0.1), Appendix 2; 2022 NextGen NHTS Compatibility with Prior Data
(V2.1); 2017 NHTS Compatibility with Prior NHTS Data; the four codebooks (2001: Appendix B of the
User's Guide). For 2001 and 2009 the crosswalk rows come from the codebooks and the data (the
official documents align 2017 and 2022 only). All documents are pinned by hash in the registry and
downloaded with `pynhts docs --wave 2001|2009|2017|2022`.
