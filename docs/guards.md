# Defaults and guards: what pynhts does so that a result is not silently wrong

Found by an adversarial review of 0.4.0 and fixed in 0.5.0. Every guard has a test on the real files
of all four waves (`tests/data/test_four_wave_guards.py`).

| Trap | Without the guard | Guard |
|---|---|---|
| The skip code -1 is not a quantity | the mean of `VMT_MILE` (2009) is 5.36 instead of 9.72 and total VMT is 7 % low | `skip="auto"` (default): -1 becomes NA in numeric columns, stays a code in coded columns; `skip="keep"` restores the raw value |
| Other negative non-answer codes (-3 no contact, -4 and -5 did not work) in 2001 and 2009 | mean commute time (2009) 23.34 instead of 24.21 minutes | every labelled negative code is a missing code of its own kind |
| Top-coded values (age 88 or 92, vehicle age 35 or 40, vehicle year) | means biased; the 2009 vehicle-age code means "25 or older", the others "33 or older" | `pynhts.core.flags`, `describe()`, and a `PynhtsWarning` when an estimator is asked about the column |
| 2001 columns that exist only for the national sample (`BESTMILE`, fuel economy, travel-period counts, the whole long-distance file) | annual VMT from `BESTMILE` 12.9 % low with the full-sample weight | `PynhtsWarning`; the national household weights are not offered |
| Raw codes pooled across waves | `TRPTRANS` "01" is 44 % of 2009 trips (car) and 10.5 % of 2017 trips (walk) | `compare_waves` flags `codes_changed` and `codes_permuted` (`URBAN`, `R_RELAT`); `harmonize.apply` raises when the frame came from another wave |
| Trip totals read as daily | 1,385 "trips per person" | the result's `unit` says "annual"; see [Methods](methods.md) |
| Tours in a wave other than 2017 | no home-based-work tour at all (the work codes differ) | `data.tours()` raises unless a `TourConfig` is passed |
| A ratio across two different replicate systems (2001 long-distance with household or person) | a variance with no meaning | `ratio_across` raises |
| A false methods sentence in a table footnote | "delete-a-group jackknife, 98 replicates" under a 2022 table | `tables.note` reads the design of the wave the result came from |

What the guards do not do: they do not mask a value you may legitimately want (`skip="keep"`,
`missing="keep"`), they do not pool weights across waves, and they do not decide for you whether a
harmonized category is close enough: `harmonize.category_report` says which categories are
`exact` and which are `approximate`.
