# Contributing

Thanks for helping. Short rules:

1. **Set up:** `uv venv && uv pip install -e ".[dev]"`.
2. **Checks before a pull request:** `ruff check src tests`, `mypy`, `pytest`. The default test
   run needs no data. Tests that need the real files carry `@pytest.mark.data`
   (`pytest -m data`, with the files registered via `pynhts register <folder>`); the live
   download test is `@pytest.mark.network` and is manual.
3. **Never commit microdata** or third-party PDFs (`.gitignore` already excludes them).
4. **Do not tune the library to match a published figure.** If a figure does not reproduce,
   record it with a note in `src/pynhts/recipes/data/*.yaml` and set its `expected` status
   honestly. Explanations of the documented gaps are very welcome as issues.
5. **New waves:** add a registry file (`_registry/<wave>.yaml`), generate the schema with
   `tools/build_schema.py` from the official codebook, and add golden tests before any
   estimator is touched.
6. Regenerate `docs/validation.md` with `python tools/make_validation_report.py` after any change
   that can move an estimate.
