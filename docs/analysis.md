# Analysis toolkit (0.7.0)

From survey files to research-ready tables without silent errors. Each module states what it does with missing values, weights and
units; the page [Feature registry](data/FEATURES.md) lists every derived variable with its formula.

## 1. Collapse trips to persons or households, with diagnostics

```python
import pynhts
from pynhts import aggregate as A

d = pynhts.load(2001)
p = A.aggregate(d, "trip", "person", {
    "n_trips":  A.Agg.n(),                                          # persons without trips get 0
    "n_active": A.Agg.n(A.Where("TRPTRANS", "in", ("25", "26"))),    # walk or bicycle (2001 codes)
    "miles":    A.Agg.sum("TRPMILES"),                              # NaN if any distance is missing
}, base_columns=["R_AGE"])
print(p.attrs["pynhts_aggregate"])   # rows, orphans, missing inputs per output, policies, weight
```

* one result row per target row (no row multiplication), unique target key, orphan child rows raise;
* `missing="propagate"` (default) makes a sum or mean NaN when a contributing value is missing; `"skip"` ignores them (FHWA's convention for miles);
* a target without child rows is a true zero for counts, sums and indicators (`empty="auto"`); `empty="nan"` refuses the inference;
* the result carries the target table's weight (person, household or trip) and `attrs["pynhts"]`; never another table's weight.

Functions: `n count sum mean median min max std quantile nunique any share first last`; conditions `Where(col, op, value)` combined with `& | ~`
or `Custom`. `source` may also be your own frame (for example trips with derived columns).

## 2. Documented features

```python
from pynhts import features
hh = features.create_household_features(d, groups=["composition", "resources", "travel", "modes"])
features.registry(level="household")        # meaning, sources, formula, eligibility, missing rule, denominator, weight, waves
```

Zero is not missing; eligibility is explicit (`hh_share_univ` divides by members who *answered* the education question); counts built from the
person file are lower bounds when `hh_n_unlisted > 0` (the person file is not always a complete roster); `strict=True` turns counts with unknown
members into NaN. Validation: in complete-roster households the worker and driver counts equal the survey's own `WRKCOUNT` and `DRVRCNT` in all four waves.

## 3. Explore, with the reasons for missing values

```python
from pynhts import eda, valid
p = d.persons(["EDUC", "WORKER"], missing="keep", skip="keep")
eda.missing_report(p)                                 # answered / skip / non-answer / blank
valid(p["EDUC"])                                      # real answers only (notna() is NOT validity for coded columns)
eda.describe(hh, ["hh_n_trips"], weight="WTHHFIN")    # weighted summaries with unweighted n
eda.correlation_matrix(hh, ["hh_n_trips", "hh_miles"], method="spearman", weight="WTHHFIN")
```

Correlation refuses nominal columns (use `eda.association_matrix`, Cramér's V), gives pairwise n, never returns an interval for weighted data
(use `pynhts.stats` for design-based inference), and says that association is not causation. `pynhts.quality.report(data)` checks keys, orphans,
weights and top-coded values.

## 4. Transform only when you decide to, without leakage

```python
from pynhts import transform
train, test = transform.split_by_household(hh, test_size=0.2, seed=1)   # no household in both sets
tr = transform.Transformer({"hh_miles": "log1p", "HHSIZE": "standardize"}).fit(train, weight="WTHHFIN")
test_t = tr.transform(test); print(tr.to_json())                       # parameters for reproducibility
transform.diagnostics(hh["hh_miles"], test_t["hh_miles__log1p"])        # before / after
```

Methods: log, log1p, sqrt, Box-Cox, Yeo-Johnson, standardize, robust, winsorize, bins. Originals are never overwritten; skewness alone is not a reason
(`transform.recommend` lists considerations).

## 5. Compare waves without pooling by accident

```python
from pynhts import trends
trends.trip_shares("mode", waves=(2001, 2009, 2017, 2022))     # each wave with its own weights and variance design
trends.wave_means("trip", "TRPMILES")                          # warns: distance is not comparable across waves
trends.pool((2009, 2017), "person", ["R_AGE"], harmonize_concepts={})   # guarded pooled workflow (always warns)
```

## 6. Tables and figures

```python
from pynhts import tables
t1 = tables.sample_characteristics(hh, ["hh_n_workers", "hh_share_univ"], weight="WTHHFIN")
tables.to_html(t1); tables.to_csv(t1, "table1.csv"); tables.to_excel(t1, "table1.xlsx")
from pynhts.viz import plots          # needs matplotlib
plots.save(plots.histogram(hh["hh_miles"], weight=hh["WTHHFIN"]), "fig1.svg")
```

Every figure states "weighted" or "unweighted sample" and the sample size; there is no way to get a weighted-looking chart from unweighted data.
For tables with margins of error, estimate with `pynhts.stats` and format with `tables.build`.

## What is deliberately not here

No automatic annualisation, no automatic transformation, no regression-coefficient variance (refit per replicate), no maps (the public file has no
geography below state and categorical density), no block-group or ACS joins (need the restricted block-group ID). See the
[repository audit](development/REPOSITORY_AUDIT.md) and the [research landscape](research/NHTS_RESEARCH_LANDSCAPE.md).
