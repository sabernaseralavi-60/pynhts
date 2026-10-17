"""Replication of McNally & Rafiq (2021), transit users' tours, from the public 2017 NHTS.

Source: McNally, M. G. and Rafiq, R. (2021). *Analysis of Activity-Travel Patterns and Tour
Formation of Transit Users*. Final Report PSR-19-33, METRANS / ITS-Irvine, sections 2.1-2.5.

The report works with **unweighted counts and percentages**, so every result here is unweighted
and carries no margin of error (``moe`` is NaN). Definitions that reproduce the report:

* transit modes ``TRPTRANS`` in 11, 14, 15, 16 (rail users: 15 and 16; bus users: 11 and 14);
* *transit users*: persons whose day starts and ends at home (work-from-home counts as home at day
  level) and who made at least one transit trip;
* *home-based work tours with transit*: complete tours of adults (18+) that contain a work stop
  (``WHYTO == "03"``) and at least one transit trip, with tours closed by ``01`` only
  (:meth:`pynhts.tours.TourConfig.mcnally_rafiq`).
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from typing import TYPE_CHECKING

import pandas as pd

from pynhts.tours import TourConfig, TourResult, build_tours

if TYPE_CHECKING:
    from pynhts.core.data import NHTSData

Result = tuple[float, float]
PK = ["HOUSEID", "PERSONID"]
TRANSIT = {"11", "14", "15", "16"}
RAIL, BUS = {"15", "16"}, {"11", "14"}
NAN = float("nan")


class Context:
    """Lazily built samples shared by all targets."""

    def __init__(self, data: NHTSData) -> None:
        """Bind the context to an opened :class:`~pynhts.NHTSData`."""
        self.data = data

    @cached_property
    def formed(self) -> TourResult:
        trips = self.data.trips(["WHYFROM", "WHYTO", "TRPTRANS"], weight=False, missing="keep")
        trips["transit"] = trips["TRPTRANS"].isin(TRANSIT)
        return build_tours(trips, TourConfig.mcnally_rafiq())

    @cached_property
    def user_trips(self) -> pd.DataFrame:
        t = self.formed.trips
        selected: pd.DataFrame = t[t["day_complete"] & t.groupby(PK)["transit"].transform("any")]
        return selected

    @cached_property
    def users(self) -> pd.DataFrame:
        """One row per transit user with household and personal characteristics."""
        cols = ["R_AGE", "R_SEX", "R_RACE", "WORKER", "HHSIZE", "NUMADLT", "HHVEHCNT", "DRVRCNT",
                "HHFAMINC", "HBPPOPDN", "RAIL"]
        ids = self.user_trips[PK].drop_duplicates()
        persons = self.data.persons(cols, weight=False)
        out = ids.merge(persons, on=PK, how="left", validate="1:1")
        flags = self.user_trips.assign(
            rail=self.user_trips["TRPTRANS"].isin(RAIL), bus=self.user_trips["TRPTRANS"].isin(BUS)
        ).groupby(PK)[["rail", "bus"]].any().reset_index()
        merged: pd.DataFrame = out.merge(flags, on=PK, how="left", validate="1:1")
        return merged

    @cached_property
    def hbw(self) -> pd.DataFrame:
        """Home-based work tours of adults with at least one transit trip on the tour."""
        res = self.formed
        adults = self.data.persons(["R_AGE"], weight=False)[[*PK, "R_AGE"]]
        on_transit = res.trips.groupby([*PK, "tour"])["transit"].any().rename("transit_tour")
        tours = res.tours.merge(adults, on=PK).merge(on_transit.reset_index(), on=[*PK, "tour"])
        keep = (tours["tour_class"] == "HBW") & tours["transit_tour"] & (tours["R_AGE"] >= 18)
        result: pd.DataFrame = tours[keep]
        return result


def _count(x: float) -> Result:
    return float(x), NAN


def _pct(mask: pd.Series) -> Result:
    return 100.0 * float(mask.mean()), NAN


def users_persons(c: Context) -> Result:
    return _count(len(c.users))


def users_trips(c: Context) -> Result:
    return _count(len(c.user_trips))


def users_transit_trips(c: Context) -> Result:
    return _count(int(c.user_trips["transit"].sum()))


def hbw_tours(c: Context) -> Result:
    return _count(len(c.hbw))


def hbw_persons(c: Context) -> Result:
    return _count(c.hbw.groupby(PK).ngroup().nunique())


def pattern_000_share(c: Context) -> Result:
    return _pct(c.hbw["pattern"] == "(0,0,0)")


def complex_share(c: Context) -> Result:
    return _pct(c.hbw["work_type"] == "complex")


def work_based_share(c: Context) -> Result:
    return _pct(c.hbw["work_type"] == "work_based")


def multi_work_tours(c: Context) -> Result:
    return _count(int((c.hbw["work_type"] == "multi_work").sum()))


def t21_hh1(c: Context) -> Result:
    return _pct(c.users["HHSIZE"] == 1)


def t21_hh2(c: Context) -> Result:
    return _pct(c.users["HHSIZE"] == 2)


def t21_hh3plus(c: Context) -> Result:
    return _pct(c.users["HHSIZE"] > 2)


def t21_veh0(c: Context) -> Result:
    return _pct(c.users["HHVEHCNT"] == 0)


def t21_veh1(c: Context) -> Result:
    return _pct(c.users["HHVEHCNT"] == 1)


def t21_veh2plus(c: Context) -> Result:
    return _pct(c.users["HHVEHCNT"] > 1)


def t21_inc_low(c: Context) -> Result:
    return _pct(c.users["HHFAMINC"].isin(["01", "02", "03", "04"]))


def t21_inc_mid(c: Context) -> Result:
    return _pct(c.users["HHFAMINC"].isin(["05", "06", "07"]))


def t21_inc_high(c: Context) -> Result:
    return _pct(c.users["HHFAMINC"].isin(["08", "09", "10", "11"]))


def t21_child(c: Context) -> Result:
    return _pct(c.users["HHSIZE"] > c.users["NUMADLT"])


def t21_veh_per_driver(c: Context) -> Result:
    u = c.users
    return _pct((u["HHVEHCNT"] > 0) & (u["HHVEHCNT"] >= u["DRVRCNT"]))


def t21_age_u18(c: Context) -> Result:
    return _pct(c.users["R_AGE"] < 18)


def t21_age_18_38(c: Context) -> Result:
    return _pct(c.users["R_AGE"].between(18, 38))


def t21_age_39_58(c: Context) -> Result:
    return _pct(c.users["R_AGE"].between(39, 58))


def t21_age_59plus(c: Context) -> Result:
    return _pct(c.users["R_AGE"] > 58)


def t21_male(c: Context) -> Result:
    return _pct(c.users["R_SEX"] == "01")


def t21_employed(c: Context) -> Result:
    return _pct(c.users["WORKER"] == "01")


def t21_white(c: Context) -> Result:
    return _pct(c.users["R_RACE"] == "01")


def t21_rail(c: Context) -> Result:
    return _pct(c.users["rail"])


def t21_bus(c: Context) -> Result:
    return _pct(c.users["bus"])


def _density(c: Context) -> pd.Series:
    return pd.to_numeric(c.users["HBPPOPDN"], errors="coerce")


def t21_dens_low(c: Context) -> Result:
    return _pct(_density(c) <= 1500)


def t21_dens_mid(c: Context) -> Result:
    d = _density(c)
    return _pct((d >= 3000) & (d <= 7000))


def t21_dens_high(c: Context) -> Result:
    return _pct(_density(c) >= 17000)


def t21_msa_rail(c: Context) -> Result:
    return _pct(c.users["RAIL"] == "01")


COMPUTE: dict[str, Callable[[Context], Result]] = {
    f.__name__: f
    for f in (
        users_persons, users_trips, users_transit_trips, hbw_tours, hbw_persons,
        pattern_000_share, complex_share, work_based_share, multi_work_tours,
        t21_hh1, t21_hh2, t21_hh3plus, t21_veh0, t21_veh1, t21_veh2plus, t21_inc_low,
        t21_inc_mid, t21_inc_high, t21_child, t21_veh_per_driver, t21_age_u18, t21_age_18_38,
        t21_age_39_58, t21_age_59plus, t21_male, t21_employed, t21_white, t21_rail, t21_bus,
        t21_dens_low, t21_dens_mid, t21_dens_high, t21_msa_rail,
    )
}
