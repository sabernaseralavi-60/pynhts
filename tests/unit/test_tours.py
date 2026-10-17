"""Tour formation on small hand-built days, with expected results worked out by hand."""

from __future__ import annotations

import pandas as pd
import pytest

from pynhts.tours import TourConfig, build_tours, chain_ids

HOME, WORK, SHOP, WFH = "01", "03", "11", "02"


def day(house, person, purposes, dwell=None):
    """Trips of one person-day; ``purposes`` = [origin, dest1, dest2, ...]."""
    n = len(purposes) - 1
    return pd.DataFrame({
        "HOUSEID": house, "PERSONID": person,
        "TDTRPNUM": [f"{i + 1:02d}" for i in range(n)],
        "WHYFROM": purposes[:-1], "WHYTO": purposes[1:],
        "DWELTIME": dwell if dwell is not None else [60.0] * n,
    })


@pytest.fixture
def trips():
    parts = [
        day("A", "01", [HOME, WORK, SHOP, HOME, SHOP, HOME, WORK]),    # HBW complex, HBO, NHB
        day("B", "01", [HOME, SHOP, WORK, SHOP, WORK, HOME]),          # work-based (1,0,1)
        day("C", "01", [HOME, WORK, WORK, HOME]),                      # multi_work
        day("D", "01", [HOME, WFH, SHOP, HOME]),                       # work-from-home
        day("E", "01", [HOME, WORK, HOME]),                            # simple
        day("F", "01", [HOME, SHOP, SHOP, SHOP, WORK, SHOP, HOME]),    # complex (3,1,0)
    ]
    return pd.concat(parts, ignore_index=True)


def tour_row(res, house, tour):
    t = res.tours
    return t[(t["HOUSEID"] == house) & (t["tour"] == tour)].iloc[0]


def test_tours_close_at_every_arrival_at_home_and_flags(trips):
    res = build_tours(trips)
    a = res.tours[res.tours["HOUSEID"] == "A"].sort_values("tour")
    assert list(a["n_trips"]) == [3, 2, 1]
    assert list(a["activities"]) == ["WNH", "NH", "W"]
    assert list(a["complete"]) == [True, True, False]
    assert list(a["tour_class"]) == ["HBW", "HBO", "NHB"]
    assert not a["day_complete"].any()           # the day ends at work
    assert build_tours(trips).tours.query("HOUSEID == 'E'")["day_complete"].all()


def test_work_tour_patterns_and_types(trips):
    res = build_tours(trips)
    expect = {"A": ("complex", "(0,1,0)"), "B": ("work_based", "(1,0,1)"),
              "C": ("multi_work", "(0,0,0)"), "E": ("simple", "(0,0,0)"),
              "F": ("complex", "(3,1,0)")}
    for house, (kind, pattern) in expect.items():
        row = tour_row(res, house, 0)
        assert (row["work_type"], row["pattern"]) == (kind, pattern), house
    assert pd.isna(tour_row(res, "A", 1)["work_type"])          # HBO tour has no work type
    assert tour_row(res, "C", 0)["n_work"] == 2


def test_trip_table_is_tagged_and_sorted(trips):
    res = build_tours(trips.sample(frac=1, random_state=3))     # shuffled input
    t = res.trips
    assert list(t.columns[-6:]) == ["invalid_purpose", "tour", "trip_in_tour", "tour_complete",
                                    "day_complete", "activity"]
    a = t[t["HOUSEID"] == "A"]
    assert list(a["tour"]) == [0, 0, 0, 1, 1, 2] and list(a["trip_in_tour"]) == [0, 1, 2, 0, 1, 0]
    assert list(a["activity"]) == ["W", "N", "H", "N", "H", "W"]
    assert len(t) == len(trips)


def test_trip_numbers_sort_numerically_not_alphabetically():
    t = day("Z", "01", [HOME] + [SHOP] * 11 + [HOME])
    t["TDTRPNUM"] = [str(i + 1) for i in range(12)]            # "1".."12": alphabetically 10 < 2
    res = build_tours(t.sample(frac=1, random_state=1))
    assert list(res.trips["TDTRPNUM"]) == [str(i) for i in range(1, 13)]
    assert res.tours.iloc[0]["n_trips"] == 12


def test_work_from_home_switch(trips):
    default = build_tours(trips)
    d = default.tours[default.tours["HOUSEID"] == "D"].sort_values("tour")
    assert list(d["activities"]) == ["H", "NH"]                 # arriving at "02" closes a tour
    assert list(d["tour_class"]) == ["HBO", "HBO"]
    strict = build_tours(trips, TourConfig(home_codes=frozenset({HOME})))
    d = strict.tours[strict.tours["HOUSEID"] == "D"]
    assert list(d["activities"]) == ["NNH"] and list(d["tour_class"]) == ["HBO"]


def test_mcnally_rafiq_preset_uses_different_home_sets_for_day_and_tour(trips):
    cfg = TourConfig.mcnally_rafiq()
    assert cfg.home_codes == {HOME} and cfg.day_home == {HOME, WFH}
    d = build_tours(trips, cfg).tours.query("HOUSEID == 'D'").iloc[0]
    assert d["complete"] and d["day_complete"]                  # day rule accepts "02" as home


def test_invalid_purposes_are_flagged_and_can_be_dropped():
    t = pd.concat([day("A", "01", [HOME, WORK, HOME]), day("B", "01", [HOME, "-9", HOME]),
                   day("C", "01", [HOME, None, HOME])], ignore_index=True)
    res = build_tours(t)
    assert res.tours.set_index("HOUSEID")["has_invalid"].to_dict() == {"A": False, "B": True,
                                                                       "C": True}
    assert res.trips["invalid_purpose"].sum() == 4
    kept = build_tours(t, TourConfig(drop_invalid=True))
    assert list(kept.tours["HOUSEID"]) == ["A"] and set(kept.trips["HOUSEID"]) == {"A"}


def test_extra_columns_are_carried_and_required_columns_checked(trips):
    trips = trips.assign(TRPTRANS="03")
    assert "TRPTRANS" in build_tours(trips).trips.columns
    with pytest.raises(ValueError, match="required"):
        build_tours(trips.drop(columns="WHYTO"))


def test_chain_ids_use_anchors_and_dwell_threshold():
    t = day("A", "01", [HOME, SHOP, SHOP, WORK, HOME], dwell=[20.0, 45.0, 480.0, -9.0])
    ids = chain_ids(t, TourConfig.fhwa_chained())
    # trip 1 ends at a 20-minute stop (kept inside the chain); trip 2 ends at a 45-minute stop
    assert list(ids) == [0, 0, 1, 2]
    assert list(chain_ids(t, threshold=60.0)) == [0, 0, 0, 1]   # a 60-minute rule keeps 45 inside
    with pytest.raises(ValueError, match="DWELTIME"):
        chain_ids(t.drop(columns="DWELTIME"))
