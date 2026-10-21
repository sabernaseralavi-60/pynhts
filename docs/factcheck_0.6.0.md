# Fact-check of the statements new in pynhts 0.6.0 (and the 0.5.0 CHANGELOG entry)

Date 2026-10-22. Checked against the raw CSV files of the four waves (`local_data/x2001`, `local_data/x2009/Ascii`,
`local_data/cache/2017/raw`, `local_data/cache/2022/raw`, replicate files in `local_data/x2001rep`, `x2009rep`,
`cache/2017/raw/*wgt.csv`), read with pandas as strings, and against the official documents: 2001 User's Guide
(Appendix B codebook) and 2001 Summary of Travel Trends (STT); 2009 User's Guide v2, Codebook v2.1, Weighting Report,
STT; 2017 User's Guide, Weighting Report, Compatibility note, codebook v1.2 (xlsx); 2022 User Guide, Weighting Memo,
Compatibility note v2.1, codebook (xlsx). `agent_eval/reference.py` was NOT used; the oracles were recomputed from
the raw CSV files. R checks used R 4.4.1 with `survey`. Scratch scripts are outside the repository.

Weights: households `WTHHFIN`, persons `WTPERFIN`, trips `WTTRDFIN`, vehicles `WTHHFIN`. "w." = weighted,
"unw." = unweighted. UG = User's Guide, CB = codebook, WM = 2022 Weighting Memo, Compat = compatibility note.

Verdicts: TRUE, FALSE, IMPRECISE (true in part, misleading, or status overstated), UNVERIFIED (no document or
data can settle it here), MISSING (a fact the file should contain and does not).

## 1. FALSE, IMPRECISE and MISSING (fix these)

