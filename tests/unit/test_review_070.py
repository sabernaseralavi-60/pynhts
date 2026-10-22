"""Regression tests for the findings of the adversarial review of 0.7.0 (fixed in 0.7.1)."""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pynhts import aggregate as A
from pynhts import eda, features, tables, transform
from pynhts.core.data import NHTSData
from pynhts.core.flags import PynhtsWarning
from pynhts.io.fetcher import NHTSIntegrityError


def _write(directory: Path, name: str, columns: dict[str, list], strings: set[str]) -> None:
    arrays = {
        k: pa.array(v, type=pa.string() if k in strings else pa.float64())
        for k, v in columns.items()
    }
    pq.write_table(pa.table(arrays), directory / f"{name}.parquet")


@pytest.fixture
def d(tmp_path: Path) -> NHTSData:
    _write(
        tmp_path,
        "household",
        {"HOUSEID": ["H1", "H2"], "HHSIZE": [3, 1], "HHVEHCNT": [1, 0], "WTHHFIN": [10.0, 20.0]},
        {"HOUSEID"},
    )
    _write(
        tmp_path,
        "person",
        {
            "HOUSEID": ["H1", "H1", "H1", "H2"],
            "PERSONID": ["01", "02", "03", "01"],
            "R_AGE": [40, 16, 9, 30],
            "EDUC": ["04", "03", "-1", "05"],
            "WORKER": ["01", "01", "-1", "02"],
            "DRIVER": ["01", "01", "-1", "01"],
            "WTPERFIN": [1.0, 2.0, 3.0, 4.0],
        },
        {"HOUSEID", "PERSONID", "EDUC", "WORKER", "DRIVER"},
    )
    _write(
        tmp_path,
        "trip",
        {
            "HOUSEID": ["H1", "H1", "H1", "H2"],
            "PERSONID": ["01", "01", "02", "01"],
            "TDTRPNUM": ["1", "2", "1", "1"],
            "TRPMILES": [5.0, -1.0, 2.0, 3.0],  # -1 = skip code, not a mile
            "TRVLCMIN": [10.0, 5.0, 8.0, 7.0],
            "STRTTIME": ["0800", "0900", "1000", "1100"],
            "DRVR_FLG": ["01", "01", "01", "01"],
            "TRPTRANS": ["03", "03", "03", "03"],
            "WHYTRP1S": ["10", "-9", "40", "01"],
            "WTTRDFIN": [1.0, 1.0, 1.0, 1.0],
        },
        {"HOUSEID", "PERSONID", "TDTRPNUM", "STRTTIME", "DRVR_FLG", "TRPTRANS", "WHYTRP1S"},
    )
    _write(
        tmp_path,
        "vehicle",
        {
            "HOUSEID": ["H1"],
            "VEHID": ["01"],
            "VEHAGE": [-8],
            "VEHTYPE": ["01"],
            "FUELTYPE": ["01"],
            "WTHHFIN": [10.0],
        },
        {"HOUSEID", "VEHID", "VEHTYPE", "FUELTYPE"},
    )
    return NHTSData(2017, tmp_path)


def test_the_skip_code_is_never_summed_as_a_distance(d):
    # P0-1: -1 in a numeric column is a skip: the person's distance is unknown (NaN), not 5 - 1 = 4
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PynhtsWarning)
        r = A.aggregate(
            d, "trip", "person", {"miles": A.Agg.sum("TRPMILES"), "lo": A.Agg.min("TRPMILES")}
        )
        s = A.aggregate(d, "trip", "person", {"miles": A.Agg.sum("TRPMILES")}, missing="skip")
        f = A.aggregate(
            d, d.trips(["TRPMILES"], skip="keep"), "person", {"miles": A.Agg.sum("TRPMILES")}
        )
        p = features.create_person_features(d, groups=["travel"])
    assert np.isnan(r["miles"].iloc[0]) and (r["lo"].dropna() >= 0).all()
    assert s["miles"].iloc[0] == 5.0
    assert np.isnan(f["miles"].iloc[0])  # a frame loaded with skip="keep" too
    assert (p["p_miles"].dropna() >= 0).all() and np.isnan(p["p_miles"].iloc[0])


def test_where_compares_codes_unpadded_and_refuses_type_mismatches(d):
    t = d.trips(["TRPTRANS", "TRPMILES"], skip="keep")
    t.loc[0, "TRPMILES"] = np.nan
    assert (
        A.Where("TRPTRANS", "==", 3).mask(t).all()
        and A.Where("TRPTRANS", "in", (3, "03")).mask(t).all()
    )
    assert not A.Where("TRPTRANS", "==", "04").mask(t).any()
    with pytest.raises(TypeError, match="coded"):
        A.Where("TRPTRANS", ">", 1).mask(t)
    with pytest.raises(TypeError, match="numeric"):
        A.Where("TRPMILES", "==", "5").mask(t)
    # NOT does not turn unknown values into matches
    lt1 = A.Where("TRPMILES", "<", 1).mask(t)
    not_ge1 = (~A.Where("TRPMILES", ">=", 1)).mask(t)
    assert t["TRPMILES"].isna().any() and not_ge1.sum() == lt1.sum()


