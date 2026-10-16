"""End-to-end loader and golden tests on the real data. Run with: pytest -m data"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

import pynhts
from pynhts.core.schema import KEYS, TABLES

pytestmark = pytest.mark.data
GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "stt2017_table1.yaml"
GLOBAL_CODES = ["-9", "-8", "-7", "-88", "-77"]
# The codebook counts -88 / -77 together with the rows holding -8 / -7 in the same column.
LUMPED = {"-88": "-8", "-77": "-7"}


def _eq(series: pd.Series, code: str, is_string: bool) -> pd.Series:
    hit = series == (code if is_string else float(code))
    return hit.fillna(False).astype(bool)


@pytest.fixture(scope="module")
def data() -> pynhts.NHTSData:
    # Default cache location comes from PYNHTS_CACHE_DIR (see conftest.py).
    return pynhts.load(2017, offline=True)


def test_load_2017_end_to_end(data):
    hh = data.households()
    assert len(hh) == 129_696 and hh["HOUSEID"].is_unique
    assert hh["HOUSEID"].str.len().eq(8).all()
    trips = data.trips(["TRPMILES", "HHFAMINC", "R_AGE"])
    assert len(trips) == 923_572
    assert list(trips.columns[:3]) == ["HOUSEID", "PERSONID", "TDTRPNUM"]
    assert trips["WTTRDFIN"].notna().all()


@pytest.mark.parametrize("table", TABLES)
def test_codebook_counts_and_weighted_totals_reproduce(data, table):
    """Every `code=label` line of the official codebook (n and weighted n) is reproduced."""
    s, w = data.schema(table), data.weight_column(table)
    df = data.table(table, missing="keep", skip="keep")
    wt = df[w].to_numpy()
    checked = 0
    for name, col in s.columns.items():
        for k in col.codes:
            members = [k.code]
            if k.code in LUMPED and not col.is_string:
                members.append(LUMPED[k.code])
            mask = np.zeros(len(df), dtype=bool)
            for code in members:
                mask |= _eq(df[name], code, col.is_string).to_numpy()
            if k.n is not None:
                assert int(mask.sum()) == k.n, (table, name, k.code)
            if k.weighted is not None:
                assert wt[mask].sum() == pytest.approx(k.weighted, rel=1e-6), (
                    table, name, k.code)
            checked += 1
    assert checked == sum(len(c.codes) for c in s.columns.values())


@pytest.mark.parametrize("table", TABLES)
def test_no_unlisted_missing_or_skip_codes_in_data(data, table):
    s = data.schema(table)
    df = data.table(table, missing="keep", skip="keep", weight=False, keys=False)
    for name, col in s.columns.items():
        listed = set(col.missing_codes) | ({col.skip_code} if col.skip_code else set())
        for code in [*GLOBAL_CODES, "-1"]:
            if code in listed:
                continue
            assert not _eq(df[name], code, col.is_string).any(), (
                f"{table}.{name} holds unlisted code {code}")


@pytest.mark.parametrize("table", TABLES)
def test_missing_nan_masks_missing_codes_but_not_skip(data, table):
    s = data.schema(table)
    raw = data.table(table, missing="keep", skip="keep", weight=False, keys=False)
    masked = data.table(table, missing="nan", skip="keep", weight=False, keys=False)
    both = data.table(table, missing="nan", skip="nan", weight=False, keys=False)
    for name, col in s.columns.items():
        for code in col.missing_codes:
            assert not _eq(masked[name], code, col.is_string).any(), (table, name, code)
        if col.skip_code:
            kept = _eq(raw[name], col.skip_code, col.is_string).sum()
            assert _eq(masked[name], col.skip_code, col.is_string).sum() == kept
            assert not _eq(both[name], col.skip_code, col.is_string).any()


@pytest.mark.parametrize("child", ["person", "trip", "vehicle"])
def test_inherited_columns_equal_parent_values(data, child):
    """Copies of parent columns inside a child file must equal the parent's own values."""
    s = data.schema(child)
    for owner in sorted({s.columns[c].owner for c in s.inherited()}):
        keys = list(KEYS[owner])
        cols = [c for c in s.inherited() if s.columns[c].owner == owner and c not in keys]
        own = data.table(child, cols, missing="keep", weight=False)
        parent = data.table(owner, cols, missing="keep", weight=False)[[*keys, *cols]]
        merged = own[keys].merge(parent, on=keys, how="left", validate="many_to_one")
        pd.testing.assert_frame_equal(
            own[cols].reset_index(drop=True),
            merged[cols].reset_index(drop=True),
            check_dtype=False,
        )


def test_golden_table1_households(data):
    g = yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))["table_1a_households"]
    hh = data.households(["HHSIZE"])
    w = hh["WTHHFIN"] / 1000
    got = {
        "all": w.sum(),
        "size_1": w[hh.HHSIZE == 1].sum(),
        "size_2": w[hh.HHSIZE == 2].sum(),
        "size_3": w[hh.HHSIZE == 3].sum(),
        "size_4plus": w[hh.HHSIZE >= 4].sum(),
    }
    for key, val in got.items():
        assert val == pytest.approx(g[key]["value"], abs=0.51), key


def test_golden_table1_persons_drivers_workers(data):
    gold = yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))
    pe = data.persons(["R_AGE_IMP", "DRIVER", "WORKER"])
    w, a = pe["WTPERFIN"] / 1000, pe["R_AGE_IMP"]
    bands = {
        "under_16": a < 16,
        "age_16_19": a.between(16, 19),
        "age_20_34": a.between(20, 34),
        "age_35_64": a.between(35, 64),
        "age_65plus": a >= 65,
        "age_16plus": a >= 16,
    }
    for key, mask in bands.items():
        pub = gold["table_1b_persons_by_imputed_age"][key]["value"]
        assert w[mask].sum() == pytest.approx(pub, abs=0.51), key
    c = gold["table_1c_drivers_workers"]
    assert w[pe.DRIVER == "01"].sum() == pytest.approx(c["drivers"]["value"], abs=0.51)
    assert w[pe.WORKER == "01"].sum() == pytest.approx(c["workers"]["value"], abs=0.51)


def test_documented_discrepancy_persons_all(data):
    """Pins the unresolved Table 1b 'All' mismatch so that any change in it is noticed."""
    gold = yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))
    d = gold["documented_discrepancy"]["persons_all"]
    pe = data.persons([])
    assert pe["WTPERFIN"].sum() / 1000 == pytest.approx(d["reproduced"], abs=0.51)
    assert d["published"] - d["reproduced"] == 19_820


def test_replicate_weights_available_for_loader(data):
    hh = data.replicate_weights("household")
    assert hh.shape == (129_696, 100)
    assert hh["WTHHFIN1"].dtype == np.float64