| # | location | statement | verdict | evidence (command / number) | suggested correction |
|---|---|---|---|---|---|
| 1 | concepts.yaml:77 | "in 2001 and 2009 Hispanic/Mexican is one of the race codes, in 2017 and 2022 it is a separate variable (HH_HISP)" | FALSE | 2001 has a separate `HHR_HISP` (1=Yes 3,708 hh) and 2009 a separate `HH_HISP` (01=Yes 10,246 hh), *in addition to* the race code (2001 `HHR_RACE` 06 "Hispanic/Mexican Only" 1,795; 2009 `HH_RACE` 07 "Hispanic/Mexican" 3,892). 2001 also has combination codes 07-17 (e.g. 10 "White & Hispanic" 1,215) that 2009 does not have (CB 2001 p. B-15; value counts of HHPUB/HHV2PUB). | "All four waves have a separate Hispanic variable (2001 HHR_HISP, later HH_HISP); 2001 and 2009 ALSO carry Hispanic as a race code (2001 06, 2009 07), and 2001 has multi-race combination codes 07-17." |
| 2 | concepts.yaml:235 | "2001 and 2009 share one scheme ..., 2017 and 2022 another" | FALSE | 2017 and 2022 WHYTO use different numbers for the same purpose (2017 08 attend school = 2022 06; 2017 05 volunteer = 2022 08; 2017 04 work-related ≠ 2022 04); the package's own crosswalk `purpose` and `compare_waves` (`codes_permuted` WHYTO 2017/2022, CHANGELOG 0.5.0) say so. | "2001 and 2009 share one scheme; 2017 and 2022 use a second scheme whose codes are renumbered between the two waves (crosswalk 'purpose')." |
| 3 | crosswalks.yaml:495-514 | `trip_class` (TRIPPURP): every row `status: exact` | FALSE | Cross-tab of TRIPPURP with the non-home end purpose: 2001/2009 put work-related business (WHYTO 13, 14) in **HBO** (2001: 7,058 home-based trips; 2009: 15,301), 2017 puts work-related (04) in **HBW** (6,150), 2022 puts 04 and 05 in HBW (559). Weighted HBW share 10.60 % (2001), 11.57 % (2009), 13.68 % (2017), 17.86 % (2022). | `status: approximate` for hbw and hb_other in all waves; note: "2001/2009 HBW excludes work-related business (in HBO); 2017/2022 HBW includes it." |
| 4 | crosswalks.yaml:478, 482, 483 | fuel: 2001/2009 "4 Gasoline" and 2017 "01 Gas" `exact`; alt_fuel `nested` | FALSE | 2009: of 7,222 vehicles with HYBRID=01, 7,084 have FUELTYPE 4 (gasoline). 2017: all 6,416 HYBRID=01 vehicles have FUELTYPE 03 and none 01. So 2009 "gasoline" contains hybrids, 2017 "gas" does not; w. alt-fuel share 0.05 % (2009) vs 2.14 % (2017). | gasoline and alt_fuel `approximate`, note "2001/2009 FUELTYPE (EIA, by model) puts hybrids in gasoline; 2017 puts hybrids, electric and alternative fuel in 03." |
| 5 | crosswalks.yaml:486 | 2017 FUELTYPE 97 "Some other fuel" → other, `exact` | FALSE | No 2001/2009 code maps to `other` (crosswalk rows 475-482). | `status: only_here` |
| 6 | crosswalks.yaml:521 | "present with the same 10 classes in all four waves" | FALSE | 2017 and 2022 WHYTRP90 have 9 classes (no 07); the next sentence of the same note says so. Value counts: 2017 {01..06, 08, 10, 11, 99}, 2022 idem. | "10 classes in 2001/2009, 9 in 2017/2022 (no vacation)." |
| 7 | crosswalks.yaml:531, 541, 551, 560 | purpose_1990 `other` (11) `exact` | IMPRECISE | w. share of class 11: 0.84 % (2001), 0.81 % (2009), 4.03 % (2017), 1.87 % (2022); 29.4 % (2017) and 44.8 % (2022) of the class-11 trips are "change type of transportation" segments, which 2001/2009 do not have. 2001/2009 home-to-home loop trips are 98 N/A (masked), 2017 loops go to 10 (58 %) or 11. | `approximate`, with that note. |
| 8 | crosswalks.yaml:527, 537, 547, 556 | purpose_1990 `school_church` `exact` | IMPRECISE | 2017 child care (WHYTO 09) → WHYTRP90 05 (97.6 %); 2001/2009 day care (24) → 04 (93 % / 81 %); 2022 care (07) → 04 (55 %). Small (2,008 trips in 2017). | note the child-care placement; `approximate` for 2017. |
| 9 | _schema/column_flags.yaml:31-32 | 2017 `R_AGE`, `R_AGE_IMP`: `source: codebook` | FALSE | 2017 codebook v1.2 prints only "Responses=5-92" (CODEBOOK_PER, CODEBOOK_TRIP); no "92 = 89+" label; no 2017 document found that states it. Data: 88 then 92 (2,557 rows), consistent with 89+. | `source: data` |
| 10 | _schema/column_flags.yaml:2 | "tests/data/test_column_flags.py re-checks all of them" | FALSE | No such file; the check is `tests/data/test_four_wave_guards.py::test_topcodes_are_what_the_flags_say`. | fix the path |
| 11 | _schema/column_flags.yaml:14-25 (2001) | 2001 top/bottom codes | MISSING | 2001 `VEHYEAR` bottom code: CB "1962=1908-1969" (1,745 vehicles; next value 1970). | add `VEHYEAR: {kind: bottom, code: 1962, boundary: 1970, meaning: "1969 or earlier", source: codebook}` |
| 12 | _schema/column_flags.yaml (2001) | idem | MISSING | 2001 `YRTOUS` (year entered US): 1958 holds 2,666 persons, next value 1970 (169); CB range "1958-2001" without a label: an undocumented bottom code. | add as `source: data` ("1969 or earlier", inference) or list as suspected sentinel |
| 13 | _schema/column_flags.yaml (all waves) | idem | MISSING | Caps at 200,000 miles: `BESTMILE` (2009 CB BEST_EDT 04/05 "set to 200,000": 78 vehicles; 95 rows at 200,000 in 2009, 156 in 2017, 7 in 2001), `ANNMILES` (127 / 136 / 258 / 108 rows at 200,000), `YEARMILE` (2001 has a flag `YRMLCAP` "Year miles was capped"; 24 / 48 / 76 rows at 200,000). | add as top-codes ("200,000 or more") or document as censored |
| 14 | concepts.yaml:105 | "earlier waves ask everybody" (PRMACT) | IMPRECISE | PRMACT skip counts: 2001 34,358 (= EDUC skip, persons < 16), 2009 38,132 (≈ WORKER skip 38,141), 2017 27,938 (= WORKER skip). Earlier waves ask every person 16+ (workers included, code "Working"). | "earlier waves ask all persons 16+, workers included" |
| 15 | concepts.yaml:83 | 2001 worker universe "skipped below age 15" | IMPRECISE | Persons with R_AGE < 15: 25,227 have -1 but 6,452 have a value (6,445 "2 No", 7 "1 Yes"). DRIVER idem (6,452 "2"). | "mostly skipped below 15; 6,452 children under 15 are coded 'No'" |
| 16 | concepts.yaml:33 | "2022 imputation unverified" | IMPRECISE | WM p. 21, Table 8: hot-deck imputation of age for 35 household respondents (and sex 121, income 96, education 123); footnote 9: "additional imputations were required for other household members". 2022 R_AGE has no missing value and no R_AGE_IMP column. | "2022: imputed (Weighting Memo, Table 8); the public R_AGE contains no missing value and has no imputation flag." |
| 17 | concepts.yaml:132; crosswalks.yaml:364, 388; urban_rural rows 390-397 `exact`; concept grade C | "vintage not verified for each"; URBRUR identical | IMPRECISE | CB: 2017 URBAN "based on ... 2014 TIGER/Line", 2022 URBAN "based on 2020 TIGER/Line". 2022 also ships `URBRUR_2010` ("based on 2010 Census"): 432 of 7,893 households (5.5 %) differ from URBRUR. URBAN 03 ("surrounded by urban areas") is URBRUR urban in 2001 (391 hh) and 2009 (62) but rural in 2017 (51) and 2022 (1). | grade H; note "2022: use URBRUR_2010 for comparisons with 2017; URBAN 03 changes side". |
| 18 | concepts.yaml:244; AGENTS.md:25 | WHYTRP1S has "three code systems" | IMPRECISE | Two numbering systems: 2001 01-13 (01 = to work) and 2009+ 01/10/20/.../97. 2017/2022 differ from 2009 only by the absent code 60 (value counts). | "two code systems (and code 60 disappears from 2017)" |
| 19 | concepts.yaml:272 | "trip weights that contain a +10-12 % methods adjustment" | IMPRECISE | 10-12 % is the analysis range in Compat 2022 p. 3; the factor finally applied varies by purpose: trip weight / person weight = 375.4-432.7 (factor 1.028-1.186); overall 2.2752 / 2.0776 = +9.5 %. | "+9.5 % overall (factor 1.03-1.19 by trip; the compatibility note cites a 10-12 % analysis range)" |
| 20 | concepts.yaml:273 | "2001 and 2009 link them" (change-mode segments) | IMPRECISE | 2001 UG Exhibit 3-1 (p. 3-26): stops only to change mode were excluded "except where public transportation was involved". 2009: no statement in the local User's Guide. | "2001 links them except transfers involving public transportation; 2009 has no change-mode purpose code" |
| 21 | concepts.yaml:291 | "2022 has HYBRID instead"; grade H | IMPRECISE | HYBRID exists in 2009 (7,222 = 01) and 2017 (6,416 = 01, identical to FUELTYPE 03) too; 2009 gasoline includes hybrids (row 4). | mention HYBRID in all three later waves and the hybrid placement; grade H only after the fix of row 4. |
| 22 | concepts.yaml:300 | "VEHYEAR has a bottom code (2009: 1974 = 1984 or earlier)" | IMPRECISE | Bottom codes exist in every wave: 2001 1962 = 1908-1969 (CB), 2009 1974 = 1923-1984 (CB), 2017 1977 (data: next 1985), 2022 1982 (data: next 1990). Only 2001 is missing from the flags (row 11). | list all four |
| 23 | concepts.yaml:318 | "4.3 % don't know in 2001, 2.2 % in 2009, 26 % in 2017, 1.5 % in 2022" | IMPRECISE | 2001 -8 DK 4.30 % (5,991/139,382) ✓; 2009 -8 2.24 % ✓; 2017 25.89 % and 2022 1.45 % are "-9 Not ascertained" (the only code there). 2001 total item non-response 5.8 % (DK 4.30 + refused 0.66 + NA 0.81). | "item non-response (don't know / not ascertained)" |
| 24 | concepts.yaml:336; docs/guards.md:9; CHANGELOG.md:41 | "-4 and -5 (did not work)" | IMPRECISE | CB 2001 and 2009: -4 = "Did not work in usual workplace last week" (2001 437, 2009 962), -5 = "Did not work last week" (1,777 / 3,097). | "-4 (not at the usual workplace) and -5 (did not work last week)" |
| 25 | concepts.yaml:180 | "2017 and 2022: shortest-path distance between geocoded points" | IMPRECISE | 2017 ✓ (UG 2017 p. 5-1: Google Maps shortest network path; Compat 2017). 2022 UG Table (line ~378): "Trip distance calculated using Google API based upon traffic patterns and likely route during time and date of trip"; 2022 derived-variables doc: loop trips use the reported loop distance. | "2017: shortest path; 2022: Google route for the trip's time (loop trips: reported distance)" |
| 26 | concepts.yaml:123 | "The 2009 file counts golf carts (292 vehicle rows); the FHWA 'household vehicles' are types 01-07" | IMPRECISE | As a pitfall of `HHVEHCNT` it misleads: HHVEHCNT 2009 equals the number of vehicle rows with VEHTYPE 01-07 in all 150,147 households (it already excludes the 292 golf carts, the 554 "other" (97) and 361 unknown-type rows); only the vehicle FILE contains them. 2001, 2017, 2022: HHVEHCNT = vehicle rows everywhere. | "HHVEHCNT is comparable; the 2009 VEHICLE FILE has 1,207 rows outside 01-07 (292 golf carts, 554 other, 361 unknown) that HHVEHCNT does not count." |
| 27 | docs/methods.md:5-6, 11-12 | `convention="design"` is "the textbook convention"; 2017 df 84 | IMPRECISE | For 2001/2009 the "design" df (98, 99) is R's `degf` = rank of the replicate weights − 1, not a textbook JK2 df (JK2 with 100 pairs has 100). For 2017 the 84 is the textbook n − H = 98 − 14 (14 variance strata × 7 units, 2017 Weighting Report §2.2, factor 6/7 ✓), but R gives 97: `svrepdesign(type="JKn", rscales=6/7)` on hhwgt.csv → `degf = 97` (run 2026-10-22). So the 2017 "design" df is neither R's nor consistent with 2001/2009. | say "R `survey` convention (df = rank − 1)" for 2001/2009 and either use 97 for 2017 or call 84 "stratified-jackknife df (n − H)" explicitly. |
| 28 | docs/methods.md:10 | 2001 `fhwa`: df 99 "of the User's Guides and of the published tables" | IMPRECISE | 2001 UG 7-E.1 gives the 98/99 factor ✓ but its worked example uses 2.000 × SE (202,586,200 ± 1,344,144 with SE 672,072), i.e. no t(99). For 2009 the UG example matches t(0.975, 100) = 1.98397 ✓. | "2001: df not stated (UG example uses 2 × SE); 99 is a pynhts choice" |
| 29 | docs/methods.md:14-15; CHANGELOG.md:23-24 | "Both conventions equal R's survey package" | IMPRECISE | Estimates and SE equal (rel. diff 1.3e-7 for 2009, 1.9e-6 for 2001, household total in domain HHSIZE ≥ 3) ✓. The df do not: `fhwa` uses 100 (2009) / 99 (2001), the R golden files hold 99 / 98 for the same rows. | "SE equal; df equal for `design` only" |
| 30 | docs/methods.md:23-24; rates.py:44-46 | "2001 with all ages 4.03 (published 4.03; with `min_age=5` 4.10)"; "`min_age=5` makes them comparable" | IMPRECISE | daily_rate 2001: 4.0252 ✓ (STT 2001 Table 3: 4.03), 39.264 miles ✓ (39.26). But the STT's 0-4-excluded per-person figure is **3.74**, which min_age=5 (4.0969) does not reproduce: 3.74 = 9.66 × 107,365 / 277,203, i.e. trips of 5+ divided by ALL persons. Per household min_age=5 gives 9.6594 = published 9.66 ✓. STT Table 1 counts persons of unknown age in "All 5+", daily_rate drops them (2,399 persons). | add "the STT prints 3.74 for 2001 without 0-4 (denominator includes 0-4); per household min_age=5 reproduces 9.66" |
| 31 | docs/data_notes.md:147-149 | list of suspected undocumented sentinels | IMPRECISE (incomplete) | Further columns with an isolated maximum: 2009 NBIKETRP 99 (5 rows, next 90); 2017 NBIKETRP 99 (14, next 90), WALK4EX 99 (34, next 98), BIKE4EX 99 (4, next 85), DELIVER 99 (34, next 95); 2022 DELIVER 99 (7, next 80), DELIV_GOOD 99 (4, next 85), LD_NUMONTRP 99 (8, next 85), LD_ICB 100 (4, next 50), EMPLOYMENT2 99 (12, next 96); 2001 DISTBLOC 996 (20, next 300), YRTOUS 1958 (row 12). All inside the printed ranges (0-99, 1-99, 0-100), so likely input caps. | extend the list or say "examples" |
| 32 | docs/data_notes.md:149 | "`OD_READ*` = 999999 in 2001/2009 (not checked)" | IMPRECISE (now checkable) | 2001 OD_READ1: 3 rows at 999,999, next 999,191; 2009 OD_READ: 12 rows, next 999,971: the tail is continuous (6-digit odometer limit), not a sentinel. 2009 MCUSED 999 lies inside the CB range "0-999". | replace "(not checked)" with the counts |
| 33 | docs/data_notes.md:151-152; CHANGELOG.md:19-20 | the suppression codes that are masked: HHSTATE "XX", HH_CBSA "XXXXX" | IMPRECISE (incomplete) | Other suppression codes stay unmasked: 2001 HHSTFIPS "XX" (1,952 hh, 2 more than HHSTATE), HHC_MSA "XXXX" (2001 28,652 hh; 2009 45,884 hh), WORKSTAT / WKSTFIPS "XX" (2,345 / 2,356 persons), long-distance ACCST/EGRST "XX", ACCMSA/EGRMSA/FARMSA "XXXX"; MAKECODE/MODLCODE "XX"/"XXX"/"XXXX" (2001, 2009). 2009 HBHUR "X" (Unassigned, 9 hh) is a category, fine. | mask or document them |
| 34 | _schema/missing_overrides.yaml:6-7 | "The 2017 codebook labels them 'Suppressed, in an MSA of less than 1 million'" | IMPRECISE | That label is HH_CBSA's; 2001 HHSTATE XX is "Suppressed, HH in state of less than 2 million" (CB 2001 B-15). | give both labels |
| 35 | agent_eval/tasks.yaml:46 (T14) | trap: "a simple-random-sample standard error is several times too small"; naive 4.0 | FALSE | SRS SE of the total = N·sqrt(p(1−p)/n) = 131.1 thousand; with-replacement weighted SE sqrt(n·var(w·y)) = 487.0 thousand; jackknife 53.39 thousand. The naive SE is 2.5-9 times too LARGE (the weights are raked to household-size controls). 4.0 is not reproduced by any naive formula tried. | "the jackknife SE is much SMALLER than a naive SE because household size is a raking control"; drop or recompute naive |
| 36 | agent_eval/tasks.yaml:46 (T14) | source "r (survey::svrepdesign ...: 53,388.56)", tol 0.001 | IMPRECISE / AMBIGUOUS | 53,388.56 is R with `type="other", scale=0.99` (FHWA convention, `tools/validate_jackknife_r.R`). R's own `type="JK2"` gives 53,657.52 (+0.50 %), outside the tolerance. Raw recomputation: f = 99/100 → 53.38856, f = 1 → 53.65752. | state "with the User's Guide multiplier 99/100" in the question, or accept both |
| 37 | agent_eval/tasks.yaml:34 (T10) | naive 0; trap "a threshold above 25 is wrong" | IMPRECISE / AMBIGUOUS | A careless `VEHAGE >= 25` gives exactly the oracle (3.822 %), so the trap does not bite. Ambiguity: oracle 3.82 excludes vehicles with VEHAGE -9 (10,746) from the denominator; all vehicles → 3.672 % (−3.9 %, outside tol 0.01). Types 01-07 only: 3.822 / 3.679. | say "among vehicles with known age"; naive = 3.67 or drop |
| 38 | agent_eval/tasks.yaml:40 (T12) | oracle 10.5378 % "of the weighted households" | AMBIGUOUS | Oracle divides by households with a valid income (excludes -1, -7, -8, -9: 6,483 hh). Share of all weighted households: 9.6705 % (outside tol 0.005). Naive 0 is not a measured careless answer (code 18 gives the oracle). | "among households that report an income" |
| 39 | agent_eval/tasks.yaml:16 (T04) | oracle 19,626.32 thousand children under 5 | AMBIGUOUS | Uses R_AGE (2,399 persons of unknown age dropped). With R_AGEWGT (the age used in weighting, which `concepts.yaml:25` calls the imputed age): 19,877.11 (+1.28 %, outside tol 0.002). | name the variable or accept both |
| 40 | agent_eval/tasks.yaml:43 (T13) | "public-transit trips (summary mode)"; naive 0 | AMBIGUOUS (mild) | Oracle 2.5447 % = PUBTRANS = TRPTRANS 11, 15, 16 ✓. "Summary mode" is a pynhts term; a reader who counts all transit codes 10-16 gets 4.78 %. Naive 0 is not a careless value. | "as defined by the official PUBTRANS flag" |
| 41 | agent_eval/tasks.yaml:5 | "`naive` ... measured when the guard did not exist" | IMPRECISE | naive = 0 for T04, T10, T11, T12, T13 are placeholders, not measurements (T10's careless answer is the oracle). | "informational; 0 = no measured value" |
| 42 | docs/waves.md:125-126 | `crosswalk("purpose_summary")` maps WHYTRP1S "to ten categories" | FALSE | `harmonize.crosswalk("purpose_summary")` has 9 categories (home, work, school_daycare_religious, medical, shopping_errands, social_recreational, transport_someone, meals, other). | "nine categories" |
| 43 | README.md:84 | harmonize: "crosswalks of trip mode (four waves) and trip purpose (2017/2022; summary purpose for all four)" | IMPRECISE (stale) | `harmonize.concepts()` lists 12 concepts. | list the 12 |
| 44 | llms.txt:3 | "every known trap is documented and guarded" | IMPRECISE | Counter-examples in this report: rows 3-8, 11-13, 31-33. | "documented traps are guarded" |
| 45 | llms.txt:15 | "Concept dictionary (JSON)" linking to `concepts.yaml` | IMPRECISE | The file is YAML; JSON only via `concepts.to_json()`. | "(YAML; JSON via to_json())" |
| 46 | concepts.yaml:14-16 vs CHANGELOG.md:15 | which tests re-check the concepts | IMPRECISE | header names test_four_wave_guards.py and test_old_waves_real.py; the concept tests are in `tests/data/test_concepts_real.py`. | name all three |
| 47 | concepts.yaml:217 | "2001: March 2001 to June 2002" | IMPRECISE (minor) | Data TDAYDATE 200103-200206 ✓, but June 2002 travel days occur only in add-on areas (1,055 hh; 0 national); UG 1.C.2: national travel days March 29, 2001 - May 4, 2002. 2009 (200803-200904; UG: 28 Mar 2008 - 30 Apr 2009) ✓, 2017 (201604-201704; UG: 19 Apr 2016 - 25 Apr 2017) ✓, 2022 (202201-202301; UG 20 Jan 2022 - 19 Jan 2023) ✓. | "2001: March 2001 - May 2002 (national), add-ons to June 2002" |

Additional observations (not statements of the package, but relevant to the same files):

* 2022 `URBANSIZE` codes 04 and 05 are labelled the other way round from 2009 and 2017 (2009/2017: 04 = 1 million+ WITHOUT rail, 05 = WITH rail; 2022 CB: 04 = with heavy rail, 05 = without). Worth a `compare_waves` check (`codes_permuted`).
* 2017 `YEARMILE` uses -88 / -77 for don't know / refused (CB), unlike every other variable.
* 2009 `PTUSED`: besides the 608 hidden 99s, 98,498 persons (32 %) are -9 "not ascertained"; the CB's -9 count (99,106) is exactly data -9 + the 99s, which confirms the 99 masking.

## 2. UNVERIFIED

| # | location | statement | verdict | evidence | suggestion |
|---|---|---|---|---|---|
| U1 | concepts.yaml:327 | 2017 PTUSED = "days used of 30" | UNVERIFIED | CB 2017 label "Count of Public Transit Usage", range 0-30, asked of everybody (no skip); the question text was not available. 2001 "Public transit use last 2 months" (frequency categories 1-6) ✓, 2009 "How often S used public transit in past month" 0-180 ✓, 2022 "Days in last 30 days" asked if LAST30_PT = 01 (1,610 / 16,997 = 9.5 % unw.) ✓. | cite the 2017 questionnaire |
| U2 | concepts.yaml:150; crosswalks.yaml:404 | "class thresholds may differ by wave" | UNVERIFIED | No Claritas documentation in the local documents. Data consistent with the codes (2009 TC 58 % rural). | keep as "unverified" |
| U3 | docs/guards.md:14 | tours: "no home-based-work tour at all" in other waves | UNVERIFIED | not re-run (0.5.0 claim); a test exists (`test_tours_refuse_other_waves_without_a_config`). | — |
| U4 | docs/guards.md:4-5 | "Every guard has a test on the real files of all four waves" | UNVERIFIED in full | `test_four_wave_guards.py` has tests for skip, negative codes, top-codes, national-only, tours, wave tags, PUBTRANS, replicates, crosswalk coverage, income, URBAN, WHYTRP90, suppression, fuel, age bands; the `tables.note` guard is not in that file. | — |
| U5 | crosswalks.yaml:338 | 2001 "some graduate school, no degree" → the person holds a bachelor's | UNVERIFIED (plausible) | Professional-school entrants need not hold a BA; status `approximate` is appropriate. | — |

## 3. TRUE (checked and confirmed)

| # | location | statement | evidence |
|---|---|---|---|
| T1 | concepts.yaml:24 | age variable R_AGE in all waves | headers of PERPUB/PERV2PUB/perpub/perv2pub |
| T2 | concepts.yaml:25 | imputed age 2001 R_AGEWGT, 2017 R_AGE_IMP; none for 2022 | CB 2001 "Age of Subject used in weighting" 0-88, no missing; CB 2017 R_AGE_IMP 5-92, no missing; 2022 header has no R_AGE_IMP |
| T3 | concepts.yaml:26 | universe 2001 0+, others 5+ | min R_AGE: 0 / 5 / 5 / 5 |
| T4 | concepts.yaml:31 | 2001 88 = 85+ | R_AGE: 84 (478) then 88 (1,983), 85-87 absent; CB "0-88" (inference from data, as flagged) |
| T5 | concepts.yaml:31 | 2009 92 = 89+ | CB 2009 "92 = 89+" (3,176) |
| T6 | concepts.yaml:31 | 2017 and 2022 92 = 89+ | data: 88 then 92 (2,557; 128) |
| T7 | concepts.yaml:32 | 2001 contains children 0-4 | 19,626 thousand w. persons with R_AGE < 5 |
| T8 | concepts.yaml:33 | 2001 2,399 persons without age | -7 1,597, -8 792, -9 10 |
| T9 | concepts.yaml:33 | 2017 496 without age | CB/data -8 44 + -7 452 |
| T10 | concepts.yaml:33 | 2009 and 2022 no missing age; 2009 imputed in weighting | data; 2009 UG p. 2-14 "AGE, SEX ... were imputed during the weighting process", WR App. E |
| T11 | concepts.yaml:41, 43 | 2001 R_SEX '1'/'2', later '01'/'02' | raw values |
| T12 | concepts.yaml:43 | 2017 and 2022 keep -7/-8 sex answers; imputed versions exist | 2017 -7 209, -8 34, R_SEX_IMP; 2022 -7 228, -8 8, -9 1, R_SEX_IMP |
| T13 | concepts.yaml:49 | 2022 HHFAMINC_IMP | equals HHFAMINC for every valid code; fills the 96 -7/-8 (cross-tab) |
| T14 | concepts.yaml:54 | 18 bands 2001/2009, 11 bands 2017/2022 | CB / data codes 01-18 and 01-11 |
| T15 | concepts.yaml:54; crosswalks.yaml:264 | eight nominal bands nest exactly | band edges 10k, 15k, 25k, 35k, 50k, 75k, 100k exist in both schemes (CB labels) |
| T16 | concepts.yaml:55 | nominal dollars | CB "Total HH income last 12 months" / "Household income", no deflation |
| T17 | concepts.yaml:61 | EDUC universe 2001 16+ | min R_AGE with valid EDUC = 16; no person 16+ skipped |
| T18 | concepts.yaml:61 | 2009 18+ | min age with valid EDUC = 18, max skip age 17 |
| T19 | concepts.yaml:61 | 2017 from 14 | valid at 14: 2,559; younger: ≤ 3 per age (R_AGE_IMP) |
| T20 | concepts.yaml:61 | 2022 from 14 | min 14, max skip age 13 |
| T21 | concepts.yaml:66 | 8 categories 2001 and 2022, 5 in 2009 and 2017 | CB |
| T22 | concepts.yaml:72 | HHR_RACE in 2001, HH_RACE later | headers |
| T23 | concepts.yaml:83 | WORKER 16+ in 2009, 2017, 2022 | min valid age 16 (2017: ≤ 5 rows younger) |
| T24 | concepts.yaml:87 | skip code -1 outside the universe | data |
| T25 | concepts.yaml:96 | DRIVER from age 15 in all waves | min valid age 15 (2001 also has 6,452 "No" under 15) |
| T26 | concepts.yaml:105 | 2022 PRMACT non-workers only, no "working" code, 9,752 skips | CB 2022 label "for those who did not work for pay"; -1 = 9,752 |
| T27 | concepts.yaml:114 | HHSIZE counts all members in every wave | HHSIZE ≥ person rows; 2017 difference = YOUNGCHILD exactly |
| T28 | concepts.yaml:114 | 2022 completeness rule changed (all 5+ for 1-3 members) | 2022 UG §3.5 and Compat 2022 p. 3 (75 % rule for 4+); 92 hh with HHSIZE > persons and no young child |
| T29 | concepts.yaml:123 | 292 golf-cart rows in the 2009 vehicle file | VEHTYPE 08 = 292 |
| T30 | concepts.yaml:141; crosswalks.yaml:364-367 | URBAN 1/2 swapped in 2001 | CB 2001 "1=In an Urban cluster 8,752; 2=In an urban area 43,414"; 2009 01 = urban area; magnitudes 62 % vs 61 % |
| T31 | concepts.yaml:150; crosswalks.yaml:414 | 2009 HBHUR merges town and rural into TC | CB 2009 "TC = Town and Country" 71,126; TC hh 58 % rural |
| T32 | concepts.yaml:150; crosswalks.yaml:421-425 | 2022 HBHUR numeric 01-05 with 05 Urban ... 01 Rural | CB 2022 |
| T33 | crosswalks.yaml:406-420 | 2001/2017 HBHUR U/S/C/T/R labels; 2009 X Unassigned only_here | CB 2001, 2017, 2009 |
| T34 | concepts.yaml:155 | 2022 has no state | Compat 2022 p. 4 (HHSTATE, HH_CBSA omitted) |
| T35 | concepts.yaml:160 | 2001 XX = 1,950 households | data; CB "Suppressed, HH in state of less than 2 million" |
| T36 | concepts.yaml:161 | 2001 dominated by add-on states (Wisconsin) | WI 17,547 hh (25 %), NY 13,423 |
| T37 | concepts.yaml:170 | XXXXX 83,369 (2009), 73,746 (2017) | data |
| T38 | concepts.yaml:170 | only large CBSAs identified | CB 2017 "Suppressed, in an MSA of less than 1 million"; 52 identified CBSAs |
| T39 | concepts.yaml:166 | HH_CBSA absent 2001 and 2022 | headers |
| T40 | concepts.yaml:180 | 2001/2009 self-reported, about 85 % whole numbers | 85.35 % (2001), 83.51 % (2009) of valid TRPMILES |
| T41 | concepts.yaml:180 | 2017 ~10 % shorter; TRPMILAD | Compat 2017 p. 1-2 (vehicle trips); TRPMILAD in 2017 trip file only |
| T42 | concepts.yaml:181 | -1 rows in 2009 TRPMILES: 181 | data (2001 also has 21) |
| T43 | concepts.yaml:181 | -8 is 1.1-1.5 % in 2001 and 2009 | 1.093 %, 1.519 % |
| T44 | concepts.yaml:186 | VMT_MILE absent 2001 | header |
| T45 | concepts.yaml:189 | 2001: TRPMILES where DRVR_FLG yes | DRVR_FLG exists in 2001 trip file |
| T46 | concepts.yaml:190 | mean ~45 % too low with -1 | 5.363 vs 9.720 (−44.8 %) |
| T47 | concepts.yaml:199 | 2017 capped at 1,200; others 1,425-1,439 | max 1,439 / 1,439 / 1,200 / 1,425 |
| T48 | concepts.yaml:208 | DWELTIME -1 in 2001, -9 later, 21-34 % | 2001 -1 21.7 % (+ -9 0.1 %), 2009 22.7 %, 2017 23.7 %, 2022 34.2 % |
| T49 | concepts.yaml:214 | TRAVDAY 1 / 01 = Sunday | CB all waves; 2001 unpadded |
| T50 | concepts.yaml:217 | 2009 March 2008 - April 2009 | TDAYDATE 200803-200904; UG |
| T51 | concepts.yaml:217 | 2017 April 2016 - April 2017 | TDAYDATE 201604-201704; UG/Compat |
| T52 | concepts.yaml:217 | 2022 January 2022 - January 2023 | TDAYDATE 202201-202301; UG |
| T53 | concepts.yaml:217 | 2001 includes September 11 | CB TDBOA911 |
| T54 | concepts.yaml:226 | TRPTRANS 08 = airplane / golf cart / motorcycle / bus | CB 2001 "Commercial/charter airplane", 2009 "Light electric veh (golf cart)", 2017 motorcycle, 2022 public bus |
| T55 | concepts.yaml:226 | 19 = cruise ship / taxi / airplane / e-scooter | CB 2001 "Ship/cruise", 2009 "Taxicab", 2017 airplane, 2022 e-scooter |
| T56 | concepts.yaml:235 | 2001/2009 WHYTO scheme 11 go to work, 41 buy goods | value sets nearly identical (2001 91 other, 2009 97 other) |
| T57 | concepts.yaml:244 | 2001 01-13 (01 = to work) | CB "01=To work (11)" |
| T58 | concepts.yaml:244 | 2009 60 absent from 2017; trips in 40 | 2017 has no 60 |
| T59 | concepts.yaml:253; missing_overrides.yaml:4-5 | 98 N/A, 99 Refused; masked | CB 2001/2009; 2017/2022 "99=Refused / Don't Know" |
| T60 | missing_overrides.yaml:5 | 9,837 rows in 2009 | 9,498 + 339 |
| T61 | concepts.yaml:253 | vacation only 2001 and 2009 | 07 = 3,937 / 12,869 / 0 / 0 |
| T62 | concepts.yaml:262 | three formats 1-5, strings, 01-05 | 2001 '1'-'5', 2009/2017 'HBW'..., 2022 '01'-'05' |
| T63 | crosswalks.yaml:495-514 | TRIPPURP hints | CB labels of the four waves |
| T64 | concepts.yaml:272 | 2001, 2009 telephone; 2017 66 % web | Compat 2022 p. 2 ("34 % phone, 66 % online"); 2017 UG Table 2-1 has 60.4 % fully online + 9.4 % mixed |
| T65 | concepts.yaml:272 | 2022 99 % web, no travel log | Compat 2022 p. 2-3 |
| T66 | concepts.yaml:273 | change-mode segments 1.07 % (2017), 0.69 % (2022) of w. trips | 1.069 %, 0.691 % |
| T67 | concepts.yaml:282 | only 2009 has golf carts; other 91 (2001) / 97 | VEHTYPE value sets |
| T68 | crosswalks.yaml:432 | 2009 codebook class frequencies differ from the file | CB 01 154,593 vs file 151,238; 03 54,760 vs 58,718 |
| T69 | concepts.yaml:291 | 2001/2009 FUELTYPE numeric 1 diesel ... 4 gasoline; 2017 01 gas, 02 diesel | CB; data |
| T70 | concepts.yaml:291 | 2001 FUELTYPE national sample only | -1 for 100 % of add-on vehicles, 0 % of national |
| T71 | concepts.yaml:287 | 2022 no FUELTYPE | header, CB |
| T72 | concepts.yaml:300 | 40 = 33+ (2001, 2017, 2022), 35 = 25+ (2009) | 2001: 32 then 40 (1,745; VEHYEAR 1962 = 1908-1969); 2009 CB "35 = 25+"; 2017 32 then 40 (6,765); 2022 32 then 40 (287) |
| T73 | concepts.yaml:300 | 2009 VEHYEAR 1974 = 1984 or earlier | CB "1974 = 1923-1984" |
| T74 | concepts.yaml:309 | 2001 BESTMILE national only; −12.9 % VMT | 2,055.4 vs 2,358.9 billion = −12.87 % |
| T75 | concepts.yaml:305 | 2022 no BESTMILE | header |
| T76 | concepts.yaml:327 | 2009 PTUSED 99 hidden missing | 608 rows at 99 between 96 and 100; CB -9 count 99,106 = 98,498 + 608 |
| T77 | concepts.yaml:327 | 2022 asked of 9.5 % | 1,610 / 16,997 (unw.) |
| T78 | concepts.yaml:336 | 23.34 vs 24.21 min | 23.335 (with -4, -5) vs 24.205 |
| T79 | concepts.yaml:332 | 2022 has no TIMETOWK | header, CB |
| T80 | concepts.yaml:345 | 2022 excludes group quarters, about −2.5 % | Compat 2022 p. 3 |
| T81 | concepts.yaml:345 | 2001 has WTHHNTL | header |
| T82 | concepts.yaml:354 | 2001 persons include 0-4 | T7 |
| T83 | concepts.yaml:354 | 2022 non-traveler adjustment and ACS commute modes | Compat 2022 p. 3 ("journey to work travel modes and telework proportions ... ACS") |
| T84 | concepts.yaml:364 | WTTRDFIN = 365 × WTPERFIN 2001/2009/2017 | ratio min = max = 365.0 in all three |
| T85 | concepts.yaml:365 | 2022 trip weights vary within person-day | 3,767 of 10,592 persons have >1 distinct trip weight |
| T86 | concepts.yaml:365 | 2.275 vs 2.078 | 2.27522 vs 2.07761 |
| T87 | concepts.yaml:370 | BEGTRIP in 2001 and 2022 LD files; none 2009/2017 | headers |
| T88 | concepts.yaml:375 | 2001 one row per trip, national sample only | 45,165 rows, 100 % in national households |
| T89 | concepts.yaml:375 | weight = national person weight × 365/28 | WTPTPFIN / WTPRNTL = 13.0357 (sd 3e-10) = 365/28; UG 7-D.4 |
| T90 | concepts.yaml:375 | 2022 one row per person | 16,997 rows = 16,997 persons |
| T91 | concepts.yaml:385 | 2001 delete-one jackknife, 99 replicates, 98/99 | UG 7-E.1 |
| T92 | concepts.yaml:385 | 2009 JK2, 100 replicates, 99/100 | UG 2009 p. 7-1 (Jackknife2, formula 99/100) |
| T93 | concepts.yaml:385 | 2017 JKn 98 replicates, 6/7 | 2017 Weighting Report §2.2 (14 strata × 7 units) |
| T94 | concepts.yaml:385 | 2022 Taylor series | Compat 2022 p. 4 |
| T95 | concepts.yaml:385 | 2001 LD replicates a different system | UG Table 7-3 (FPTPWT01-99 national) |
| T96 | crosswalks.yaml:266-323 | income codes and hints, nested/exact statuses | CB labels 2001, 2009, 2017, 2022 |
| T97 | crosswalks.yaml:264 | 2022 HHFAMINC_IMP exists | T13 |
| T98 | crosswalks.yaml:332-357 | education codes and hints | CB labels (2001 unpadded '1'-'8') |
| T99 | crosswalks.yaml:330 | universes 16+/18+/14+ | T17-T20 |
| T100 | crosswalks.yaml:366-381 | URBAN codes/hints all waves | CB |
| T101 | crosswalks.yaml:390-397 | URBRUR codes/hints | CB (see row 17 for the scope caveat) |
| T102 | crosswalks.yaml:434-466 | VEHTYPE codes/hints | CB |
| T103 | crosswalks.yaml:449 | only 2009 has golf cart | T67 |
| T104 | crosswalks.yaml:475-485 | FUELTYPE codes/hints | CB (see rows 4-5 for statuses) |
| T105 | crosswalks.yaml:473 | 2001/2009 FUELTYPE EIA-derived | CB source column "EIA" |
| T106 | crosswalks.yaml:523-560 | WHYTRP90 codes/hints | CB (including the "Medical/Dentral" typo) |
| T107 | crosswalks.yaml:532, 542 | vacation only_here | T61 |
| T108 | crosswalks.yaml:521 | 98/99 masked | T59 |
| T109 | column_flags.yaml:15-24 | 2001 R_AGE, R_AGEWGT, HHR_AGE, AGE_P1-P7: 88, boundary 84 | each column: 84 (or 83) then 88 |
| T110 | column_flags.yaml:25 | 2001 VEHAGE 40, boundary 32 | T72 |
| T111 | column_flags.yaml:27-29 | 2009 R_AGE, VEHAGE, VEHYEAR from codebook | CB 2009 |
| T112 | column_flags.yaml:33-34 | 2017 VEHAGE 40/32, VEHYEAR 1977/1985 (data) | CB lists 1977 without label; next 1985 |
| T113 | column_flags.yaml:36-38 | 2022 R_AGE 92/88, VEHAGE 40/32, VEHYEAR 1982/1990 (data) | data; CB ranges 1-40 and 1982-2023 |
| T114 | column_flags.yaml:9-12, 42-44 | 2001 national-only list | every listed column is -1 for 98.5-100 % of add-on rows and valid for national rows; a scan of all 2001 columns found no unlisted national-only column |
| T115 | column_flags.yaml:10 | nine add-on areas | CB SMPLAREA 01-09 add-ons, 10 remaining |
| T116 | column_flags.yaml:12 | BESTMILE −12.9 % | T74 |
| T117 | flags.py:51-70 | caution text logic (above/below boundary, add-on -1) | code read |
| T118 | missing_overrides.yaml:8-18 | codes per wave | data and CB |
| T119 | docs/guards.md:8 | VMT_MILE mean 5.36 vs 9.72; total 7 % low | 5.363 / 9.720; total −7.05 % |
| T120 | docs/guards.md:9 | 2009 commute 23.34 vs 24.21 | T78 |
| T121 | docs/guards.md:10 | 2009 vehicle-age code 25+, others 33+ | T72 |
| T122 | docs/guards.md:11 | 2001 national-only columns; BESTMILE −12.9 % | T74, T114 |
| T123 | docs/guards.md:12 | TRPTRANS 01: 44 % of 2009 trips, 10.5 % of 2017 | 44.32 %, 10.49 % (w.) |
| T124 | docs/guards.md:13 | 1,385 "trips per person" | 1,384.98 |
| T125 | AGENTS.md:4 | four waves only | registry |
| T126 | AGENTS.md:13 | 38 concepts | `concepts.table()` 38 rows |
| T127 | AGENTS.md:20 | jackknife 2001/2009/2017, Taylor 2022 | T91-T94 |
| T128 | AGENTS.md:21 | WTTRDFIN = 365 × person weight 2001-2017 | T84 |
| T129 | AGENTS.md:22-23 | 2022 about +10 %: 2.275 not 2.078 | +9.5 % (see row 19) |
| T130 | AGENTS.md:24-25 | TRPTRANS 08 meanings; URBAN swapped | T54, T30 |
| T131 | AGENTS.md:27 | `harmonize.concepts()` | 12 concepts |
| T132 | AGENTS.md:29 | 2022 excludes group quarters; 2001 includes 0-4 | T80, T7 |
| T133 | AGENTS.md:31-32 | age 88 = 85+ / 92 = 89+; VEHAGE 35 = 25+ / 40 = 33+ | T4-T6, T72 |
| T134 | AGENTS.md:33-34 | 2001 national-only items | T114 |
| T135 | AGENTS.md:37 | universes education 16+/18+/14+, 2022 PRMACT non-workers | T17-T20, T26 |
| T136 | AGENTS.md:48 | 2009 3.79 trips per person per day | 3.7945 |
| T137 | AGENTS.md:61 | design: 2009 multiplier 1, 99 df; differences ~0.5 % | R JK2 degf 99; sqrt(1/0.99) = 1.00504 |
| T138 | AGENTS.md:65 | 14 tasks | tasks.yaml |
| T139 | docs/methods.md:10-12 | 2001 98/99, 2009 99/100 and JK2, 2017 6/7, 98 replicates in 14 strata | T91-T93 |
| T140 | docs/methods.md:11 | 2009 fhwa df 100 | UG 2009 example: half-width / SE = 1.983972 = t(0.975, 100) |
| T141 | docs/methods.md:12 | 84 = 98 − 14 (arithmetic and stratified-jackknife reasoning) | 2017 WR §2.2 (see row 27 for R) |
| T142 | docs/methods.md:14 | 2009 SE differ by 0.5 % | 57,259.38 / 56,972.37 = 1.00504 |
| T143 | docs/methods.md:16 | SE agree with R to about 2e-5 | observed 1.3e-7 and 1.9e-6 |
| T144 | docs/methods.md:22-23 | 2009 3.79 and 36.13 (published 3.79, 36.13) | daily_rate 3.7945, 36.130; STT 2009 Table 3 |
| T145 | docs/methods.md:23 | 2001 all ages 4.03 (published 4.03) | 4.0252; STT 2001 Table 3 "includes ... younger than 4 year olds" 4.03 |
| T146 | docs/methods.md:24 | 2017 3.37, 2022 2.275 | 3.3715, 2.2752 |
| T147 | docs/methods.md:29-33 | trip totals annual; 2022 +10 %, 2.275 vs 2.078 | T84, T86 |
| T148 | docs/methods.md:34-35 | 2001 LD total = annual national-sample trips; 2022 LD total counts persons | T88-T90 |
| T149 | rates.py:9-11 | daily rate = total / 365 / persons; 2022 2.275 vs 2.078 | T86 |
| T150 | rates.py:30-31 | trips without distance add 0 miles, as FHWA tables | with 0 fill 2009 36.130 = STT 36.13; 2001 39.264 = 39.26 |
| T151 | rates.py:51-53 | min_age restricts numerator and person denominator; household denominator unrestricted | code read; 2001 per hh min_age=5 9.6594 = STT 9.66 |
| T152 | rates.py daily_rate per household 2009 | (not stated, checked) | 9.496 / 90.422 vs STT 9.50 / 90.42 |
| T153 | docs/data_notes.md:148 | 2009 MCUSED 999: 45 rows, next 700 | data |
| T154 | docs/data_notes.md:148-149 | 2009 NWALKTRP 99: 138 rows, next 98 | data |
| T155 | docs/data_notes.md:149 | 2022 NUMONTRP 99: 16 rows, next 50 | data |
| T156 | docs/data_notes.md:151-152 | masked: negative codes, 2009 PTUSED 99, WHYTRP90 98/99, XX/XXXXX | T59, T76 |
| T157 | docs/waves.md:119-123 | 12 crosswalk concepts with those names | `harmonize.concepts()` |
| T158 | docs/waves.md:121 | income 8 bands nest exactly; education five levels | T15, `crosswalk("education")` 5 categories |
| T159 | docs/waves.md:124 | age_bands end at 85+ | consistent with every top-code (85+, 89+) |
| T160 | README.md:61 | 2009 persons 283,054 thousand | R golden 283,053,872 |
| T161 | README.md:65 | 2009 daily rate 3.79 | T144 |
| T162 | README.md:68 | `concepts.find("VEHAGE", 2009)`: top-code 35 = 25+, grade H | output checked |
| T163 | README.md:85-86 | rows for concepts and rates | modules exist |
| T164 | CHANGELOG.md:11 | 38 concepts × 4 waves | T126 |
| T165 | CHANGELOG.md:16-17 | 9 new crosswalk concepts | 12 − 3 |
| T166 | CHANGELOG.md:25 | 14 tasks | T138 |
| T167 | CHANGELOG.md:37-38 | VMT_MILE 5.36 vs 9.72, total 7 % low | T119 |
| T168 | CHANGELOG.md:40-42 | 2009 commute 23.34 vs 24.21 | T78 |
| T169 | CHANGELOG.md:43-46 | top-codes and national-only (content) | T4-T6, T72, T114 |
| T170 | CHANGELOG.md:53-55 | summary public_transit = PUBTRANS (2009, 2017, 2022) | cross-tabs: 0 disagreements in 1,167,321 / 923,572 / 31,074 trips |
| T171 | CHANGELOG.md:55 | 2001 WHYTRP1S 13: 39.7 % school/religious | 39.69 % (w.) WHYTO 20 |
| T172 | CHANGELOG.md:60-63 | 45,967 persons without 2009 DAYWGT = persons without trips | DAYWGT blank 45,967; persons not in trip file 45,967; CNTTDTR = 0 45,967 |
| T173 | CHANGELOG.md:64-65 | top-codes in all four waves; LD weight national × 365/28 | T4-T6, T89 |
| T174 | tasks.yaml:7 (T01) | 113,101.33 thousand; naive 150.147 | sum WTHHFIN = 113,101,330; 150,147 rows |
| T175 | tasks.yaml:10 (T02) | 24.2052; naive 23.34 | 24.20516; with -4/-5 23.3350 |
| T176 | tasks.yaml:13 (T03) | 9.7198; naive 5.36 | 9.71984; with -1 5.3627 |
| T177 | tasks.yaml:16 (T04) | 19,626.32 with R_AGE | 19,626.322 (see row 39) |
| T178 | tasks.yaml:19 (T05) | 3.7945; naive 1,385 | 3.79446; 1,384.98 |
| T179 | tasks.yaml:22 (T06) | 2.2752; naive 2.078 | 2.27522; 2.07761 |
| T180 | tasks.yaml:25 (T07) | 2,617.13 million; naive 0.045165 | sum WTPTPFIN 2,617,126,367; 45,165 rows |
| T181 | tasks.yaml:28 (T08) | 10.4683; naive 44.39 | walk 23 / trips with known mode 10.4683; / all trips 10.4488 (inside tol); code 01 44.32-44.40 |
| T182 | tasks.yaml:31 (T09) | 67.9188; naive 11.13 | URBAN 2: 67.9188; code 1: 11.1322 |
| T183 | tasks.yaml:34 (T10) | 3.82 | 3.8200 (known-age vehicles) (see row 37) |
| T184 | tasks.yaml:37 (T11) | 37,227.74 thousand | 37,227.743 (CNTTDTR = 0 and not in trip file agree) |
| T185 | tasks.yaml:40 (T12) | 10.5378 with valid-income denominator | 10.53782 (see row 38) |
| T186 | tasks.yaml:43 (T13) | 2.5447 | 2.54465 (= PUBTRANS) |
| T187 | tasks.yaml:46 (T14) | 53.3886 with f = 99/100 | 53.38856 (see rows 35-36) |

## 4. Count of statements checked per file

| file | checked | FALSE | IMPRECISE / MISSING / AMBIGUOUS | UNVERIFIED | TRUE |
|---|---|---|---|---|---|
| src/pynhts/concepts.yaml | 113 | 2 | 15 | 2 | 94 |
| src/pynhts/harmonize/crosswalks.yaml (0.6.0 part) | 22 | 4 | 3 | 2 | 13 |
| src/pynhts/_schema/column_flags.yaml + core/flags.py | 17 | 2 | 3 (missing) | 0 | 12 |
| src/pynhts/_schema/missing_overrides.yaml | 4 | 0 | 1 | 0 | 3 |
| src/pynhts/rates.py | 5 | 0 | 1 | 0 | 4 |
| docs/guards.md | 9 | 0 | 1 | 2 | 6 |
| AGENTS.md | 14 | 0 | 1 | 0 | 13 |
| llms.txt | 2 | 0 | 2 | 0 | 0 |
| docs/methods.md (3 new / changed sections) | 14 | 0 | 4 | 0 | 10 |
| docs/data_notes.md (new bullets) | 6 | 0 | 3 | 0 | 3 |
| docs/waves.md (changed paragraph) | 4 | 1 | 0 | 0 | 3 |
| README.md (changed lines) | 5 | 0 | 1 | 0 | 4 |
| CHANGELOG.md 0.5.0 / 0.6.0 | 15 | 0 | 3 | 0 | 12 |
| agent_eval/tasks.yaml (14 oracles, naive values, questions) | 33 | 1 | 6 | 0 | 26 |
| **total** | **263** | **10** | **44** | **6** | **203** |

(Counts are tallies of distinct statements: a section-3 row that confirms one statement for several waves counts
once, and a few rows that confirm two statements count twice. A section-1 row that cites several files counts in
each of them. The counts are therefore approximate to a few units; the verdicts are not.)
