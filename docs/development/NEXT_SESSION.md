# Where we stopped (2026-10-22, pynhts 0.7.1 on PyPI, commit d86d777, CI green)

Resume with the phrase «کارخانه بسته نرم‌افزاری» (or "ادامه pynhts"). Read `~/.claude/research-kit/PACKAGES.md` (section "Updates 2026-10-22"),
the last ledger entries `PKG-20261022-02..10`, then `git status` here.

## State
* Released: 0.7.0 (has two numeric defects, not yanked) and 0.7.1 (fixes; `docs/review_0.7.0.md`). New layers: `aggregate`, `features` (93),
  `valid`/`answer_status`, `eda`, `quality`, `transform`, `trends`, `tables` exports, `viz.plots`; docs in `docs/analysis.md`, `docs/data/`,
  `docs/development/REPOSITORY_AUDIT.md`, `docs/research/`; paper audit in `docs/paper_data_audit/` (scripts `tools/paper_audit/`, run_all ~40 s).
* Uncommitted by design: `tools/pilot_bench/run_sprint.py` (the user's own work; never commit it). Third-party PDFs in `some papers/` are ignored.

## Suggested next steps (none started)
1. A second fact-check of the corrected 0.7.1 documentation (statement by statement), as done for 0.6.0; the adversarial review covered the new code once.
2. Race and Hispanic origin: DONE after 0.7.1 (unreleased, see CHANGELOG; `harmonize.race_ethnicity`). Still to do: a crosswalk for medical condition; then re-run
   the paper audit for P01, P02, P10 with the new race code (P01 uses `HHR_RACE` and `HHINCTTL`). Income needs no new crosswalk: `HHFAMINC` is crosswalked since 0.6.0,
   and `HHINCTTL` is a 2001-only column with the same 18 bands (P01's cut points on it give shares 15.2 / 25.1 / 36.4 / 23.3, on `HHFAMINC` 16.9 / 25.9 / 36.1 / 21.1);
   map it by the 2001 rows of `crosswalk("income")` only if a recipe needs it.
3. Regression-coefficient variance (refit per replicate) for the logistic/ZINB papers; then reproduce Yang 2011 Table 2 with standard errors.
4. Resolve open audit items: Lidbe 2001 medical-condition cells, Zhou 2014 sample rule, Quinn 2016 denominator; ask the authors if needed.
5. Systematic literature review (the landscape is a first pass: 11 papers read in full, 17 abstract-only leads) before any novelty claim.
6. Paper: JOSS or SoftwareX software paper using the audit as validation evidence (check each journal's own scope and policy); needs the user for Zenodo DOI, ORCID, JOSS submission.
7. Environment: `files.pythonhosted.org` times out for scipy/statsmodels/scikit-learn on this network (no mirror switched); models that need them would run on Colab (cloud-factory) or after the network is fixed.

## Rules to remember
* Run ruff, mypy and pytest in a fresh Python 3.10 uv env (`$TEMP/ci310d`) AND mypy in the project `.venv` before every push; adversarial review with real data before tagging.
* Write file bodies with the Write tool (bash heredocs with apostrophes fail). Version bump touches pyproject, `__init__`, CITATION.cff, README, CHANGELOG.
