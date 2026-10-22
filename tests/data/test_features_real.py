"""Real-data validation of the 0.7.0 feature, aggregation, trend and quality layers.

Run with: pytest -m data. The strongest check is independent: in every household with a
complete roster, our worker and driver counts equal the survey WRKCOUNT and DRVRCNT.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

import pynhts
from pynhts import aggregate as A
from pynhts import features, quality, rates, trends
from pynhts.core.flags import PynhtsWarning

pytestmark = pytest.mark.data
WAVES = (2001, 2009, 2017, 2022)


@pytest.fixture(scope="module", params=WAVES)
def wave(request):
    d = pynhts.load(request.param, offline=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PynhtsWarning)
        hh = features.create_household_features(d)
    return d, hh


def test_member_counts_equal_the_official_counts_in_complete_rosters(wave):
    d, hh = wave
    off = d.households(["WRKCOUNT", "DRVRCNT"], missing="nan")
    m = hh.merge(off[["HOUSEID", "WRKCOUNT", "DRVRCNT"]], on="HOUSEID")
    full = m[m["hh_n_unlisted"] == 0]
    assert len(full) > 0.8 * len(m)
    for ours, theirs in (("hh_n_workers", "WRKCOUNT"), ("hh_n_drivers", "DRVRCNT")):
        ref = pd.to_numeric(full[theirs])
        ok = ref.notna()
        assert (full.loc[ok, ours] == ref[ok]).all(), (
            f"{ours} differs from {theirs} in a complete roster"
        )


def test_household_trips_and_modes_add_up(wave):
    d, hh = wave
    assert hh["hh_n_trips"].sum() == len(d.trips([]))
    mode_cols = [c for c in hh.columns if c.startswith("hh_trips_mode_")]
    gap = hh[mode_cols].sum(axis=1) + hh["hh_trips_unknown_mode"] - hh["hh_n_trips"]
    assert (gap == 0).all()
    assert len(hh) == len(d.households([])) and hh["HOUSEID"].is_unique


def test_person_trip_counts_equal_the_survey_count_where_it_exists(wave):
    d, _ = wave
    if "CNTTDTR" not in d.columns("person"):
        pytest.skip("no CNTTDTR in this wave")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PynhtsWarning)
        p = A.aggregate(d, "trip", "person", {"n": A.Agg.n()}, base_columns=["CNTTDTR"])
    ref = pd.to_numeric(p["CNTTDTR"])
    ok = ref.notna()
    share = float((p.loc[ok, "n"] == ref[ok]).mean())
    assert share > 0.97, f"person trip counts agree with CNTTDTR for only {share:.3f}"


def test_trip_sequence_is_complete(wave):
    d, _ = wave
    t = features.create_trip_features(d, groups=["sequence"])
    persons_with_trips = t[["HOUSEID", "PERSONID"]].drop_duplicates()
    assert t["t_is_first"].sum() == len(persons_with_trips) == t["t_is_last"].sum()


def test_quality_report_is_clean_for_every_wave(wave):
    d, _ = wave
    rep = quality.report(d)
    assert rep.ok, str(rep)


def test_vehicle_features_cover_all_vehicles(wave):
    d, _ = wave
    v = features.create_vehicle_features(d)
    assert len(v) == len(d.vehicles([])) and v["v_type"].notna().mean() > 0.95


def test_2017_published_totals_through_the_new_layer():
    """Lidbe et al. 2021 Table 1 (2017): 8.60 household and 3.37 person trips per day."""
    d = pynhts.load(2017, offline=True)
    assert rates.daily_rate(d, "trips", per="person")["estimate"].iloc[0] == pytest.approx(
        3.37, abs=0.005
    )
    assert rates.daily_rate(d, "trips", per="household")["estimate"].iloc[0] == pytest.approx(
        8.60, abs=0.005
    )


def test_trip_shares_are_distributions_and_per_wave():
    sh = trends.trip_shares("mode", waves=(2009, 2017))
    assert set(sh["wave"]) == {2009, 2017}
    assert np.allclose(sh.groupby("wave")["share"].sum(), 1.0, atol=1e-9)
    pv = sh[(sh["category"] == "private_vehicle")]
    assert (pv["share"] > 0.75).all() and (pv["moe"] < 0.01).all()


def test_wave_means_warns_for_trip_distance_and_pool_refuses_it():
    with pytest.warns(PynhtsWarning, match="NOT comparable"):
        out = trends.wave_means("trip", "TRPMILES", waves=(2009, 2017), min_age=5)
    assert (
        out["mean"].iloc[1] > out["mean"].iloc[0]
    )  # routed 2017 distances are longer than self-reports
    with pytest.raises(ValueError, match="not comparable"):
        trends.pool((2009, 2017), "trip", ["TRPMILES"])
    with pytest.warns(PynhtsWarning):
        p = trends.pool((2009, 2017), "person", ["R_AGE", "R_SEX"], harmonize_concepts={})
    assert set(p["wave"]) == {2009, 2017}
    assert np.allclose(p.groupby("wave")["w_norm"].mean(), 1.0)
