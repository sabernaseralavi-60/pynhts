"""Unit tests for aggregate, features, validity, eda, transform, quality and the new tables helpers.

A tiny synthetic NHTS-2017-shaped wave (three households) is written to Parquet; every expected
number below is worked out by hand in the comments.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pynhts import aggregate as A
from pynhts import answer_status, eda, features, quality, tables, transform, valid
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
        {
            "HOUSEID": ["H1", "H2", "H3"],
            "HHSIZE": [3, 2, 1],
            "HHVEHCNT": [2, 0, 1],
            "WTHHFIN": [100.0, 200.0, 300.0],
        },
        {"HOUSEID"},
    )
    _write(
        tmp_path,
        "person",
        {
            "HOUSEID": ["H1", "H1", "H1", "H2", "H2", "H3"],
            "PERSONID": ["01", "02", "03", "01", "02", "01"],
            "R_AGE": [40, 38, 10, 70, 68, 30],
            "EDUC": ["04", "03", "-1", "-7", "05", "05"],
            "WORKER": ["01", "02", "-1", "02", "-9", "01"],
            "DRIVER": ["01", "01", "-1", "02", "01", "01"],
            "WTPERFIN": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        },
        {"HOUSEID", "PERSONID", "EDUC", "WORKER", "DRIVER"},
    )
    _write(
        tmp_path,
        "trip",
        {
            "HOUSEID": ["H1", "H1", "H1", "H1", "H3", "H3"],
            "PERSONID": ["01", "01", "01", "02", "01", "01"],
            "TDTRPNUM": ["01", "02", "03", "01", "01", "02"],
            "TRPMILES": [5.0, 3.0, 1.0, -9.0, 20.0, 2.0],
            "TRVLCMIN": [10.0, 8.0, 5.0, 12.0, 30.0, 10.0],
            "STRTTIME": ["0730", "1215", "1830", "0900", "0800", "2300"],
            "DRVR_FLG": ["01", "01", "-1", "01", "02", "02"],
            "TRPTRANS": ["03", "03", "01", "03", "11", "02"],
            "WHYTRP1S": ["10", "01", "40", "10", "10", "01"],
            "WTTRDFIN": [10.0, 10.0, 10.0, 20.0, 60.0, 60.0],
        },
        {"HOUSEID", "PERSONID", "TDTRPNUM", "STRTTIME", "DRVR_FLG", "TRPTRANS", "WHYTRP1S"},
    )
    _write(
        tmp_path,
        "vehicle",
        {
            "HOUSEID": ["H1", "H1", "H3"],
            "VEHID": ["01", "02", "01"],
            "VEHAGE": [3, 12, 40],
            "VEHTYPE": ["01", "04", "03"],
            "FUELTYPE": ["01", "02", "01"],
            "WTHHFIN": [100.0, 100.0, 300.0],
        },
        {"HOUSEID", "VEHID", "VEHTYPE", "FUELTYPE"},
    )
    return NHTSData(2017, tmp_path)


# ---- valid ----
def test_valid_separates_answers_skips_and_nonanswers():
    s = pd.Series(["01", "-1", "-7", None, "02", "-9"])
    assert valid(s).tolist() == [True, False, False, False, True, False]
    assert answer_status(s).tolist() == [
        "answered",
        "skip",
        "nonanswer",
        "blank",
        "answered",
        "nonanswer",
    ]
    assert valid(pd.Series([1.0, -1.0, -7.0, np.nan])).tolist() == [True, False, False, False]


# ---- aggregate ----
def test_trip_to_person_counts_and_true_zeros(d):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PynhtsWarning)
        r = A.aggregate(d, "trip", "person", {"n": A.Agg.n(), "miles": A.Agg.sum("TRPMILES")})
    assert len(r) == 6  # one row per person, file order kept
    assert r["n"].tolist() == [3, 1, 0, 0, 0, 2]  # persons without trips are true zeros
    assert r["miles"].tolist()[0] == 9.0  # 5 + 3 + 1
    assert np.isnan(r["miles"].iloc[1])  # the only trip of H1/02 has no distance
    assert r["miles"].iloc[2] == 0.0 and r["miles"].iloc[5] == 22.0
    rep = r.attrs["pynhts_aggregate"]
    assert rep.n_targets_with_source == 3 and rep.n_targets_without_source == 3
    assert r.attrs["pynhts"]["weight"] == "WTPERFIN" and "WTPERFIN" in r


def test_missing_skip_ignores_unknown_values(d):
    r = A.aggregate(d, "trip", "person", {"miles": A.Agg.sum("TRPMILES")}, missing="skip")
    # H1/02's only trip has an unknown distance: under "skip" the sum of nothing known is NaN
    assert np.isnan(r["miles"].iloc[1]) and r["miles"].iloc[0] == 9.0
    rep = r.attrs["pynhts_aggregate"]
    assert rep.specs["miles"]["rows_with_missing_input"] == 1


def test_where_share_any_first_last_quantile(d):
    specs = {
        "walk": A.Agg.n(A.Where("TRPTRANS", "==", "01")),
        "work_share": A.Agg.share(A.Where("WHYTRP1S", "==", "10")),
        "any_bus": A.Agg.any(A.Where("TRPTRANS", "in", ("11", "12"))),
        "first_mode": A.Agg.first("TRPTRANS"),
        "last_mode": A.Agg.last("TRPTRANS"),
        "long": A.Agg.n(A.Where("TRPMILES", ">=", 4) & A.Where("TRVLCMIN", "<=", 30)),
        "med_min": A.Agg.median("TRVLCMIN"),
        "q": A.Agg.quantile("TRVLCMIN", 1.0),
        "n_modes": A.Agg.nunique("TRPTRANS"),
    }
    r = A.aggregate(d, "trip", "person", specs, missing="skip")
    p = r.iloc[0]
    assert p["walk"] == 1 and p["work_share"] == pytest.approx(1 / 3) and not p["any_bus"]
    assert (p["first_mode"], p["last_mode"]) == ("03", "01")  # in trip-number order
    assert p["long"] == 1 and p["med_min"] == 8.0 and p["q"] == 10.0 and p["n_modes"] == 2
    h3 = r.iloc[5]
    assert bool(h3["any_bus"]) and h3["n_modes"] == 2
    assert np.isnan(r["work_share"].iloc[2])  # no trips: a share is undefined
    assert r["first_mode"].isna().iloc[2]


def test_empty_policy_nan_refuses_the_zero(d):
    r = A.aggregate(d, "trip", "person", {"n": A.Agg.n()}, empty="nan")
    assert r["n"].iloc[0] == 3 and np.isnan(r["n"].iloc[2])


def test_trip_to_household_and_vehicle_to_household(d):
    t = A.aggregate(d, "trip", "household", {"n": A.Agg.n()})
    assert t["n"].tolist() == [4, 0, 2]
    v = A.aggregate(d, "vehicle", "household", {"n_veh": A.Agg.n(), "old": A.Agg.max("VEHAGE")})
    assert v["n_veh"].tolist() == [2, 0, 1] and v["old"].iloc[0] == 12.0
    assert v.attrs["pynhts"]["weight"] == "WTHHFIN"


def test_target_must_be_an_ancestor_and_names_must_not_collide(d):
    with pytest.raises(ValueError, match="not an ancestor"):
        A.aggregate(d, "household", "trip", {"n": A.Agg.n()})
    with pytest.raises(ValueError, match="collides"):
        A.aggregate(d, "trip", "household", {"HHSIZE": A.Agg.n()}, base_columns=["HHSIZE"])
    with pytest.raises(ValueError):
        A.Agg("median")  # a column is required
    with pytest.raises(ValueError):
        A.Where("TRPMILES", "~", 1)


def test_orphan_rows_raise_or_are_reported(d):
    t = d.trips(["TRPMILES"]).copy()
    t = pd.concat(
        [
            t,
            pd.DataFrame(
                {"HOUSEID": ["H9"], "PERSONID": ["01"], "TDTRPNUM": ["01"], "TRPMILES": [1.0]}
            ),
        ]
    )
    with pytest.raises(NHTSIntegrityError, match="no person row"):
        A.aggregate(d, t, "person", {"n": A.Agg.n()})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PynhtsWarning)
        r = A.aggregate(d, t, "person", {"n": A.Agg.n()}, orphans="report")
    assert r["n"].sum() == 6 and r.attrs["pynhts_aggregate"].n_orphan_source_rows == 1


# ---- features ----
@pytest.fixture
def hh(d):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PynhtsWarning)
        return features.create_household_features(d)


def test_household_composition(hh):
    h1, h2, h3 = hh.iloc[0], hh.iloc[1], hh.iloc[2]
    assert (h1.hh_n_persons_listed, h1.hh_n_adults, h1.hh_n_children, h1.hh_n_older) == (3, 2, 1, 0)
    assert (h1.hh_n_workers, h1.hh_n_drivers, h1.hh_n_unlisted) == (
        1,
        2,
        0,
    )  # -1 is not applicable, not "no"
    assert (h1.hh_n_univ, h1.hh_n_edu_answered, h1.hh_share_univ) == (1, 2, 0.5)
    # H2: unknown worker status of one member and an unknown education of another
    assert (h2.hh_n_workers, h2.hh_n_workers_unknown) == (0, 1)
    assert (h2.hh_n_edu_answered, h2.hh_n_edu_unknown, h2.hh_share_univ) == (1, 1, 1.0)
    assert h2.hh_n_older == 2 and h3.hh_n_adults == 1


def test_strict_makes_counts_with_unknowns_nan(d):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PynhtsWarning)
        s = features.create_household_features(d, groups=["composition"], strict=True)
    assert np.isnan(s["hh_n_workers"].iloc[1]) and s["hh_n_workers"].iloc[0] == 1


def test_resources_and_zero_vehicle(hh):
    assert hh["hh_veh_per_person"].tolist() == pytest.approx([2 / 3, 0.0, 1.0])
    assert hh["hh_veh_per_driver"].tolist() == pytest.approx([1.0, 0.0, 1.0])
    assert hh["hh_zero_vehicle"].tolist() == [False, True, False]


def test_household_travel_modes_and_entropy(hh):
    assert hh["hh_n_trips"].tolist() == [4, 0, 2]
    assert hh["hh_zero_trip"].tolist() == [False, True, False]
    assert hh["hh_trips_mode_private_vehicle"].tolist() == [3, 0, 0]
    assert hh["hh_trips_mode_walk"].iloc[0] == 1 and hh["hh_trips_mode_public_transit"].iloc[2] == 1
    assert hh["hh_mode_share_private_vehicle"].iloc[0] == pytest.approx(0.75)
    assert np.isnan(hh["hh_mode_share_walk"].iloc[1])  # zero-trip household
    assert hh["hh_n_modes"].tolist() == [2, 0, 2] and hh["hh_multimodal"].tolist() == [
        True,
        False,
        True,
    ]
    assert hh["hh_mode_entropy"].iloc[2] == pytest.approx(np.log(2))
    assert np.isnan(hh["hh_mode_entropy"].iloc[1])
    assert hh["hh_trips_purpose_work"].tolist() == [2, 0, 1]
    # known + unknown mode always equals the trip count
    mode_cols = [c for c in hh.columns if c.startswith("hh_trips_mode_")]
    assert (
        hh[mode_cols].sum(axis=1) + hh["hh_trips_unknown_mode"] - hh["hh_n_trips"]
    ).abs().sum() == 0


def test_miles_propagate_versus_skip_and_vmt(d):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PynhtsWarning)
        p = features.create_household_features(d, groups=["travel"])
        s = features.create_household_features(d, groups=["travel"], miles_missing="skip")
    assert np.isnan(p["hh_miles"].iloc[0]) and s["hh_miles"].iloc[0] == 9.0
    assert p["hh_miles"].iloc[1] == 0.0 and p["hh_miles"].iloc[2] == 22.0
    assert s["hh_vmt"].iloc[0] == 8.0  # driver trips in private vehicles: 5 + 3
    assert s["hh_vmt"].iloc[2] == 0.0  # a bus passenger and a cyclist drive no vehicle miles


def test_fleet_and_vehicle_features(d):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PynhtsWarning)
        f = features.create_household_features(d, groups=["fleet"])
        v = features.create_vehicle_features(d)
    assert f["hh_n_vehicles_listed"].tolist() == [2, 0, 1]
    assert f["hh_fleet_median_age"].iloc[0] == 7.5 and np.isnan(f["hh_fleet_median_age"].iloc[1])
    assert f["hh_n_vehicles_new"].tolist() == [1, 0, 0]
    assert v["v_age_band"].astype(str).tolist() == ["3-5", "11-15", "16+"]
    assert v["v_type"].tolist() == ["car", "pickup", "suv"] and v["v_fuel"].tolist() == [
        "gasoline",
        "diesel",
        "gasoline",
    ]


def test_person_and_trip_features(d):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PynhtsWarning)
        p = features.create_person_features(d)
        t = features.create_trip_features(d)
    assert p["p_n_trips"].tolist() == [3, 1, 0, 0, 0, 2] and p["p_any_trip"].tolist() == [
        True,
        True,
        False,
        False,
        False,
        True,
    ]
    assert p["p_worker"].tolist() == ["yes", "no", "not_applicable", "no", "unknown", "yes"]
    assert p["p_edu_cat"].tolist()[:2] == ["bachelor", "some_college_assoc"] and pd.isna(
        p["p_edu_cat"].iloc[2]
    )
    assert p["p_edu_status"].tolist()[2:5] == ["not_applicable", "unknown", "answered"]
    assert p["p_work_trips"].iloc[0] == 1 and p["p_nonwork_trips"].iloc[0] == 2
    assert t["t_order"].tolist() == [1, 2, 3, 1, 1, 2]
    assert t["t_is_first"].tolist() == [True, False, False, True, True, False]
    assert t["t_is_last"].tolist() == [False, False, True, True, False, True]
    assert t["t_distance_band"].astype("string").fillna("nan").tolist() == [
        "5-10",
        "3-5",
        "1-3",
        "nan",
        "10-25",
        "1-3",
    ]
    assert t["t_depart_period"].tolist() == [
        "am_peak",
        "midday",
        "pm_peak",
        "midday",
        "am_peak",
        "night",
    ]
    assert t["t_mode_group"].tolist()[:3] == ["private_vehicle", "private_vehicle", "walk"]
    assert t["t_is_work"].tolist() == [True, False, False, True, True, False]


def test_registry_documents_every_feature_and_groups_are_checked(d):
    reg = features.registry()
    assert {
        "name",
        "level",
        "formula",
        "eligibility",
        "missing",
        "denominator",
        "weighting",
        "waves",
    } <= set(reg.columns)
    assert reg["name"].is_unique and set(reg["level"]) == {"person", "household", "trip", "vehicle"}
    assert (reg["formula"].str.len() > 3).all()
    assert features.describe_feature("hh_share_univ").denominator.startswith("members who answered")
    with pytest.raises(KeyError):
        features.describe_feature("nope_feature")
    with pytest.raises(ValueError, match="unknown group"):
        features.create_household_features(d, groups=["bogus"])
    # lineage travels with the result
    cols = features.create_trip_features(d, groups=["sequence"])
    assert (
        "t_order" in cols.attrs["pynhts_features"]["features"]
        or cols.attrs["pynhts_features"]["level"] == "trip"
    )


# ---- eda ----
def test_missing_report_and_describe(d):
    p = d.persons(["EDUC", "R_AGE"], missing="keep", skip="keep")
    m = eda.missing_report(p, ["EDUC"])
    assert m.loc["EDUC", ["answered", "skip", "nonanswer"]].tolist() == [4, 1, 1]
    desc = eda.describe(p, ["R_AGE", "EDUC"], weight="WTPERFIN")
    row = desc[desc["column"] == "R_AGE"].iloc[0]
    assert row["n"] == 6 and row["mean"] == pytest.approx(
        np.average([40, 38, 10, 70, 68, 30], weights=[1, 2, 3, 4, 5, 6])
    )
    assert desc.attrs["weighted"] is True
    assert eda.weighted_quantile(pd.Series([1, 2, 3, 4]), pd.Series([1, 1, 1, 1]), 0.5) == 2.0


def test_correlation_refuses_nominal_and_keeps_weights_honest():
    rng = np.random.default_rng(0)
    x = rng.normal(size=300)
    df = pd.DataFrame(
        {
            "x": x,
            "y": x + rng.normal(size=300) * 0.3,
            "w": rng.uniform(1, 3, 300),
            "c": rng.choice(["a", "b"], 300),
        }
    )
    with pytest.raises(TypeError, match="nominal"):
        eda.correlation_matrix(df, ["x", "c"])
    pr = eda.correlation_matrix(df, ["x", "y"])
    assert (
        pr.r.loc["x", "y"] > 0.9
        and pr.ci_low is not None
        and pr.ci_low.loc["x", "y"] < pr.r.loc["x", "y"]
    )
    wr = eda.correlation_matrix(df, ["x", "y"], weight="w", method="spearman")
    assert wr.ci_low is None and any("no interval" in n for n in wr.notes)
    kr = eda.correlation_matrix(df, ["x", "y"], method="kendall")
    assert 0.6 < kr.r.loc["x", "y"] < 1
    with pytest.raises(ValueError):
        eda.correlation_matrix(df, ["x", "y"], method="kendall", weight="w")
    # an unweighted vector equals the numpy value
    assert pr.r.loc["x", "y"] == pytest.approx(np.corrcoef(df["x"], df["y"])[0, 1])


def test_cramers_v_and_group_comparison():
    a = pd.Series(["u", "u", "v", "v"] * 50)
    assert eda.cramers_v(a, a) > 0.95
    assert eda.cramers_v(a, pd.Series(["p", "q"] * 100)) < 0.1
    df = pd.DataFrame({"v": [1.0, 2.0, 3.0, 4.0], "g": ["a", "a", "b", "b"], "w": [1, 1, 1, 3]})
    g = eda.compare_groups(df, "v", "g", weight="w")
    assert g.loc["b", "mean"] == pytest.approx(3.75) and g.loc["b", "diff_vs_ref"] == pytest.approx(
        2.25
    )
    cmp = eda.compare_distributions(df["v"], df["v"] + 10)
    assert cmp.attrs["ks_distance"] == 1.0


# ---- transform ----
def test_transformer_fits_on_training_only_and_round_trips_json():
    rng = np.random.default_rng(1)
    df = pd.DataFrame(
        {
            "x": rng.lognormal(1.0, 0.8, 500),
            "z": rng.normal(5, 2, 500),
            "h": np.repeat(np.arange(100), 5),
        }
    )
    train, test = transform.split_by_household(df, test_size=0.2, seed=3, group="h")
    assert set(train["h"]).isdisjoint(set(test["h"])) and len(train) + len(test) == len(df)
    tr = transform.Transformer({"x": "boxcox", "z": "standardize"}).fit(train)
    out = tr.transform(test)
    assert "x" in out and "x__boxcox" in out and out["x"].equals(test["x"])  # originals untouched
    assert abs(tr.params["x"]["lambda"]) < 0.3  # lognormal -> lambda near 0
    again = transform.Transformer.from_json(tr.to_json()).transform(test)
    assert np.allclose(again["z__standardize"], out["z__standardize"])
    assert abs(tr.transform(train)["z__standardize"].mean()) < 1e-9
    with pytest.raises(ValueError, match="zero or negative"):
        transform.Transformer({"z": "log"}).fit(pd.DataFrame({"z": [0.0, 1.0, 2.0]}))
    with pytest.raises(RuntimeError):
        transform.Transformer({"z": "sqrt"}).transform(df)
    diag = transform.diagnostics(df["x"], np.log(df["x"]))
    assert abs(diag.loc["skewness", "after"]) < abs(diag.loc["skewness", "before"])
    assert "zeros" in transform.recommend(pd.Series([0.0] * 50 + [1.0, 2.0, 100.0]))[0]


# ---- quality, tables ----
def test_quality_report_flags_orphans(d, tmp_path):
    rep = quality.report(d)
    assert (
        rep.ok
        and rep.tables.loc["trip", "rows"] == 6
        and rep.tables.loc["person", "orphan_rows"] == 0
    )
    assert "OK" in str(rep)


def test_sample_characteristics_and_exports(tmp_path, d):
    p = d.persons(["EDUC", "R_AGE"], missing="nan", skip="nan")
    t = tables.sample_characteristics(
        p, ["R_AGE", "EDUC"], weight="WTPERFIN", labels={"R_AGE": "Age"}
    )
    assert {"Characteristic", "Level", "n", "Estimate", "Missing n"} == set(t.columns)
    assert "weighted with WTPERFIN" in t.attrs["notes"]
    html_ = tables.to_html(t, caption="Table 1")
    assert html_.startswith("<table><caption>Table 1") and "weighted with WTPERFIN" in html_
    tables.to_csv(t, str(tmp_path / "t1.csv"))
    assert (tmp_path / "t1.csv.notes.txt").exists()


def test_plots_label_weighting(d):
    pytest.importorskip("matplotlib")
    import matplotlib

    matplotlib.use("Agg")
    from pynhts.viz import plots

    p = d.persons(["R_AGE"])
    fig = plots.histogram(p["R_AGE"], weight=p["WTPERFIN"], bins=5)
    assert any("weighted; n = 6" in t.get_text() for t in fig.axes[0].texts)
    fig2 = plots.histogram(p["R_AGE"], bins=5)
    assert any("unweighted sample" in t.get_text() for t in fig2.axes[0].texts)
    out = Path(d.directory) / "f.svg"
    plots.save(fig, str(out))
    assert out.exists()
    with pytest.raises(ValueError):
        plots.save(fig, "x.jpg")
