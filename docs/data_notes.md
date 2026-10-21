# NHTS 2017: pitfalls found while building pynhts

*This page covers 2017, then 2022, 2009 and 2001, in that order.*

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

# NHTS 2009: pitfalls found while importing it

Release 2.1 (October 2011). Every item was checked against the files or the official documents;
the tests are in `tests/data/test_old_waves_real.py` and `tests/unit/test_old_waves.py`.

## Files and codebook

* The archive `Ascii.zip` (95 MB) is called ASCII but holds **four comma-separated CSV files** in
  its folder `Ascii/`: `HHV2PUB.CSV`, `PERV2PUB.CSV`, `DAYV2PUB.CSV` (the trip table: "day trip
  file") and `VEHV2PUB.CSV`, with 150,147 households, 308,901 persons, 1,167,321 trips and 309,163
  vehicles. There is no long-distance file. The hashes are pinned in the registry.
* **The codebook exists only as a PDF** (the data dictionary `.xls` lists names, types and labels
  but no codes). `tools/build_schema_pdf.py` reads the PDF layout page by page; no code or type is
  guessed. All 3,435 compared code lines (unweighted and weighted frequency) reproduce on the data,
  except for three documented cases:
  * the PDF prints control character 0x16 for the 3 of `MAKECODE` 35 (Nissan/Datsun); repaired
    by the data (35 occurs in exactly the printed 12,345 rows);
  * `PTUSED` (public transit uses): the codebook counts 99,106 rows as -9; the file has 98,498
    rows of -9 and 608 rows of 99. 98,498 + 608 = 99,106, so the value **99 is a hidden missing
    code**; pynhts masks it;
  * `VEHTYPE`: the printed frequencies of the four main classes differ from the file (cars
    154,593 printed, 151,238 in the file; SUVs 54,760 against 58,718) while they add up to the
    same 294,409 vehicles. 3,355 vehicles sit in another class than the codebook says; the data are
    used as they are and the test lists the four classes as a known gap.
* Coded columns keep leading zeros (`"01"`). Yes/no and sex are `"01"`/`"02"`; in 2001 they are
  `"1"`/`"2"`.

## Weights and variance

* **Replicate weights are a separate 399 MB archive** (`ReplicatesASCII.zip`): 100 replicates
  made with the jackknife-2 method. The User's Guide gives Var = 99/100 x sum of the 100 squared
  deviations. The 95 % margin of error is `t(0.975, 100) = 1.984` times the standard error (not
  1.96): all 27 printed margins of error of the report's Table 1 match that to rounding.
* The replicate file's travel-day weight `DAYWGT` is **missing for 45,967 persons: exactly the
  persons without any trip on the travel day** (`CNTTDTR` = 0; 13.15 % of the weighted persons;
  in 2001 and 2017 the zero-trip persons do have a weight). Because `WTTRDFIN` is 365 x `WTPERFIN`
  everywhere else, pynhts fills the missing day weights and replicates with 365 x the person
  weights (registry entry `fill_from`), so person-day analyses at `level="trip"` can include the
  persons who did not travel. A trip row that belongs to a unit without any weight raises an error.
* `WTTRDFIN` is 365 x `WTPERFIN`, as in 2017. Vehicles use the household weight.
* The four per-person, per-driver and per-household PMT/VMT rows of the report's Table 3 print a
  margin of error that equals 1.96 x the standard error at the printed precision, not 1.984 x; the
  totals of Table 1 use 1.984. The library always uses t and reports those rows (and the margin of
  the daily trips per person) as "estimate reproduced, margin of error differs" (see
  [Validation](validation.md)).

## Variables

* The public person file starts at age 5. **Age and vehicle age are top-coded in every wave**
  (`pynhts.core.flags.topcoded_columns(wave)`, verified on the data): `R_AGE` 92 means "89 or
  older" in 2009, 2017 and 2022 and 88 means "85 or older" in 2001; `VEHAGE` 40 means "33 or
  older" in 2001, 2017 and 2022 (the values 33-39 never occur) and 35 means "25 or older" in 2009;
  `VEHYEAR` has a bottom code (2009: 1974 = 1984 or earlier). Means of these columns are biased
  upward by up to 0.4 years for vehicle age; use bands. The estimators warn.
* `TRPMILES` is -1 (appropriate skip) on 181 trips and -9/-8/-7 on 18,484 more. Summing the
  column with only the -9/-8/-7 codes masked subtracts the 181 skip rows: the report's person
  miles (3,732,791 million) need `skip="nan"`.
* "Household vehicles" in the report are vehicles of types 01-07 (210,778 thousand); the vehicle
  file also holds golf carts, "other" and unknown types (211,501 thousand). The same holds for
  vehicle trips: 63.2 million driver trips are in a golf cart (mode 08), which the report leaves
  out of the 233,849 million vehicle trips.
* `TRPTRANS` codes differ from every other wave: 08 is a golf cart (a commercial airplane in
  2001), 22 a bicycle (a taxi in 2001), 23 walking (a limousine in 2001).

# NHTS 2001: pitfalls found while importing it

The User's Guide is version 3 (January 2004); the codebook has a "Changed in V4?" column and the
site carries release notes for version 4 (`v4ReleaseNotes.html`), whose changes the data contain.
The tests are the same files as for 2009.

## Files and codebook

* `Ascii.zip` (64 MB) holds **five comma-separated CSV files** (lower-case `.csv`): `HHPUB` (69,817
  households), `PERPUB` (160,758 persons), `DAYPUB` (642,292 trips), `VEHPUB` (139,382 vehicles)
  and `LDTPUB` (45,165 long-distance trips).
* **The long-distance file has one row per long trip** (key `HOUSEID, PERSONID, TPTRPNUM`), with
  the travel-period weight `WTPTPFIN`, which is the *national-sample* person weight times 365/28
  (`WTPRNTL` x 13.0357 in all 45,165 rows; User's Guide Table 7-3), so `survey("longdist").total()`
  is annual long-distance person trips of the national sample (2.617 billion); 2022 has one row
  per person, and its total counts persons. Replicates exist for the 60,282 persons of the national
  travel-period sample.
* The codebook is Appendix B of the User's Guide (PDF); the schema is read from it with the same
  tool as 2009. All 6,327 compared code lines reproduce. The codebook labels a blank cell as
  `[missing]` (undefined weights): it is kept as a code and matches the empty cells.
* A few numeric codes are printed with more digits than the file stores (`BTUCOST` 325.577914285714
  against 325.57791429); the test compares floats to 1e-9.
* Codes are padded for most variables (`"01"`) but **yes/no and sex are `"1"`/`"2"`**, and the
  summary trip purpose `WHYTRP1S` numbers its 13 categories 01-13 (`"01"` = to work), whereas 2009
  and later use 01 = home, 10 = work, 20 = school. The raw column cannot be pooled
  (`pynhts.harmonize.crosswalk("purpose_summary")`).

## Children under 5

* The file contains children 0-4: for the first time all household members were eligible for a
  person interview (User's Guide 2-D.2), so their travel was collected. The report's
  "2001" column leaves them out of the trips and the persons aged 5 and older (257,576 thousand),
  and its "includes 0-4" column adds them (277,203 thousand persons, 407,262 million trips).
* **Table 3 of the report mixes the two**: its "2001" per-person rates (3.74 trips, 36.89
  miles) divide the trips and miles of persons of known age 5 and older by *all* persons, children
  0-4 and unknown ages included. Counting the same trips over persons aged 5+ gives 4.09 trips.
  The per-household rates (9.66, 95.24) and the average trip length (10.04) use the same trips.
  The recipe `stt2001` reproduces the printed values with that definition and says so.
* 2,399 persons have no age (`R_AGE` -7/-8/-9); the report counts them in "All 5+" but not in
  the trips of Table 3.

## Weights and variance

* **99 replicate weights**, delete-one jackknife: Var = 98/99 x sum of the squared deviations.
  The guide's worked example (202,586,200 household vehicles, SE 672,072, interval = estimate
  +/- 2 SE) is reproduced to the unit by the estimate and the standard error (672,071.9, also from R's
  `survey` package).
* Replicates live in `replicates_ascii.zip` (439 MB): `hh50wt.csv`, `pr50wt.csv` (person and
  travel-day weights) and `ldt50wt.csv`. The household key is called `ID9` there; undefined weights
  are the quoted string `"."`; the long-distance file names its replicates `FPTPWT01` ... `FPTPWT99`
  (zero-padded), the others `WTHFIN1`, `WTPFIN1`, `WTTDFN1`. The weight sets of the "100 percent
  reported households" (`EXPFLLHH`, ...) are in the same files and are not used by default.
* The main long-distance file prints `WTPTPFIN` with 4 decimals, its replicate file with 6, so
  the two agree only to 7.6e-11 relative; the registry sets the tolerance for this wave.
* The 2004 report's totals differ in the sixth digit from the same quantities in the 2009
  report (vehicle trips 233,040 against 233,030 million; VMT 2,274,797 against 2,274,769). The
  current file gives the later values, so the 2004 report was computed from an earlier version.
