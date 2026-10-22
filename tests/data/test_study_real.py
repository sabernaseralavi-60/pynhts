"""The study layer on the real 2017 file: a published paper's sample and Table 1 rebuilt from a YAML file.

Zhang & Zhang (2018) Sustainability 10:2720 (audit script p14): 228,002 answered the ridesharing question, 219,026
complete cases, Table 1 means. The YAML in docs/examples states the same rules as data. Run with: pytest -m data
"""

from __future__ import annotations

from pathlib import Path

import pytest

import pynhts
from pynhts import study as S

pytestmark = pytest.mark.data

YAML = Path(__file__).resolve().parents[2] / "docs" / "examples" / "ridesharing_35_states.yaml"


@pytest.fixture(scope="module")
def result():
    return S.Study.from_yaml(YAML).run(pynhts.load(2017, offline=True))


def test_sample_flow_matches_the_paper(result):
    f = result.flow.set_index("rule")
    assert f.loc["person records in the 2017 file", "n_after"] == 264234
    assert f.loc["answered the ridesharing question", "n_after"] == 228002        # printed 228,002: exact
    final = int(f["n_after"].iloc[-1])
    assert abs(final - 219026) / 219026 < 0.002                                     # 218,831: 0.09 % fewer
    assert len(result.data) == final


def test_table_1_means_are_graded_without_tuning(result):
    published = [
        {"variable": "ride", "stat": "mean", "value": 0.309}, {"variable": "ride", "stat": "sd", "value": 1.757},
        {"variable": "veh", "stat": "mean", "value": 2.232}, {"variable": "female", "stat": "mean", "value": 0.531},
        {"variable": "age", "stat": "mean", "value": 53.025}, {"variable": "worker", "stat": "mean", "value": 0.549},
        {"variable": "driver", "stat": "mean", "value": 0.919}, {"variable": "inc", "stat": "mean", "value": 6.315},
        {"variable": "rent", "stat": "mean", "value": 0.212},
    ]
    g = S.compare(result, published)
    assert set(g["status"]) <= {"EXACT", "CLOSE"}, g
    assert (g["status"] == "EXACT").sum() >= 5
    # the public file caps the 30-day public transit count at 30, the paper prints 240
    assert result.table().set_index("variable").loc["pt", "max"] == 30


def test_report_and_a_group_split_on_real_data(result):
    text = result.report(by="female")
    assert "removed" in text and "female=1" in text and "unweighted" in result.methods()
    t = result.table(by="driver").set_index(["group", "variable"])
    assert t.loc[("driver=1", "age"), "mean"] > 40 and t.loc[("driver=0", "age"), "mean"] > 40


def test_count_distribution_reproduces_the_printed_usage_bands(result):
    t = result.count_distribution("ride", bands=[(1, 1), (2, 2), (1, 5), (6, 20), (21, 99)]).set_index("band")
    users = t.loc[">= 1 (users)", "n"]
    assert abs(users - 16817) <= 10 and abs(t.loc["0 (non-users)", "n"] - 202209) <= 250   # printed 16,817 and 202,209
    s = t["share_of_users_pct"]
    assert s["1"] == pytest.approx(28.32, abs=0.05) and s["2"] == pytest.approx(25.15, abs=0.05)
    assert s["1-5"] == pytest.approx(81.19, abs=0.05) and s["6-20"] == pytest.approx(17.61, abs=0.05)
    assert s["21-99"] == pytest.approx(1.21, abs=0.05)


# ---- adversarial review of 0.8.0 on the real files ---------------------------------------------------------
def test_study_mean_equals_the_default_loader_when_a_hidden_missing_code_is_present():
    """2009 PTUSED: 99 is a hidden missing code (608 persons); the study mean must be the default loader's (1.4673)."""
    import numpy as np

    d = pynhts.load(2009, offline=True)
    res = S.Study(title="t", wave=2009, unit="person", weight=None, steps=[S.Complete("answered", ["PTUSED"])],
                  variables=[S.Var("pt", "PTUSED", "count")]).run(d)
    ref = d.persons(["PTUSED"], weight=False)["PTUSED"].dropna()
    assert len(res.data) == len(ref) and (res.data["pt"] == 99).sum() == 0
    assert np.isclose(res.data["pt"].mean(), ref.mean()) and 1.46 < ref.mean() < 1.48


def test_keep_and_drop_on_the_real_2017_person_file_ignore_skips_and_non_answers():
    d = pynhts.load(2017, offline=True)
    res = S.Study(title="t", wave=2017, unit="person", weight=None,
                  steps=[S.Keep("commute up to 60 minutes", pynhts.aggregate.Where("TIMETOWK", "<=", 60))],
                  variables=[S.Var("t", "TIMETOWK")]).run(d)
    ref = d.persons(["TIMETOWK"], weight=False)["TIMETOWK"]
    assert len(res.data) == int((ref <= 60).sum())            # 101,700; the raw rule kept 225,850
    assert res.data["t"].min() >= 0
