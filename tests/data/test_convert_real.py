"""Real-data checks of the Parquet cache. Run with: pytest -m data

Needs the cache built by ``convert(2017, ("core", "replicates"), cache=local_data/cache)``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest

from pynhts.core.schema import TABLES, load_schema
from pynhts.io import convert, parquet_dir, replicate_columns

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "local_data" / "cache"
RAWCSV = ROOT / "local_data" / "raw_csv_2019copy"
pytestmark = pytest.mark.data


@pytest.fixture(scope="module")
def pdir() -> Path:
    d = parquet_dir(2017, CACHE)
    if not (d / "trip.parquet").is_file() or not (d / "repw_trip.parquet").is_file():
        pytest.skip("Parquet cache not built (run convert for core and replicates)")
    return d


@pytest.mark.parametrize("table", TABLES)
def test_parquet_schema_matches_codebook_types(pdir, table):
    s = load_schema(table)
    pf = pq.ParquetFile(pdir / f"{table}.parquet")
    names = pf.schema_arrow.names
    assert set(names) == set(s.columns)
    for f in pf.schema_arrow:
        expected = "string" if s.columns[f.name].is_string else "double"
        assert str(f.type) == expected, f.name


def test_household_roundtrip_equals_csv(pdir):
    s = load_schema("household")
    csv = pd.read_csv(RAWCSV / "hhpub.csv", dtype={n: str for n, c in s.columns.items()
                                                    if c.is_string}, keep_default_na=False)
    pq_df = pq.read_table(pdir / "household.parquet").to_pandas()
    assert list(csv.columns) == list(pq_df.columns)
    pd.testing.assert_frame_equal(csv, pq_df, check_dtype=False)
    assert (pq_df["HOUSEID"].str.len() == 8).all()


def test_trip_codes_kept_not_masked(pdir):
    t = pq.read_table(pdir / "trip.parquet", columns=["TRPTRANS", "TRWAITTM"]).to_pandas()
    assert (t["TRPTRANS"] == "03").any() and (t["TRPTRANS"] == "-9").any()
    assert (t["TRWAITTM"] == -1).any()  # appropriate skip kept distinct


def test_keys_unique(pdir):
    for table in TABLES:
        s = load_schema(table)
        df = pq.read_table(pdir / f"{table}.parquet", columns=list(s.key)).to_pandas()
        assert not df.duplicated().any(), table


def test_replicate_columns_and_dtypes(pdir):
    t = pq.ParquetFile(pdir / "repw_household.parquet").schema_arrow
    assert t.names == ["HOUSEID", "WTHHFIN", *replicate_columns("WTHHFIN")]
    assert str(t.field("WTHHFIN").type) == "double"
    assert str(t.field("WTHHFIN1").type) == "float"


def test_full_weights_agree_between_main_and_replicate_files(pdir):
    hh = pq.read_table(pdir / "household.parquet", columns=["HOUSEID", "WTHHFIN"]).to_pandas()
    rh = pq.read_table(pdir / "repw_household.parquet", columns=["HOUSEID", "WTHHFIN"]).to_pandas()
    m = hh.merge(rh, on="HOUSEID", suffixes=("", "_r"))
    assert len(m) == len(hh) == len(rh)
    np.testing.assert_array_equal(m["WTHHFIN"], m["WTHHFIN_r"])

    trips = pq.read_table(pdir / "trip.parquet",
                          columns=["HOUSEID", "PERSONID", "WTTRDFIN"]).to_pandas()
    rt = pq.read_table(pdir / "repw_trip.parquet",
                       columns=["HOUSEID", "PERSONID", "WTTRDFIN"]).to_pandas()
    m = trips.merge(rt, on=["HOUSEID", "PERSONID"], how="left", suffixes=("", "_r"))
    assert m["WTTRDFIN_r"].notna().all()  # every trip finds its person-day weights
    np.testing.assert_array_equal(m["WTTRDFIN"], m["WTTRDFIN_r"])


def test_replicates_scatter_around_full_weight(pdir):
    rh = pq.read_table(pdir / "repw_household.parquet").to_pandas()
    reps = rh[replicate_columns("WTHHFIN")].astype("float64").to_numpy()
    full = rh["WTHHFIN"].to_numpy()
    assert np.isfinite(reps).all() and (reps >= 0).all()
    # jackknife: replicate totals deviate by a few percent at most, never wildly
    ratio = reps.sum(axis=0) / full.sum()
    assert ratio.min() > 0.9 and ratio.max() < 1.1


def test_forced_rebuild_is_byte_identical():
    before = convert(2017, ("core",), cache=CACHE, offline=True)["household.parquet"].sha256
    after = convert(2017, ("core",), cache=CACHE, offline=True, force=True)[
        "household.parquet"
    ].sha256
    assert before == after
