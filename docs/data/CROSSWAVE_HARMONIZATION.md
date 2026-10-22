# Cross-wave harmonization

Generated from `pynhts.harmonize` and `pynhts.concepts`. See also `docs/waves.md` for the narrative and pitfalls.

## Available crosswalks

| concept | waves | rows | status counts |
| --- | --- | --- | --- |
| density | 2001, 2009, 2017, 2022 | 20 | {'exact': 18, 'approximate': 1, 'only_here': 1} |
| education | 2001, 2009, 2017, 2022 | 26 | {'exact': 16, 'nested': 9, 'approximate': 1} |
| fuel | 2001, 2009, 2017 | 12 | {'approximate': 8, 'exact': 3, 'only_here': 1} |
| income | 2001, 2009, 2017, 2022 | 58 | {'nested': 40, 'exact': 18} |
| mode | 2001, 2009, 2017, 2022 | 94 | {'exact': 54, 'merge': 24, 'approximate': 12, 'only_here': 4} |
| purpose | 2017, 2022 | 40 | {'exact': 29, 'approximate': 6, 'merge': 5} |
| purpose_1990 | 2001, 2009, 2017, 2022 | 38 | {'exact': 24, 'approximate': 12, 'only_here': 2} |
| purpose_summary | 2001, 2009, 2017, 2022 | 41 | {'exact': 29, 'approximate': 8, 'merge': 4} |
| trip_class | 2001, 2009, 2017, 2022 | 20 | {'exact': 12, 'approximate': 8} |
| urban_area | 2001, 2009, 2017, 2022 | 16 | {'exact': 16} |
| urban_rural | 2001, 2009, 2017, 2022 | 8 | {'exact': 8} |
| vehicle_type | 2001, 2009, 2017, 2022 | 33 | {'exact': 32, 'only_here': 1} |

Status values: `exact` same meaning; `nested` finer categories collapse into the shared one; `merge` several codes map to one; `approximate` the groups differ in a documented way; `only_here` no counterpart in the other wave (the category is kept, flagged).

## Two workflows, deliberately separate (`pynhts.trends`)

1. **Harmonized descriptive trends**: `trends.trip_shares(...)` and `trends.wave_means(...)` estimate each wave with its own weights and variance design (jackknife replicates 2001-2017, Taylor series 2022) and put the estimates side by side. Nothing is pooled. A variable whose concept is `N` (trip distance, trip counts, trip weights) raises a `PynhtsWarning`.
2. **Pooled modelling**: `trends.pool(...)` stacks waves with a `wave` column, refuses `N` concepts unless told otherwise, requires an explicit crosswalk for coded columns (raw codes are never stacked silently) and rescales weights within wave (`w_norm`). It always warns: the waves are independent cross-sections, not a panel; the sampling frame (random-digit dialling until 2009, address-based since 2017), collection mode, trip definition and distance measurement changed; model the wave effect.

## Documented breaks that matter before comparing

* **Trip distance** (`N`): 2001 and 2009 self-reported; 2017 routed shortest path; 2022 route computed for the trip date. The compatibility document says routed 2017 distances are about 10 % shorter than self-reports would be, yet the weighted mean distance of a trip of persons aged 5+ is higher in 2017 (9.75 miles in 2009, 10.71 in 2017; `trends.wave_means`): a change in measurement and a real change cannot be separated. `TRPMILAD` (2017) scales the distance up for comparison with 2001/2009.
* **Trip counting** (`N`): telephone interview with prompts (2001, 2009), web diary (2017: about 66 % web; 2022: about 99 % web); 2022 trip weights contain a methods adjustment (+9.5 % overall).
* **Universe**: 2001 includes children aged 0-4; the other waves start at 5 (`min_age=5`).
* **Weights**: the trip weight is annual (365 x the person weight) in 2001-2017; wave weights have different population bases and must not be pooled as they are.
* **Codes**: the same code means different things in different waves (`TRPTRANS` 08, `URBAN` 1/2 swapped in 2001, `WHYTRP1S` two numbering systems): always map through a crosswalk.