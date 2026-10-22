# Feature registry

Generated from `pynhts.features.registry()`; each feature lists its scientific meaning, sources, exact formula, eligibility, missing-value rule, denominator, weight and the waves in which it exists. Creators: `create_person_features`, `create_household_features`, `create_trip_features`, `create_vehicle_features`.

Conventions: zero is not missing (counts of nothing are 0; unknown member values are counted separately and, with `strict=True`, make the count NaN); eligibility is explicit; household values are never repeated onto child rows; household features carry the household weight, never the trip weight; survey-day quantities are observed, not annual. Validation of the member counts: in every household whose person file is a complete roster they equal the survey's own `WRKCOUNT` and `DRVRCNT` in all four waves (`tests/data/test_features_real.py`).


## Person level (20 features)


### demographics

| name | meaning | source variables | formula | missing | denominator | waves |
| --- | --- | --- | --- | --- | --- | --- |
| p_age_band | Age in the bands of pynhts.harmonize.age_bands | person.R_AGE | harmonize.age_bands(R_AGE, wave) | NaN for unknown age; top-coded ages are inside the top band | - | 2001,2009,2017,2022 |
| p_edu_cat | Education: less_than_hs, hs_grad, some_college_assoc, bachelor, graduate | person.EDUC | harmonize.apply(EDUC, "education") | NaN for skip (-1: not asked), non-answers and persons under 18; see p_edu_status | - | 2001,2009,2017,2022 |
| p_edu_status | answered / not_applicable / unknown for the education question | person.EDUC | answer_status(EDUC) | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| p_worker | Worker status: yes / no / not_applicable / unknown | person.WORKER | WORKER code 1 -> yes, 2 -> no, -1 -> not_applicable, -7/-8/-9 -> unknown | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| p_driver | Driver status: yes / no / not_applicable / unknown | person.DRIVER | DRIVER code 1 -> yes, 2 -> no, -1 -> not_applicable, -7/-8/-9 -> unknown | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |

### travel

| name | meaning | source variables | formula | missing | denominator | waves |
| --- | --- | --- | --- | --- | --- | --- |
| p_n_trips | Number of trips on the travel day (0 for persons without trips) | trip rows | count of the person's trip rows | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | persons, including those with no trips | 2001,2009,2017,2022 |
| p_miles | Distance travelled on the travel day (TRPMILES summed) | trip.TRPMILES | sum of TRPMILES over the person's trips | NaN if any trip has no distance (miles_missing='skip' ignores them as FHWA does) | - | 2001,2009,2017,2022 |
| p_minutes | Travel time on the travel day (TRVLCMIN summed) | trip.TRVLCMIN | sum of TRVLCMIN over the person's trips | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| p_any_trip | At least one trip on the travel day | trip rows | p_n_trips > 0 | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |

### modes

| name | meaning | source variables | formula | missing | denominator | waves |
| --- | --- | --- | --- | --- | --- | --- |
| p_trips_mode_walk | Trips by mode group walk | trip.TRPTRANS | count of trips whose harmonize.apply(TRPTRANS, "mode", level="summary") == "walk" | trips with an unknown mode are in no group | - | 2001,2009,2017,2022 |
| p_trips_mode_bike | Trips by mode group bike | trip.TRPTRANS | count of trips whose harmonize.apply(TRPTRANS, "mode", level="summary") == "bike" | trips with an unknown mode are in no group | - | 2001,2009,2017,2022 |
| p_trips_mode_private_vehicle | Trips by mode group private_vehicle | trip.TRPTRANS | count of trips whose harmonize.apply(TRPTRANS, "mode", level="summary") == "private_vehicle" | trips with an unknown mode are in no group | - | 2001,2009,2017,2022 |
| p_trips_mode_other_vehicle | Trips by mode group other_vehicle | trip.TRPTRANS | count of trips whose harmonize.apply(TRPTRANS, "mode", level="summary") == "other_vehicle" | trips with an unknown mode are in no group | - | 2001,2009,2017,2022 |
| p_trips_mode_school_bus | Trips by mode group school_bus | trip.TRPTRANS | count of trips whose harmonize.apply(TRPTRANS, "mode", level="summary") == "school_bus" | trips with an unknown mode are in no group | - | 2001,2009,2017,2022 |
| p_trips_mode_public_transit | Trips by mode group public_transit | trip.TRPTRANS | count of trips whose harmonize.apply(TRPTRANS, "mode", level="summary") == "public_transit" | trips with an unknown mode are in no group | - | 2001,2009,2017,2022 |
| p_trips_mode_other_transit | Trips by mode group other_transit | trip.TRPTRANS | count of trips whose harmonize.apply(TRPTRANS, "mode", level="summary") == "other_transit" | trips with an unknown mode are in no group | - | 2001,2009,2017,2022 |
| p_trips_mode_other | Trips by mode group other | trip.TRPTRANS | count of trips whose harmonize.apply(TRPTRANS, "mode", level="summary") == "other" | trips with an unknown mode are in no group | - | 2001,2009,2017,2022 |

