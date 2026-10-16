# Methods

## Estimators

`data.survey(table, columns)` returns a `Survey`: the rows of a table bound to the 98 replicate
weights of the unit that carries the weight.

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

## Variance

For an estimate `theta` with replicate estimates `theta_1 ... theta_98`:

    Var(theta) = (6/7) * sum_r (theta_r - theta)^2          (stratified jackknife, JKn)
    MOE        = t(0.975, 98) * sqrt(Var)                   (95 %)

The factor 6/7 = (n_h - 1)/n_h comes from the 14 variance strata of 7 variance units described
in the 2017 NHTS weighting report. For ratios, the ratio is recomputed under every replicate
weight, so the variance reflects the variability of numerator and denominator jointly.
`level=` changes the confidence level; the degrees of freedom default to 98 as in FHWA's
tables.

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
the replicate weights are available (`data.replicate_weights`) for users who refit a model once
per replicate. Only the 2017 wave is supported.
