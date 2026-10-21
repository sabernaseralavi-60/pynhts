# pynhts 0.4.0: adversarial review and plan to close the package on four waves

Reviewer: Claude Opus 5.5 (survey statistics, transportation data, research software), 2026-10-21.
Commit reviewed: `c571aad` (PyPI 0.4.0). Nothing under `src/`, `tests/`, `tools/` or the YAML registries
was changed. Every number below was produced on this machine from the cached real data
(`PYNHTS_CACHE_DIR=local_data/cache`, `pynhts.load(wave, offline=True, replicates=True)`) or read from the
official documents in `local_data/docs_*` and the pinned 2017/2022 PDFs. Anything not verified is marked
**unverified**. Minimal reproductions are given inline; they run as written against the cache.

---

## 1. Verdict

**The engine is sound; the semantic layer is not yet safe.** Not ready to be declared closed.

What is solid (verified, not taken on trust):

* The replicate-variance engine is numerically correct. An independent implementation with R's `survey`
  package, reading the **raw CSV files** (not the pynhts Parquet), gives the same estimates and standard errors
  to 1e-7: 2009 one-person households SE 53,388.56 (R) vs 53,388.57 (pynhts); 2001 household vehicles
  202,586,200 with SE 672,071.9 in both, which equals the 2001 User's Guide example (672,072) to the unit.
* The replicate factors match what FHWA actually used in its published tables: in the 2009 *Summary of Travel
  Trends*, 20 of the 21 printed margins of error with enough digits are `t(0.975,100) x sqrt(0.99) x SE_raw`
  (ratio 1.9740 exactly for VMT and PMT).
