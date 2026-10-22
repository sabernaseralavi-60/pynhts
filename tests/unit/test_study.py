"""The study layer (sample flow, descriptive table, grading) on the tiny synthetic wave; hand-worked numbers.

Persons (file order): R_AGE 40, 38, 10, 70, 68, 30; EDUC 04, 03, -1, -7, 05, 05; WORKER 01, 02, -1, 02, -9, 01;
weights WTPERFIN 1..6; households H1 (persons 1-3, size 3), H2 (persons 4-5, size 2), H3 (person 6, size 1).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pynhts import study as S
from pynhts.aggregate import Where
from pynhts.core.data import NHTSData


def _write(directory: Path, name: str, columns: dict[str, list], strings: set[str]) -> None:
    arrays = {k: pa.array(v, type=pa.string() if k in strings else pa.float64()) for k, v in columns.items()}
    pq.write_table(pa.table(arrays), directory / f"{name}.parquet")


@pytest.fixture
def d(tmp_path: Path) -> NHTSData:
    _write(tmp_path, "household", {"HOUSEID": ["H1", "H2", "H3"], "HHSIZE": [3, 2, 1], "HHVEHCNT": [2, 0, 1],
                                   "WTHHFIN": [100.0, 200.0, 300.0]}, {"HOUSEID"})
    _write(tmp_path, "person", {
        "HOUSEID": ["H1", "H1", "H1", "H2", "H2", "H3"], "PERSONID": ["01", "02", "03", "01", "02", "01"],
        "R_AGE": [40, 38, 10, 70, 68, 30], "EDUC": ["04", "03", "-1", "-7", "05", "05"],
        "WORKER": ["01", "02", "-1", "02", "-9", "01"], "HHSIZE": [3, 3, 3, 2, 2, 1],
        "WTPERFIN": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
    }, {"HOUSEID", "PERSONID", "EDUC", "WORKER"})
    return NHTSData(2017, tmp_path)


def _spec(weight: str | None = "auto") -> S.Study:
    return S.Study(
        title="Adults with a degree answer", wave=2017, unit="person", weight=weight, aim="Test study.",
        steps=[S.Keep("aged 18+", Where("R_AGE", ">=", 18)), S.Complete("education answered", ["EDUC"]),
               S.Complete("worker status answered", ["WORKER"], skip="ok")],
        variables=[S.Var("age", "R_AGE", "number", label="Age"),
                   S.Var("worker", Where("WORKER", "==", "01"), "binary", na="false"),
                   S.Var("edu", "EDUC", "category"),
                   S.Var("k", lambda f: pd.to_numeric(f["R_AGE"]).sub(30).clip(upper=5), "count", needs=["R_AGE"])],
    )


def test_sample_flow_counts_every_rule(d):
    r = _spec().run(d)
    f = r.flow
    assert f["n_after"].tolist() == [6, 5, 4, 3]
    assert f["n_removed"].tolist() == [0, 1, 1, 1]     # age 10; EDUC -7; WORKER -9 (the -1 skip would have stayed)
    assert (f["n_before"] - f["n_removed"] == f["n_after"]).all()
    assert r.data[["age"]].squeeze().tolist() == [40, 38, 30]
    assert r.data.attrs["pynhts"] == {"wave": 2017, "table": "person", "weight": "WTPERFIN"}


def test_skip_is_not_a_non_answer(d):
    only = lambda skip: S.Study(title="t", wave=2017, unit="person", weight=None,  # noqa: E731
                                steps=[S.Complete("worker answered", ["WORKER"], skip=skip)],
                                variables=[S.Var("age", "R_AGE")])
    assert len(only("invalid").run(d).data) == 4      # persons 1, 2, 4, 6: the skip (-1) and the non-answer (-9) go
    assert len(only("ok").run(d).data) == 5           # the skip stays: "does not apply" is an answer


def test_descriptive_table_unweighted_and_weighted(d):
    un = _spec(weight=None).run(d).table().set_index(["variable", "level"])
    assert un.loc[("age", ""), "n"] == 3
    assert un.loc[("age", ""), "mean"] == pytest.approx(36.0)
    assert un.loc[("age", ""), "sd"] == pytest.approx(np.sqrt(28.0))      # sample sd, deviations 4, 2, -6
    assert un.loc[("worker", ""), "share_pct"] == pytest.approx(200 / 3)
    assert un.loc[("k", ""), "zero_pct"] == pytest.approx(100 / 3)
    wt = _spec().run(d).table().set_index(["variable", "level"])
    assert wt.loc[("age", ""), "mean"] == pytest.approx(296 / 9)           # weights 1, 2, 6
    assert wt.loc[("worker", ""), "share_pct"] == pytest.approx(700 / 9)
    assert wt.loc[("k", ""), "zero_pct"] == pytest.approx(600 / 9)
    sh = wt.loc["edu"]["share_pct"]                       # levels carry the codebook label: "05 Graduate degree ..."
    assert {k[:2]: v for k, v in sh.items()} == {"03": pytest.approx(200 / 9), "04": pytest.approx(100 / 9),
                                                  "05": pytest.approx(600 / 9)}
    assert sh.index[2].startswith("05 ")
    assert wt.loc[("age", ""), "min"] == 30 and wt.loc[("age", ""), "max"] == 40


def test_group_table_and_difference(d):
    r = _spec().run(d)
    t = r.table(by="worker")
    assert set(t["group"]) == {"worker=0", "worker=1"}
    diff = r.difference("worker", "worker=1", "worker=0").set_index("variable")
    assert diff.loc["age", "mean_a"] == pytest.approx(220 / 7)            # ages 40 and 30, weights 1 and 6
    assert diff.loc["age", "mean_b"] == 38
    assert diff.loc["age", "difference"] == pytest.approx(220 / 7 - 38)
    with pytest.raises(KeyError):
        r.table(by="nope")


def test_grade_and_compare(d):
    assert [S.grade(0.309, 0.3091), S.grade(10.0, 10.1), S.grade(10.0, 10.4), S.grade(10.0, 12), S.grade(0, 0.5),
            S.grade(1.0, float("nan"))] == ["EXACT", "CLOSE", "ACCEPTABLE", "GAP", "GAP", "NOT_COMPUTED"]
    r = _spec(weight=None).run(d)
    cmp = S.compare(r, [{"variable": "sample", "stat": "n", "value": 3}, {"variable": "age", "stat": "mean", "value": 36.0},
                        {"variable": "age", "stat": "sd", "value": 5.3}, {"variable": "worker", "stat": "share_pct", "value": 70.0},
                        {"variable": "edu", "stat": "share_pct", "level": "05", "value": 33.3}])
    assert cmp["status"].tolist() == ["EXACT", "EXACT", "EXACT", "ACCEPTABLE", "EXACT"]
    assert cmp["pynhts"].iloc[3] == pytest.approx(200 / 3)


def test_dictionary_form_gives_the_same_study(d):
    spec = {"title": "t", "wave": 2017, "unit": "person", "weight": None, "aim": "a",
            "steps": [{"label": "aged 18+", "keep": {"column": "R_AGE", "op": ">=", "value": 18}},
                      {"label": "education answered", "complete": ["EDUC"]},
                      {"label": "not in H2", "drop": {"all": [{"column": "HOUSEID", "op": "==", "value": "H2"},
                                                              {"column": "R_AGE", "op": ">", "value": 60}]}}],
            "variables": [{"name": "age", "source": "R_AGE"},
                          {"name": "worker", "where": {"column": "WORKER", "op": "==", "value": "01"}, "kind": "binary"},
                          {"name": "lnsize", "source": "HHSIZE", "transform": "log"}]}
    r = S.Study.from_dict(spec).run(d)
    assert r.flow["n_after"].tolist() == [6, 5, 4, 3]                     # age 10; EDUC -7 (age 70, H2); age 68 in H2 dropped
    t = r.table().set_index("variable")
    assert t.loc["lnsize", "mean"] == pytest.approx(np.log(3) * 2 / 3)    # sizes 3, 3 and 1 (persons 1, 2, 6)
    assert r.study.required_columns() == ["R_AGE", "EDUC", "HOUSEID", "WORKER", "HHSIZE"]
    with pytest.raises(ValueError, match="one of keep"):
        S.Study.from_dict({"wave": 2017, "unit": "person", "steps": [{"label": "x"}]})
    with pytest.raises(ValueError, match="transform"):
        S.Study.from_dict({"wave": 2017, "unit": "person", "variables": [{"name": "a", "source": "R_AGE", "transform": "sqrt"}]})


def test_the_study_refuses_what_would_be_silent(d):
    other = S.Study(title="t", wave=2009, unit="person", variables=[S.Var("age", "R_AGE")])
    with pytest.raises(ValueError, match="NHTS 2009"):
        other.run(d)
    with pytest.raises(ValueError, match="equal raw NHTS columns"):
        S.Study(title="t", wave=2017, unit="person", variables=[S.Var("R_AGE", "R_AGE")]).run(d)
    with pytest.raises(ValueError, match="unique"):
        S.Study(title="t", wave=2017, unit="person", variables=[S.Var("a", "R_AGE"), S.Var("a", "WORKER")]).run(d)
    with pytest.raises(ValueError, match="kind"):
        S.Var("a", "R_AGE", kind="mean")  # type: ignore[arg-type]


def test_report_and_files(d, tmp_path):
    r = _spec().run(d)
    text = r.report(by="worker")
    assert "# Adults with a degree answer" in text and "Test study." in text
    assert "removed" in r.methods() and "WTPERFIN" in r.methods() and "leaving 3 records" in r.methods()
    assert "| aged 18+ | 6 | 1 | 5 |" in text and "worker=0" in text and "Difference" in text
    assert any(a == "weighted with WTPERFIN" for a in r.assumptions)
    un = _spec(weight=None).run(d)
    assert any("statistics are unweighted" in a for a in un.assumptions)
    assert not any(a.startswith("weighted with") for a in un.assumptions)
    assert "unweighted" in un.methods()
    pytest.importorskip("matplotlib")
    out = r.save(tmp_path / "out", by="worker")
    names = {p.name for p in out}
    assert {"report.md", "table1.csv", "flow.csv", "flow.png"} <= names
    assert (tmp_path / "out" / "table1.csv").read_text().startswith("group,variable")


def test_count_distribution_reports_zeros_and_bands(d):
    r = _spec(weight=None).run(d)                      # k = 5, 5, 0
    t = r.count_distribution("k", bands=[(1, 4), (5, None)])
    assert t["band"].tolist() == ["0 (non-users)", ">= 1 (users)", "1-4", "5+"]
    assert t["n"].tolist() == [1, 2, 0, 2]
    assert t.loc[0, "share_of_all_pct"] == pytest.approx(100 / 3) and t.loc[1, "share_of_all_pct"] == pytest.approx(200 / 3)
    assert t.loc[2, "share_of_users_pct"] == 0 and t.loc[3, "share_of_users_pct"] == 100
    w = _spec().run(d).count_distribution("k", bands=[(5, 5)])      # weights 1 and 2 on the users, 6 on the zero
    assert w.loc[0, "share_of_all_pct"] == pytest.approx(600 / 9) and w.loc[2, "band"] == "5"


# ---- adversarial review of 0.8.0: skips, non-answers and hidden codes never act as numbers -----------------
@pytest.fixture
def d2(tmp_path: Path) -> NHTSData:
    """Ages 40, -7 (refused), 10, 70; TIMETOWK 30, -1 (skip), 90, -7; R_SEX 01, 02, -7, 02; WORKER 01, 02, 01, 02."""
    _write(tmp_path, "household", {"HOUSEID": ["H1", "H2"], "HHSIZE": [2, 2], "WTHHFIN": [1.0, 1.0]}, {"HOUSEID"})
    _write(tmp_path, "person", {
        "HOUSEID": ["H1", "H1", "H2", "H2"], "PERSONID": ["01", "02", "01", "02"], "R_AGE": [40, -7, 10, 70],
        "TIMETOWK": [30, -1, 90, -7], "R_SEX": ["01", "02", "-7", "02"], "WORKER": ["01", "02", "01", "02"],
        "EDUC": ["10", "10", "02", "10"], "WTPERFIN": [1.0, 2.0, 3.0, 4.0]},
           {"HOUSEID", "PERSONID", "R_SEX", "WORKER", "EDUC"})
    return NHTSData(2017, tmp_path)


def _run(d, *steps, variables=None, **kw):
    return S.Study(title="t", wave=2017, unit="person", weight=None, steps=list(steps),
                   variables=variables or [S.Var("age", "R_AGE")], **kw).run(d)


def test_a_drop_rule_does_not_remove_a_non_answer_by_its_negative_code(d2):
    r = _run(d2, S.Drop("under 18", Where("R_AGE", "<", 18)))
    assert len(r.data) == 3                         # only age 10 goes; the refused age (-7) stays
    assert r.flow["n_removed"].tolist() == [0, 1]
    assert _run(d2, S.Drop("under 18", Where("R_AGE", "<", 18), raw=True)).flow["n_removed"].tolist() == [0, 2]


def test_a_keep_rule_does_not_admit_skips_or_non_answers(d2):
    r = _run(d2, S.Keep("commute up to 60", Where("TIMETOWK", "<=", 60)))
    assert len(r.data) == 1                         # the skip (-1) and the refusal (-7) are not minutes
    assert len(_run(d2, S.Keep("not male", Where("R_SEX", "!=", "01"))).data) == 2     # not the -7
    skipped = _run(d2, S.Keep("the skip itself", Where("TIMETOWK", "==", -1), raw=True))
    assert skipped.data["age"].isna().tolist() == [True] and len(skipped.data) == 1


def test_a_binary_variable_from_a_raw_column_must_hold_only_0_and_1(d2):
    with pytest.raises(ValueError, match="only 0 and 1"):
        _run(d2, variables=[S.Var("worker", "WORKER", "binary")])
    out = _run(d2, variables=[S.Var("worker", Where("WORKER", "==", "01"), "binary")])
    assert out.table().set_index("variable").loc["worker", "share_pct"] == pytest.approx(50.0)


def test_variable_names_may_not_equal_any_nhts_column_loaded_or_not(d2):
    with pytest.raises(ValueError, match="equal raw NHTS columns"):
        _run(d2, variables=[S.Var("HHFAMINC", "R_AGE")])


def test_a_rule_on_a_study_variable_needs_no_raw_column(d2):
    r = _run(d2, S.Keep("old", Where("age", ">", 50)), variables=[S.Var("age", "R_AGE")])
    assert r.data["age"].tolist() == [70.0]


def test_cap_and_top_code_warnings_reach_the_study(d2):
    from pynhts.core.flags import PynhtsWarning

    with pytest.warns(PynhtsWarning, match="R_AGE is top-coded"):
        r = _run(d2)
    assert any("R_AGE is top-coded" in a for a in r.assumptions)


def test_figures_and_save_work_for_a_count_outcome(d2, tmp_path):
    pytest.importorskip("matplotlib").use("Agg")          # no display needed (a broken Tk would fail otherwise)
    r = _run(d2, variables=[S.Var("age", "R_AGE", "count", role="outcome"), S.Var("w", Where("WORKER", "==", "01"), "binary")])
    figs = r.figures()
    assert "dist_age" in figs and hasattr(figs["dist_age"], "savefig")
    assert "dist_age.png" in {p.name for p in r.save(tmp_path / "o", by="w")}


def test_compare_matches_the_category_code_exactly_and_needs_a_group_with_by(d2):
    r = _run(d2, variables=[S.Var("edu", "EDUC", "category"), S.Var("w", Where("WORKER", "==", "01"), "binary")])
    # codes are 10 and 02: a published level 1 must not be graded against 10 (it was, by prefix), 2 is the padded 02
    assert S.compare(r, [{"variable": "edu", "level": "1", "stat": "share_pct", "value": 75.0}]).loc[0, "status"] == (
        "NOT_COMPUTED")
    assert S.compare(r, [{"variable": "edu", "level": "2", "stat": "share_pct", "value": 25.0}]).loc[0, "status"] == "EXACT"
    assert S.compare(r, [{"variable": "edu", "level": "10", "stat": "share_pct", "value": 75.0}]).loc[0, "status"] == "EXACT"
    with pytest.raises(ValueError, match="needs a group"):
        S.compare(r, [{"variable": "w", "stat": "mean", "value": 0.5}], by="w")


def test_grade_keeps_the_printed_precision_of_a_string():
    assert S.grade("5.10", 5.14) == "CLOSE" and S.grade(5.1, 5.14) == "EXACT" and S.grade("5.14", 5.14) == "EXACT"
