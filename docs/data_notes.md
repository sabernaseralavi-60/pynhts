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
  reproduce the sum of the bands exactly. The cause is not established.
* 656 trips have `TRPMILES = -9`. They count as trips but add no miles.
* The 2017 survey changed how trip distance is obtained (shortest route between geocoded
  points instead of self-report). The report therefore prints "original" and "adjusted"
  2017 values; pynhts reproduces the **original** ones, which are what the public variable
  `TRPMILES` contains.
