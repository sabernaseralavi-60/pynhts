"""Reproduction of the control totals of the 2022 NHTS Data User Guide (Tables 10 and 11).

The guide prints unweighted case counts and weighted sums "to help users verify the correctness
of their tabulations". They are the only published numbers that tie the public 2022 files to the
weights, so each one is a target here. Definitions follow the guide:

* households, persons, vehicles (``WTHHFIN``), trips (``WTTRDFIN``): all rows;
* workers ``WORKER == "01"`` and drivers ``DRIVER == "01"`` among persons;
* person miles of travel: ``TRPMILES`` over all trips (the 14 trips whose distance is -9 add
  nothing; the guide's *case* count for PMT is the unweighted sum of those miles);
* vehicle trips: trips on which the respondent drove (``DRVR_FLG == "01"``);
* vehicle miles: ``VMT_MILE`` on those trips (-9 adds nothing).

Targets whose published value this library does not reproduce are kept, with their expected
status ``not_reproduced``, and are explained in ``ug2022.yaml``.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from typing import TYPE_CHECKING

import pandas as pd

from pynhts.stats.survey import TaylorSurvey

if TYPE_CHECKING:
    from pynhts.core.data import NHTSData

Result = tuple[float, float]


def _taylor(survey: object) -> TaylorSurvey:
    if not isinstance(survey, TaylorSurvey):
        raise TypeError("recipe ug2022 needs NHTS 2022")
    return survey


class Context:
    """Lazily built surveys shared by all targets of the recipe."""

    def __init__(self, data: NHTSData) -> None:
        """Bind the context to an opened 2022 :class:`~pynhts.NHTSData`."""
        self.data = data

    @cached_property
    def households(self) -> TaylorSurvey:
        return _taylor(self.data.survey("household", ["HHSIZE"]))

    @cached_property
    def persons(self) -> TaylorSurvey:
        return _taylor(self.data.survey("person", ["WORKER", "DRIVER"]))

    @cached_property
    def vehicles(self) -> TaylorSurvey:
        return _taylor(self.data.survey("vehicle", ["VEHID"]))

    @cached_property
    def trips(self) -> TaylorSurvey:
        return _taylor(self.data.survey("trip", ["TRPMILES", "DRVR_FLG", "VMT_MILE"]))

    @cached_property
    def driven(self) -> pd.Series:
        """Trips on which the respondent drove."""
        driven: pd.Series = self.trips.rows["DRVR_FLG"] == "01"
        return driven


def _pair(frame: pd.DataFrame) -> Result:
    row = frame.iloc[0]
    return float(row["estimate"]), float(row["moe"])


def _cases(n: float) -> Result:
    return float(n), 0.0


def hh_cases(ctx: Context) -> Result:
    return _cases(len(ctx.households.rows))


def hh_weighted(ctx: Context) -> Result:
    return _pair(ctx.households.total())


def per_cases(ctx: Context) -> Result:
    return _cases(len(ctx.persons.rows))


def per_weighted(ctx: Context) -> Result:
    return _pair(ctx.persons.total())


def veh_cases(ctx: Context) -> Result:
    return _cases(len(ctx.vehicles.rows))


def veh_weighted(ctx: Context) -> Result:
    return _pair(ctx.vehicles.total())


def trips_cases(ctx: Context) -> Result:
    return _cases(len(ctx.trips.rows))


def trips_weighted(ctx: Context) -> Result:
    return _pair(ctx.trips.total())


def workers_cases(ctx: Context) -> Result:
    return _cases((ctx.persons.rows["WORKER"] == "01").sum())


def workers_weighted(ctx: Context) -> Result:
    return _pair(ctx.persons.total(domain=ctx.persons.rows["WORKER"] == "01"))


def drivers_cases(ctx: Context) -> Result:
    return _cases((ctx.persons.rows["DRIVER"] == "01").sum())


def drivers_weighted(ctx: Context) -> Result:
    return _pair(ctx.persons.total(domain=ctx.persons.rows["DRIVER"] == "01"))


def pmt_cases(ctx: Context) -> Result:
    return _cases(ctx.trips.rows["TRPMILES"].sum())


def pmt_weighted(ctx: Context) -> Result:
    return _pair(ctx.trips.total("TRPMILES"))


def vtrips_cases(ctx: Context) -> Result:
    return _cases(ctx.driven.sum())


def vtrips_weighted(ctx: Context) -> Result:
    return _pair(ctx.trips.total(domain=ctx.driven))


def vmt_cases(ctx: Context) -> Result:
    return _cases(ctx.trips.rows["VMT_MILE"][ctx.driven].sum())


def vmt_weighted(ctx: Context) -> Result:
    return _pair(ctx.trips.total("VMT_MILE", domain=ctx.driven))


COMPUTE: dict[str, Callable[[Context], Result]] = {
    f.__name__: f
    for f in (
        hh_cases, hh_weighted, per_cases, per_weighted, veh_cases, veh_weighted, trips_cases,
        trips_weighted, workers_cases, workers_weighted, drivers_cases, drivers_weighted,
        pmt_cases, pmt_weighted, vtrips_cases, vtrips_weighted, vmt_cases, vmt_weighted,
    )
}
