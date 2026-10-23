# Paper 02 - A reproducibility ladder with design-aware re-estimation for survey-based travel research (22 NHTS studies)

Status 2026-10-23: draft complete (English and Persian), not submitted. Idea I-03 of `docs/idea_register.md` widened; analysis plan: `analysis_plan.md` (dated).

## Run
```
python run_all.py                # studies (about 15 min) -> summaries -> numbers -> figures -> tests
python run_all.py --ml           # plus the classifier / boosting / tuned runs (about 2.5 hours in total)
python run_all.py --manuscript   # plus manuscript/final/*.docx and *.pdf (Quarto)
```
* `src/engine.py`, `src/countmodels.py`: the three regimes (naive, weighted, design) for logit/OLS/Poisson and NB2/ZINB; `src/mlkit.py`: pipelines for the ML studies.
* `src/studies/pNN_*.py`: one script per re-estimated study (published targets inside each script); `results/tables/*.csv` are the outputs.
* The package versions of the machinery are `pynhts.models` and `pynhts.validate` (see `docs/models.md` of the repository).
* `lit/`: search log, scope decision, `verify_refs.py` (Crossref + OpenAlex retraction guard) and `refs.bib`.
* Numbers in the manuscript are injected from `results/numbers/*.json`; `manuscript/build.py --lang en|fa`.
