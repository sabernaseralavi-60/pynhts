# From a research statement to data, tables and figures: `pynhts.study`

A research project states its aim and a few exact assumptions: the wave and the unit of analysis, who is in the sample and in
which order people are removed, how each variable is built, whether the numbers are weighted. `pynhts.study` takes those
statements (as Python objects, a dictionary or a YAML file) and returns

* the analysis **data** (one row per unit, only the variables you defined, plus the weight),
* the **sample-flow table** (how many records each rule removed: the table every paper needs and few print correctly),
* a **descriptive table** (mean, sd, min, max, share; per group with the difference),
* the **assumptions** you stated and a **methods paragraph**,
* **figures** (the flow, the distribution of the outcome with its share of zeros, shares by group),
* a **comparison with published numbers** (EXACT, CLOSE, ACCEPTABLE, GAP), with nothing tuned to match.

It exists because 21 published US NHTS papers were rebuilt with pynhts (`docs/paper_data_audit/`) and the same work was done by
hand each time. What took the time was never the computation; it was recovering the unwritten rules of each paper: which records
were dropped, whether a skip counts as an answer, whether the mean is over everybody or over the people who travelled.

```python
import pynhts
from pynhts import study as S
from pynhts.aggregate import Where

spec = S.Study(
    title="Ridesharing in 35 states", aim="Is vehicle ownership related to ridesharing?", wave=2017, unit="person",
    weight=None,                                    # explicit: unweighted, as the paper did ("auto" = the person weight)
    steps=[S.Drop("low-use states excluded", Where("HHSTATE", "in", ["WV", "MS", "WY"])),
           S.Keep("answered the ridesharing question", Where("RIDESHARE", ">=", 0)),
           S.Complete("complete key variables", ["veh", "age"])],
    variables=[S.Var("ride", "RIDESHARE", "count", label="Rideshare uses in 30 days", role="outcome"),
               S.Var("veh", "HHVEHCNT", "number", label="Household vehicles"),
               S.Var("female", Where("R_SEX", "==", "02"), "binary", label="Female"),
               S.Var("age", "R_AGE", "number")])
res = spec.run(pynhts.load(2017))

res.flow                      # records before, removed and after for every rule
res.table()                   # mean / sd / min / max / share per variable; res.table(by="female") per group
res.count_distribution("ride")   # zeros, users, and users by band (1, 2, 3-5, 6-10 ...)
print(res.report(by="female"))   # Markdown: aim, data, flow, table, difference, assumptions
res.save("out/ridesharing", by="female")   # report.md, table1.csv, flow.csv and the PNG figures
S.compare(res, [{"variable": "ride", "stat": "mean", "value": 0.309}])   # EXACT / CLOSE / ACCEPTABLE / GAP
```

The same study as data: `Study.from_yaml("docs/examples/ridesharing_35_states.yaml")` is the sample and Table 1 of Zhang & Zhang
(2018) and reproduces its sample to 0.09 % and its Table 1 means as EXACT or CLOSE (`tests/data/test_study_real.py`).

## The rules it enforces

* **Skip is not a non-answer.** `Complete(..., skip="invalid")` removes a skip (`-1`, "does not apply") and a non-answer
  (`-7 -8 -9`); `skip="ok"` keeps the skip, which is right for "time to work" of a non-worker. In the audit of Jiao et al. (2020) the skip
  of the work questions is 76,476 of the 191,150 adults who travelled: treating it as missing would drop 40 % of the sample.
* **A variable is never a raw column.** A variable name may not equal an NHTS column name, so a derived `age` cannot be confused
  with `R_AGE`. Numbers are read as numbers with negatives as missing; a dummy built from a condition is missing when a column it
  reads is a skip or non-answer (`na="false"` evaluates the condition as it is). A `kind="binary"` variable from a raw column must hold only 0 and 1
  (otherwise it raises; build the dummy with `Where`).
* **Rules never see a non-answer as a number.** `Keep` and `Drop` read the columns with the skip (`-1`), the non-answers (`-7 -8 -9`) and the codebook's
  hidden missing codes (99 of the 2009 `PTUSED`, "XX" of the 2001 `HHSTATE`) set to missing, so `Drop(Where("R_AGE", "<", 18))` does not remove a
  refused age and `Keep(Where("TIMETOWK", "<=", 60))` does not admit a skip; a row with a missing value does not satisfy the rule (add a `Complete`
  step to remove it). `raw=True` evaluates a rule on the codes as they are in the file (to select the skip itself: `Where("TIMETOWK", "==", -1)`). Variables are
  read the same way, so a mean agrees with the one from `data.persons(...)`.
* **Cautions are not lost.** A top-coded or capped column (age 92 = 89+, `PTUSED` 30, `NWALKTRP` 99) raises the usual `PynhtsWarning` when the study runs and
  the text is added to the assumption register.
* **Weighted or not is stated, never implied.** `weight=None` is explicit; many papers print unweighted Stata tables, and a
  weighted table describes the population, not the sample.
* **The base of a mean is a rule.** "Mean over persons with at least one auto trip" and "mean over persons with any trip" differ by
  5 % for drivers and 45 % for non-drivers (audit P22). Write it as a `Keep` step and it appears in the flow table and in the methods text.
* **The wave must match.** A study for 2017 run on 2009 data raises an error.

## What it does not do

It does not choose the model, tune a rule to reach a number, or impute. Statistics are descriptive (no standard errors); for
survey-design margins of error use `pynhts.stats` and `pynhts.tables`. Variables from other sources (ACS block-group data, transit
stops) and the restricted census-tract identifier are not in the public file; the audit lists which papers need them.
