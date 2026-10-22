# Variable registry and data model

pynhts keeps three machine-readable layers, none of which replaces the original variable names or values:

1. **Schema** (`src/pynhts/_schema/<wave>/*.yaml`): every CSV column per wave, parsed from the official codebook (XLSX or PDF): owner table, type, length, missing codes, skip code, range, every code with label and unweighted/weighted frequency. `pynhts.dictionary(wave)` and `pynhts.describe(variable, wave)` read it; the codebook frequencies reproduce from the data (codebook quirks found on the way are listed in docs/data_notes.md).
2. **Registry** (`src/pynhts/_registry/<wave>.yaml`): files, SHA-256 hashes, weights, replicate-weight design (variance method as data).
3. **Concept dictionary** (`src/pynhts/concepts.yaml`): what a variable means in each wave, universe, unit, comparability, pitfalls and the evidence for each statement.

Cross-wave comparability categories used in the concept dictionary: `C` comparable as is, `H` comparable after the named harmonization, `N` do not compare (definition or universe changed). Not-yet-assessed variables have no concept entry; absence is not a claim of comparability.

## Size per wave

| wave | variables | tables | with a code list or range |
| --- | --- | --- | --- |
| 2001 | 495 | household, person, trip, vehicle, longdist | 495 |
| 2009 | 209 | household, person, trip, vehicle | 209 |
| 2017 | 247 | household, person, trip, vehicle | 235 |
| 2022 | 278 | household, person, trip, vehicle, longdist | 253 |

## Concepts (41): comparability {'H': 27, 'N': 11, 'C': 3}

| concept | table | 2001 | 2009 | 2017 | 2022 | comparability | harmonize |
| --- | --- | --- | --- | --- | --- | --- | --- |
| age | person | R_AGE | R_AGE | R_AGE | R_AGE | H | pynhts.harmonize.age_bands |
| sex | person | R_SEX | R_SEX | R_SEX | R_SEX | H | strip zero padding: 2001 uses '1'/'2', later waves '01'/'02' |
| household_income | household | HHFAMINC | HHFAMINC | HHFAMINC | HHFAMINC | H | harmonize.crosswalk("income") |
| education | person | EDUC | EDUC | EDUC | EDUC | H | harmonize.crosswalk("education") |
| race_household | household | HHR_RACE | HH_RACE | HH_RACE | HH_RACE | H | harmonize.crosswalk("race_household") |
| hispanic_household | household | HHR_HISP | HH_HISP | HH_HISP | HH_HISP | H | harmonize.crosswalk("hispanic_household") |
| race_person | person |  |  | R_RACE | R_RACE | H | harmonize.crosswalk("race_person") |
| hispanic_person | person |  |  | R_HISP | R_HISP | H | harmonize.crosswalk("hispanic_person") |
| worker | person | WORKER | WORKER | WORKER | WORKER | H | restrict to 16+ and strip zero padding |
| driver | person | DRIVER | DRIVER | DRIVER | DRIVER | H | restrict to the driving-age universe and strip zero padding |
| primary_activity | person | PRMACT | PRMACT | PRMACT | PRMACT | N |  |
| household_size | household | HHSIZE | HHSIZE | HHSIZE | HHSIZE | C |  |
| household_vehicles | household | HHVEHCNT | HHVEHCNT | HHVEHCNT | HHVEHCNT | C |  |
| urban_rural | household | URBRUR | URBRUR | URBRUR | URBRUR | H | harmonize.crosswalk("urban_rural") |
| urbanized_area | household | URBAN | URBAN | URBAN | URBAN | H | harmonize.crosswalk("urban_area") |
| block_group_density | household | HBHUR | HBHUR | HBHUR | HBHUR | H | harmonize.crosswalk("density") |
| state | household | HHSTATE | HHSTATE | HHSTATE |  | N |  |
| cbsa | household |  | HH_CBSA | HH_CBSA |  | N |  |
| trip_distance | trip | TRPMILES | TRPMILES | TRPMILES | TRPMILES | N |  |
| vehicle_miles_of_trip | trip |  | VMT_MILE | VMT_MILE | VMT_MILE | H | 2001: TRPMILES of the trips on which DRVR_FLG is yes |
| trip_duration | trip | TRVLCMIN | TRVLCMIN | TRVLCMIN | TRVLCMIN | C |  |
| dwell_time | trip | DWELTIME | DWELTIME | DWELTIME | DWELTIME | H |  |
| travel_day | trip | TRAVDAY | TRAVDAY | TRAVDAY | TRAVDAY | H | strip zero padding |
| trip_mode | trip | TRPTRANS | TRPTRANS | TRPTRANS | TRPTRANS | H | harmonize.crosswalk("mode") |
| trip_purpose_detailed | trip | WHYTO | WHYTO | WHYTO | WHYTO | H | harmonize.crosswalk("purpose") |
| trip_purpose_summary | trip | WHYTRP1S | WHYTRP1S | WHYTRP1S | WHYTRP1S | H | harmonize.crosswalk("purpose_summary") |
| trip_purpose_1990 | trip | WHYTRP90 | WHYTRP90 | WHYTRP90 | WHYTRP90 | H | harmonize.crosswalk("purpose_1990") |
| trip_class | trip | TRIPPURP | TRIPPURP | TRIPPURP | TRIPPURP | H | harmonize.crosswalk("trip_class") |
| trip_counting | trip |  |  |  |  | N |  |
| vehicle_type | vehicle | VEHTYPE | VEHTYPE | VEHTYPE | VEHTYPE | H | harmonize.crosswalk("vehicle_type") |
| vehicle_fuel | vehicle | FUELTYPE | FUELTYPE | FUELTYPE |  | H | harmonize.crosswalk("fuel") |
| vehicle_age | vehicle | VEHAGE | VEHAGE | VEHAGE | VEHAGE | H | bands, not means |
| annual_miles_best | vehicle | BESTMILE | BESTMILE | BESTMILE |  | H |  |
| annual_miles_self | vehicle | ANNMILES | ANNMILES | ANNMILES | ANNMILES | H |  |
| transit_use | person | PTUSED | PTUSED | PTUSED | PTUSED | N |  |
| commute_time | person | TIMETOWK | TIMETOWK | TIMETOWK |  | H |  |
| weight_household | household | WTHHFIN | WTHHFIN | WTHHFIN | WTHHFIN | N |  |
| weight_person | person | WTPERFIN | WTPERFIN | WTPERFIN | WTPERFIN | N |  |
| weight_trip | trip | WTTRDFIN | WTTRDFIN | WTTRDFIN | WTTRDFIN | N |  |
| long_distance_trips | longdist | BEGTRIP |  |  | BEGTRIP | N |  |
| replicate_design |  |  |  |  |  | N | pynhts handles it per wave (registry) |

## Derived variables

Official derived variables (for example `TRPMILES`, `R_AGE_IMP`, `WTTRDFIN`) are part of the schema like any other column and keep their original names. Features created by pynhts are named with a level prefix (`p_`, `hh_`, `t_`, `v_`), are listed in the feature registry with their formula and source variables, and carry `attrs["pynhts_features"]` lineage when created (source variables, formula, missing rule). pynhts never modifies the downloaded data.

## Lineage of a result

Every table and every estimate carries `attrs["pynhts"]` (wave, table, weight column, variance design, unit); aggregation results add `attrs["pynhts_aggregate"]` (source, keys, row counts, missing-value policy, missing inputs per output); feature frames add `attrs["pynhts_features"]`.
