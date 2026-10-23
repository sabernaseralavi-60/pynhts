"""Paper 02: manuscript builds, numbers are consistent with the result tables, figures exist (run: pytest -q in the paper folder)."""

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

HERE = Path(__file__).resolve().parents[1]
RES = HERE / "results"


def numbers(name):
    return json.loads((RES / "numbers" / f"{name}.json").read_text(encoding="utf-8"))


def test_headline_numbers_are_consistent_with_the_census_table():
    c = pd.read_csv(RES / "tables" / "census_coefficients.csv")
    s = numbers("summary")
    assert s["n_coef"] == len(c)
    assert s["n_sign_flip"] == int(c["sign_flip"].sum())
    assert s["n_sig_lost"] == int((c["sig_naive"] & ~c["sig_design"]).sum())
    assert s["median_se_ratio"] == pytest.approx(float(c["se_ratio"].median()))


def test_hypotheses_of_the_plan_are_decided_by_the_numbers_not_by_the_text():
    s, ml = numbers("summary"), numbers("ml")
    assert s["median_se_ratio"] > 1.5  # H2
    assert s["share_sig_lost"] > 0.10  # H3
    assert ml["afv"]["leaky"]["rf"] - ml["afv"]["grouped"]["rf"] > 0.15  # H4


def test_ladder_register_has_all_studies_and_sensible_counts():
    st = pd.read_csv(RES / "tables" / "studies.csv")
    assert len(st) == 22 and st["id"].is_unique
    assert (st["L2_attempted"] == "yes").sum() == numbers("ladder")["n_l2_attempted"]


@pytest.mark.parametrize("fig", ["fig_flow_en", "fig_flow_fa", "fig_ladder", "fig_weights", "fig_se", "fig_case", "fig_leak", "fig_r2", "fig_holdout"])
def test_figures_exist(fig):
    assert (RES / "figures" / f"{fig}.png").stat().st_size > 10_000


@pytest.mark.parametrize("lang", ["en", "fa"])
def test_manuscript_renders_without_unresolved_tokens(lang):
    r = subprocess.run([sys.executable, "build.py", "--lang", lang, "--no-render"], cwd=HERE / "manuscript", capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-500:] + r.stderr[-1500:]
    text = (HERE / "manuscript" / "build" / lang / "manuscript.qmd").read_text(encoding="utf-8")
    assert "{{" not in text and "}}" not in text