### purposes

| name | meaning | source variables | formula | missing | denominator | waves |
| --- | --- | --- | --- | --- | --- | --- |
| p_work_trips | Trips whose purpose summary is work | trip.WHYTRP1S | count of trips with purpose_summary == "work" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| p_nonwork_trips | Trips with a known purpose other than work | trip.WHYTRP1S | count of trips with a purpose_summary that is not "work" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| p_trips_unknown_purpose | Trips whose purpose is unknown | trip.WHYTRP1S | count of trips with no purpose category | p_work_trips and p_nonwork_trips do not include these trips | - | 2001,2009,2017,2022 |

Weight to use: person weight (WTPERFIN); a person-day quantity.


## Household level (59 features)


### composition

| name | meaning | source variables | formula | missing | denominator | waves |
| --- | --- | --- | --- | --- | --- | --- |
| hh_n_persons_listed | Persons of the household listed in the person file | person.R_AGE; household.HHSIZE | see description | members with unknown age are in none of the age counts; see hh_n_age_unknown | - | 2001,2009,2017,2022 |
| hh_n_unlisted | HHSIZE minus listed persons (children under 5 in 2009 and later, and members who were not interviewed) | person.R_AGE; household.HHSIZE | see description | members with unknown age are in none of the age counts; see hh_n_age_unknown | - | 2001,2009,2017,2022 |
| hh_n_adults | Listed members aged 18 or more | person.R_AGE; household.HHSIZE | see description | members with unknown age are in none of the age counts; see hh_n_age_unknown | - | 2001,2009,2017,2022 |
| hh_n_children | Listed members under 18 | person.R_AGE; household.HHSIZE | see description | members with unknown age are in none of the age counts; see hh_n_age_unknown | - | 2001,2009,2017,2022 |
| hh_n_older | Listed members aged 65 or more | person.R_AGE; household.HHSIZE | see description | members with unknown age are in none of the age counts; see hh_n_age_unknown | - | 2001,2009,2017,2022 |
| hh_n_workers | Members who are workers | person.WORKER | count of members with WORKER == yes | members with unknown WORKER: counted in hh_n_workers_unknown; strict=True makes hh_n_workers NaN | - | 2001,2009,2017,2022 |
| hh_n_workers_unknown | Members whose WORKER is a non-answer | person.WORKER | count of members with WORKER in (-7, -8, -9) | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_n_drivers | Members who are drivers | person.DRIVER | count of members with DRIVER == yes | members with unknown DRIVER: counted in hh_n_drivers_unknown; strict=True makes hh_n_drivers NaN | - | 2001,2009,2017,2022 |
| hh_n_drivers_unknown | Members whose DRIVER is a non-answer | person.DRIVER | count of members with DRIVER in (-7, -8, -9) | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_n_univ | Members with a bachelor's or graduate degree | person.EDUC | count of members with p_edu_cat in ("bachelor", "graduate") | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_n_edu_answered | Members who answered the education question | person.EDUC | count of members with answer_status(EDUC) == answered | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_n_edu_unknown | Members with a refused / unknown education | person.EDUC | count of members with answer_status(EDUC) == nonanswer | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_share_univ | Share of members who answered with a university degree | person.EDUC | hh_n_univ / hh_n_edu_answered | NaN when nobody answered; unknowns are excluded from numerator and denominator | members who answered EDUC | 2001,2009,2017,2022 |
| hh_n_age_unknown | Listed members with an unknown age | person.R_AGE | count of members with no valid age | these members are in none of the age counts | - | 2001,2009,2017,2022 |

