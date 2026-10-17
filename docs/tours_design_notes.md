# Design notes for `pynhts.tours` (paper-driven development)

*Status: planning note written 2026-10-17. Nothing here is implemented in the library yet. The only
code is the throw-away probe `tools/probe_tours_replication.py`.*

## 1. Candidate papers

Citation counts are Crossref's `is-referenced-by-count` on 2026-10-17 (they undercount against
Google Scholar). "Read" means the text was actually read; anything else is marked unverified.

| | Paper | NHTS data | Open text read? | Published numbers to target | Replication feasibility |
|---|---|---|---|---|---|
| **A** | McNally & Rafiq (2021), *Analysis of Activity-Travel Patterns and Tour Formation of Transit Users*, METRANS final report PSR-19-33 (open). Journal versions: Rafiq & McNally 2020, *Transp. Res. A* 142:237-259, doi 10.1016/j.tra.2020.10.018 (2 citations); 2021, *Transp. Res. A* 152:1-18, doi 10.1016/j.tra.2021.07.011 (45); 2022, *Transp. Res. A*, doi 10.1016/j.tra.2022.04.003 (9) | **2017** | Final report: yes. Journal papers: no (paywalled) | Sample counts, Table 2.1 (percentages), tour-pattern shares, Tables 2.2-2.5 | **High, shown by the probe below** |
| **B** | McGuckin & Murakami (1999), *Transp. Res. Rec.* 1693, doi 10.3141/1693-12 (186 citations); McGuckin, Zmud & Nakamoto (2005), *Transp. Res. Rec.* 1917, doi 10.1177/0361198105191700122 (125); FHWA "What is trip chaining?" note (open) | 1995 NPTS and 2001 NHTS | FHWA note: yes. Journal papers: no | FHWA note prints Tables 1-2 (commute trips and miles, 1995 and 2001) | **Low for Phase 1** (needs two other waves), good for Phase 2 |
| **C** | Ahmed & Hyland (2022), *Exploring the role of ride-hailing in trip chains*, *Transportation*, doi 10.1007/s11116-022-10269-w (29) | 2017 (50 largest CBSAs, per a search summary) | No (publisher blocked access) | Unknown | **Unverified**: cannot be judged without the text |

Other papers found but not proposed: Zhu & Guo (2022, *Transp. Res. D*, doi 10.1016/j.trd.2022.103524, 34
citations; uses 2009 and 2017, full text not accessible); Kwon (2023, *GRI Review* 25(2), 2017 NHTS,
multinomial logit; only the abstract was read); ORNL (2025) trip chaining in New York State, 2009 and
2017, OSTI doi 10.2172/3002353 (not read); Primerano et al. (2007/2008, *Transportation*,
doi 10.1007/s11116-007-9134-8, 193 citations; Sydney data, a methods reference only).

## 2. What the probe shows (candidate A)

`tools/probe_tours_replication.py` rebuilds the report's sample from the public 2017 files:

| Quantity | Published (report) | Reproduced |
|---|---:|---:|
| Transit users (person-days that start and end at home with >= 1 transit trip) | 4,994 | **4,994** |
| Their trips | 20,222 | **20,222** |
| Their transit trips | 10,011 | **10,011** |
| Home-based work tours with transit (adults) | 2,454 | 2,456 |
| Persons in those tours | 2,448 | 2,451 |
| Simple work tour, pattern (0,0,0) | 49 % | 49.2 % |
| Simple / complex / work-based tours | 49 / 32 / 19 % | 49.2 / 30.5 / 20.4 % |
| Tours with two or more work stops and no other stop | 70 (2.8 %) | 67 |

Also checked outside the script and reproduced exactly: household size, household vehicles, low
income, age below 18, ages 38-58 and over 58, male, employed, rail users (42.7 %) and bus users (62.4 %)
among the 4,994 users. Not reproduced yet: the middle/high income split, the 18-38 age boundary,
white share (59.8 % against 59.3 %) and vehicles per licensed driver; these look like category
definitions that the report does not spell out.

## 3. Requirements for `pynhts.tours` learned from the probe

1. **Home anchor.** The sample matches exactly only if a destination with purpose 02 (work from
   home) counts as home, together with 01. The tour-level work-tour count is closer with 01 alone
   (2,456) than with 01 and 02 (2,471). The report may use different rules at the two steps, or the
   work-activity rule may differ; unresolved. Make the home set a parameter.
2. **Two levels of completeness.** Day level (first trip leaves home, last trip arrives home) and tour
   level (each trip arriving home closes a tour). Both are needed.
3. **Activity types.** H, W, N derived from `WHYTO`: work is code 03 only (adding 04, work-related
   meeting, gives 2,551 tours, far from 2,454).
4. **Work-tour patterns.** The 3-tuple (stops before work, stops after work, stops between work
   activities) and the report's classes simple / complex / work-based; tours with several work stops
   and no other stop form a separate "other" class.
5. **Mode sets.** Transit = codes 11, 14, 15, 16; rail = 15 and 16; bus = 11 and 14. Adding paratransit
   (12) or charter/shuttle (13) breaks the sample counts.
6. **Chaining threshold.** The FHWA 2001 chained-trip file counts a stop of 30 minutes or less inside a
   tour. Keep the dwell threshold as an optional parameter (`DWELTIME` is in the 2017 file); candidate B
   needs it.
7. **Weights.** The report uses unweighted counts. Tours of one person-day share the person-day weight
   `WTTRDFIN`, so the existing `Survey` unit aggregation gives design-correct standard errors for
   tour-level estimates without new variance code. This is where pynhts can add something the original
   did not offer.
8. **Output.** A tours table (keys, number of trips, activity pattern, class, modes, start and end
   times) and a trips table carrying the tour identifier.

## 4. Open questions to resolve before coding

* Which exact rules separate 2,454 from 2,456 tours and 70 from 67 "other" tours?
* How are trips with invalid codes (-9, -8, -7) treated? In the probe they are kept.
* The journal versions may differ from the final report; their tables were not read.

## 5. What a replication paper can honestly claim

The sample construction of a published transit-tour study can be rebuilt from the public file to
within about 0.1 % on tours and exactly on the user sample, and the definitions that make this work
can be written down and released as open code. A natural contribution is a **weighted, design-based
re-estimate with margins of error** and a **sensitivity analysis of the operational definitions**
(home set, work code, dwell threshold). That is a methods-and-data note, not a new behavioural finding;
target journals must be checked against their own scope and policies before any submission.
