"""Unit tests for the Taylor-series engine against row-level brute force (no real data)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pynhts.core.data import NHTSData
from pynhts.io.registry import load_registry, supported_waves
from pynhts.stats import TaylorSurvey, ratio_across, t_ppf, taylor_variance


def _design(seed: int = 1):
    """3 strata of 4 households; each household has 1-3 persons; weights vary."""
    rng = np.random.default_rng(seed)
    n_hh = 12
    stratum = np.repeat([10, 20, 30], 4)
    n_per = rng.integers(1, 4, n_hh)
    hh_of_person = np.repeat(np.arange(n_hh), n_per)
    w = rng.uniform(50, 150, len(hh_of_person))
    y = rng.normal(10, 3, len(hh_of_person))
    rows = pd.DataFrame({"y": y, "g": rng.integers(0, 2, len(hh_of_person))})
    return rows, w, hh_of_person, stratum, n_hh


def _brute_total_var(y, w, hh, stratum, n_hh):
    z = np.bincount(hh, weights=w * y, minlength=n_hh)
    var = 0.0
    for h in np.unique(stratum):
        zc = z[stratum == h]
        var += len(zc) / (len(zc) - 1) * ((zc - zc.mean()) ** 2).sum()
    return z.sum(), var


def test_total_matches_brute_force_ultimate_cluster_formula():
    rows, w, hh, stratum, n_hh = _design()
    s = TaylorSurvey(rows, np.arange(len(rows)), w, hh, stratum)
    out = s.total("y")
    est, var = _brute_total_var(rows["y"].to_numpy(), w, hh, stratum, n_hh)
    assert out["estimate"][0] == pytest.approx(est)
    assert out["se"][0] == pytest.approx(np.sqrt(var))
    assert s.df == n_hh - 3
    assert out["moe"][0] == pytest.approx(t_ppf(0.975, n_hh - 3) * np.sqrt(var))


def test_mean_and_ratio_match_delta_method_by_hand():
    rows, w, hh, stratum, n_hh = _design(3)
    y = rows["y"].to_numpy()
    x = np.abs(rows["y"].to_numpy()) + 1
    rows["x"] = x
    s = TaylorSurvey(rows, np.arange(len(rows)), w, hh, stratum)
    r_hat = (w * y).sum() / (w * x).sum()
    lin = w * (y - r_hat * x) / (w * x).sum()
    _, var = _brute_total_var(lin, np.ones_like(w), hh, stratum, n_hh)
    out = s.ratio("y", "x")
    assert out["estimate"][0] == pytest.approx(r_hat)
    assert out["se"][0] == pytest.approx(np.sqrt(var))
    m = s.mean("y")
    lin_m = w * (y - (w * y).sum() / w.sum()) / w.sum()
    _, var_m = _brute_total_var(lin_m, np.ones_like(w), hh, stratum, n_hh)
    assert m["se"][0] == pytest.approx(np.sqrt(var_m))


def test_domain_keeps_empty_clusters_in_the_design():
    rows, w, hh, stratum, n_hh = _design(5)
    dom = rows["g"].to_numpy() == 1
    s = TaylorSurvey(rows, np.arange(len(rows)), w, hh, stratum)
    out = s.total("y", domain=dom)
    est, var = _brute_total_var(rows["y"].to_numpy() * dom, w, hh, stratum, n_hh)
    assert out["estimate"][0] == pytest.approx(est)
    assert out["se"][0] == pytest.approx(np.sqrt(var))
    live = np.unique(hh[dom])
    assert out["df"][0] == len(live) - len(np.unique(stratum[live]))  # like survey::degf


def test_groups_equal_separate_domains():
    rows, w, hh, stratum, _ = _design(7)
    s = TaylorSurvey(rows, np.arange(len(rows)), w, hh, stratum)
    by = s.mean("y", by="g")
    for g in (0, 1):
        one = s.mean("y", domain=rows["g"] == g)
        assert by.loc[by["g"] == g, "se"].iloc[0] == pytest.approx(one["se"][0])
        assert by.loc[by["g"] == g, "df"].iloc[0] == one["df"][0]


def test_zero_weight_units_stay_in_variance_but_not_in_df():
    rows, w, hh, stratum, n_hh = _design(9)
    w = w.copy()
    w[hh == 0] = 0.0  # household 0 is outside this day type
    s = TaylorSurvey(rows, np.arange(len(rows)), w, hh, stratum)
    assert s.df == (n_hh - 1) - 3
    _, var = _brute_total_var(rows["y"].to_numpy(), w, hh, stratum, n_hh)
    assert s.total("y")["se"][0] == pytest.approx(np.sqrt(var))


def test_ratio_across_two_tables_equals_stacked_design():
    rows, w, hh, stratum, n_hh = _design(11)
    people = TaylorSurvey(rows, np.arange(len(rows)), w, hh, stratum)
    hh_rows = pd.DataFrame({"one": np.ones(n_hh)})
    w_hh = np.linspace(200.0, 400.0, n_hh)
    homes = TaylorSurvey(hh_rows, np.arange(n_hh), w_hh, np.arange(n_hh), stratum)
    out = ratio_across(people, "y", homes, "one")
    # stack both tables under one design: numerator on person rows, denominator on household rows
    stacked = pd.DataFrame({
        "num": np.r_[rows["y"].to_numpy(), np.zeros(n_hh)],
        "den": np.r_[np.zeros(len(rows)), np.ones(n_hh)],
    })
    st = TaylorSurvey(stacked, np.arange(len(stacked)), np.r_[w, w_hh],
                      np.r_[hh, np.arange(n_hh)], stratum)
    ref = st.ratio("num", "den")
    assert out["estimate"][0] == pytest.approx(ref["estimate"][0])
    assert out["se"][0] == pytest.approx(ref["se"][0])


def test_single_cluster_stratum_is_an_error_not_a_guess():
    with pytest.raises(ValueError, match="single cluster"):
        taylor_variance(np.array([[1.0], [2.0], [3.0]]), np.array([0, 0, 1]))
    rows = pd.DataFrame({"y": [1.0, 2.0, 3.0]})
    with pytest.raises(ValueError, match="at least two"):
        TaylorSurvey(rows, np.arange(3), np.ones(3), np.arange(3), np.array([0, 0, 1]))


def test_mixing_variance_designs_is_refused():
    from pynhts.stats import Survey

    rows, w, hh, stratum, n_hh = _design(2)
    t = TaylorSurvey(rows, np.arange(len(rows)), w, hh, stratum)
    j = Survey(rows, np.arange(len(rows)), w, np.ones((len(rows), 98)))
    with pytest.raises(TypeError, match="same variance design"):
        ratio_across(t, "y", j, "y")


# -- NHTSData on a tiny synthetic 2022-like directory ------------------------------------------
def _write(directory: Path, name: str, columns: dict[str, list], strings: set[str]) -> None:
    arrays = {k: pa.array(v, type=pa.string() if k in strings else pa.float64())
              for k, v in columns.items()}
    pq.write_table(pa.table(arrays), directory / f"{name}.parquet")


@pytest.fixture
def d22(tmp_path: Path) -> NHTSData:
    ids = [f"H{i}" for i in range(6)]
    _write(tmp_path, "household", {
        "HOUSEID": ids, "STRATUMID": ["1", "1", "1", "2", "2", "2"],
        "HHSIZE": [1, 2, 3, 2, 1, 4], "WTHHFIN": [10.0, 20, 30, 40, 50, 60],
        "WTHHFIN5D": [0.0, 25, 35, 45, 0, 65], "WTHHFIN2D": [15.0, 0, 0, 0, 55, 0]},
        {"HOUSEID", "STRATUMID"})
    _write(tmp_path, "trip", {
        "HOUSEID": ["H0", "H0", "H1", "H3", "H5"], "PERSONID": ["01"] * 5,
        "TRIPID": ["01", "02", "01", "01", "01"], "TRPMILES": [1.0, 2, 3, 4, 5],
        "WTTRDFIN": [11.0, 12, 21, 41, 61]}, {"HOUSEID", "PERSONID", "TRIPID"})
    return NHTSData(2022, tmp_path)


def test_taylor_wave_loader_binds_rows_to_clusters(d22):
    assert d22.variance_method == "taylor"
    assert d22.key("trip") == ("HOUSEID", "PERSONID", "TRIPID")
    hh = d22.survey("household", ["HHSIZE"])
    assert isinstance(hh, TaylorSurvey) and hh.n_clusters == 6 and hh.n_strata == 2
    assert hh.total()["estimate"][0] == pytest.approx(210.0)
    tr = d22.survey("trip", ["TRPMILES"])
    assert tr.n_clusters == 6  # households without a trip stay in the design
    assert tr.total("TRPMILES")["estimate"][0] == pytest.approx(11 + 24 + 63 + 164 + 305)
    obs = d22.survey("trip", ["TRPMILES"], clusters="observed")
    assert obs.n_clusters == 4
    with pytest.raises(ValueError, match="clusters must be"):
        d22.survey("trip", ["TRPMILES"], clusters="some")  # type: ignore[arg-type]


def test_weight_sets_and_unsupported_calls(d22):
    assert d22.weight_column("household", "weekday") == "WTHHFIN5D"
    assert d22.weight_column("trip", "weekend") == "WTTRDFIN2D"
    wd = d22.survey("household", ["HHSIZE"], weights="weekday")
    assert wd.total()["estimate"][0] == pytest.approx(170.0)
    assert wd.df == (4 - 2)  # four weighted households in two strata
    with pytest.raises(ValueError, match="no replicate weights"):
        d22.replicate_weights("household")
    old_wave = NHTSData(2017, d22.directory)
    assert "longdist" not in old_wave.tables and "longdist" in d22.tables
    with pytest.raises(ValueError, match="unknown table"):
        old_wave.table("longdist")
    with pytest.raises(ValueError, match="weights must be one of"):
        old_wave.survey("household", weights="weekday")


def test_registry_describes_both_variance_designs():
    assert supported_waves() == [2017, 2022]
    r17, r22 = load_registry(2017), load_registry(2022)
    assert (r17.variance_method, r22.variance_method) == ("jkn", "taylor")
    assert "replicates" in r17.groups and r22.groups == ("core",)
    assert set(r22.tables) == {"household", "person", "trip", "vehicle", "longdist"}
    assert r22.variance["strata"] == "STRATUMID" and r22.variance["cluster"] == "HOUSEID"
    assert r22.members["tripv2pub.csv"].rows == 31074
