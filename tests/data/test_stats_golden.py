"""JKn estimates and margins of error against the published 2017 tables. pytest -m data"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

import pynhts
from pynhts.stats import Survey, ratio_across

pytestmark = pytest.mark.data
GOLD = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / "golden" / "stt2017_table1.yaml").read_text("utf-8")
)


@pytest.fixture(scope="module")
def data() -> pynhts.NHTSData:
    return pynhts.load(2017, offline=True)


@pytest.fixture(scope="module")
def hh(data) -> Survey:
    return data.survey("household", ["HHSIZE"])


@pytest.fixture(scope="module")
def persons(data) -> Survey:
    return data.survey("person", ["R_AGE_IMP", "DRIVER", "WORKER"])


@pytest.fixture(scope="module")
def person_trips(data) -> Survey:
    """Person survey with each person's daily trip count and miles attached."""
    trips = data.trips(["TRPMILES"], weight=False)
    per = trips.groupby(["HOUSEID", "PERSONID"]).agg(
        ntrips=("TDTRPNUM", "size"), pmt=("TRPMILES", "sum")).reset_index()
    base = data.survey("person", [])
    rows = base.rows.merge(per, on=["HOUSEID", "PERSONID"], how="left", validate="1:1")
    rows[["ntrips", "pmt"]] = rows[["ntrips", "pmt"]].fillna(0)
    return Survey(rows, base._unit, base._w, base._r)


def _check(row: pd.Series, pub_value: float, pub_moe: float, scale: float = 1.0, tol=0.51):
    """Estimate agrees at the publication's rounding; MOE within rounding or 0.1 percent.

    The 0.1 percent allowance covers the largest observed gap (985.54 vs the printed 985, 0.05
    percent), consistent with the report rounding the SE before applying the multiplier.
    """
    assert row["estimate"] / scale == pytest.approx(pub_value, abs=tol)
    assert row["moe"] / scale == pytest.approx(pub_moe, abs=max(tol, 0.001 * pub_moe))


def test_t_multiplier_is_the_one_used_by_fhwa():
    # published MOE / our SE for a clean case (drivers: 827 / 416.9) = t(0.975, 98)
    from pynhts.stats import t_ppf
    assert t_ppf(0.975, 98) == pytest.approx(1.9845, abs=1e-4)


def test_table1a_household_size_bands_and_moes(hh):
    g = GOLD["table_1a_households"]
    size = hh.rows["HHSIZE"].clip(upper=4)
    hh.rows["size"] = size
    res = hh.total(by="size").set_index("size")
    for key, code in [("size_1", 1.0), ("size_2", 2.0), ("size_3", 3.0), ("size_4plus", 4.0)]:
        row = res.loc[code]
        assert row["estimate"] / 1e3 == pytest.approx(g[key]["value"], abs=0.51)
        if g[key]["moe"] is not None:
            assert row["moe"] / 1e3 == pytest.approx(g[key]["moe"], abs=0.51)
    assert hh.total().iloc[0]["moe"] / 1e3 < 0.5  # controlled total: published MOE is "-"


def test_table1b_age_bands_moes(persons):
    g = GOLD["table_1b_persons_by_imputed_age"]
    a = persons.rows["R_AGE_IMP"]
    bands = {"under_16": a < 16, "age_16_19": a.between(16, 19), "age_20_34": a.between(20, 34),
             "age_35_64": a.between(35, 64), "age_65plus": a >= 65, "age_16plus": a >= 16}
    for key, dom in bands.items():
        row = persons.total(domain=dom).iloc[0]
        _check(row, g[key]["value"], g[key]["moe"], scale=1e3)


def test_table1c_drivers_workers_moes(persons):
    g = GOLD["table_1c_drivers_workers"]
    _check(persons.total(domain=persons.rows["DRIVER"] == "01").iloc[0],
           g["drivers"]["value"], g["drivers"]["moe"], scale=1e3)
    _check(persons.total(domain=persons.rows["WORKER"] == "01").iloc[0],
           g["workers"]["value"], g["workers"]["moe"], scale=1e3)


def test_table3b_average_trip_length_from_trip_level_survey(data):
    """Trip rows with person-day replicates: mean trip miles and its MOE."""
    g = GOLD["table_3b_person_rates"]["average_person_trip_length_miles"]
    trips = data.survey("trip", ["TRPMILES"])
    row = trips.mean("TRPMILES").iloc[0]
    assert row["estimate"] == pytest.approx(g["value"], abs=0.006)
    assert row["moe"] == pytest.approx(g["moe"], abs=0.006)
    assert row["n"] == 922_916  # 656 trips have TRPMILES = -9 and are excluded


def test_table3b_trips_per_person_and_trip_length(person_trips):
    g = GOLD["table_3b_person_rates"]
    row = person_trips.mean("ntrips").iloc[0]
    assert row["estimate"] == pytest.approx(g["daily_person_trips_per_person"]["value"], abs=0.006)
    assert row["moe"] == pytest.approx(g["daily_person_trips_per_person"]["moe"], abs=0.006)
    ratio = person_trips.ratio("pmt", "ntrips").iloc[0]
    assert ratio["estimate"] == pytest.approx(g["average_person_trip_length_miles"]["value"],
                                              abs=0.006)
    assert ratio["moe"] == pytest.approx(g["average_person_trip_length_miles"]["moe"], abs=0.006)


def test_table3b_pmt_per_person_estimate_matches_but_moe_is_a_documented_gap(person_trips):
    g = GOLD["table_3b_person_rates"]["daily_pmt_per_person"]
    d = GOLD["documented_discrepancy"]["pmt_per_person_moe"]
    row = person_trips.mean("pmt").iloc[0]
    assert row["estimate"] == pytest.approx(g["value"], abs=0.006)
    assert row["moe"] == pytest.approx(d["reproduced"], abs=0.002)  # pinned, see the YAML note
    assert row["moe"] < g["moe"]


def test_table3a_per_household_rates_via_cross_survey_ratio(hh, person_trips):
    g = GOLD["table_3a_household_rates"]
    trips = ratio_across(person_trips, "ntrips", hh).iloc[0]
    pmt = ratio_across(person_trips, "pmt", hh).iloc[0]
    t, p = g["daily_person_trips_per_household"], g["daily_pmt_per_household"]
    assert trips["estimate"] == pytest.approx(t["value"], abs=0.006)
    assert trips["moe"] == pytest.approx(t["moe"], abs=0.006)
    assert pmt["estimate"] == pytest.approx(p["value"], abs=0.006)
    assert pmt["moe"] == pytest.approx(p["moe"], abs=0.006)


def test_vehicle_survey_uses_household_replicates(data):
    veh = data.survey("vehicle", ["VEHYEAR"])
    assert veh.n_units == 129_696 and len(veh.rows) == 256_115
    assert veh.total().iloc[0]["se"] > 0
    assert veh.mean("VEHYEAR").iloc[0]["estimate"] > 2000


def test_decode_labels(data):
    hh = data.households(["HHFAMINC", "HOMEOWN"])
    out = data.decode_labels(hh, ["HOMEOWN"], table="household")
    assert set(out["HOMEOWN"].dropna()) <= {"Own", "Rent", "Other"} | set(
        data.labels("HOMEOWN").values())
    assert "Own" in set(out["HOMEOWN"].dropna())
    assert out["HHFAMINC"].equals(hh["HHFAMINC"])  # untouched when not requested
