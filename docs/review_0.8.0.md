# Independent adversarial review of pynhts 0.8.0 (2026-10-22)

A read-only reviewer (Opus) went through everything since v0.7.1 (`git diff v0.7.1..HEAD`) with the real files. 16 findings, all fixed in 0.8.0.
Numbers marked *re-measured* differ from the reviewer's because they were re-computed here before they entered the documentation.

| # | Sev | Finding | Fix |
|---|---|---|---|
| 1 | P0 | `study` read raw codes: hidden missing codes (2009 `PTUSED` 99, 608 persons) counted as values; the mean was 1.8135 instead of 1.4673 | variables read a masked view; real-data test against the default loader |
| 2 | P0 | `Keep`/`Drop` rules saw -1/-7/-8/-9 as numbers (`R_AGE < 18` removed 496 refused ages; `TIMETOWK <= 60` kept 259,474 rows of which 157,774 skips/non-answers, *re-measured*; 101,700 real) | rules read the masked view; `raw=True` for the codes; missing never satisfies a rule |
| 3 | P0 | `Var(kind="binary")` of a raw column returned codes (share 119.66 %) | raises unless the column holds only 0/1 |
| 4 | P1 | 2009 White marked `exact` against 2017/2022, but 2009 offered a Hispanic race answer (Hispanic households filed White: 47.8 % in 2009, 69.0 % in 2017, 71.0 % in 2022, *re-measured*; overall weighted White 76.7 % and 75.5 %) | 2009 White `approximate`; docs and tests |
| 5 | P1 | `figures()`/`save()` crashed for a count outcome (`Figure.transAxes`) | use the axes of the returned figure; test |
| 6 | P1 | the study never showed top-code/cap warnings (rule 6) | `PynhtsWarning` and an assumption line |
| 7 | P2 | 2001 `MEDCOND` yes share 8.7 % is 8.8 % | docs |
| 8-10 | P2 | `compare` category match by prefix; missing group graded against the first group; printed precision lost | exact code match, error, string precision |
| 11-13 | P2 | `Keep` on a study variable failed; name-clash check on loaded columns only; trip studies lost the trip key | fixed |
| 14 | P2 | two tests that could not fail (race fallback; assumptions) | NA-safe assertions; the fallback fires for 15 households in 2009 |
| 15 | P2 | `NWALKTRP` flagged as capped in 2009 but not 2017 (364 at 99) | flagged |
| 16 | P2 | README said 16 crosswalks | 19 |

Checked and correct (reviewer): every code and hint of the new crosswalks against the codebooks; `race_ethnicity` (missing handling, refusals, 2001 person frames);
the race, Hispanic and medical-condition numbers quoted in the docs (except #4 and #7); PTUSED/NWALKTRP caps 2009/2017/2022; the Zhang & Zhang YAML study
(264,234 -> 228,002 -> 218,831, 0.09 % below the published sample); weighted statistics; the sample-flow arithmetic; 44 concepts and 93 features.
Not checked: the audit figures in `docs/study.md` (Jiao 76,476 of 191,150; the P22 5 %), the "9 of 21 SUFFICIENT" count, the audit CSVs.