### resources

| name | meaning | source variables | formula | missing | denominator | waves |
| --- | --- | --- | --- | --- | --- | --- |
| hh_veh_per_person | Vehicles per household member | household.HHVEHCNT; household.HHSIZE | HHVEHCNT / HHSIZE | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | HHSIZE (all members, incl. under 5) | 2001,2009,2017,2022 |
| hh_veh_per_driver | Vehicles per driver | household.HHVEHCNT; person.DRIVER | HHVEHCNT / hh_n_drivers | NaN when the household has no (known) driver | drivers | 2001,2009,2017,2022 |
| hh_zero_vehicle | No vehicle in the household | household.HHVEHCNT | HHVEHCNT == 0 | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |

### travel

| name | meaning | source variables | formula | missing | denominator | waves |
| --- | --- | --- | --- | --- | --- | --- |
| hh_n_trips | Trips of all members on the travel day | trip rows | count of the household's trip rows | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_zero_trip | No member made a trip on the travel day | trip rows | hh_n_trips == 0 | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_miles | Distance travelled by all members on the travel day | trip.TRPMILES | sum of TRPMILES over the household's trips | NaN if any trip has no distance (miles_missing='skip' ignores them) | - | 2001,2009,2017,2022 |
| hh_vmt | Vehicle miles driven by members on the travel day | trip.TRPMILES; trip.DRVR_FLG; trip.TRPTRANS | sum of TRPMILES of trips with DRVR_FLG == yes and mode group "private_vehicle" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |

### modes

| name | meaning | source variables | formula | missing | denominator | waves |
| --- | --- | --- | --- | --- | --- | --- |
| hh_trips_mode_walk | Household trips by mode group walk | trip.TRPTRANS | count of household trips with mode group "walk" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_trips_mode_bike | Household trips by mode group bike | trip.TRPTRANS | count of household trips with mode group "bike" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_trips_mode_private_vehicle | Household trips by mode group private_vehicle | trip.TRPTRANS | count of household trips with mode group "private_vehicle" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_trips_mode_other_vehicle | Household trips by mode group other_vehicle | trip.TRPTRANS | count of household trips with mode group "other_vehicle" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_trips_mode_school_bus | Household trips by mode group school_bus | trip.TRPTRANS | count of household trips with mode group "school_bus" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_trips_mode_public_transit | Household trips by mode group public_transit | trip.TRPTRANS | count of household trips with mode group "public_transit" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_trips_mode_other_transit | Household trips by mode group other_transit | trip.TRPTRANS | count of household trips with mode group "other_transit" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_trips_mode_other | Household trips by mode group other | trip.TRPTRANS | count of household trips with mode group "other" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_trips_unknown_mode | Household trips whose mode is unknown | trip.TRPTRANS | hh_n_trips minus trips in any mode group | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_mode_share_walk | Share of the household's known-mode trips in walk | trip.TRPTRANS | hh_trips_mode_walk / trips with a known mode | NaN for zero-trip households | trips with a known mode | 2001,2009,2017,2022 |
| hh_mode_share_bike | Share of the household's known-mode trips in bike | trip.TRPTRANS | hh_trips_mode_bike / trips with a known mode | NaN for zero-trip households | trips with a known mode | 2001,2009,2017,2022 |
| hh_mode_share_private_vehicle | Share of the household's known-mode trips in private_vehicle | trip.TRPTRANS | hh_trips_mode_private_vehicle / trips with a known mode | NaN for zero-trip households | trips with a known mode | 2001,2009,2017,2022 |
| hh_mode_share_other_vehicle | Share of the household's known-mode trips in other_vehicle | trip.TRPTRANS | hh_trips_mode_other_vehicle / trips with a known mode | NaN for zero-trip households | trips with a known mode | 2001,2009,2017,2022 |
| hh_mode_share_school_bus | Share of the household's known-mode trips in school_bus | trip.TRPTRANS | hh_trips_mode_school_bus / trips with a known mode | NaN for zero-trip households | trips with a known mode | 2001,2009,2017,2022 |
| hh_mode_share_public_transit | Share of the household's known-mode trips in public_transit | trip.TRPTRANS | hh_trips_mode_public_transit / trips with a known mode | NaN for zero-trip households | trips with a known mode | 2001,2009,2017,2022 |
| hh_mode_share_other_transit | Share of the household's known-mode trips in other_transit | trip.TRPTRANS | hh_trips_mode_other_transit / trips with a known mode | NaN for zero-trip households | trips with a known mode | 2001,2009,2017,2022 |
| hh_mode_share_other | Share of the household's known-mode trips in other | trip.TRPTRANS | hh_trips_mode_other / trips with a known mode | NaN for zero-trip households | trips with a known mode | 2001,2009,2017,2022 |
| hh_n_modes | Number of different mode groups used | trip.TRPTRANS | number of mode groups with at least one trip | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_multimodal | Two or more mode groups used on the travel day | trip.TRPTRANS | hh_n_modes >= 2 | False for zero-trip households (nothing was used) | - | 2001,2009,2017,2022 |
| hh_mode_entropy | Shannon entropy (natural log) of the mode-group trip shares | trip.TRPTRANS | -sum(p ln p) over mode groups, 0 ln 0 = 0 | NaN for zero-trip households | trips with a known mode | 2001,2009,2017,2022 |

