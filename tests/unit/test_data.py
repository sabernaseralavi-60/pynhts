"""Unit tests for NHTSData with tiny synthetic Parquet files (no real data needed)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pynhts.core.data import NHTSData
from pynhts.io.fetcher import NHTSIntegrityError


def _write(directory: Path, name: str, columns: dict[str, list], strings: set[str]) -> None:
    arrays = {
        k: pa.array(v, type=pa.string() if k in strings else pa.float64())
        for k, v in columns.items()
    }
    pq.write_table(pa.table(arrays), directory / f"{name}.parquet")


@pytest.fixture
def d(tmp_path: Path) -> NHTSData:
    _write(tmp_path, "household", {
        "HOUSEID": ["H1", "H2", "H3"], "HHSIZE": [2, -9, 4],
        "HHFAMINC": ["07", "-7", "03"], "BIKE": ["01", "-7", "03"],
        "WTHHFIN": [100.0, 200.0, 300.0]},
        {"HOUSEID", "HHFAMINC", "BIKE"})
    _write(tmp_path, "person", {
        "HOUSEID": ["H1", "H1", "H2", "H3"], "PERSONID": ["01", "02", "01", "01"],
        "R_AGE": [30, 8, -7, 50], "BIKE4EX": [1, -8, 2, 3],
        "HHSIZE": [2, 2, -9, 4],  # a copy of the household column, as in the real file
        "WTPERFIN": [1.0, 2.0, 3.0, 4.0]},
        {"HOUSEID", "PERSONID"})
    _write(tmp_path, "trip", {
        "HOUSEID": ["H1", "H1", "H1", "H3"], "PERSONID": ["01", "01", "02", "01"],
        "TDTRPNUM": ["01", "02", "01", "01"], "TRPMILES": [5.0, -9, 2.0, 7.0],
        "TRWAITTM": [-1, 3, -8, 4], "TRPTRANS": ["03", "-9", "01", "06"],
        "WTTRDFIN": [10.0, 10.0, 20.0, 40.0]},
        {"HOUSEID", "PERSONID", "TDTRPNUM", "TRPTRANS"})
    _write(tmp_path, "vehicle", {
        "HOUSEID": ["H1", "H2"], "VEHID": ["01", "01"], "VEHYEAR": [2010, -7],
        "WTHHFIN": [100.0, 200.0]}, {"HOUSEID", "VEHID"})
    return NHTSData(2017, tmp_path)


def test_missing_nan_masks_numeric_and_string_codes(d):
    t = d.trips(["TRPMILES", "TRPTRANS"])
    assert np.isnan(t.loc[1, "TRPMILES"]) and t.loc[0, "TRPMILES"] == 5.0
    assert pd.isna(t.loc[1, "TRPTRANS"]) and t.loc[0, "TRPTRANS"] == "03"  # zero kept


def test_missing_keep_leaves_all_codes(d):
    t = d.trips(["TRPMILES", "TRPTRANS"], missing="keep")
    assert t.loc[1, "TRPMILES"] == -9 and t.loc[1, "TRPTRANS"] == "-9"


def test_skip_code_is_distinct_from_missing(d):
    # default skip="auto": the skip code is never a quantity, so it is NA in numeric columns
    wait = d.trips(["TRWAITTM"])["TRWAITTM"]
    assert np.isnan(wait.iloc[0]) and np.isnan(wait.iloc[2])
    keep = d.trips(["TRWAITTM"], skip="keep")["TRWAITTM"]
    assert keep.iloc[0] == -1 and np.isnan(keep.iloc[2])  # -1 kept, -8 masked
    wait2 = d.trips(["TRWAITTM"], skip="nan")["TRWAITTM"]
    assert np.isnan(wait2.iloc[0]) and np.isnan(wait2.iloc[2])
    with pytest.raises(ValueError, match="skip must be"):
        d.trips(["TRWAITTM"], skip="drop")
    kept = d.trips(["TRWAITTM"], missing="keep")["TRWAITTM"]
    assert kept.iloc[0] == -1 and kept.iloc[2] == -8


def test_join_parent_columns_preserves_rows_and_order(d):
    t = d.trips(["TRPMILES", "BIKE4EX", "BIKE"])
    assert len(t) == 4 and list(t["TDTRPNUM"]) == ["01", "02", "01", "01"]
    # person onto trips by (HOUSEID, PERSONID); "-8" is masked
    assert t["BIKE4EX"][[0, 1, 3]].tolist() == [1, 1, 3] and np.isnan(t.loc[2, "BIKE4EX"])
    assert t["BIKE"].tolist() == ["01", "01", "01", "03"]  # household onto trips by HOUSEID


def test_joined_columns_are_masked_with_their_own_schema(d):
    p = d.persons(["BIKE", "HHSIZE"])  # BIKE is joined from household, HHSIZE is a copy
    assert pd.isna(p.loc[2, "BIKE"])
    # masking is per column and uses only codes the codebook declares for that column:
    # HHSIZE declares no missing codes, so a stray -9 would be left visible (and is caught
    # by the data-level audit test, which proves the real files contain no such values)
    assert p.loc[2, "HHSIZE"] == -9
    assert p["BIKE"].tolist()[:2] == ["01", "01"]


def test_lazy_selection_and_key_weight_switches(d):
    t = d.trips(["TRPMILES"], keys=False, weight=False)
    assert list(t.columns) == ["TRPMILES"]
    t = d.trips(["TRPMILES"])
    assert list(t.columns) == ["HOUSEID", "PERSONID", "TDTRPNUM", "TRPMILES", "WTTRDFIN"]
    assert list(d.trips(["BIKE4EX"], keys=False, weight=False).columns) == ["BIKE4EX"]


def test_orphan_child_row_raises(d, tmp_path):
    _write(tmp_path, "trip", {
        "HOUSEID": ["H1", "HX"], "PERSONID": ["01", "01"], "TDTRPNUM": ["01", "01"],
        "TRPMILES": [1.0, 2.0], "WTTRDFIN": [1.0, 1.0]},
        {"HOUSEID", "PERSONID", "TDTRPNUM"})
    with pytest.raises(NHTSIntegrityError, match="without a parent"):
        d.trips(["BIKE4EX"])


def test_duplicate_parent_key_raises(d, tmp_path):
    _write(tmp_path, "household", {
        "HOUSEID": ["H1", "H1"], "HHSIZE": [1, 2], "BIKE": ["01", "02"],
        "WTHHFIN": [1.0, 1.0]}, {"HOUSEID", "BIKE"})
    with pytest.raises(NHTSIntegrityError, match="not unique"):
        d.persons(["BIKE"])


def test_unreachable_and_unknown_columns(d):
    with pytest.raises(KeyError, match="cannot be joined"):
        d.trips(["VEHYEAR"])  # vehicle attributes are not a parent of trips
    with pytest.raises(KeyError, match="unknown"):
        d.trips(["NOT_A_COLUMN"])
    with pytest.raises(ValueError):
        d.table("trips")
    with pytest.raises(ValueError):
        d.trips(["TRPMILES"], missing="bogus")  # type: ignore[arg-type]


def test_vehicle_own_personid_is_not_the_person_key(d):
    s = d.schema("vehicle")
    assert s.columns["PERSONID"].owner == "vehicle" and s.columns["VEHID"].owner == "vehicle"
    assert d.schema("trip").columns["PERSONID"].owner == "person"


def test_vehicles_pull_household_columns(d):
    v = d.vehicles(["VEHYEAR", "BIKE"])
    assert v.loc[0, "BIKE"] == "01" and pd.isna(v.loc[1, "BIKE"])
    assert np.isnan(v.loc[1, "VEHYEAR"])


def test_weight_columns_and_replicate_error(d):
    assert d.weight_column("trip") == "WTTRDFIN" and d.weight_column("vehicle") == "WTHHFIN"
    with pytest.raises(FileNotFoundError, match="missing"):
        d.replicate_weights("household")
    with pytest.raises(ValueError):
        d.replicate_weights("vehicle")


def test_labels(d):
    assert d.labels("TRPTRANS")["03"]
    assert "Person ID" in d.schema("vehicle").columns["PERSONID"].label


def test_survey_rows_validates_level_and_keys(d):
    rows = pd.DataFrame({"HOUSEID": ["H1"], "PERSONID": ["01"], "x": [1.0]})
    with pytest.raises(ValueError, match="level"):
        d.survey_rows(rows, "vehicle")
    with pytest.raises(KeyError, match="PERSONID"):
        d.survey_rows(rows.drop(columns="PERSONID"), "trip")
    with pytest.raises(FileNotFoundError, match="replicate"):
        d.survey_rows(rows, "trip")  # keys fine, but this synthetic cache has no replicates


def test_string_columns_are_arrow_backed(d):
    # Python-object strings needed ~3x the memory on the real trip table (OOM on a 13 GB runtime).
    t = d.trips(["TRPTRANS"])
    assert isinstance(t["TRPTRANS"].dtype, pd.StringDtype)
    assert t["TRPTRANS"].dtype.storage == "pyarrow"
