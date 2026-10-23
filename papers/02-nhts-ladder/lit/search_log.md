# Search log (2026-10-23; tool = FastTrack Literature Open MCP unless noted; Crossref/OpenAlex REST for verification)

| # | query (abridged) | tool | quality |
|---|---|---|---|
| 1 | what are we weighting for regression survey weights | search_papers | good: Gelman 2007, Bollen 2016, Miratrix 2018 (not kept) |
| 2 | complex survey variance estimation replicate weights jackknife | search_papers | mostly manuals; kept Rust & Rao via verify |
| 3 | data leakage ML-based science reproducibility crisis | search_papers | very good: Kapoor 2023, REFORMS, Rosenblatt 2024 |
| 4 | SMOTE oversampling before cross-validation bias | search_papers | one strong hit: Demircioglu 2024 |
| 5 | multiverse / many analysts same data | search_papers | Schweinsberg 2021; Steegen, Silberzahn, Simonsohn by verify |
| 6 | reproducibility replication transport survey data | search_papers | weak (off-topic): confirms the gap |
| 7 | ML vs discrete choice travel behaviour | search_papers | Wang 2024 benchmark, Hagenauer 2017, Martin-Baos 2023 |
| 8 | NHTS sampling/replicate weights bias | search_papers | Conway 2018, Wang 2022 (NHTS selection); Birrell 2019 via duplication test |
| 9 | duplication test (full research question) | run_duplication_test | no duplicate; closest = Birrell 2019, Gard 2023 |
| 10 | 27 classic references by author/title/year | verify_reference and `lit/verify_refs.py --query` | all resolved in Crossref |
| 11 | LeapSpace review (ScienceDirect, 2026-10-23): how NHTS studies handle design, weights, variance | external AI report, `manuscript/final/improve.md` | 108-reference draft; 49 DOIs new to us, all resolved in Crossref, none retracted (`lit/refs_batch4.txt`); 17 not used (see `SKIP` in `lit/gen_bib.py`: subject did not support the sentence, e.g. BEV economics cited for weights); 4 without DOI not verifiable (Pucher & Renne 2003, Sharp & Murakami 2005, Mei 2005, Erlbaum 2005) left out; one metadata error caught (Korn & Graubard book is 1999, not 2011) |
Counter-view pass: query 5 (analytic dispersion), 3-4 (leakage), and Bollen 2016 / Miratrix 2018 on when weights are NOT needed.
Retraction Guard: `lit/verify_refs.py` (Crossref `updated-by` + OpenAlex `is_retracted`), 55 entries (2026-10-23 LeapSpace batch: 104 entries resolved, none retracted; 90 in refs.bib, 81 cited in the printed list); two corrections noted
(Silberzahn 2018, Simonsohn 2020: publisher corrections, original cited).
Excluded near-misses: Miratrix 2018 (survey *experiments*), Skinner & Mason 2012 (weight modification, not needed here).
