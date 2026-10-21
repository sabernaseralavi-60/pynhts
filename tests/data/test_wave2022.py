"""NHTS 2022 on the real files. Run with: pytest -m data

Three independent oracles: the codebook (every code frequency, unweighted and weighted), the
User Guide control totals (recipe ``ug2022``) and R's ``survey`` package (golden file produced by
``tools/validate_taylor_r.R``).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import pynhts
from pynhts import recipes
from pynhts.stats import TaylorSurvey

pytestmark = pytest.mark.data
GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "taylor_2022_r.csv"
LUMPED = {"-88": "-8", "-77": "-7"}


@pytest.fixture(scope="module")
def data() -> pynhts.NHTSData:
    return pynhts.load(2022, offline=True)


def test_tables_and_row_counts(data):
    assert data.tables == ("household", "person", "trip", "vehicle", "longdist")
    assert data.variance_method == "taylor"
    sizes = {t: len(data.table(t)) for t in data.tables}
    assert sizes == {"household": 7893, "person": 16997, "trip": 31074, "vehicle": 14684,
                     "longdist": 16997}
    for t in data.tables:
        key = list(data.key(t))
        assert not data.table(t, key, weight=False)[key].duplicated().any(), t


def test_every_codebook_frequency_reproduces(data):
    """All 2,639 code lines of the 2022 codebook: unweighted n and weighted n."""
    checked = 0
    for table in data.tables:
        s, w = data.schema(table), data.weight_column(table)
        df = data.table(table, missing="keep", skip="keep")
        wt = df[w].to_numpy()
        for name, col in s.columns.items():
            for k in col.codes:
                members = [k.code]
                if k.code in LUMPED and not col.is_string:
                    members.append(LUMPED[k.code])
                mask = np.zeros(len(df), dtype=bool)
                for code in members:
                    hit = df[name] == (code if col.is_string else float(code))
                    mask |= hit.fillna(False).to_numpy(dtype=bool)
                if k.n is not None:
                    assert int(mask.sum()) == k.n, (table, name, k.code)
                if k.weighted is not None:
                    assert wt[mask].sum() == pytest.approx(k.weighted, rel=1e-6), (
                        table, name, k.code)
                checked += 1
    assert checked == 2639


def test_user_guide_control_totals(data):
    table = recipes.run("ug2022", data)
    wrong = table[table["status"] != table["expected"]]
    assert wrong.empty, wrong[["id", "published", "estimate", "status"]]
    counts = table["status"].value_counts().to_dict()
    assert counts == {"reproduced": 15, "not_reproduced": 3}


def test_child_files_copy_the_household_stratum(data):
    hh = data.households(["STRATUMID"], weight=False).set_index("HOUSEID")["STRATUMID"]
    assert hh.nunique() == 20 and hh.notna().all()  # 18 strata + 2 Alaska/Hawaii substrata
    for table in ("person", "trip", "vehicle"):
        child = data.table(table, ["STRATUMID"], weight=False)
        assert (child["STRATUMID"].to_numpy() == hh.loc[child["HOUSEID"]].to_numpy()).all()


def test_weight_sets_cover_the_right_days(data):
    hh = data.households(["TRAVDAY"], weights="all")
    wd = data.households(weights="weekday")["WTHHFIN5D"]
    we = data.households(weights="weekend")["WTHHFIN2D"]
    assert wd.sum() == pytest.approx(hh["WTHHFIN"].sum(), rel=1e-9)
    assert we.sum() == pytest.approx(hh["WTHHFIN"].sum(), rel=1e-9)
    assert ((wd > 0) & (we > 0)).sum() == 0  # a household has either weekday or weekend weight
    with pytest.raises(ValueError, match="weights must be"):
        data.weight_column("household", "monthly")


def test_no_replicate_weights_in_2022(data):
    with pytest.raises(ValueError, match="no replicate weights"):
        data.replicate_weights("household")


# -- Taylor-series estimator against R's survey package ----------------------------------------
def _estimates(data: pynhts.NHTSData) -> dict[str, tuple[float, float, float]]:
    """The same estimands as tools/validate_taylor_r.R: id -> (estimate, se, df)."""
    out: dict[str, tuple[float, float, float]] = {}

    def put(name: str, frame: pd.DataFrame, svy: TaylorSurvey, row: int = 0) -> None:
        out[name] = (float(frame["estimate"].iloc[row]), float(frame["se"].iloc[row]),
                     float(frame["df"].iloc[row]))

    hh = data.survey("household", ["HHSIZE", "HHVEHCNT", "CENSUS_R"])
    assert isinstance(hh, TaylorSurvey)
    put("hh_total", hh.total(), hh)
    put("hh_mean_size", hh.mean("HHSIZE"), hh)
    put("hh_share_no_vehicle", hh.proportion(hh.rows["HHVEHCNT"] == 0), hh)
    by = hh.mean("HHSIZE", by="CENSUS_R")
    for i, code in enumerate(by["CENSUS_R"]):
        put(f"hh_mean_size_region_{code}", by, hh, i)
    hh5 = data.survey("household", ["HHSIZE"], weights="weekday")
    assert isinstance(hh5, TaylorSurvey)
    put("hh_total_weekday_weights", hh5.total(), hh5)

    pe = data.survey("person", ["WORKER", "R_AGE", "R_SEX"])
    assert isinstance(pe, TaylorSurvey)
    worker = pe.rows["WORKER"] == "01"
    put("per_total", pe.total(), pe)
    put("per_workers_total", pe.total(domain=worker), pe)
    put("per_share_workers", pe.proportion(worker), pe)
    ok = pe.rows["R_AGE"] >= 0
    put("per_mean_age", pe.mean("R_AGE", domain=ok), pe)
    by = pe.mean("R_AGE", domain=ok & pe.rows["R_SEX"].notna(), by="R_SEX")
    for i, code in enumerate(by["R_SEX"]):
        put(f"per_mean_age_sex_{code}", by, pe, i)

    for suffix, clusters in (("", "all"), ("_observed", "observed")):
        tr = data.survey("trip", ["TRPMILES", "TRPTRANS"], clusters=clusters)
        assert isinstance(tr, TaylorSurvey)
        walk = tr.rows["TRPTRANS"] == "20"
        put(f"trip_total{suffix}", tr.total(), tr)
        put(f"trip_share_walk{suffix}", tr.proportion(walk), tr)
        if not suffix:
            put("trip_pmt_total", tr.total("TRPMILES"), tr)
            put("trip_mean_miles", tr.mean("TRPMILES"), tr)
            put("trip_total_domain_walk", tr.total(domain=walk), tr)
        ve = data.survey("vehicle", ["VEHID"], clusters=clusters)
        put(f"veh_total{suffix}", ve.total(), ve)

    from pynhts.stats import ratio_across

    tr = data.survey("trip", ["TRPMILES"])
    r = ratio_across(tr, None, hh, None)
    out["trips_per_household"] = (float(r["estimate"][0]), float(r["se"][0]), hh.df)  # whole design
    return out


def test_taylor_estimator_matches_r_survey_package(data):
    golden = pd.read_csv(GOLDEN, dtype={"id": str}).set_index("id")
    ours = _estimates(data)
    assert set(ours) == set(golden.index)
    for name, (est, se, df) in ours.items():
        ref = golden.loc[name]
        assert est == pytest.approx(ref["estimate"], rel=1e-9, abs=1e-9), name
        assert se == pytest.approx(ref["se"], rel=1e-9, abs=1e-12), name
        assert df == ref["df"], name


def test_ignoring_childless_households_understates_the_error(data):
    """R/SAS run on the trip file alone drop households without trips; the design keeps them."""
    full = data.survey("trip", ["TRPMILES"]).total()["se"][0]
    observed = data.survey("trip", ["TRPMILES"], clusters="observed").total()["se"][0]
    assert full > observed * 1.02  # +3.5 % here (5.857e9 against 5.660e9)


def test_survey_rows_binds_user_rows_to_trip_weights(data):
    trips = data.trips(["TRPMILES"])
    some = trips.iloc[::2][["HOUSEID", "PERSONID", "TRIPID", "TRPMILES"]]
    svy = data.survey_rows(some, "trip")
    assert isinstance(svy, TaylorSurvey) and len(svy.rows) == len(some)
    assert svy.total()["estimate"][0] == pytest.approx(
        trips.iloc[::2]["WTTRDFIN"].sum(), rel=1e-12
    )
