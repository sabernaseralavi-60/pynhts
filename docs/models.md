# Design-aware models and leakage-safe validation: `pynhts.models`, `pynhts.validate`

Most published NHTS regressions are fitted **unweighted with model-based standard errors**, and most published
classifiers are scored with a **random split of rows, after oversampling**. Both choices change conclusions. The paper
`papers/02-nhts-ladder` re-estimated 13 published studies to measure by how much; these two modules are what that work
needed, turned into reusable code.

## `pynhts.models`: one call, four regimes

```python
import pandas as pd, pynhts
from pynhts import models

d = pynhts.load(2017, replicates=True)
p = d.persons(["R_AGE", "R_SEX", "WORKER", "DRIVER", "CNTTDTR"], missing="keep", skip="keep", weight=False)
p = p[(pd.to_numeric(p["R_AGE"]) >= 18) & pd.to_numeric(p["CNTTDTR"]).ge(0)].reset_index(drop=True)
X = pd.DataFrame({"age": pd.to_numeric(p["R_AGE"]), "female": (p["R_SEX"] == "02").astype(float),
                  "worker": (p["WORKER"] == "01").astype(float), "driver": (p["DRIVER"] == "01").astype(float)})
y = pd.to_numeric(p["CNTTDTR"])

res = models.fit(d, p, y, X, family="poisson", level="person", regime="design")
res.table()                                   # estimate, se, z, p, 95 % interval; attrs["pynhts"] names the design
models.compare_regimes(d, p, y, X, family="poisson", level="person")   # naive / clustered / weighted / design side by side
```

| regime | point estimate | standard error |
|---|---|---|
| `naive` | unweighted | model-based (iid): what most papers report |
| `clustered` | unweighted | sandwich with households as clusters |
| `weighted` | survey-weighted | sandwich with households as clusters (`cluster="none"`: every observation its own cluster, the cost of unequal weights alone) |
| `design` | survey-weighted | the wave's variance design: replicate-weight jackknife (2001, 2009, 2017) or Taylor linearisation over strata and households (2022) |

The regimes answer different questions: unweighted fits describe the association among respondents, weighted fits the association in the population. In the 310 coefficients of paper 02 the design-aware standard error was a median 2.19 times the unweighted one, almost entirely because of the unequal weights; household clustering and the replicate formula added little on average, but the replicate formula changed some verdicts, so use `design` where replicate weights exist.

* Families: `gaussian` (OLS), `binomial` (logit), `poisson` need only NumPy; `nb` (negative binomial NB2) needs SciPy. The
  jackknife of the negative binomial uses Newton/chord steps from the full-sample optimum (checked against exact refits).
* `compare_regimes` returns the four fits with `se_ratio` (design over naive), `se_ratio_weights`, `se_ratio_clustering`, `sign_flip` and
  `sig_change`, and raises a `PynhtsWarning` when the unweighted and the design-aware fit disagree in sign or in significance (report the design-aware one for population claims).
* The function never drops rows silently: missing values in `y` or `X` raise an error.
* **Validation.** `tests/data/test_models_real.py` compares coefficients and standard errors of the logit, Poisson and OLS fits on
  230,458 adults of NHTS 2017 with R's `survey::svyglm` on a `svrepdesign` (JKn, `tools/validate_models_r.R`,
  `tests/golden/models_2017_r.csv`): coefficients agree to 1e-5 relative, standard errors to 0.2 %; the 2022 Taylor design is checked the same way
  (`tools/validate_models_taylor_r.R`, `tests/golden/models_2022_r.csv`, standard errors to 0.5 %). p-values use Student t on the design degrees of freedom.

## `pynhts.validate`: how much of a score is the pipeline?

```python
from pynhts import validate
rep = validate.audit_classifier(lambda: RandomForestClassifier(200), X, y, groups=household_id, weights=wt)
print(rep)      # AUC under resample-then-split, split-then-resample, grouped, grouped + weighted; the inflation
```

`audit_classifier` scores one model under four pipelines that differ only in where the oversampling (SMOTE) happens and in what is
split (rows or households), and warns when the leaky pipeline inflates the AUC by more than 0.05. `group_split`, `smote` and
`weighted_auc` are available separately. Only NumPy is required; the estimator is any object with scikit-learn's interface.

## What it is for

The rules in `AGENTS.md` (number 11 and 12) tell a human or an agent when to use them: a regression on NHTS rows should be reported
with `regime="design"`; an ML score on NHTS rows should be accompanied by a grouped, train-only-resampled score.
