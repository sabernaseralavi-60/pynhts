# NHTS 2017: pitfalls found while building pynhts

Every item below was checked against the files or the official documents, and each is covered
by a test. They are the reason the library exists.

## Download and files

* **The ORNL server answers HTTP 200 with an HTML page for files that do not exist.** A status
  check proves nothing. pynhts pins SHA-256 hashes for both archives and every member
  (`src/pynhts/_registry/2017.yaml`).
* The files dated 2019 and the archive currently served (modified 2023) are byte-identical:
  all four core CSV hashes match.
* There is **no trip-level replicate file**. `perwgt.csv` holds two blocks, the person weight
  (`WTPERFIN`, `WTPERFIN1..98`) and the travel-day weight (`WTTRDFIN`, `WTTRDFIN1..98`); trips
  get replicates by joining on `HOUSEID` + `PERSONID`.

## Codes

* Coded columns are **strings with leading zeros** (`"01"`). Letting a reader infer types
  silently turns them into integers. pynhts types every column from the codebook.
* Four different kinds of non-answer exist: `-9` not ascertained, `-8` don't know, `-7`
  refused, and `-1` **appropriate skip** (the question did not apply; not missing). `-88`/`-77`
  are "don't know"/"prefer not to answer" in numeric fields where -8/-7 could be real values.
* The codebook counts `-88` together with the `-8` rows (and `-77` with `-7`) in `YEARMILE` and
  `OD_READ`: 149 and 144 rows hold -8/-7 although only -88/-77 are listed. Masking only the
  listed codes would leave them in as negative numbers. pynhts masks them too.
* The codebook lists only the codes **observed in each table**, so the same variable can
  declare different codes in the household and trip files. pynhts masks per column from the
  schema of the table the column is read from, and a test proves that the real data contain no
  undeclared missing or skip code.

## Tables and keys

* **Child files carry copies of parent columns** (107 of them: 35 in the person file, 35 in
  the vehicle file, 37 in the trip file). A naive merge creates `_x`/`_y` columns or picks the
  wrong weight. The loader reads copies from the child table and joins only genuinely missing
  columns, with a validated many-to-one join. A test proves that every copy equals its parent.
* **The same name can be a different variable.** In the vehicle file `PERSONID` is the person
  who mainly drives the vehicle, not the person key, and `VEHID` is the vehicle's own key.
  Ownership is therefore decided by name *and* label, and only toward ancestors.
* Vehicles use the **household** weight `WTHHFIN`.

## Weights and variance

* The 2017 weighting report builds 98 jackknife replicates (14 variance strata of 7 units), so
  Var = 6/7 * sum of squared replicate deviations. FHWA's margin of error equals the standard
  error times t(0.975, 98) = 1.984 (checked against the published margins of error).
* `WTTRDFIN` equals 365 x `WTPERFIN`, in the full weights and in every replicate (to 1e-7,
  float32 storage). All trips of one person share one weight, which lets trip estimates run on
  264,234 person-days instead of a 923,572 x 98 matrix.
* Replicates are stored as float32; they are cast to float64 before any squaring.
* Rates *per household* published by FHWA are person-weighted totals divided by
  household-weighted households. They are ratios across two weight systems, which
  `pynhts.stats.ratio_across` supports.

## Variables

* `R_AGE` leaves 496 persons without an age; the report's age bands use the imputed age
  `R_AGE_IMP`.
* The public person file starts at age 5. The report's printed total of persons (321,419
  thousand) exceeds the sum of its own age bands (301,599) by 19,820 thousand; the weights
  reproduce the sum of the bands exactly. The report's own Table A-1 prints the same 321,419 as
  the Census control total ("population in occupied housing units, 2016"), which counts every
  age, so the difference is most likely the population under 5, which the file does not
  contain (its size is plausible, but it was not checked against a Census table).
* 656 trips have `TRPMILES = -9`. They count as trips but add no miles.
* The 2017 survey changed how trip distance is obtained (shortest route between geocoded
  points instead of self-report). The report therefore prints "original" and "adjusted"
  2017 values; pynhts reproduces the **original** ones, which are what the public variable
  `TRPMILES` contains.

## Distances in 2017 version 1.2

* `TRPMILES` is the shortest-path distance; `TRPMILAD` (added in 1.2) is the same distance
  scaled by 1.0735 for private-vehicle work trips and 1.1151 for other private-vehicle trips so
  that 2017 can be compared with earlier surveys. The report's "2017 adj." rows and the adjusted
  VMT/PMT totals of its Table 1d are reproduced from `TRPMILAD` (the adjusted vehicle miles scale
  `VMT_MILE` of driver trips by `TRPMILAD / TRPMILES`).
