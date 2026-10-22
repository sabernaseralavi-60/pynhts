# Where we stopped (2026-10-22, pynhts 0.8.0 on PyPI; tag v0.8.0 on 9259bfa, CI 4/4 green, fresh-venv install verified)

Resume with the phrase «کارخانه بسته نرم‌افزاری» (or "ادامه pynhts"). Read `~/.claude/research-kit/PACKAGES.md` (section "Updates 2026-10-22", last entry),
the last ledger entries `PKG-20261022-19..22`, then `git status` here.

## State
* Released: 0.8.0 = race/Hispanic crosswalks + `race_ethnicity`, medical-condition crosswalks (`medical_condition`, `condition_duration`, `condition_effect`;
  44 concepts, 19 crosswalks), `pynhts.study`, cap flags (PTUSED, NWALKTRP 2009 and 2017) and the fixes of the independent review (`docs/review_0.8.0.md`:
  3 P0 in `study`, 3 P1, 10 P2, all fixed). 0.7.0 (two numeric defects) is not yanked; yank only on the user's request.
* Uncommitted by design: `tools/pilot_bench/run_sprint.py` (the user's own work; never commit it). Third-party PDFs in `some papers/` are ignored.
* Tests: 333 unit (py3.10 fresh env, 1 torch skip) and 601+ with the real files in the project venv (about 8 minutes).

## Open, in the order suggested (none started)
1. Re-run the paper audit for P01, P02, P10 with the race crosswalk (P01 uses `HHR_RACE`, `HHINCTTL`), and with the medical-condition crosswalk for the Lidbe 2021 cells
   (the audit scripts are in `tools/paper_audit/`, `run_all.py` takes about 40 s). Note: `study` rules changed in 0.8.0 (a refused age is no longer "under 18"):
   re-run all 21 scripts that use `Study` and compare the sample flows with `docs/paper_data_audit/` before trusting old numbers.
2. A second fact-check of the documentation of 0.7.1 and 0.8.0 statement by statement (the reviewer did not check the audit figures in `docs/study.md`:
   Jiao 76,476 of 191,150, the P22 "5 % for drivers", "9 of 21 SUFFICIENT").
3. Regression-coefficient variance (refit per replicate) for the logistic/ZINB papers; then Yang 2011 Table 2 with standard errors.
4. Resolve open audit items: Lidbe 2001 medical-condition cells, Zhou 2014 sample rule, Quinn 2016 denominator.
5. Proposed: an explicit "base" for conditional daily means in `aggregate` (audit P22); automatic cap detector in `quality.report` (PKG-20261022-15);
   forest/marginal-effect plots in `viz`; purpose-sequence proxy for mobility motifs; state map of a share (needs state shapes).
6. Systematic literature review (11 papers read in full, 17 abstract-only leads) before any novelty claim; then a JOSS/SoftwareX paper using the audit as
   validation evidence (check each journal's scope and policy; needs the user for the Zenodo DOI, ORCID, submission).
7. Environment: `files.pythonhosted.org` times out for scipy/statsmodels/scikit-learn on this network; models that need them run on Colab (cloud-factory).
   The project venv's Tk install is broken: use `matplotlib.use("Agg")` in tests that draw.

## Rules to remember
* Run ruff, mypy and pytest in a fresh Python 3.10 uv env (`$TEMP/ci310e`) AND mypy in the project `.venv` before every push; an adversarial review with the real data
  BEFORE tagging (it found 3 P0 again in 0.8.0). Re-measure every number a reviewer quotes before it enters the docs.
* Write file bodies and patch scripts with the Write tool (bash heredocs with apostrophes fail). Version bump touches pyproject, `__init__`, CITATION.cff, README, CHANGELOG.
* Real-data tests need `PYNHTS_CACHE_DIR=$PWD/local_data/cache` outside pytest; never grep recursively from the repo root (local_data is huge).
