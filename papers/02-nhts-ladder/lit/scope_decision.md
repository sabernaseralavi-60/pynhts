# Scope decision (2026-10-23)

Paper type: methods / reproducibility paper with a case-study set of 22 NHTS studies (framework first, cases second; no critique of one paper).
Field: transport survey analysis, applied statistics (complex surveys), applied machine learning.
Maturity: complex-survey inference and ML-leakage literatures are mature (decades of method papers); the transport literature that
*applies* them to NHTS is thin (no study found that re-estimates published NHTS models under the replicate-weight design).
Depth chosen: **comparative / methods, ~55 verified references kept** (above the 20-25 floor of the journal standard), in four blocks:
1. survey weights and design-based variance in regression (Lumley, Solon, Winship, Gelman, Bollen, Rust & Rao, Wolter, Birrell, Gard);
2. reproducibility and analytic flexibility (Peng, Stodden, Hardwicke, Steegen, Silberzahn, Schweinsberg, Simonsohn);
3. leakage, resampling and validation design in ML (Kapoor, REFORMS, Demircioglu, Rosenblatt, Chawla, Blagus, Roberts, Ploton, Vabalas);
4. the model families and their NHTS applications (NB/ZINB, PSM, SEM; the 22 case studies; ML-vs-DCM travel-demand benchmarks; NHTS data quality).
Case studies are cited neutrally as data points of the framework; each DOI resolved through Crossref and none is retracted.
Saturation: the last two query rounds (transport reproducibility; NHTS weights) returned known or off-topic papers.
Novelty claim stays "to verify": `run_duplication_test` (OpenAlex + semantic, 12 neighbours, 2026-10-23) found no paper that re-estimates
published NHTS regressions or classifiers under the survey design; closest neighbours are health/neuroscience demonstrations that weights and
replicate variance change significance (Birrell 2019; Gard 2023) and NHTS-based studies of selection bias (Wang 2022). No systematic review was run.
