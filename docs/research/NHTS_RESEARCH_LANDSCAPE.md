# How NHTS data are used in research: what the analyses need from a package

Status: **a first pass, not a systematic review.** Evidence: (a) ten US NHTS papers and one out-of-scope South African report (E11) read in full during the paper-data audit of 2026-10-22
(E01-E11 in `NHTS_FUNCTIONALITY_EVIDENCE.csv`); the descriptive numbers that can be reconstructed from each text were checked against pynhts (E07 and E10 could not be reproduced: the analysed population is not stated); (b) seventeen further studies
found by five OpenAlex searches the same day, of which only the **abstract snippet** was read (L01-L17). Nothing below is cited from memory.
Research areas without evidence in these two sets are marked *not yet searched*; the absence of a study here is not evidence that none exists,
and no feature is claimed to be novel because of it. Official sources (nhts.ornl.gov documentation, user guides, codebooks, weighting reports,
FHWA publications) are the basis of the package registry; their pinned copies were read in earlier sessions and are not re-fetched here.

## What the evidence shows across areas

* The **unit of analysis is rarely the unit of the file**: person-day (active-travel prevalence, E01, E03), person (E02, E04, E10), household
  (fee burden, L03, L13; vehicle ownership, L11), vehicle (E05, E09), trip (mode shares, E06, L05, L06). Studies collapse trips to persons or persons
  to households themselves, with the rule often unstated (E02, E03, E07, E10: the analysed population cannot be reconstructed from the text).
* **Weights are used inconsistently**: replicate-weight jackknife (E03), scaled weights stated but unweighted numbers printed (E04), no weights stated for the SEMs (E02, E10) and none for the classifiers of E05.
* **Cross-wave comparison is common** (E08, L05, L06, L08, L14, L16) and always flagged by the authors as method-sensitive; distance changed its measurement
  between 2009 and 2017.
* **Machine-learning studies** (E05, L11, L12) use person- or household-level feature tables built by hand, with class imbalance and no group-aware splitting mentioned in the snippets.
* **Equity and representation** (L01, L08, L15, L17) rest on subgroup shares by race, income and rurality, where the weighted-versus-unweighted comparison matters.

## Area by area

