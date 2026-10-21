"""Reference solutions of the agent tasks: the way the package is meant to be used.

Each function takes a loader ``load(wave)`` and returns the number the task asks for. They are the
oracle's second leg: ``tasks.yaml`` stores the expected number, ``tests/data/test_agent_tasks.py``
checks that these functions reproduce it.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from typing import Any

import pynhts
from pynhts import harmonize, rates

Load = Callable[[int], Any]


def households_2009(load: Load) -> float:
    return float(load(2009).survey("household", ["HHSIZE"]).total().iloc[0]["estimate"] / 1e3)


def commute_time_2009(load: Load) -> float:
    s = load(2009).survey("person", ["TIMETOWK"])
    return float(s.mean("TIMETOWK").iloc[0]["estimate"])


def vmt_per_driver_trip_2009(load: Load) -> float:
    s = load(2009).survey("trip", ["VMT_MILE"])
    return float(s.mean("VMT_MILE").iloc[0]["estimate"])


def children_under_5_2001(load: Load) -> float:
    s = load(2001).survey("person", ["R_AGE"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", pynhts.core.flags.PynhtsWarning)
        res = s.total(domain=s.rows["R_AGE"] < 5)
    return float(res.iloc[0]["estimate"] / 1e3)


def daily_trips_per_person_2009(load: Load) -> float:
    return float(rates.daily_rate(load(2009), "trips", per="person").iloc[0]["estimate"])


def daily_trips_per_person_2022(load: Load) -> float:
    return float(rates.daily_rate(load(2022), "trips", per="person").iloc[0]["estimate"])


def long_distance_trips_2001(load: Load) -> float:
    s = load(2001).survey("longdist", ["BEGTRIP"])
    return float(s.total().iloc[0]["estimate"] / 1e6)


def _share(load: Load, wave: int, table: str, column: str, concept: str, category: str) -> float:
    s = load(wave).survey(table, [column])
    cat = harmonize.apply_column(s.rows, column, concept)
    res = s.proportion(cat == category, domain=cat.notna())
    return float(100 * res.iloc[0]["estimate"])


def walk_share_2009(load: Load) -> float:
    return _share(load, 2009, "trip", "TRPTRANS", "mode", "walk")


def urban_area_share_2001(load: Load) -> float:
    return _share(load, 2001, "household", "URBAN", "urban_area", "urban_area")


def vehicles_25_plus_2009(load: Load) -> float:
    d = load(2009)
    s = d.survey("vehicle", ["VEHAGE"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", pynhts.core.flags.PynhtsWarning)
        res = s.proportion(s.rows["VEHAGE"] >= 25, domain=s.rows["VEHAGE"].notna())
    return float(100 * res.iloc[0]["estimate"])


def persons_without_trips_2009(load: Load) -> float:
    s = load(2009).survey("person", ["CNTTDTR"])
    return float(s.total(domain=s.rows["CNTTDTR"] == 0).iloc[0]["estimate"] / 1e3)


def income_100k_share_2001(load: Load) -> float:
    return _share(load, 2001, "household", "HHFAMINC", "income", "100k_plus")


def transit_share_2017(load: Load) -> float:
    d = load(2017)
    s = d.survey("trip", ["TRPTRANS"])
    cat = harmonize.apply_column(s.rows, "TRPTRANS", "mode", level="summary")
    res = s.proportion(cat == "public_transit", domain=cat.notna())
    return float(100 * res.iloc[0]["estimate"])


def se_one_person_households_2009(load: Load) -> float:
    s = load(2009).survey("household", ["HHSIZE"])
    return float(s.total(domain=s.rows["HHSIZE"] == 1).iloc[0]["se"] / 1e3)


REFERENCE: dict[str, Callable[[Load], float]] = {
    "T01": households_2009, "T02": commute_time_2009, "T03": vmt_per_driver_trip_2009,
    "T04": children_under_5_2001, "T05": daily_trips_per_person_2009,
    "T06": daily_trips_per_person_2022, "T07": long_distance_trips_2001, "T08": walk_share_2009,
    "T09": urban_area_share_2001, "T10": vehicles_25_plus_2009, "T11": persons_without_trips_2009,
    "T12": income_100k_share_2001, "T13": transit_share_2017,
    "T14": se_one_person_households_2009,
}
