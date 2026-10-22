# Recovered conventions and open ambiguities (paper data audit, 2026-10-22)

Format as in the paper-reproduce assumption register: ID, paper, statement, evidence, residual risk.
"Recovered" = chosen because it reproduces a printed number with the public pynhts data; it is a reading of the
paper, not a claim about what the authors did. Scripts: `tools/paper_audit/pNN_*.py`.

| ID | Paper | Convention | Evidence | Residual risk |
|---|---|---|---|---|
| A-01 | P01 Yang 2011 | "missing age 12,142" = ages 0-4 (9,743) plus not-ascertained (2,399); the paper's youngest group is 5-10 | 9,743 + 2,399 = 12,142 exactly | none |
| A-02 | P01 | race/ethnicity = the single household-respondent code `HHR_RACE` (01 White, 02 Black, 03 Asian, 06 Hispanic/Mexican only); all other codes excluded | analysis sample 130,222 EXACT; shares W 77.3 / B 12.9 / A 2.5 / H 7.3 EXACT. The Hispanic-origin flag `HHR_HISP` gives 12.5 % Hispanic and n = 133,533 | low |
| A-03 | P01 | household income = `HHINCTTL` with cuts <20k (01-04), 20-40k (05-08), 40-80k (09-16), >80k (17-18) | shares 15.2 / 25.1 / 36.4 / 23.3 vs printed 15.2 / 25.1 / 36.4 / 23.4; `HHFAMINC` gives 16.9 / 25.9 / 36.1 / 21.1 | low |
| A-04 | P01 | "less than one mile" = `TRPMILES` <= 1 | elderly share 24.4 vs printed 24 (strict < 1 gives 34.6) | adolescents 45.5 vs 43 not explained (children+adolescents pooled gives about 42) |
| A-05 | P01 | Table 1 prints n per age group that disagrees with Table 2 of the same paper; Table 2's n (11,556 / 13,651 / 84,712 / 20,303) equals ours exactly | exact match | the printed Table 1 n row looks like a typo in the paper |
| A-06 | P02 Zhou 2014 | final sample taken as workers aged 18+ with at least one trip and complete internet, education, income and urban items; shopping trip = `WHYTRP1S` 40 | n = 106,211 vs 85,663; 13 of 20 Table 2 means within 5 % | the rule that removes a further 20,548 records is unknown; state GDP and density are external |
| A-07 | P03 Quinn 2016 | walker/biker = at least one walk (23) or bicycle (22) trip of >= 10 min (`TRVL_MIN`), trips for exercise (`WHYTO` 51) excluded | prevalence 11.93 / 1.14 % (printed 11.74 / 1.11) with denominator = adults with a trip; 10.67 / 1.02 with all adults | the paper's own counts do not add up (324,184 persons printed; the public file has 308,901) |
| A-08 | P05 Deka 2019 | printed Table 1 and Table 2 means are UNWEIGHTED although the text says scaled weights | mean rides 0.297 unweighted vs printed 0.299; weighted 0.433 | the sample is persons 16+ with a rideshare answer (n = 235,716); N of the ZINB models not printed |
| A-09 | P05 | block-group ACS variables and transit stop counts need the home block-group ID | not in the public files | restricted NHTS file required |
| A-10 | P06 Jia 2019 | each respondent = main driver (vehicle `PERSONID`); newest vehicle; "within 3 years" = `VEHAGE` <= 2; fuel 01/02/03 only; FUELTYPE 03 = AFV | n = 31,174 vs 31,322; AFV share 4.06 % vs 4.2 %; Table 1 means mostly EXACT. `VEHAGE` <= 3 gives 47,489 persons | popden sd (1.30 printed vs 1.89 here) and race sd unresolved |
| A-11 | P07 Krizek 2019 | LV = bicycle (02) + golf cart/Segway (07); the 503 scooter/skateboard trips are a write-in category not separable in the public file | 8,034 and 826 EXACT | "large metropolitan area" is not defined; MSAs >= 1 million (MSASIZE 04/05) gives private-vehicle 81.9 % vs 76.8 %; MSACAT 01 gives 78.4 % |
| A-12 | P09 Fu 2020 | the population (which NHTS year, which trips are "EV") is not stated | 6 readings in 2017 plus 2009 and 2001 all-trip tests: mean absolute error of the nine category shares 3.8-4.8 points; H-H share is 10.8 % in the paper vs about 1-2 % in every reading | cannot be tested without the authors' definition |
| A-13 | P10 Lidbe 2021 | long-distance = daily trips of >= 50 miles; medical condition = `MEDCOND` yes; trip shares use trip weights `WTTRDFIN` | 2017 Table 3 eight cells EXACT/CLOSE; Table 1 both waves EXACT | 2001: medical-condition trips are 4.40 % in the data vs 5.49 % printed |
| A-14 | P11 Alberini 2021 | passenger vehicles = `VEHTYPE` 1-3 in the 49 states + DC (not AK/HI); powertrain from `HFUEL` and `FUELTYPE`; weights `WTHHFIN` | 195,251 vehicles and Tables 1-4 EXACT; 1 %/99 % trimming of ANNMILES differs slightly (142,888 vs 140,961) | MILESDRIVEN and TRIPANNMILES are the paper's own regressions, not rebuilt |
| A-15 | P12 Xue 2021 | persons 16+ with complete education, driver, income, web use, urban, sex and delivery items | n = 227,087 vs 173,500; closest alternative: persons with at least one shopping trip, n = 96,432 (age 56.2, female 55.3 %, driver 94.6 % vs printed 56.8, 56.4, 94.6) | the printed shopping-trip means (3.3 trips, 15.5 miles, 36.6 min) match no daily definition |

Not applicable: P04 (Stats SA, South African NHTS 2013).
Duplicate: P08 is byte-identical to P06 (SHA-256 96d19c6c...e336debe2), as are the two copies in `some papers/`.
