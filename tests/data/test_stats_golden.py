"""Survey behaviour on the real data (the published-table checks live in test_recipes.py)."""

from __future__ import annotations

import pytest

import pynhts
from pynhts.stats import t_ppf

pytestmark = pytest.mark.data


@pytest.fixture(scope="module")
def data() -> pynhts.NHTSData:
    return pynhts.load(2017, offline=True)


def test_t_multiplier_is_the_one_used_by_fhwa():
    # published MOE / our SE (drivers: 827 / 416.9) = t(0.975, 98)
    assert t_ppf(0.975, 98) == pytest.approx(1.9845, abs=1e-4)


def test_trip_survey_uses_person_day_units_and_drops_missing_distances(data):
    trips = data.survey("trip", ["TRPMILES"])
    assert trips.n_units == 264_234 and len(trips.rows) == 923_572
    row = trips.mean("TRPMILES").iloc[0]
    assert row["n"] == 922_916  # 656 trips have TRPMILES = -9 and are excluded
    assert row["estimate"] == pytest.approx(10.70, abs=0.006)
    assert row["moe"] == pytest.approx(0.40, abs=0.006)


def test_vehicle_survey_uses_household_replicates(data):
    veh = data.survey("vehicle", ["VEHYEAR"])
    assert veh.n_units == 129_696 and len(veh.rows) == 256_115
    assert veh.total().iloc[0]["se"] > 0
    assert veh.mean("VEHYEAR").iloc[0]["estimate"] > 2000


def test_by_groups_sum_to_total_on_real_data(data):
    hh = data.survey("household", ["HOMEOWN"])
    parts = hh.total(by="HOMEOWN")
    assert parts["estimate"].sum() == pytest.approx(hh.total(domain=hh.rows["HOMEOWN"].notna())
                                                    .iloc[0]["estimate"])


def test_decode_labels(data):
    hh = data.households(["HHFAMINC", "HOMEOWN"])
    out = data.decode_labels(hh, ["HOMEOWN"], table="household")
    assert "Own" in set(out["HOMEOWN"].dropna())
    assert out["HHFAMINC"].equals(hh["HHFAMINC"])  # untouched when not requested