* 41 walk trips exceed the 2009 maximum walk distance of 46 miles, the longest at 2,648 miles
  (checked in the data); the margins of error of walk mileage are large because of them (2017
  compatibility document).

# NHTS 2022: pitfalls found while importing it

Every item was checked against the files or the official documents and is covered by a test
(`tests/data/test_wave2022.py`, `tests/unit/test_taylor.py`, `tests/unit/test_harmonize.py`).

## Which files and which guide

* The data are served under `/media/2022/` (`/assets/2022/` is not the data). The archive
  `csv.zip` (4.5 MB) holds **five** files, `hhv2pub`, `perv2pub`, `tripv2pub`, `vehv2pub` and
  `ldtv2pub`, and a citation page. The names say "v2": this is release 2.1 (April 2025).
* **The site still links the first-release (V1) User Guide.** Its control totals (trips
  231,715,789,629; drivers 240,744,989; vehicles 230,496,688) belong to the V1 trip and household
  weights. Version 2.0 rebuilt both (trimmed household weights; trip weights with the methods
  adjustment). Against the current files only the V2.x guide matches, e.g. trips
  253,754,536,507. pynhts pins the V2.x documents.
* The long-distance file has one row per person (the most recent trip of 50+ miles), not one
  row per trip; do not count its rows as trips.
* `STRATUMID` is the variance stratum (the V1 guide calls it `HHSTRATUMID_2010`). It is
  copied into the person, trip and vehicle files, equal to the household value in every row.

## Weights and variance

* **No replicate weights.** Standard errors need Taylor-series linearisation (see
  [Methods](methods.md)).
* Weight sets: seven-day (`WTHHFIN`, `WTPERFIN`, `WTTRDFIN`), weekday (`...5D`) and weekend
  (`...2D`). 5,662 households have a weekday weight and 2,231 a weekend weight; none has both.
* **`WTTRDFIN` varies within a person-day** (3,767 of 10,592 person-days with trips) and is
  not 365 times the person weight; in 2017 the trip weight was constant within a person-day.
* Households without any trip on the travel day (1,705 of 7,893) have no trip row. Software that
  takes the trip file alone drops them from the variance (`clusters="observed"`); the design
  keeps them.
* The trip key is `HOUSEID, PERSONID, TRIPID` (2017: `TDTRPNUM`).

## Comparing with 2017

* **Raw codes are not comparable.** `TRPTRANS` 02 is a bicycle in 2017 and a van in 2022, 03
  a car and an SUV, 20 a boat and walking. `WHYTO` has different codes too. Use
  `pynhts.harmonize` (see [Comparing waves](waves.md)).
* **Trip counts are adjusted in 2022 and not in 2017.** The 2022 trip weights include a factor
  for the move to web-only reporting without a travel log (the 2017 data showed 10-12 % more
  trips with a log). Trip rates between 2017 and 2022 are therefore not like for like.
* The 2022 population excludes group quarters (about 2.5 % fewer people); 2017 did not.
* 2022 has no state, CBSA or vehicle model (`HHSTATE`, `HH_CBSA`, `MODEL`) and no `HHRESP`,
  and the add-on households of the state studies are not in the file.
* **The guide and the codebook disagree on two purpose codes.** The User Guide's Table 12 prints
  18 = religious and 19 = rest or relaxation; the codebook says 18 = rest or relaxation and
  19 = religious, and ORNL's own summary purpose agrees with the codebook (code 19 trips are
  in `WHYTRP1S` 20, code 18 trips in 50). pynhts follows the codebook.
* The guide groups recreational vehicles under "Other Vehicle"; ORNL's `TRIPMODE` counts them as
  private-vehicle trips.
* Table 11 of the V2.x guide prints vehicle trips and VMT whose weighted totals this library
  does not reproduce while the case counts do (see [Validation](validation.md)).

## Missing values

* `TRPMILES` is -9 on 14 trips and `VMT_MILE` -9 on 3 driver trips; they count as trips but
  add no miles. The guide's "cases" for person miles of travel is the unweighted sum of
  `TRPMILES` (434,079), not a count.
* `R_SEX` has -7/-8/-9 codes; they are masked (`missing="nan"`) like all coded missing values.
