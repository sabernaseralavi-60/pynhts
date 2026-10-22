# Idea register (research factory rule: one idea = one paper; every merge or drop is dated and decided by the user)

| ID | Paper | Title (working) | Status (2026-10-22) | Notes |
|---|---|---|---|---|
| I-01 | 1 | pynhts: survey-weight-aware Python access to the US National Household Travel Survey (SoftwareX, Original Software Publication) | manuscript built (`paper/softwarex/`), **not submitted**; open author items in `SUBMISSION_NOTES.md` | cites the authors' 2025 Urban Science paper (ref. 14) and audits it as study P24 (not independent) |
| I-02 | 2 | How much of the state-to-state variation of trip-generation coefficients is sampling noise? A design-aware re-analysis of the 2017 NHTS | **proposed, not started**; waiting for the user's decision | evidence so far: `tools/paper_audit/probe_p24_heterogeneity.py` (small model, unweighted: household size, drivers, vehicles, income homogeneous within noise; age, transit, rideshare not); details and plan in `docs/research/NEW_PAPER_OPTIONS.md` |
| I-03 | 3 | What NHTS papers do not say: a reproducibility audit and typology of unstated rules (22 studies) | **proposed, not started**; waiting for the user's decision | needs model re-estimation under alternative defensible rules to show whether conclusions move; keep neutral framing (general framework, studies as cases); overlap with the SoftwareX Impact section must be kept small |
| I-04 | - | Pure reproduction of the 2025 paper with pynhts | **not an independent paper**; folded into I-02 as its reproducibility package | decided in `docs/research/NEW_PAPER_OPTIONS.md` (option C); the user may overrule |

Overrides and merges: none so far. The decision on I-02 and I-03 (order, merge, drop) is the user's; record it here with its date.
