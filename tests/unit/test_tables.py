"""Table formatting: rounding, group labels, LaTeX escaping, Markdown."""

from __future__ import annotations

import pandas as pd

from pynhts import tables


def res(est, moe, n, **groups):
    return pd.DataFrame({
        **{k: [v] for k, v in groups.items()},
        "estimate": [est], "se": [moe / 2], "moe": [moe], "ci_low": [est - moe],
        "ci_high": [est + moe], "cv": [0.1], "n": [n],
    })


def test_pm_style_scaling_and_rounding():
    t = tables.build([tables.Row("Share (%)", res(0.34567, 0.0123, 1234), scale=100)])
    assert t.iloc[0].tolist() == ["Share (%)", "34.6 ± 1.2", "1,234"]


def test_other_styles():
    r = [tables.Row("x", res(1500.0, 20.0, 5), digits=0)]
    assert tables.build(r, style="se").iloc[0, 1] == "1,500 (10)"
    assert tables.build(r, style="ci").iloc[0, 1] == "1,500 [1,480, 1,520]"
    assert tables.build(r, style="estimate", show_n=False).shape == (1, 2)


def test_grouped_rows_use_labels_and_negative_zero_is_clean():
    g = pd.concat([res(0.4, 0.05, 10, R_SEX="01"), res(-0.00001, 0.0, 3, R_SEX="02")],
                  ignore_index=True)
    t = tables.build([tables.Row("Sex", g, scale=100, group_labels={"01": "Male", "02": "Female"})])
    assert t["Characteristic"].tolist() == ["Sex: Male", "Sex: Female"]
    assert t.iloc[1, 1] == "0.0 ± 0.0"


def test_nan_prints_en_dash():
    t = tables.build([tables.Row("x", res(float("nan"), float("nan"), 0))])
    assert t.iloc[0, 1] == "– ± –"


def test_latex_booktabs_escaping_and_structure():
    t = tables.build([tables.Row("Work & 50% of_tours", res(1.0, 0.1, 7))])
    tex = tables.to_latex(t, caption="A & B", label="tab:x")
    for part in (r"\toprule", r"\midrule", r"\bottomrule", r"\caption{A \& B}",
                 r"\label{tab:x}", r"Work \& 50\% of\_tours", r"1.0 $\pm$ 0.1", "$n$"):
        assert part in tex
    assert tex.count(r"\begin{tabular}{lrr}") == 1 and r"\end{table}" in tex
    assert "replicate weights" not in tex  # a bare result does not know its design


def test_note_names_the_design_of_the_wave_the_result_came_from():
    for design in ("jackknife-2 (JK2) with 100 replicate weights",
                   "Taylor-series linearisation with variance strata"):
        r = res(1.0, 0.1, 7)
        r.attrs["pynhts"] = {"wave": 2009, "design": design}
        note = tables.note(tables.build([tables.Row("a", r)]))
        assert design in note and "98" not in note


def test_markdown():
    t = tables.build([tables.Row("a|b", res(2.0, 0.5, 4))])
    md = tables.to_markdown(t)
    assert md.splitlines()[1] == "| :-- | --: | --: |"
    assert r"a\|b" in md and "2.0 ± 0.5" in md and "| n |" in md
