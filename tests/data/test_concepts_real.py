"""Checkable statements of the concept dictionary, on the real files. Run with: pytest -m data"""

from __future__ import annotations

import pytest

import pynhts

pytestmark = pytest.mark.data
WAVES = (2001, 2009, 2017, 2022)


@pytest.fixture(scope="module")
def d() -> dict[int, pynhts.NHTSData]:
    return {w: pynhts.load(w, offline=True) for w in WAVES}


def test_age_universe_and_missing_age(d):
    expected_min = {2001: 0, 2009: 5, 2017: 5, 2022: 5}
    expected_na = {2001: 2399, 2009: 0, 2017: 496, 2022: 0}
    for w in WAVES:
        age = d[w].persons(["R_AGE"], weight=False)["R_AGE"]
        assert age.min() == expected_min[w], w
        assert int(age.isna().sum()) == expected_na[w], w


def test_universes_of_worker_driver_and_education(d):
    # (variable, wave) -> (largest age that carries the skip code, smallest age that answers)
    expected = {
        ("WORKER", 2001): (14, 0), ("WORKER", 2009): (15, 16), ("WORKER", 2017): (15, 16),
        ("WORKER", 2022): (15, 16),
        ("DRIVER", 2001): (14, 0), ("DRIVER", 2009): (14, 15), ("DRIVER", 2017): (14, 15),
        ("DRIVER", 2022): (14, 15),
        ("EDUC", 2001): (15, 16), ("EDUC", 2009): (17, 18), ("EDUC", 2017): (13, 14),
        ("EDUC", 2022): (13, 14),
    }
    for (var, w), (skip_max, ans_min) in expected.items():
        p = d[w].persons(["R_AGE", var], weight=False, skip="keep")
        skipped = p[var].astype("string") == "-1"
        answered = ~skipped & p[var].notna()
        assert p.loc[skipped, "R_AGE"].max() == skip_max, (var, w)
        assert p.loc[answered, "R_AGE"].min() == ans_min, (var, w)


def test_primary_activity_is_asked_of_non_workers_only_in_2022(d):
    share = {}
    for w in WAVES:
        p = d[w].persons(["PRMACT"], weight=False, skip="keep")["PRMACT"].astype("string")
        share[w] = float((p == "-1").mean())
        if w == 2022:
            assert int((p == "-1").sum()) == 9752
    # 2022 skips more than half of the persons (the workers); the other waves only children
    assert share[2022] > 0.5 and max(share[w] for w in (2001, 2009, 2017)) < 0.25


def test_trip_duration_cap_and_distance_precision(d):
    cap = {2001: 1439, 2009: 1439, 2017: 1200, 2022: 1425}
    whole = {2001: 0.853, 2009: 0.835, 2017: 0.010, 2022: 0.012}
    for w in WAVES:
        t = d[w].trips(["TRVLCMIN", "TRPMILES"], weight=False, skip="nan")
        assert t["TRVLCMIN"].max() == cap[w], w
        miles = t["TRPMILES"].dropna()
        assert float((miles == miles.round()).mean()) == pytest.approx(whole[w], abs=0.002), w


def test_dwell_time_missing_share_is_structural(d):
    share = {2001: 0.218, 2009: 0.227, 2017: 0.237, 2022: 0.342}
    for w in WAVES:
        dwell = d[w].trips(["DWELTIME"], weight=False, skip="nan")["DWELTIME"]
        assert float(dwell.isna().mean()) == pytest.approx(share[w], abs=0.002), w


def test_change_of_mode_segments_are_trips_in_2017_and_2022_only(d):
    for w, code, pct in ((2017, "07", 1.07), (2022, "09", 0.69)):
        t = d[w].trips(["WHYTO", "WTTRDFIN"], weight=False)
        share = 100 * t["WTTRDFIN"][t["WHYTO"] == code].sum() / t["WTTRDFIN"].sum()
        assert share == pytest.approx(pct, abs=0.01), w
    for w in (2001, 2009):  # linked trips: there is no change-of-mode purpose at all
        codes = {c.code for c in d[w].schema("trip").columns["WHYTO"].codes}
        assert not any("change type" in c.label.lower()
                       for c in d[w].schema("trip").columns["WHYTO"].codes), codes


def test_item_nonresponse_of_self_reported_annual_miles_differs_by_wave(d):
    expected = {2001: 0.043, 2009: 0.022, 2017: 0.259, 2022: 0.015}  # share of vehicles
    for w in WAVES:
        v = d[w].vehicles(["ANNMILES"], weight=False, missing="keep", skip="keep")["ANNMILES"]
        dont_know = v.isin([-8, -9]) if w != 2017 and w != 2022 else v == -9
        if w in (2001, 2009):
            dont_know = v == -8
        assert float(dont_know.mean()) == pytest.approx(expected[w], abs=0.002), w


def test_vehicle_count_variable_matches_vehicle_rows_except_2009(d):
    rates = {}
    for w in WAVES:
        hh = d[w].households(["HHVEHCNT"], weight=False)
        rows = d[w].vehicles(weight=False, keys=True).groupby("HOUSEID").size()
        got = hh.set_index("HOUSEID")["HHVEHCNT"]
        counted = rows.reindex(got.index).fillna(0)
        rates[w] = float((counted != got).mean())
    assert rates[2009] == pytest.approx(0.0068, abs=0.0005)
    assert rates[2001] < 0.0005 and rates[2017] < 0.0005 and rates[2022] < 0.0005