| Area | Typical unit | Dependent variables | Explanatory variables | Tables | Weight | Common methods | Pitfalls seen | pynhts 0.7.0 support | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| A trip generation and travel behaviour | person-day, household | trips/day, miles/day | age, income, workers, vehicles, urbanity | person, trip | person (rates: trip weights over person weights) | descriptive rates, regression | 2022 trip weights contain a methods adjustment; annual vs daily | `rates.daily_rate`, `aggregate`, `p_n_trips`, `hh_n_trips` | E08, L02 |
| B household travel characteristics | household | household trips, miles, VMT | size, vehicles, income, life cycle | household, trip | household | descriptive, SEM | person file is not a complete roster; household values repeated on children | `create_household_features` (composition, resources, travel) | E08, L03 |
| C vehicle ownership and VMT | household, vehicle | vehicles, annual miles, VMT | drivers, income, fuel cost, vehicle age | household, vehicle | household | regression, quantile regression, ML | BESTMILE built from older waves; top-coded VEHAGE; mileage measures disagree | vehicle features, `hh_veh_per_driver`, top-code flags, recipes | E05, E09, L03, L10, L11, L13 |
| D mode choice and public transit | trip, person | mode, transit/ride-hailing use | age, income, density, vehicles | trip, person | trip or person | logit, nested logit, ZINB | codes change meaning per wave; ride-hailing merged with taxi in the trip file | `harmonize.apply(..., "mode")`, mode-group features, `trends.trip_shares` | E04, L05, L06, L09, L12 |
| E walking and cycling | person-day, trip | any walk/bike trip, share | age, sex, income, region, month | person, trip | person (replicates) | logistic regression | minimum-duration rules; exercise trips; scooter mode not in public file | person-day aggregation (`aggregate`), `p_trips_mode_walk/bike` | E01, E03, E06, L07 |
| F purposes and trip chaining | trip chain, person-day | chain length, stops | purpose sequence, mode | trip | person-day | descriptive, logit | no standard chain definition; `tours` is 2017-only by design | `t_order`, `t_is_first/last`, `pynhts.tours` | E07, L09, L16 |
| G demographic and socioeconomic differences | person | any travel outcome | age, sex, race, education, income | person | person | all | race and income variables differ by wave; age top-coded | `p_age_band`, `p_edu_cat`, `compare_groups`, crosswalks (education, income) | E01, E08, L06 |
| H urban, suburban, rural | household, trip | any | density, MSA size, urbanity | household | household | descriptive | classification differs by wave (`URBAN` 1/2 swapped in 2001) | concepts (`urban_rural`, `block_group_density`) | E04, L06, L17 |
| I equity and accessibility | household, person | travel burden, access | income, race, rurality, transit | trip, household | household/person | descriptive, logit | representation of subgroups; block-group joins need restricted IDs | `sample_characteristics`, weighted vs unweighted shares | L01, L08, L15, L17 |
| J household composition and mobility | household | trips, vehicles | members by age, workers, drivers, education | person -> household | household | descriptive | unlisted members; unknown vs zero | composition features, `hh_n_unlisted` | E05, L11 |
| K teleworking, online shopping, substitution | person | shopping trips, purchases | web use, deliveries, density, work type | person, trip | none in SEM | SEM | unstated sample rules; two surveys only (2009, 2017 ask) | person-day features; external state join not provided | E02, E10 |
| L energy and emissions | vehicle, household | fuel use, CO2/km | MPG, VMT, fuel cost | vehicle | household | descriptive, regression | MPG is rated, not on-road | vehicle features, EIA variables in schema | E09, E07 |
| M road safety and exposure | driver | exposure (VMT) | age, sex | person, vehicle | household/person | validation of exposure | public file has no crashes | VMT by age/sex with design-based SE | L04 |
| N travel-demand modelling | person-day | activity-travel patterns | demographics, land use | all | person-day | choice models, microsimulation | survey-day only; no panel | arrays/tensors (`ml`), features | E07, L12 |
| O machine learning and prediction | person, household, vehicle | adoption, ownership, mode | all of the above | joined tables | rarely used | RF, XGBoost, SVM, SHAP | leakage between persons of a household; class imbalance; unweighted metrics | `split_by_household`, `Transformer`, `ml` | E05, L11, L12 |
| P changes across waves | person, trip | shares, rates | wave | all four | per wave | descriptive, odds ratios | distance, trip counting and sample frame changed; weights not poolable | `trends`, `compare_waves`, concept comparability | E08, L05, L06, L08, L14, L16 |
| Q survey integration, transferability, synthetic populations | person, household | distributions | demographics | person, household | design weights | synthesis, calibration | design information must travel with the data | replicate-weight and Taylor designs, `survey_rows` | L14, L15 |

*Not yet searched in this session:* weather and seasonality beyond E01, long-distance travel (the 2001 long-distance file and the 2022 long-distance table
exist in pynhts), freight-related use, children's and school travel beyond L07, COVID-period change (2022 is the first post-pandemic wave).

## Common operations that justify package functionality (inferred from the evidence)

1. person-day and household aggregation of trips with an explicit missing-value rule (E01-E03, E10, L09);
2. harmonized categories (mode, purpose, education, income, race) across waves (E08, L05, L06, L08);
3. design-based prevalence and mean with margins of error (E03; E06 reports 90 % intervals);
4. a sample-flow (cohort) table so a methods section can say who was excluded and why (E01-E03, E10 are not reproducible without it);
5. leakage-safe splits and documented feature tables for ML (E05, L11, L12);
6. honest cross-survey comparison with method caveats (L14, E08).

## Reproducibility opportunities

Each row in the evidence table has a `validation_opportunity`. Already executed (code in `tools/paper_audit`): E01 sample and odds ratios, E08 totals and
rates, E09 tables 1-4, E05 table 1 and sample size, E04 weighted totals; E02, E03, E06, E07 and E10 only in part, with the reasons documented in
`docs/paper_data_audit/recovered_conventions.md`.

## Limits of this document

Seventeen leads came from five search queries (limit 8 each): this is a sample of a literature of several thousand NHTS studies (the search engine's own
estimate for the first query alone was about 10,000 records, which includes false matches). Citation counts and abstracts are as returned by OpenAlex on
2026-10-22. Before citing any lead, open it and read it; before claiming novelty for any feature, run a systematic check.