### purposes

| name | meaning | source variables | formula | missing | denominator | waves |
| --- | --- | --- | --- | --- | --- | --- |
| hh_trips_purpose_home | Household trips with purpose home | trip.WHYTRP1S | count of household trips with purpose_summary "home" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_trips_purpose_work | Household trips with purpose work | trip.WHYTRP1S | count of household trips with purpose_summary "work" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_trips_purpose_school_daycare_religious | Household trips with purpose school_daycare_religious | trip.WHYTRP1S | count of household trips with purpose_summary "school_daycare_religious" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_trips_purpose_medical | Household trips with purpose medical | trip.WHYTRP1S | count of household trips with purpose_summary "medical" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_trips_purpose_shopping_errands | Household trips with purpose shopping_errands | trip.WHYTRP1S | count of household trips with purpose_summary "shopping_errands" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_trips_purpose_social_recreational | Household trips with purpose social_recreational | trip.WHYTRP1S | count of household trips with purpose_summary "social_recreational" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_trips_purpose_transport_someone | Household trips with purpose transport_someone | trip.WHYTRP1S | count of household trips with purpose_summary "transport_someone" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_trips_purpose_meals | Household trips with purpose meals | trip.WHYTRP1S | count of household trips with purpose_summary "meals" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_trips_purpose_other | Household trips with purpose other | trip.WHYTRP1S | count of household trips with purpose_summary "other" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_trips_unknown_purpose | Household trips whose purpose is unknown | trip.WHYTRP1S | count of trips with no purpose category | the hh_trips_purpose_* counts do not include these trips | - | 2001,2009,2017,2022 |

### fleet

| name | meaning | source variables | formula | missing | denominator | waves |
| --- | --- | --- | --- | --- | --- | --- |
| hh_n_vehicles_listed | Vehicles listed in the vehicle file | vehicle rows | count of vehicle rows | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_fleet_median_age | Median vehicle age in years (top-coded ages stay at the code) | vehicle.VEHAGE | median of VEHAGE | NaN when no vehicle age is known; median, not mean, because of the top code | - | 2001,2009,2017,2022 |
| hh_n_vehicles_new | Vehicles aged 5 years or less | vehicle.VEHAGE | count of VEHAGE <= 5 | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_n_veh_car | Vehicles of type car | vehicle.VEHTYPE | count of vehicles with harmonize.apply(VEHTYPE, "vehicle_type") == "car" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_n_veh_suv | Vehicles of type suv | vehicle.VEHTYPE | count of vehicles with harmonize.apply(VEHTYPE, "vehicle_type") == "suv" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_n_veh_van | Vehicles of type van | vehicle.VEHTYPE | count of vehicles with harmonize.apply(VEHTYPE, "vehicle_type") == "van" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_n_veh_pickup | Vehicles of type pickup | vehicle.VEHTYPE | count of vehicles with harmonize.apply(VEHTYPE, "vehicle_type") == "pickup" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| hh_n_vehicles_age_unknown | Listed vehicles with an unknown age | vehicle.VEHAGE | count of vehicles with no valid VEHAGE | these vehicles are not counted in hh_n_vehicles_new and not in hh_fleet_median_age | - | 2001,2009,2017,2022 |

