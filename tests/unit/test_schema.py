from __future__ import annotations

import pytest

from pynhts.core.schema import KEYS, TABLES, load_schema

EXPECTED_COLUMNS = {"household": 58, "person": 121, "trip": 115, "vehicle": 60}


@pytest.mark.parametrize("table", TABLES)
def test_column_counts_match_csv(table):
    assert len(load_schema(table).columns) == EXPECTED_COLUMNS[table]


@pytest.mark.parametrize("table", TABLES)
def test_keys_are_present_and_strings(table):
    s = load_schema(table)
    for k in KEYS[table]:
        assert s.columns[k].is_string, k


def test_coded_columns_keep_leading_zeros_as_strings():
    trip = load_schema("trip")
    assert trip.columns["TRPTRANS"].dtype == "string"
    assert trip.columns["TRPMILES"].dtype == "float64"
    assert trip.columns["WTTRDFIN"].dtype == "float64"


def test_missing_codes_are_classified():
    c = load_schema("trip").columns["TRWAITTM"]
    assert c.missing_codes == {"-9": "not_ascertained", "-8": "dont_know", "-7": "refused"}
    assert c.skip_code == "-1"


def test_ownership_flags_copied_household_columns():
    veh = load_schema("vehicle")
    assert "WTHHFIN" in veh.inherited() and veh.columns["WTHHFIN"].owner == "household"
    assert "VEHYEAR" in veh.owned()
    assert load_schema("household").inherited() == []


def test_unknown_table_and_wave():
    with pytest.raises(ValueError):
        load_schema("trips")
    with pytest.raises(ValueError):
        load_schema("trip", wave=1995)