def test_user_frames_are_guarded(d):
    t = d.trips(["TRPMILES"], skip="auto")
    dup = pd.concat([t, t.iloc[:1]], ignore_index=True)
    with pytest.raises(NHTSIntegrityError, match="repeated rows"):
        A.aggregate(d, dup, "person", {"n": A.Agg.n()})
    r = A.aggregate(d, dup, "person", {"n": A.Agg.n()}, allow_duplicates=True)
    assert r["n"].sum() == len(dup)
    # a filtered frame: persons without rows are unknown by default, zero only on request
    part = t[t["TRPMILES"].notna()]
    assert np.isnan(A.aggregate(d, part, "person", {"n": A.Agg.n()})["n"]).sum() >= 1
    assert (A.aggregate(d, part, "person", {"n": A.Agg.n()}, empty="auto")["n"] >= 0).all()
    # first/last follow the trip number, not the row order of the frame
    shuffled = t.sample(frac=1.0, random_state=1)
    a = A.aggregate(d, shuffled, "person", {"f": A.Agg.first("TDTRPNUM")}, empty="auto")
    b = A.aggregate(d, t, "person", {"f": A.Agg.first("TDTRPNUM")}, empty="auto")
    assert a["f"].equals(b["f"])
    with pytest.raises(ValueError, match="order column"):
        A.aggregate(d, t.drop(columns="TDTRPNUM").assign(x=1.0), "person", {"f": A.Agg.first("x")})


def test_weighted_rank_ties_and_pooled_effect_size():
    r = eda._weighted_rank(np.array([1.0, 1.0, 2.0]), np.array([1.0, 3.0, 1.0]))
    assert r.tolist() == [3.0, 3.0, 5.0 - 0.5] or np.allclose(
        r, [2.0, 2.0, 4.5]
    )  # tie mid-rank (0+4)/2 = 2
    g = pd.DataFrame({"y": [0, 1, 0, 1, 10, 11, 10, 11.0], "g": list("aaaabbbb")})
    out = eda.compare_groups(g, "y", "g")
    assert out.loc["b", "std_diff"] == pytest.approx(20.0)  # pooled within-group sd 0.5


def test_split_by_household_does_not_depend_on_row_order():
    df = pd.DataFrame({"HOUSEID": np.repeat([f"H{i:03d}" for i in range(50)], 3), "x": range(150)})
    a, _ = transform.split_by_household(df, seed=5)
    b, _ = transform.split_by_household(df.sample(frac=1.0, random_state=2), seed=5)
    assert set(a["HOUSEID"]) == set(b["HOUSEID"])


def test_education_universe_is_adults_only(d):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PynhtsWarning)
        p = features.create_person_features(d, groups=["demographics"])
        hh = features.create_household_features(d, groups=["composition"])
    assert p["p_edu_status"].tolist() == [
        "answered",
        "not_applicable",
        "not_applicable",
        "answered",
    ]  # age 16 answered, outside 18+
    assert pd.isna(p["p_edu_cat"].iloc[1])
    assert (
        hh["hh_n_edu_answered"].tolist() == [1, 1] and hh["hh_share_univ"].iloc[0] == 1.0
    )  # only the 40-year-old counts
    assert hh["hh_n_age_unknown"].tolist() == [0, 0]


def test_unknown_inputs_have_companion_counts(d):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PynhtsWarning)
        pp = features.create_person_features(d, groups=["purposes"])
        hh = features.create_household_features(d, groups=["purposes", "fleet"])
    assert (
        pp["p_trips_unknown_purpose"].tolist() == [1, 0, 0, 0] and pp["p_work_trips"].iloc[0] == 1
    )
    assert hh["hh_trips_unknown_purpose"].tolist() == [1, 0] and hh[
        "hh_n_vehicles_age_unknown"
    ].tolist() == [1, 0]
    assert hh["hh_n_vehicles_new"].iloc[0] == 0 and np.isnan(hh["hh_fleet_median_age"].iloc[0])
    names = set(features.registry()["name"])
    assert {
        "hh_n_age_unknown",
        "hh_n_vehicles_age_unknown",
        "hh_trips_unknown_purpose",
        "p_trips_unknown_purpose",
    } <= names


def test_sample_characteristics_excludes_skips_and_nonanswers(d):
    p = d.persons(["EDUC"], missing="keep", skip="keep")
    t = tables.sample_characteristics(p, ["EDUC"], weight="WTPERFIN")
    assert "-1" not in set(t["Level"]) and t["Missing n"].iloc[0] == 1


def test_plots_report_clipped_weight_and_omit_missing_n(d):
    pytest.importorskip("matplotlib")
    import matplotlib

    matplotlib.use("Agg")
    from pynhts.viz import plots

    x = pd.Series(np.arange(100.0))
    w = pd.Series(np.ones(100))
    fig = plots.histogram(x, weight=w, clip_quantile=0.9)
    text = " ".join(t.get_text() for t in fig.axes[0].texts)
    assert "of the weight" in text and "top 0.5%" not in text
    fig2 = plots.bar_share(pd.Series(["a", "b"]), pd.Series([0.6, 0.4]))
    assert "n = 0" not in " ".join(t.get_text() for t in fig2.axes[0].texts)
