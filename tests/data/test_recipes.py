"""Reproduce the published 2017 Summary of Travel Trends tables. Run with: pytest -m data"""

from __future__ import annotations

import pytest

import pynhts
from pynhts import recipes

pytestmark = pytest.mark.data


@pytest.fixture(scope="module")
def table():
    return recipes.run("stt2017", pynhts.load(2017, offline=True))


def test_every_target_has_its_expected_status(table):
    wrong = table[table["status"] != table["expected"]]
    assert wrong.empty, wrong[["id", "published", "estimate", "moe", "status", "expected"]]


def test_reproduction_scorecard(table):
    counts = table["status"].value_counts().to_dict()
    assert counts == {"reproduced": 20, "estimate_only": 2, "not_reproduced": 2}
    assert len(table) == 24


def test_households_and_persons_reproduce_to_the_thousand(table):
    t = table.set_index("id")
    for key in ["hh_all", "hh_size1", "hh_size2", "hh_size3", "hh_size4plus", "age_16plus",
                "age_65plus", "drivers", "workers"]:
        assert abs(t.loc[key, "estimate_diff"]) <= 0.51, key


def test_controlled_totals_have_zero_variance(table):
    t = table.set_index("id")
    assert t.loc["hh_all", "moe"] < 0.01 and t.loc["age_65plus", "moe"] < 0.1


def test_documented_gaps_are_the_known_ones(table):
    gaps = table[table["status"] != "reproduced"].set_index("id")
    assert set(gaps.index) == {"persons_all", "pmt_per_person", "vmt_per_driver",
                               "vtrips_per_driver"}
    assert gaps.loc["persons_all", "estimate"] == pytest.approx(301_599, abs=1)
    assert gaps.loc["pmt_per_person", "moe_rel_diff"] == pytest.approx(-0.0676, abs=0.002)


def test_markdown_report_renders(table):
    md = recipes.to_markdown(table)
    assert md.count("\n") == len(table) + 2 and "reproduced" in md
