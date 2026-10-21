# Methods

## What a total counts (units)

Every result frame carries `result.attrs["pynhts"]` with the wave, table, weight, variance design
and **unit** of a total. Totals from travel-day weights are **annual**: `WTTRDFIN` is 365 x the
person weight in 2001, 2009 and 2017, so `survey("trip").total()` is annual person trips and must
be divided by 365 for a daily figure (and by persons for a rate: 2009 gives 3.79 trips per person per
day). In 2022 `WTTRDFIN` also contains the methods adjustment (about +10 %): daily trips per person
are 2.275 from the trip weights (the official route) and 2.078 from `CNTTDTR` x the person weight.
A 2001 long-distance total is annual long-distance trips of the national sample; a 2022
long-distance total counts persons.

## Estimators

`data.survey(table, columns)` returns the rows of a table bound to the weights and to the wave's
variance design:

* **2001, 2009, 2017** (`Survey`): the replicate weights of the unit that carries the weight,
  with the jackknife variance `factor x sum of squared deviations`: 98 replicates and the
  stratified-jackknife (JKn) factor 6/7 in 2017 (14 strata of 7 units), 100 replicates and 99/100
  in 2009 (jackknife-2, User's Guide chapter 7), 99 replicates and 98/99 in 2001 (delete-one
  jackknife, User's Guide 7-E.1). The margin of error is `t(0.975, df) x SE` with df equal to the
  number of replicates; the registry of each wave stores the three numbers;
* **2022** (`TaylorSurvey`): the public files carry **no replicate weights**, so errors use
  Taylor-series linearisation with the stratum (`STRATUMID`) and the household (`HOUSEID`) as
  primary sampling unit, as the 2022 User Guide prescribes (see below).

Both classes offer the same `total`, `mean`, `proportion` and `ratio` methods.

| Table | Weight | Replicate unit |
|---|---|---|
| household, vehicle | `WTHHFIN` | household |
| person | `WTPERFIN` | person |
| trip | `WTTRDFIN` | person-day |

Supported estimators, each with optional `domain=` (subpopulation) and `by=` (groups):

* `total(y)`: weighted total (`y=None` counts rows),
* `mean(y)`: ratio of the weighted total of `y` to the weighted count of rows with a value,
* `proportion(condition)`: mean of a boolean,
* `ratio(numerator, denominator)`: ratio of two weighted totals,
* `ratio_across(survey_a, y_a, survey_b, y_b)`: ratio between two surveys that share the
  replicate index (person-weighted trips per household-weighted household).

Every result row has `estimate`, `se`, `moe`, `ci_low`, `ci_high`, `cv` and `n` (rows
contributing).

## Variance, 2017 (jackknife)

For an estimate `theta` with replicate estimates `theta_1 ... theta_98`:

    Var(theta) = (6/7) * sum_r (theta_r - theta)^2          (stratified jackknife, JKn)
    MOE        = t(0.975, 98) * sqrt(Var)                   (95 %)

The factor 6/7 = (n_h - 1)/n_h comes from the 14 variance strata of 7 variance units described
in the 2017 NHTS weighting report. For ratios, the ratio is recomputed under every replicate
weight, so the variance reflects the variability of numerator and denominator jointly.
`level=` changes the confidence level; the degrees of freedom default to 98 as in FHWA's
tables.

## Variance, 2022 (Taylor series)

The 2022 User Guide (Appendix 1) and the Weighting Memo say to use Taylor-series
linearisation with the analysis weight, the stratum and the household as cluster. This is the
"ultimate cluster" estimator (clusters sampled with replacement within strata, no finite
population correction), the one SAS `PROC SURVEYMEANS ... STRATA ... CLUSTER` and R's
`survey::svydesign(ids=~HOUSEID, strata=~STRATUMID, weights=..., nest=TRUE)` compute:

    Var(theta) = sum_h  n_h/(n_h - 1)  *  sum_{c in h} (Z_c - mean_h Z)^2

where `Z_c` is the household total of the estimator's linearised values (for a ratio
`R = Y/X`: `w (y - R x) / X`). The 7,893 households fall in 20 strata (18 strata plus the
Alaska/Hawaii substrata of the Pacific division). The degrees of freedom are, as in `survey::degf`,
the number of weighted clusters minus their strata, computed per domain, so a domain estimate
has fewer degrees of freedom than the whole sample (`df` column of every result).

Choices that matter:

* **Households with no row stay in the design.** A household with no trip on the travel day
  contributes zero to a trip total but is still a sampled cluster. `data.survey("trip", ...)`
  keeps all 7,893 households (`clusters="all"`, the design-correct default). Software fed the
  trip file alone sees only households with trips; `clusters="observed"` reproduces that, with
  smaller standard errors (3.5 % smaller for the trip total here).
* **Weights.** Seven-day weights by default; `weights="weekday"` (`...5D`) and `"weekend"`
  (`...2D`) select the day-type sets. Households outside the day type have weight 0: they stay in
  the variance but not in the degrees of freedom.
* **Trips carry their own weight in 2022** (`WTTRDFIN` varies within a person-day, unlike 2017),
  so every table row is its own weight unit.
* **Validation.** Estimates, standard errors and degrees of freedom equal R's `survey` package
  to 1e-9 for 24 estimands (`tools/validate_taylor_r.R`, `tests/golden/taylor_2022_r.csv`).

## Rows and units

All rows of one unit share one weight, so `sum_rows w_row * y_row = sum_units W_u * (sum of y
in unit u)`. The engine aggregates row values to the unit once (`numpy.bincount`) and works
on a matrix of at most 264,234 x 98 doubles, even for 923,572 trips.

## Missing values

A row whose analysis variable is NA is dropped from numerator and denominator (complete cases
inside the domain), like `na.rm = TRUE` in R's `survey` package. Load tables with
`missing="nan"` (default) so that survey codes become NA. This is a statement about the
estimator, not about nonresponse bias: item nonresponse can bias an estimate and pynhts does not
adjust for it.

## What is not provided

Variance for regression coefficients and other model-based estimates is not implemented yet;
the 2017 replicate weights are available (`data.replicate_weights`) for users who refit a model
once per replicate. For 2022 use a survey-regression package with the same design
(`STRATUMID`, `HOUSEID`, weight). Waves before 2001 are not supported.