Weight to use: household weight (WTHHFIN); never the trip or person weight.


## Trip level (11 features)


### distance_time

| name | meaning | source variables | formula | missing | denominator | waves |
| --- | --- | --- | --- | --- | --- | --- |
| t_distance_band | Trip distance band in miles (<1, 1-3, 3-5, 5-10, 10-25, 25-50, 50+) | trip.TRPMILES | pd.cut(TRPMILES, bins) with right-open bins | NaN if TRPMILES unknown | - | 2001,2009,2017,2022 |
| t_duration_band | Trip duration band in minutes | trip.TRVLCMIN | pd.cut(TRVLCMIN, bins) | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| t_depart_period | Departure period: am_peak 6-9, midday 9-15, pm_peak 15-19, evening 19-22, night | trip.STRTTIME | hour of STRTTIME (HHMM) | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| t_is_long_distance | Trip of 50 miles or more | trip.TRPMILES | TRPMILES >= 50 | NaN if TRPMILES unknown | - | 2001,2009,2017,2022 |

### purpose_mode

| name | meaning | source variables | formula | missing | denominator | waves |
| --- | --- | --- | --- | --- | --- | --- |
| t_mode | Mode category of the cross-wave crosswalk | trip.TRPTRANS | harmonize.apply(TRPTRANS, "mode") | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| t_mode_group | Mode summary group | trip.TRPTRANS | harmonize.apply(TRPTRANS, "mode", level="summary") | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| t_purpose | Trip purpose summary (home, work, ...) | trip.WHYTRP1S | harmonize.apply(WHYTRP1S, "purpose_summary") | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| t_is_work | Purpose summary is work | trip.WHYTRP1S | t_purpose == "work" | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |

### sequence

| name | meaning | source variables | formula | missing | denominator | waves |
| --- | --- | --- | --- | --- | --- | --- |
| t_order | Position of the trip within the person's travel day (1 = first) | trip key | rank by the trip number (TDTRPNUM / TRIPID) within person | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| t_is_first | First trip of the person's day | trip key | t_order == 1 | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| t_is_last | Last trip of the person's day | trip key | t_order == number of trips of the person | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |

Weight to use: trip weight (WTTRDFIN) = 365 x person weight: totals are annual, rates need the person/household denominator (pynhts.rates).


## Vehicle level (3 features)


### vehicle

| name | meaning | source variables | formula | missing | denominator | waves |
| --- | --- | --- | --- | --- | --- | --- |
| v_age_band | Vehicle age band 0-2, 3-5, 6-10, 11-15, 16+ (the top code falls in 16+) | vehicle.VEHAGE | pd.cut(VEHAGE, bins) | NaN if age unknown | - | 2001,2009,2017,2022 |
| v_type | Vehicle type category | vehicle.VEHTYPE | harmonize.apply(VEHTYPE, "vehicle_type") | counts skip rows with an unknown input; sums are NaN when a contributing value is unknown (miles_missing='skip' ignores it); ratios are NaN when the denominator is zero or unknown | - | 2001,2009,2017,2022 |
| v_fuel | Fuel category (gasoline, diesel, alt_fuel, other) | vehicle.FUELTYPE | harmonize.apply(FUELTYPE, "fuel") | 2022 has no fuel crosswalk | - | 2001,2009,2017 |

Weight to use: household weight (WTHHFIN).
