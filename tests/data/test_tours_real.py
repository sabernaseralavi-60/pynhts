"""Tour formation on the real NHTS 2017 trips. Run with: pytest -m data"""

from __future__ import annotations

import time

import pandas as pd
import pytest

import pynhts
from pynhts.tours import TourConfig, build_tours, chain_ids

pytestmark = pytest.mark.data
PK = ["HOUSEID", "PERSONID"]
TRANSIT = {"11", "14", "15", "16"}


@pytest.fixture(scope="module")
def data() -> pynhts.NHTSData:
    return pynhts.load(2017, offline=True, replicates=True)


@pytest.fixture(scope="module")
def trips(data) -> pd.DataFrame:
    t = data.trips(["WHYFROM", "WHYTO", "TRPTRANS", "DWELTIME"], weight=False, missing="keep")
    t["transit"] = t["TRPTRANS"].isin(TRANSIT)
    return t


@pytest.fixture(scope="module")
def mr(trips) -> pynhts.tours.TourResult:
    return build_tours(trips, TourConfig.mcnally_rafiq())


def test_structural_invariants_on_all_trips(mr, trips):
    t, tours = mr.trips, mr.tours
    assert len(t) == len(trips) == 923_572 and int(tours["n_trips"].sum()) == 923_572
    assert tours["tour_class"].isin(["HBW", "HBO", "NHB"]).all()
    # a tour numbers from 0 and its trips are consecutive
    assert (t.groupby(PK)["tour"].min() == 0).all()
    last = t.groupby([*PK, "tour"])["trip_in_tour"].max() + 1
    assert (last.to_numpy() == tours["n_trips"].to_numpy()).all()
    # only the last trip of a complete tour arrives at home
    home = t["activity"] == "H"
    complete = t["tour_complete"]
    assert home[complete].groupby([t["HOUSEID"], t["PERSONID"], t["tour"]]).sum().eq(1).all()
    # classes are exhaustive and HBW tours contain work
    assert (tours.loc[tours["tour_class"] == "HBW", "n_work"] > 0).all()
    assert (tours.loc[tours["tour_class"] == "NHB", "complete"] == False).all()  # noqa: E712


def test_formation_is_fast_enough(trips):
    start = time.perf_counter()
    build_tours(trips, TourConfig.mcnally_rafiq())
    assert time.perf_counter() - start < 60  # about 10 s on a laptop; loose bound on purpose


def test_transit_user_sample_matches_mcnally_rafiq_exactly(mr):
    t = mr.trips
    users = t[t["day_complete"] & t.groupby(PK)["transit"].transform("any")]
    assert users.groupby(PK).ngroup().nunique() == 4_994
    assert len(users) == 20_222
    assert int(users["transit"].sum()) == 10_011


def _hbw_transit_tours(res, data):
    age = data.persons(["R_AGE"], weight=False)[[*PK, "R_AGE"]]
    on_transit = res.trips.groupby([*PK, "tour"])["transit"].any().rename("transit_tour")
    tours = res.tours.merge(age, on=PK).merge(on_transit.reset_index(), on=[*PK, "tour"])
    return tours[(tours["tour_class"] == "HBW") & tours["transit_tour"] & (tours["R_AGE"] >= 18)]


def test_hbw_transit_tours_close_to_the_published_counts(mr, data):
    hbw = _hbw_transit_tours(mr, data)
    # published: 2,454 tours and 2,448 persons
    assert len(hbw) == 2_456 and hbw.groupby(PK).ngroup().nunique() == 2_451
    share = hbw["pattern"].value_counts(normalize=True) * 100
    assert share["(0,0,0)"] == pytest.approx(49.2, abs=0.1)  # published 49
    kinds = hbw["work_type"].value_counts(normalize=True) * 100
    assert kinds["simple"] == pytest.approx(46.5, abs=0.1)
    assert kinds["complex"] == pytest.approx(30.5, abs=0.1)
    assert kinds["work_based"] == pytest.approx(20.4, abs=0.1)
    assert int((hbw["work_type"] == "multi_work").sum()) == 67  # published 70


def test_default_config_treats_work_from_home_as_home(trips, data):
    hbw = _hbw_transit_tours(build_tours(trips), data)
    assert len(hbw) == 2_471 and hbw.groupby(PK).ngroup().nunique() == 2_466


def test_work_code_choice_matters(trips, data):
    cfg = TourConfig(home_codes=frozenset({"01"}), work_codes=frozenset({"03", "04"}))
    assert len(_hbw_transit_tours(build_tours(trips, cfg), data)) == 2_535


def test_chains_with_fhwa_threshold_are_a_refinement_of_person_days(trips):
    ids = chain_ids(trips, TourConfig.fhwa_chained())
    sorted_trips = build_tours(trips).trips
    assert len(ids) == len(sorted_trips)
    per_day = ids.groupby([sorted_trips["HOUSEID"], sorted_trips["PERSONID"]]).max() + 1
    assert per_day.min() >= 1 and per_day.max() < 50


def test_weighted_tour_estimates_tie_back_to_the_trip_survey(mr, data):
    tours = mr.tours.copy()
    s = data.survey_rows(tours, "trip")
    # trips are carried by tours, so the weighted total of n_trips equals the trip survey total
    trip_total = data.survey("trip", []).total().iloc[0]["estimate"]
    assert s.total("n_trips").iloc[0]["estimate"] == pytest.approx(trip_total, rel=1e-9)
    shares = s.proportion(tours["tour_class"] == "HBW").iloc[0]
    assert 0.1 < shares["estimate"] < 0.6 and shares["moe"] > 0 and shares["n"] == len(tours)
    by_class = s.total(by="tour_class")
    assert list(by_class["tour_class"]) == ["HBO", "HBW", "NHB"] and (by_class["se"] > 0).all()