* Replicate groups are aligned across household, person and travel-day weights in 2001, 2009 and 2017 (100 %
  of persons have their deleted replicate equal to their household's), so `ratio_across` is valid there.
* Domain estimation is design-correct by construction: filtering rows never drops replicate units (unit
  matrices keep all units), so the classic "filter instead of domain=" variance bug cannot happen with
  `survey_rows`.
* All 26 numeric claims of README/docs that I recomputed hold (Section 7; one carries a false explanation),
  the codebook-frequency tests for 2001/2009 pass (3,435 and 6,327 lines), all recipe statuses equal their
  expected status.

What is not safe (each confirmed with data, Section 2):

1. **Non-answer codes leak into numbers.** In 2001/2009, the codes -3, -4, -5, -6 (e.g. `TIMETOWK` -5 "did not
   work last week") are neither masked by `missing="nan"` nor by `skip="nan"`: 2009 mean commute time is
   biased by -0.87 min (about 5 standard errors).
2. **The default `skip="keep"` returns wrong numbers silently** for every numeric variable with a skip code:
   2009 mean `VMT_MILE` is 5.36 by default instead of 9.72; total VMT is 7 % low.
3. **Top-codes are undocumented in three of four waves**: `R_AGE` 88 means 85+ in 2001, 92 means 89+ in 2017
   and 2022 (not "92"), `VEHAGE` 40 means 33+ in 2001/2017/2022 and 35 means 25+ in 2009.
4. **`pynhts.tours` runs on 2001/2009 with 2017 purpose codes and returns zero home-based-work tours**, no
   error.
5. **2001 national-sample-only variables** (BESTMILE, the whole EIA fuel block, travel-period counts) are
   weighted with full-sample weights by default: annual VMT from BESTMILE is 13 % low.
6. **`compare_waves` misses a permuted code**: `URBAN` codes 1/2 are swapped between 2001 and 2009 but the
   status is `relabelled` ("same coded values").
7. **Publication footnote is wrong for three waves**: `tables.note()` always prints "delete-a-group
   jackknife, 98 replicate weights".
8. **Factual errors in the docs written last session** (2009 "no complete travel day", 2001 "computed trips
   of children 0-4", stale "2009 and earlier not supported", ...) and two crosswalk statuses that the data
   contradict.

None of these is hard to fix (most are S/M effort), but together they are exactly the "سوتی" the user wants
to avoid. The highest-value differentiator for the "close the file" release is not more waves or ML, it is a
**machine-readable, data-verified concept dictionary with per-wave comparability, universes, top-codes,
national-only flags and measured effect sizes, enforced by guards** (Section 8).

---

## 2. P0 bugs and errors found (with reproduction)

### P0-1. Negative non-answer codes other than -1/-7/-8/-9 are never masked (2001, 2009)

`tools/build_schema_pdf.py:48` defines `MISSING = {"-9", "-8", "-7"}` and `:250` only `-1` as skip; every other
negative code printed in the codebook is kept as a number. Schema scan (all four waves, every column): the
unmasked negative codes are

| wave | column | code | label | rows |
|---|---|---|---|---:|
| 2001 | TIMETOWK | -4 / -5 | did not work in usual workplace / did not work last week | 437 / 1,777 |
| 2001 | CARRODE | -5 | did not work last week | 23 |
| 2001 | OD_READ1 | -3 / -4 / -5 / -6 | no contact / vehicle sold / no odometer / broken | 5,107 / 518 / 463 / 25 |
| 2001 | OD_READ2 | -3 / -4 / -5 / -6 | idem | 17,377 / 3,237 / 74 / 353 |
| 2009 | TIMETOWK | -4 / -5 | idem | 962 / 3,097 |
| 2009 | CARRODE | -5 | did not work last week | 271 |

```python
import pynhts
d = pynhts.load(2009, replicates=True)
s = d.survey("person", ["TIMETOWK"], skip="nan")   # even with skip masked
s.mean("TIMETOWK")                                   # 23.335 min, n = 120,156 (includes -4/-5 as minutes)
s.mean("TIMETOWK", domain=s.rows["TIMETOWK"] >= 0)   # 24.205 min, n = 116,097; SE about 0.165
```
2001: 22.670 vs 23.540 min (2,214 rows). The 2017 test `test_no_unlisted_missing_or_skip_codes_in_data`
(`tests/data/test_loader_golden.py:63`) only looks for -9/-8/-7/-88/-77/-1 and only in 2017, so this was never
caught. **Fix:** in the schema builder, every negative labelled code that is not the skip code becomes a
missing code with its kind (`did_not_work`, `no_contact`, ...); regenerate the 2001/2009 schemas; add a
four-wave test "no negative value survives `missing='nan', skip='nan'` in any numeric column".

### P0-2. Default `skip="keep"` feeds -1 into numeric estimators

`NHTSData.table` and `survey` default to `skip="keep"` (`src/pynhts/core/data.py:156`, `:316`). The docstring
says numeric columns "need care", but the default path is the one humans and agents take:

| wave | `survey("trip", ["VMT_MILE"])` default mean | with `skip="nan"` | total VMT, default vs `skip="nan"` |
|---|---:|---:|---:|
| 2009 | 5.36 | 9.72 | -7.0 % |
| 2017 | 5.27 | 9.55 | -7.2 % |
| 2022 | 6.92 | 11.48 | -5.0 % |

`YEARMILE` mean: 8,796 vs 12,888 (2009), 7,682 vs 11,621 (2017). 2009 `TRPMILES` has 181 rows of -1.
**Fix:** `skip="auto"` as default: the skip code becomes NA in numeric columns (it is never a quantity) and
stays a code in coded columns; or estimators raise when a numeric variable still contains the skip code.

### P0-3. Undocumented top-codes in age and vehicle age

The schema stores ranges like `5-92`, and `docs/data_notes.md:190-191` says only 2009 `R_AGE` is top-coded.
The data say otherwise (counts of values; the values between threshold and code never occur):

| wave | R_AGE near the top | meaning | VEHAGE top | VEHYEAR bottom |
|---|---|---|---|---|
| 2001 | 84: 478, 85-87: none, **88: 1,983** | 88 = 85+ (not labelled in the codebook) | 40 (1,745 veh., 1.25 %), 33-39 absent | 1962 = 1969 or older |
| 2009 | 88: 1,091, **92: 3,176** | 92 = 89+ (codebook) | 35 = 25+ (codebook; 11,976, 3.87 %) | 1974 = 1984 or older |
| 2017 | 88: 718, 89-91: none, **92: 2,557** | 92 = 89+ (codebook says range 5-92) | 40 (6,765, 2.64 %), 33-39 absent | 1977 = 1984 or older |
| 2022 | 88: 28, 89-91: none, **92: 128** | 92 = 89+ | 40 (287, 1.95 %), 33-39 absent | 1982 = 1989 or older |

Also top-coded: 2001 `HHR_AGE`, `AGE_P1..P9`, `R_AGEWGT` (max 88), 2017 `R_AGE_IMP`. Naive means: mean
vehicle age 8.87 / 9.39 / 10.38 / 10.32 years; the upward bias is bounded by share x (code - threshold), up to
0.39 years in 2009 and with a different threshold (25+) than the other waves. **Fix:** a `topcode` field per
column (threshold, code, source "codebook" or "data"), a warning from `mean()`/`ratio()` on top-coded
variables, and harmonized age bands that end at 85+.

### P0-4. Tours silently wrong for 2001 and 2009

`NHTSData.tours` (`src/pynhts/core/data.py:479-521`) has no wave check, and `TourConfig` defaults are 2017
codes (`src/pynhts/tours/config.py:28-29`: home `{"01","02"}`, work `{"03"}`). In 2009 work is 10-14 and `03`
does not exist; in 2001 work is 11-14.

```python
from pynhts.tours import build_tours
t = pynhts.load(2009).trips(["WHYFROM", "WHYTO", "TRPTRANS", "STRTTIME", "ENDTIME"],
                            weight=False, missing="keep")
t = t[t.HOUSEID.isin(t.HOUSEID.drop_duplicates().iloc[:5000])]
build_tours(t).tours.tour_class.value_counts()     # HBO 14,437, NHB 1,030, HBW: none
```
2001: HBO 17,095, NHB 1,451, HBW none. (`d.tours()` itself was not called because it writes into the cache.)
**Fix:** raise unless `wave == 2017` or a wave-specific config is passed explicitly.

### P0-5. 2001 national-sample-only variables weighted with full-sample weights

The 2001 file mixes the national sample (26,038 households, `WTHHNTL` present) and nine add-on areas. Some
variables exist only for the national sample; for add-on records they are -1. Scan of skip-or-NA share
(national / add-on):

* vehicle: `BESTMILE` (0.01/0.99), `FUELTYPE`, `VTYPFUEL`, `EPATMPG`, `EPATMPGF`, `EIADMPG`, `GSYRGAL`,
  `GSTOTCST`, `GSCOST`, `BTUCOST`, `BTUTCOST`, `BTUYEAR`, `ANNUALZD`, `ANULZDSE`, `BEST_FLG` (all 0.00/1.00);
* household/person/trip: `CNTTPHH`, `CNTTPTR`, `CNTTPUNQ`, `BEGTRAV`, `ENDTRAV`, `TPOVRLAP`;
* the whole long-distance file (`LDTPUB`, 100 % of rows in national households).

The User's Guide confirms BESTMILE "computed only for vehicles in the National Sample households"
(`UsersGuide.txt:20847`). With the default `WTHHFIN`:

```python
d = pynhts.load(2001)
v = d.vehicles(["BESTMILE", "WTHHNTL"], missing="keep")
ok = v.BESTMILE >= 0
(v.BESTMILE[ok] * v.WTHHFIN[ok]).sum()                          # 2.055e12 annual VMT
(v.BESTMILE[ok & v.WTHHNTL.notna()] * v.WTHHNTL[ok & v.WTHHNTL.notna()]).sum()   # 2.359e12
```
`d.survey("vehicle", ["BESTMILE"], skip="nan").total("BESTMILE")` returns the 2.055e12 (-12.9 %), with no
warning. **Fix:** flag these columns `national_only` in the schema/concept dictionary; `survey()` warns (or
raises) when one of them is analysed with full-sample weights; document the right weight. Note: national
household replicates (`FHHWT01-99`) are **not** in the public replicate archive (only `WTHFIN`, `EXPFHH` in
`hh50wt.csv`), so design-correct SEs for national household/vehicle estimates are not available.

### P0-6. `compare_waves` declares a swapped code system "relabelled"

`harmonize._similar` (`src/pynhts/harmonize/__init__.py:146-152`) accepts labels that share a third of their
words. `URBAN`: 2001 `1` = "In an Urban cluster" (8,752 HH), `2` = "In an urban area" (43,414); 2009 `01` =
"In an urban area" (91,918), `02` = "In an Urban cluster" (14,582).

```python
from pynhts import harmonize
c = harmonize.compare_waves(2001, 2009); c[c.variable == "URBAN"].status   # 'relabelled'
```
`relabelled` is documented as "same coded values, other wording", i.e. poolable. A permutation detector
(label of code k in wave A equals the label of another code in wave B) finds it; it also flags the expected
cases (TRPTRANS, WRKTRANS, PRMACT, R_RELAT ...). Caveat for the detector: `_norm` strips symbols, so
"Crude Estimate/4" equals "Crude Estimate*4" (`BEST_OUT`); compare labels with symbols kept.

### P0-7. Wrong methods footnote in generated tables

`src/pynhts/tables.py:132-133` always returns "(delete-a-group jackknife, 98 replicate weights)". That is false
for 2001 (99 replicates, delete-one JK1), 2009 (100 replicates, JK2), 2022 (Taylor series, no replicates) and
inexact for 2017 (stratified JKn, not delete-a-group). Anyone pasting `to_latex` output into a paper on
2001/2009/2022 publishes a false methods statement. **Fix:** build the note from the registry of the wave
the result came from (results need to carry their wave and design).

### P0-8. False or stale statements in the docs (written last session)

| where | statement | evidence |
|---|---|---|
| `docs/data_notes.md:178-180`, `CHANGELOG.md:23-24` | 2009 `DAYWGT` is missing for 45,967 persons "(no complete travel day)" | They are exactly the persons with **zero trips**: all 45,967 have `CNTTDTR = 0`; no zero-trip person has a day weight; weighted share 13.15 % of persons. In 2001 (19,843) and 2017 (45,040) zero-trip persons do have a day weight. |
| `docs/data_notes.md:228-229`, `src/pynhts/recipes/stt_trends.py:9` | children 0-4 "whose trips the survey contractor computed" / "imputed" | 2001 User's Guide 2-D.2 (`UsersGuide.txt:1571-1574`) and STT 2001 "Travel of 0-4 year-olds" (`STT.txt:520-526`): travel of 0-4 year-olds was **collected** ("measured for the first time"), not computed. |
| `docs/methods.md:101` | "2009 and earlier waves are not supported." | Stale since 0.4.0. |
| `docs/waves.md:135` | "Geography, vehicle models, state add-ons exist in 2017 only" | 2001 and 2009 have `HHSTATE`, `MAKECODE`/`MODLCODE` and add-on samples. |
| `docs/data_notes.md:190-191` | 2009 `R_AGE` is top-coded (implies only 2009) | All four waves are top-coded (P0-3). |
| `docs/data_notes.md:213-215` | longdist rows carry "the travel-period person weight" for "the travel-period sample" | It is the **national-sample** travel-period weight (User's Guide Table 7-3, "National Weights"), `WTPTPFIN = WTPRNTL x 365/28` in all 45,165 rows. |
| `docs/data_notes.md:242-243` | UG example reproduced "to 0.05 % by the SE" | Understated: 672,071.9 vs 672,072 (R and pynhts). The test tolerance `rel=5e-4` (`tests/data/test_old_waves_real.py:101`) can be tightened to `abs=1`. |
| docstrings | "98 replicates", "NHTS 2017" | `stats/survey.py:5,213,347`, `stats/jackknife.py:1`, `core/data.py:304` (longdist "2022 only"), `:323`, `:623`, `io/fetcher.py:97` ("only 2017 in Phase 1"), `io/converter.py:9`, `docs/index.md:22`, `paper/paper.md:27`. |

### P0-9. Two crosswalk statuses contradicted by the data

`src/pynhts/harmonize/crosswalks.yaml` (cross-tabulated against ORNL's derived variables in every wave):

* **2001 `WHYTRP1S` 13 -> `other`, status `exact` (line 254).** In 2001, 39.7 % (weighted) of code-13 trips have
  `WHYTO` 20 "School/religious activity" (4,019 trips), 2.6+0.5+0.4 % have a refused/don't-know/NA `WHYTO`;
  in 2009 `WHYTO` 20 goes to `WHYTRP1S` 20 (3,341 trips). So 2001 `other` is inflated and
  `school_daycare_religious` deflated; the status must be `approximate` with that note.
* **2009 (and 2001) Amtrak `15` -> summary `public_transit` (lines 160, 185).** ORNL's own 2009 `PUBTRANS`
  puts Amtrak (116 trips), ferry (123) and special transit (621) **outside** public transit and codes
  09/10/16/17/18 as transit; the 2022 guide puts Amtrak in "other transit". Only 2017 code 15 (Amtrak *and*
  commuter rail in one code) is mixed. Map 2009/2001 Amtrak to `other_transit` and test the summary level
  against `PUBTRANS` (2009, 2017, 2022) and `TRIPMODE` (2022).

### P0-10. Frames carry no wave; `harmonize.apply` trusts the `wave=` argument

```python
t17 = pynhts.load(2017).trips(["TRPTRANS"], weight=False)
harmonize.apply(t17.TRPTRANS, "mode", wave=2009)   # 100.0 % mapped, agrees with wave=2017 on 0.7 % of rows
t17.attrs                                           # {}
```
And pooling raw codes is unguarded: share of trips with `TRPTRANS == "01"` is 0.443 in 2009 (car) and 0.105 in
2017 (walk). **Fix:** set `frame.attrs["pynhts"] = {"wave":..., "table":..., "weight":...}` (and on the
`Survey` objects); `apply` raises on a mismatch; a `pynhts.concat_waves()` that refuses raw coded columns
listed as `codes_changed`.

---

## 3. Statistical audit

### 3.1 Replicate designs, checked against the documents and against the weights themselves

Structure measured on the replicate files (share of units with weight 0 in each replicate; how often a unit is
zeroed; strongly perturbed units = |replicate/full - 1| > 0.25):

| wave | documents say | measured structure | factor used | verdict |
|---|---|---|---|---|
| 2001 | "delete-one Jackknife", formula 98/99 x sum (UG 7-E.1, `UsersGuide.txt:4518-4539`) | 1.00 % of units zero per replicate (HH 643-792 of 69,817); 69,289 HH zeroed exactly once, 528 never; no other strong perturbation | 98/99, df 99 | consistent with JK1; R `svrepdesign(type="JK1")` gives the identical SE |
| 2009 | UG 7-6: "Jackknife2", formula 99/100 x sum; UG change log 4/18/11 "JK2 was used not JK1"; Weighting Report 2.2: each variance stratum split in two halves, one deleted and the other **doubled**, strata combined into 100 groups | 0.50 % of units zero per replicate; 74,825 HH zeroed once, 75,322 never; median 844 HH strongly perturbed per replicate (the doubled halves); `VARSTRAT` (public file) = index of the replicate that zeroes the unit for 100 % of zeroed HH | 99/100, df 100 | **structure is JK2; the textbook JK2 coefficient is 1, not 99/100.** But FHWA's published 2009 MOEs use 99/100 (20 of 21 tight targets fit `t100 x sqrt(0.99)`), and R matches pynhts with that factor. Keep 0.99 as the FHWA convention; document that the design-based JK2 SE is sqrt(1/0.99) = 0.50 % larger (R `type="JK2"`: 53,657.5 vs 53,388.6). |
| 2017 | Weighting Report 2.2: JKn, 14 variance strata x 7 units, factor (n_h-1)/n_h = 6/7 | every unit zeroed exactly once; 122-3,797 zero units per replicate | 6/7, df 98 | consistent. Design df would be 98 - 14 = 84 (t 1.989 vs 1.984); FHWA used 98, keep. |
| 2022 | Weighting Memo p. 32: Taylor series, strata + household clusters (SAS example) | 20 strata, 7,893 HH | Taylor, df per domain | consistent; validated against R before. Note SAS `PROC SURVEYMEANS` uses the full-design df for domains, pynhts the domain df (`survey::degf` on a subset); more conservative for small domains. Taylor treats the trimmed/raked weights as fixed (no calibration term). |

Alignment of replicate groups (prerequisite of `ratio_across`): person vs household and person vs travel-day
deleted replicate agree for 100 % of persons in 2001, 2009 and 2017. **Exception:** the 2001 long-distance
replicates `FPTPWT01-99` are a different (national) replicate system; only 9.2 % of national persons share
their deleted index with `WTPFIN`. `ratio_across(d01.survey("longdist"), None, d01.survey("person"))` still
runs (no check in `src/pynhts/stats/survey.py:340-367`). Measured effect is small: per-person long-distance
rate 9.441, SE 0.13612 (mixed) vs 0.13611 (consistent, national persons from the same replicate file); for
persons 65+ SE 0.1982 vs 0.1967 (+0.8 %) and estimate 6.685 vs 6.673 (different denominators). Add a guard and
a documented helper rather than leaving it to luck.

### 3.2 Weights and what their totals mean

* **All travel-day totals are annual.** `WTTRDFIN = 365 x WTPERFIN` in 2001, 2009 and 2017 (2009 replicates:
  ratio 365 +/- 3e-5 in all 100). `d.survey("trip").total()` is annual person trips (2009: 3.92e11); an agent
  dividing by persons gets "1,385 trips per person". Nowhere in `docs/methods.md` is "annual" said.
* **2022 is different:** `WTTRDFIN` includes the methods adjustment. Daily trips per person = 2.078 from
  `CNTTDTR x WTPERFIN` but 2.275 from trip weights (+9.5 %); in 2009 and 2017 the two routes agree (3.794,
  3.372). Both look legitimate; only the trip-weight route is the official one.
* **2009 zero-trip persons** have no `DAYWGT` (P0-8). Because their replicate day weight would be exactly 365 x
  `WTPERFIN`, filling it in is safe and would let person-day analyses at `level="trip"` include non-travelers
  (today `_bind` raises "rows belong to a unit with a missing weight", `core/data.py:407-411`).
* **2001 long-distance file:** national sample only, `WTPTPFIN = WTPRNTL x 365/28` (ratio 13.0357 = 365/28 in
  every row), one row per trip of 50+ miles in the 28-day travel period. `survey("longdist").total()` =
  2,617 million annual long-distance person trips (SE 37.7 million): meaningful, but it must be labelled
  "annual, national sample". Household-level travel-period trips need `WTTRPNTL` (not offered).
* **2022 long-distance file:** one row per person (16,997 = all persons), person weight; `total()` counts
  persons, not trips. Same method name, opposite meaning to 2001.
* **2001 100 %-reported households** (`EXPFLLHH`, `EXPFHH1-99`) and national weights: not exposed; the 2001 UG
  (`UsersGuide.txt:4380-4387`) says that for most estimates "it may be preferable to use the national sample"
  because add-on response rates were lower. pynhts silently uses the full sample. National person/trip
  replicates could be derived as `FPTPWT_r x 28/365` (and x 28 for trips) for the 60,282 national persons:
  **inferred, unverified at replicate level** (only the full weights were checked).
* **2022 population** excludes group quarters (about -2.5 %, compatibility doc p. 3); prior waves were
  weighted to the 5+ population including them. 2022 weights also include a non-traveler adjustment from ATUS
  and were calibrated to ACS journey-to-work modes and telework, so 2022 commute mode shares are not
  independent of the ACS.

### 3.3 Other estimator checks

* Ratio and mean estimators recompute the ratio under every replicate (correct). Complete-case handling inside
  the domain is documented.
* Units with zero weight (2022 weekday/weekend sets) stay in the variance and leave the df (correct).
* df choices: 2001 uses 99 (JK1 convention is R-1 = 98; t differs in the 4th digit), 2017 uses 98 (FHWA; design
  df 84). Harmless, but say it.
* **2009 User's Guide worked example is an unused oracle:** "total transit trips 7,492,304,015, SE
  250,003,726" (`UsersGuideV2.txt:3309-3313`). `PUBTRANS == "01"` gives 7,519,544,155 (+0.36 %), SE 248.7 M
  with factor 0.99 and 249.9 M with factor 1. Not reproduced; the estimate gap suggests another data version or
  definition (**unexplained**). Worth one more attempt, then document.

---

## 4. Variable comparability evidence table

Legend: **C** comparable as is (after padding), **H** comparable after an explicit harmonization, **N** not
comparable / do not pool. "data" = verified on the files in this review; "doc" = official document.

| # | concept (names by wave) | 2001 | 2009 | 2017 | 2022 | comp. | trap | evidence |
|---|---|---|---|---|---|---|---|---|
| 1 | Age `R_AGE` | 0-88, 88 = 85+, 2,399 missing; imputed `R_AGEWGT` | 5-88, 92 = 89+, no missing (imputed during weighting, UG 2-14) | 5-88, 92 = 89+, 496 missing; `R_AGE_IMP` | 5-88, 92 = 89+, no missing (imputation **unverified**) | H | 2001 includes 0-4 (mean age 35.5 vs 38.1 for 5+); different top-code threshold; use the imputed version per wave | data; UG 2009 p. 2-14 |
| 2 | Sex `R_SEX` | `"1"/"2"`, 21 missing | `"01"/"02"`, no missing (imputed) | -7/-8 present; `R_SEX_IMP` | 237 missing; `R_SEX_IMP` | H | use imputed versions; padding | data |
| 3 | Household income `HHFAMINC` | 18 codes, $5k bands, top 100k+ | 18 codes, same | 11 codes, top 200k+ | 11 codes; `HHFAMINC_IMP` | H | nests into 8 nominal bands (<10k, 10-15, 15-25, 25-35, 35-50, 50-75, 75-100, 100k+); **nominal dollars** | data |
| 4 | Education `EDUC` | 8 codes (incl. vocational, some graduate), asked 16+ | 5 codes, asked 18+ | 5 codes, answered from 14 | 8 codes (other meaning), answered from 14 | H | different universes: restrict to 18+ (better 25+); 2001/2022 detail must collapse | data (skip ages) |
| 5 | Race (household) | `HHR_RACE`, 17 codes incl. "Hispanic/Mexican only" and combinations | `HH_RACE`, 07 = Hispanic/Mexican (3,892 HH) | `HH_RACE`, Hispanic separate (`HH_HISP`) | idem | N/H | names differ (HHR_ vs HH_); Hispanic is a race code in 2001/2009 | data |
| 6 | Race (person) `R_RACE`, `R_HISP` | absent | absent | present | present (`R_RACE_IMP`) | N | only 2017/2022 | schema |
| 7 | Worker `WORKER` | skip ages 0-14 | 16+ | 16+ | 16+ | H | universe; 2001 `"1"` | data |
| 8 | Driver `DRIVER` | skip ages 0-14 | 15+ | 15+ | 15+ | H | universe | data |
| 9 | Primary activity `PRMACT` | 11 codes, 16+ | 11 codes | 10 codes | asked of **non-workers only** (no "working" code; 9,752 skips) | N | universe changed in 2022 | data |
| 10 | Relationship `R_RELAT` | 1 = self | 01 = self | 01 = self | **07 = self**, 01 = spouse | H | codes permuted (flagged `review_labels`) | data |
| 11 | Household size `HHSIZE` | all ages | all ages | all ages | all ages, max 10 | C | completed-household rule changed in 2022 (all 5+ members for 1-3 person HH) | data; compat 2022 |
| 12 | Vehicles `HHVEHCNT` | = vehicle rows | differs from vehicle rows in 0.68 % of HH | = rows | = rows | C (mostly) | 2009 file includes golf carts (VEHTYPE 08, 292 rows); STT "household vehicles" = types 01-07 | data |
| 13 | Life cycle `LIF_CYC` | 10 codes | same | same | same | C | 2001 -9 (69) | data |
| 14 | Workers `WRKCOUNT` | "with jobs", max 10 | max 6 | max 7 | max 6 | C | worker universe | data |
| 15 | Urban/rural `URBRUR` | 1/2 | 01/02 (-9: 2) | 01/02 | 01/02 | H | geography vintage differs (2017 label: 2014 TIGER; others **unverified**) | data |
| 16 | Urbanized area `URBAN` | **1 = cluster, 2 = urban area** | 01 = urban area, 02 = cluster | as 2009 | as 2009 | N/H | swapped codes, `compare_waves` misses it (P0-6) | data |
| 17 | Claritas density `HBHUR` | U,S,C,T,R | U,S,C,**TC** (town and country merged), X | U,S,C,T,R | numeric 01-05 | H | 2009 merges town+rural | data |
| 18 | MSA size `MSASIZE` | 6 codes | 6 codes | 6 codes | 6 codes | C/H | MSA delineation vintage differs | data |
| 19 | Census division/region | unpadded | padded | padded | padded | C | 2001 sample dominated by add-on states (WI 17,547 HH): never unweighted | data |
| 20 | State `HHSTATE` | 36 codes incl. **"XX" suppressed** (1,950 HH) | 51 | 51 | absent | N | "XX" is not masked; 2022 none | data |
| 21 | CBSA `HH_CBSA` | absent | large CBSAs + **"XXXXX"** suppressed (83,369 HH) | large CBSAs + "XXXXX" (73,746) | absent | N | suppression code treated as a value | data |
| 22 | Trip distance `TRPMILES` | self-reported, 85 % integer, -8: 7,023 (1.1 %) | self-reported (converted), 84 % integer, -8: 17,734 (1.5 %), -1: 181 | shortest path, 99 % non-integer, -9: 656; `TRPMILAD` x1.0735/1.1151 | calculated, 99 % non-integer, -9: 14 | N/H | method change (~10 % shorter in 2017, compat doc); heaping in 2001/2009; missing distances add 0 miles | data; compat 2017 |
| 23 | Driver distance `VMT_MILE` | absent (use driver `TRPMILES`) | -1 on 419,179 trips | -1 on 312,273 | -1 on 10,584 | H | P0-2 default trap | data |
| 24 | Trip duration `TRVLCMIN` | 0-1439 | 0-1439 | 0-1200 | 0-1425 | C | 2017 cap | data |
| 25 | Dwell time `DWELTIME` | skip -1 on 21.7 % | -9 on 23 % | -9 on 24 % | -9 on 34 % | H | the "missing" is structural (last trip of the day), coded differently | data |
| 26 | Start/end time `STRTTIME`/`ENDTIME` | HHMM, -9 | HHMM, -9 | HHMM | HHMM, -9 | C | strings | data |
| 27 | Travel day `TRAVDAY`, `TDWKND`, `TDAYDATE` | `"1"`..`"7"` (1 = Sunday) | padded | padded | padded | C | travel days: 2001 Mar 2001-Jun 2002 (incl. 9/11), 2009 Mar 2008-Apr 2009, 2017 Apr 2016-Apr 2017, 2022 Jan 2022-Jan 2023 (pandemic recovery) | data (TDAYDATE) |
| 28 | Trip mode `TRPTRANS` | 26 codes | 24 codes | 21 codes | 21 codes | H | crosswalk exists; Amtrak summary issue (P0-9) | data; crosswalk |
| 29 | Summary purpose `WHYTRP1S` | 13 codes 01-13 | 01,10..97 incl. 60 | no 60 | no 60 | H | crosswalk; 2001 13 issue (P0-9) | data |
| 30 | **1990-NPTS purpose `WHYTRP90`** | 12 codes | 12 codes | 10 codes | 10 codes | H (official!) | ORNL's own cross-wave purpose, present in all four waves; 07 vacation only 2001/2009; **98 N/A and 99 refused not masked** (9,837 rows in 2009) | data |
| 31 | Home-based purpose `TRIPPURP` | `"1"`..`"5"` | `HBW`.. strings | strings | `"01"`..`"05"` | H | same 5 classes, three code formats | data |
| 32 | Trip linking | linked (mode changes not trips) | linked | WHYTO 07 "change type of transportation" = 1.07 % of weighted trips | WHYTO 09 = 0.69 % | N/H | 2017/2022 count some transfer segments as trips | data; STT 2009 App. B |
| 33 | Trip counts (method) | CATI, prompts | CATI, prompts | 66 % web without prompts | 99 % web, no travel log, **trip weights adjusted +10-12 %** | N | not like-for-like trip rates | compat 2017, 2022 |
| 34 | Vehicle type `VEHTYPE` | 91 = other | 08 golf cart, 97 other | 97 something else | no 97/08 | H | | data |
| 35 | Fuel `FUELTYPE` | numeric, 1 = diesel ... 4 = gasoline, **national sample only** | numeric 1-4 | string, **01 = gas**, 02 = diesel, 03 = hybrid/electric/alt | absent (`HYBRID`) | N/H | codes reversed; typed numeric in 2001/2009 | data |
| 36 | Hybrid `HYBRID` | absent | asked for model year 2002+ only | all | all | H | universe | data; STT 2009 |
| 37 | Vehicle age `VEHAGE`/`VEHYEAR` | 40 = 33+ | 35 = 25+ | 40 = 33+ | 40 = 33+ | H | top-codes (P0-3) | data |
| 38 | Annual miles `BESTMILE` | **national sample only** | all | all | absent | N/H | P0-5 | data; UG 2001 |
| 39 | `ANNMILES` (self-report) | -8 on 4.3 % | -8 on 2.2 % | -9 on 26 % | -9 on 1.5 % | H | very different item nonresponse | data |
| 40 | `YEARMILE` | -8 on 15 % | -8 on 16 % | -88 on 21 % | absent | H | | data |
| 41 | Transit use `PTUSED` | categorical frequency, last 2 months | count of uses, past month, 0-180; 99 hidden missing; -9 on 32 % | days used of 30 | days of 30, asked of 9.5 % only | N | four definitions | data; codebooks |
| 42 | Commute time `TIMETOWK` | -4/-5 codes | -4/-5 codes | 0-600 | absent | H | P0-1 | data |
| 43 | Distance to work `DISTTOWK` | -9 on 27 % | ok | absent | absent | N | | data |
| 44 | Medical condition `MEDCOND` | asked 16+ | 15+ | all 5+ | all 5+ | H | universe | data |
| 45 | Weights | full sample incl. 9 add-ons; national weights for some items | incl. add-ons | incl. add-ons; weights at higher geography | national only; excludes group quarters; non-traveler and ACS calibration | N for levels | compare rates and shares, not totals | docs |

At least 30 of these rows were verified on the data in this review (distributions, codes, ranges, universes).

---

## 5. Agent and human misinterpretation traps, and the guard that would catch each

Each line was run ("naive agent" one-liners) unless marked.

| # | naive action | what comes back | right answer / issue | guard |
|---|---|---|---|---|
| 1 | `survey("trip",["VMT_MILE"]).mean("VMT_MILE")` | 5.36 (2009) | 9.72 | `skip="auto"` default (P0-2) |
| 2 | `survey("person",["TIMETOWK"],skip="nan").mean(...)` | 23.34 | 24.21 | mask all negative non-answer codes (P0-1) |
| 3 | mean `R_AGE`, 2001 vs 2017 | 35.47 vs 40.72 | 38.06 (2001, 5+) vs 40.72 | warn: 2001 includes 0-4; top-code warning |
| 4 | mean `VEHAGE` per wave | 8.87 / 9.39 / 10.38 / 10.32 | biased up, thresholds differ | `topcode` metadata + warning |
| 5 | `survey("trip").total() / survey("person").total()` | 1,385 "trips per person" (2009) | /365 = 3.79 | result `unit` column ("annual person trips"); docs |
| 6 | 2022 trips per person from `CNTTDTR x WTPERFIN` | 2.078 | 2.275 with trip weights | concept note + a `rates()` helper that uses the official route |
| 7 | pool raw `TRPTRANS` 2009+2017 | "01" share 44 % / 11 % | car vs walk | `concat_waves` refusing `codes_changed` columns |
| 8 | `harmonize.apply(..., wave=2009)` on 2017 codes | 100 % mapped | 0.7 % agreement | wave tag in `attrs`; `apply` checks |
| 9 | `d09.tours()` / `build_tours` on 2009 | 0 HBW tours | work codes 10-14 | wave check in `tours` |
| 10 | `d01.survey("vehicle",["BESTMILE"]).total(...)` | 2.055e12 | 2.359e12 with national weights | `national_only` flag + warning |
| 11 | `d01.survey("longdist").total()` read as "trips in the travel period" | 2.617e9 | it is annual (x365/28) and national | labelled units; docs |
| 12 | `d22.survey("longdist").total()` read as "long-distance trips" | the person total, about 3.06e8 (inferred: 16,997 rows = all persons, person weight; not run) | it counts persons | same |
| 13 | `WHYTRP90` frequencies with `missing="nan"` | includes 98/99 (9,837 rows, 2009) | they are N/A/refused | mask positive missing codes |
| 14 | state shares in 2001 | "XX" is a state (1,950 HH) | suppressed | suppression code kind |
| 15 | `compare_waves(2001,2009)` says URBAN `relabelled` | pool it | codes swapped | permutation detector |
| 16 | `to_latex(..., notes=None)` for a 2022 table | "98 replicate weights" | Taylor series | wave-aware note |
| 17 | `survey_rows(rows, "trip")` with 2009 non-travelers | NHTSIntegrityError | legitimate analysis | fill 2009 day weights |
| 18 | `survey_rows(rows, level=0.9)` thinking `level` is the confidence (as in `survey()`) | ValueError (read from code, not run): here `level` is the weight unit, confidence is `level_conf` | API naming | rename with deprecation (P2) |
| 19 | `table(..., weight=...)` vs `weights=...` | two parameters, one bool, one weight set | confusion | rename (P2) |
| 20 | 2022 `PARK2_PAMOUNT` mean | $36.8 | mixes one-time, weekly, monthly, yearly payments (`PARK2_PAYTYPE`) | concept note (unverified impact) |
| 21 | filtering rows instead of `domain=` | same SE (design kept) | — | already safe (good) |

### AI-readiness of the docs

* No `AGENTS.md`, no `llms.txt`, no machine-readable statement of units, universes, top-codes, national-only
  status or cross-wave comparability. `pynhts.dictionary()` / `describe()` expose codebook facts only
  (owner, type, codes, missing codes, range).
* Docstrings are good in style but several are stale (P0-8). Results do not carry their wave, weight or unit,
  so an agent cannot self-check.
* What an agent needs, in this order: (1) a single `pynhts.concepts` table (YAML + function + JSON export)
  keyed by concept with per-wave variable name, universe, unit, harmonized categories, top-code, missing
  semantics, `national_only`, comparability grade and a measured effect size with source; (2) guards that
  read it; (3) a 1-page `AGENTS.md` with the 20 traps above and canonical recipes; (4) `llms.txt` pointing to
  them; (5) a task harness (Section 8, P1-9) to measure that agents stop falling into the traps.

---

## 6. Test and validation gaps

* **No four-wave invariant tests.** The 2017-only tests `test_no_unlisted_missing_or_skip_codes_in_data`,
  `test_inherited_columns_equal_parent_values` (`tests/data/test_loader_golden.py:63-105`) are not run for
  2001/2009/2022 and only look for six codes. (I checked the copies by hand: all child copies equal the parent
  in all four waves, except float-printing differences of 2001 `WTHHNTL`/`EXPFLHHN` in the vehicle file.)
* **No test of the replicate structure** (zero share per replicate, unit zeroed once, alignment across levels,
  2009 `VARSTRAT` = replicate index). These are cheap and would catch a wrong prefix, padding or file.
* **No independent cross-implementation for 2001/2009/2017 in the suite.** R reproduces pynhts exactly
  (Section 1); add a golden CSV like `tests/golden/taylor_2022_r.csv` from `svrepdesign` on the raw CSV.
* **2001 has no published MOE oracle except one** (UG vehicles). STT 2001 prints no MOEs. The 2009 UG transit
  example is unused (Section 3.3).
* **Recipes cover Tables 1 and 3 only.** Unused published oracles: STT 2009/2001 tables of trips by purpose,
  mode share, trips by age and sex, commute length and time, vehicle availability, vehicle occupancy;
  2017 STT tables beyond 1/3; 2022 User Guide tables beyond 10/11; the 2001/2009 columns that the 2017 STT
  reprints (cross-wave oracle for the same quantity computed in two reports).
* **Crosswalk tests** check coverage (>99.9 % mapped) and 2017/2022 against `WHYTRP1S`/`TRIPMODE`, but not 2001/
  2009 against `PUBTRANS`/`TRPPUB`/`WHYTO` (which found P0-9).
* **CI never touches data.** The 2022 archive is 4.5 MB and the 2017 core 84 MB; a scheduled data job is
  cheap. Locally, `pytest` (README "unit tests, no data needed") errors at collection without matplotlib
  because `tests/unit/test_viz.py:5` imports it unconditionally (use `pytest.importorskip`).
* Tours: `chain_ids` remains unvalidated (documented); tours never tested on 2001/2009/2022.

Tests that would have caught real bugs here: four-wave "no negative values after masking" (P0-1),
"estimators refuse a numeric column holding the skip code" (P0-2), "values between top-code threshold and code
never occur" (P0-3), "tours refuse waves != 2017" (P0-4), "national-only columns warn" (P0-5), permutation
detector on all wave pairs (P0-6), "summary mode public_transit == PUBTRANS" (P0-9).

---

## 7. Fact-check of documentation claims

24 numeric claims were recomputed; all hold except where noted in P0-8.

| claim (file) | recomputed | verdict |
|---|---|---|
| 2017: 31 of 37 reproduce, 3 estimate-only, 3 gaps (README:16-17) | 31/3/3 | true |
| 2009: 35 of 40, 5 MOE convention (README:13-15) | 35/5 | true |
| 2001: 40 of 47 (README:15) | 40 reproduced, 7 not | true |
| 2022: 15 of 18 (README:18) | 15/3 | true |
| 2017 drivers 223,277 thousand, MOE 827 (README:44) | 223,277 / 827 | true |
| 2017 mean TRPMILES 10.70, MOE 0.40 (README:45) | 10.70 / 0.40 | true |
| 2009 persons 283,054 thousand (README:61) | 283,054 | true |
| 386 names, 19 identical, 47 changed (README:65, waves.md:51-59) | 386/19/47; 111 + 142 only-one-wave | true |
| 107 copied columns: 35/35/37 (README:85, data_notes:36-38) | 35/35/37 | true |
| codebook lines 3,435 (2009) and 6,327 (2001) (README:91) | tests pass | true |
| 2009 PTUSED: 98,498 x -9 + 608 x 99 (data_notes:162-164) | 98,498 / 608 | true |
| 2009 VEHTYPE cars 151,238, SUV 58,718, four classes 294,409 (data_notes:165-168) | same | true |
| 2009 driven golf-cart trips 63.2 million (data_notes:197) | 63.2 | true |
| 2009 TRPMILES -1 on 181, -9/-8/-7 on 18,484 (data_notes:192) | 181; 17,734+454+296 = 18,484 | true |
| 2009 DAYWGT missing for 45,967 persons (data_notes:178) | 45,967 | count true, **reason false** |
| 2017 41 walk trips > 46 miles, max 2,648 (data_notes:81) | 41 / 2,648 | true |
| 2022 weekday 5,662 / weekend 2,231 / none both (data_notes:110) | same | true |
| 2022 3,767 of 10,592 person-days with varying trip weight (data_notes:111) | same | true |
| 2022 1,705 of 7,893 HH without trips (data_notes:113) | 1,705 | true |
| 2022 20 strata (methods:62) | 20 | true |
| purpose 14/18 and mode 13/20 categories comparable (waves.md:89-91) | 14/18, 13/20 | true |
| 2001/2009: 41 codes changed, 11 type changed; 2009/2017 37 and 4; padding 50 (waves.md:105-108) | same | true |
| TRPTRANS 08 and 19 meanings in the four waves (waves.md:110-112) | checked in schemas | true |
| 2001 persons 5+ 257,576 thousand, all ages 277,203 (data_notes:229-230) | 257,576.9 / 277,203.2 | true |
| 2001 2,399 persons without age (data_notes:236) | 10 + 792 + 1,597 | true |
| UG 2001 SE "to 0.05 %" (data_notes:243) | exact to the unit | understated |
| "2009 and earlier not supported" (methods:101) | | false (stale) |
| "children 0-4 trips computed by the contractor" (data_notes:228) | UG: collected | false |
| "Geography ... exist in 2017 only" (waves.md:135) | 2001/2009 have them | false |
| methods footnote in `tables.note` | | false for 3 waves |

Observation (hypothesis, unverified): three of the four "off by less than one unit" 2001 targets are
consistent with **truncation** in the 2004 report (257,576.9 -> 257,576; 132,239.6 -> 132,239; 384,484.8 ->
384,484), the fourth is not (64,611.2 -> 64,612).

---

## 8. Prioritized plan: four waves, close the file

Effort: S < 1 day, M 1-3 days, L > 3 days (agent-days). Risk = risk of the change itself.

### P0: must fix before declaring the package closed

| id | what | why (evidence) | acceptance test | effort | risk |
|---|---|---|---|---|---|
| P0-1 | Mask every negative non-answer code (kind per code) in 2001/2009; regenerate schemas | Section 2, P0-1 | four-wave test: after `missing="nan", skip="nan"` no numeric column holds a negative value; 2009 mean TIMETOWK = 24.21 | S | low (codebook-frequency test still passes because codes stay in the YAML) |
| P0-2 | Safe skip default (`skip="auto"`: NA in numeric columns, code in coded columns) or estimator error | P0-2 | `d09.survey("trip",["VMT_MILE"]).mean("VMT_MILE")` = 9.72 with defaults; existing recipes unchanged | S | medium: behaviour change, bump minor version, CHANGELOG |
| P0-3 | Top-code metadata (`topcode: {code, threshold, source}`) for R_AGE, R_AGE_IMP, R_AGEWGT, HHR_AGE, AGE_P*, VEHAGE, VEHYEAR in all waves; warning on mean/ratio; docs | P0-3 | test: values strictly between threshold and code have zero rows in every wave; `describe("R_AGE",2017)["topcode"]` = 92/89 | S-M | low |
| P0-4 | `tours` refuses waves other than 2017 unless a config is passed explicitly | P0-4 | `pynhts.load(2009).tours()` raises `ValueError` | S | low |
| P0-5 | `national_only` flag for 2001 columns (list in P0-5) + warning in `survey()`; doc the national weights and the lack of national HH replicates | P0-5 | test: the flagged list equals the data scan (skip share > 95 % in add-on, < 50 % in national); `survey("vehicle",["BESTMILE"])` warns | S-M | low |
| P0-6 | Permutation detector in `compare_waves` (`codes_permuted` status), labels compared with symbols kept | P0-6 | `URBAN` (2001, 2009) is not `relabelled`; known permutations listed in a test | S | low (more variables flagged is fine) |
| P0-7 | Wave-aware `tables.note` (method, replicates, factor, df) | P0-7 | note text for each of the four waves matches the registry | S | low |
| P0-8 | Correct the false/stale statements (table in P0-8) | P0-8 | doc test grep for "98 replicate", "not supported", "computed" | S | none |
| P0-9 | Crosswalk fixes: 2001 WHYTRP1S 13 `approximate` + note; 2009/2001 Amtrak summary `other_transit`; tests against PUBTRANS/TRPPUB/WHYTO | P0-9 | summary `public_transit` == `PUBTRANS=="01"` for every 2009 and 2017 trip; 2001 note asserts 39.7 % share | S | low |
| P0-10 | Results and frames carry `wave/table/weight/unit` (`attrs`); `harmonize.apply` raises on wave mismatch; results say "annual" where they are | P0-10, Section 3.2 | `apply(t17.TRPTRANS,"mode",wave=2009)` raises; `survey("trip").total()` has `unit == "annual person trips"` | M | medium (pandas `attrs` propagate imperfectly; keep it advisory plus explicit `wave=` checks) |

### P1: high value (the actual differentiators)

| id | what | why | acceptance test | effort | risk |
|---|---|---|---|---|---|
| P1-1 | **`pynhts.concepts`**: machine-readable dictionary of ~40 concepts x 4 waves (variable per wave, universe, unit, top-code, missing semantics, imputed version, national-only, comparability grade, pitfalls with measured effect and source); JSON/YAML export; used by the guards | no NHTS tool offers this; Section 4 is its seed | every row of Section 4 present; each data claim (universe ages, codes, top-codes, shares) is an executable assertion run on the real data | L | low; main risk is drift, mitigated because claims are tests |
| P1-2 | Extended crosswalks with `category_report`: income (8 nominal bands, CPI note), education (5 levels, 18+/25+), race/ethnicity (coarse, honest loss), URBAN/URBRUR/HBHUR, VEHTYPE, FUELTYPE, `TRIPPURP` (5 classes), **`WHYTRP90`** (official NPTS-90 purpose in all four waves), age bands to 85+, worker/driver 16+ | Section 4 rows 1-5, 15-17, 30-31, 34-35 | each crosswalk: 100 % of non-missing codes mapped, data cross-tab tests, loss report | M | low |
| P1-3 | Positive and string missing codes: WHYTRP90 98/99, suppression "XX"/"XXXXX" (kind `suppressed`), 2009 PTUSED 99 (done); review probable sentinels before masking: 2009 `MCUSED` 999 (45 rows, next value 700), `NWALKTRP` 99 (138 rows, next 98), 2022 `NUMONTRP` 99 (16, next 50), 2001/2009 `OD_READ*` 999999 (**unverified**) | Section 5 #13-14; sentinel scan | after masking, no labelled "N/A/refused/suppressed" code survives `missing="nan"` | S | low |
| P1-4 | Four-wave invariant test module (codes, top-codes, copies, replicate structure and alignment, 365 rule, 2022 exceptions) | Section 6 | runs on all four waves in < 5 min | M | none |
| P1-5 | 2009 day weights for zero-trip persons = 365 x WTPERFIN (all replicates; ratio verified 365 +/- 3e-5), documented | Section 3.2 | `survey_rows(persons_as_person_days, "trip")` works in 2009; trip totals unchanged | S | low |
| P1-6 | Variance-convention transparency: `convention="fhwa"` (default, current numbers) vs `"design"` (JK2 factor 1 in 2009, JK1 df 98, JKn df 84; Taylor full-design df like SAS); documented table | Section 3.1 | `"design"` equals R `svrepdesign(type="JK2")` for 2009 (53,657.5) | S-M | low if the default stays FHWA |
| P1-7 | `ratio_across` refuses surveys from different replicate systems (2001 longdist vs person/household); helper `longdist_rates()` using national persons from `ldt50wt` | Section 3.1 | mixed call raises; helper reproduces 9.441 / SE 0.13611 | S | low |
| P1-8 | Rates helper with the official route per wave (trip weights; 2022 adjustment; per-household via `ratio_across`) and units in results | Section 3.2, traps 5-6 | 2022 trips per person per day = 2.275; 2009 = 3.79 | S-M | low |
| P1-9 | `AGENTS.md` + `llms.txt` + an **agent task harness**: ~25 questions with oracle answers (STT figures, the traps of Section 5), a script that grades answers; run once with a plain LLM agent before and after the guards and publish the failure rate | AI-agent value is the stated goal; measurable | harness runs offline on the cache; documented baseline vs guarded failure counts | M | low |
| P1-10 | More oracles: 2009 UG transit example (try to explain the +0.36 %), STT 2009/2001 purpose and mode tables, the 2001/2009 columns reprinted in the 2017 STT, R `svrepdesign` golden CSV for 2001/2009/2017 | Section 6 | new recipe targets with expected statuses; golden R values equal to 1e-9 | M | low |
| P1-11 | CI: scheduled data job for 2022 (4.5 MB) and 2017 core; `importorskip` in `test_viz.py` | Section 6 | green scheduled workflow | S | low |

### P2: nice to have

* `weights="national"` for 2001 person/trip analyses with replicates derived from `FPTPWT x 28/365`
  (verify the derivation first: unverified) and the 100 %-reported weight sets (`EXPFLL*`).
* `concat_waves()` / pooled helper that returns long data with harmonized concepts and a **loss report**, and
  estimates per wave side by side; never a pooled weight.
* Linked-trip helper for 2017/2022 ("change type of transportation") for comparisons with 2001/2009, only if it
  can be validated against a published linked-trip figure (**unverified** that one exists).
* API cleanup with deprecation: `survey_rows(level=, level_conf=)` -> `unit=`, `level=`; `weight=` (bool) vs
  `weights=` (set) -> `with_weight=`.
* Type fixes: 2001/2009 `FUELTYPE` as coded strings; 2009 `WRKTIME` "08:00AM" vs 2017 "08:00 AM".
* Regression variance by replicate refits.
* Hosted docs; then the JOSS/methods paper, written after P0/P1 so that it can claim the concept dictionary,
  guards and the agent harness as contributions (measured, not asserted).

### Suggested order

P0-8, P0-7, P0-4 (hours) -> P0-1, P0-2, P0-3 (schema + loader, one release) -> P0-5, P0-6, P0-9, P0-10 ->
release 0.5.0 -> P1-4 (tests first) -> P1-1 with P1-2/P1-3 -> P1-5..P1-8 -> P1-9 (harness, measure) ->
P1-10, P1-11 -> 1.0.0 (needs the user's approval per the release rules) -> paper.

---

## 9. What not to do

* **No more waves** (pre-2001 NPTS is out of scope by decision) and no state/add-on special files.
* **Do not switch the 2009 factor to 1.0 by default.** FHWA's published MOEs use 0.99; offer the design
  convention as an option and document it.
* **Do not try to undo the 2022 trip adjustment, impute missing distances, or "correct" 2017 distances
  beyond TRPMILAD.** Document, measure, let the analyst decide.
* **Do not pool weights across waves** or build a single weighted multi-wave sample.
* **Do not attempt to harmonize all 386+ variables.** Curate ~40 concepts with evidence; leave the rest to
  `compare_waves`.
* **Do not extend `pynhts.tours` to 2001/2009/2022** without a published oracle for each wave; guard it instead.
* **Do not add ML features** (the `ml` bridge is enough); do not add an LLM inside the package.
* **Do not chase the remaining 2017/2022 recipe gaps** further; they are documented and not tuned.
* **Do not mask suspected sentinels (MCUSED 999, NUMONTRP 99, ...) without documentary evidence**; flag them
  as "suspected" in the concept dictionary instead.

---

## Appendix: how the evidence was produced

All scripts were run with `PYNHTS_CACHE_DIR=local_data/cache` and `python -I`; none writes to `local_data`.
They live in the session scratchpad (temporary); the essential code is reproduced inline above.

* Sentinel scan: every column of every table of the four waves, raw values vs schema codes/ranges
  (undeclared negatives, values outside the range, maximum equal to 9/99/999-type sentinels, mass at maximum).
* Label scan: codes whose label says refused/don't know/N/A/unknown but are not masked.
* Replicate structure and alignment: zero share per replicate, units zeroed once, deleted-replicate index
  compared across household/person/travel-day/long-distance files, 2009 `VARSTRAT`.
* MOE convention: `MOE_published / SE_raw` with its rounding interval for every 2009 STT target.
* R cross-check: `survey::svrepdesign` on `HHV2PUB.CSV` + `hh50wt.csv` (2009, factor 0.99 and JK2) and
  `VEHPUB.csv` + `hh50wt.csv` (2001, JK1).
* Crosswalk checks: cross-tabulations of the mode/purpose crosswalks against `WHYTRP90`, `WHYTO`, `PUBTRANS`,
  `TRPPUB`, `TRIPMODE`, `TRPHHVEH` in all four waves.
* Naive-agent probes: the one-liners of Section 5.
* Fact-check: README/docs numbers recomputed (Section 7); unit tests (137 pass, `test_viz.py` needs
  matplotlib); `tests/data/test_old_waves_real.py -k "codebook_frequency or row_counts"` (4 pass).
