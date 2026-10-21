"""Replication of Tables 1 and 3 of FHWA's *Summary of Travel Trends: 2017 NHTS*.

Each ``compute`` function returns ``(estimate, margin_of_error)`` in the units of the report
(before the division by the target's ``scale``). Definitions follow the report and the NHTS
variables:

* household size bands: ``HHSIZE``; person age bands: the imputed age ``R_AGE_IMP``;
* drivers ``DRIVER == "01"``; workers ``WORKER == "01"``;
* person trips and person miles: all trips and ``TRPMILES`` (trips whose distance is -9 add 0
  miles but still count as trips);
* vehicle trips and vehicle miles: trips on which the respondent drove (``DRVR_FLG == "01"``)
  and ``VMT_MILE`` (-1 treated as 0 miles);
* rates per person/driver use one survey; rates per household divide person-weighted totals by
  household-weighted households (:func:`pynhts.stats.ratio_across`).
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from pynhts.stats.survey import Survey, TaylorSurvey, ratio_across

if TYPE_CHECKING:
    from pynhts.core.data import NHTSData

Result = tuple[float, float]


def _jkn(survey: Survey | TaylorSurvey) -> Survey:
    """This recipe reproduces published JKn margins of error, so it needs the 2017 replicates."""
    if not isinstance(survey, Survey):
        raise TypeError("recipe stt2017 needs NHTS 2017 (replicate weights)")
    return survey


class Context:
    """Lazily built surveys shared by all targets of the recipe."""

    def __init__(self, data: NHTSData) -> None:
        """Bind the context to an opened :class:`~pynhts.NHTSData`."""
        self.data = data

    @cached_property
    def households(self) -> Survey:
        return _jkn(self.data.survey("household", ["HHSIZE"]))

    @cached_property
    def persons(self) -> Survey:
        return _jkn(self.data.survey("person", ["R_AGE_IMP", "DRIVER", "WORKER"]))

    @cached_property
    def trips(self) -> Survey:
        return _jkn(self.data.survey("trip", ["TRPMILES"]))

    @cached_property
    def person_travel(self) -> Survey:
        """Person survey carrying each person's daily trip and mile totals."""
        trips = self.data.trips(["DRVR_FLG", "VMT_MILE", "TRPMILES"], weight=False)
        driven = trips["DRVR_FLG"] == "01"
        frame = pd.DataFrame({
            "HOUSEID": trips["HOUSEID"], "PERSONID": trips["PERSONID"],
            "ntrips": 1.0,
            "pmt": trips["TRPMILES"].fillna(0.0).astype(float),
            "vtrips": driven.astype(float),
            "vmt": np.where(driven & (trips["VMT_MILE"] >= 0), trips["VMT_MILE"], 0.0),
        })
        per = frame.groupby(["HOUSEID", "PERSONID"], as_index=False).sum()
        base = self.persons
        rows = base.rows.merge(per, on=["HOUSEID", "PERSONID"], how="left", validate="1:1")
        cols = ["ntrips", "pmt", "vtrips", "vmt"]
        rows[cols] = rows[cols].fillna(0.0)
        rows["is_driver"] = (rows["DRIVER"] == "01").astype(float)
        return Survey(rows, base._unit, base._w, base._r, level=base.level)


def _pair(frame: pd.DataFrame) -> Result:
    row = frame.iloc[0]
    return float(row["estimate"]), float(row["moe"])


def _hh_band(ctx: Context, lo: float, hi: float) -> Result:
    size = ctx.households.rows["HHSIZE"]
    return _pair(ctx.households.total(domain=size.between(lo, hi)))


def _age_band(ctx: Context, lo: float, hi: float) -> Result:
    age = ctx.persons.rows["R_AGE_IMP"]
    return _pair(ctx.persons.total(domain=age.between(lo, hi)))


def hh_all(ctx: Context) -> Result:
    return _pair(ctx.households.total())


def hh_size1(ctx: Context) -> Result:
    return _hh_band(ctx, 1, 1)


def hh_size2(ctx: Context) -> Result:
    return _hh_band(ctx, 2, 2)


def hh_size3(ctx: Context) -> Result:
    return _hh_band(ctx, 3, 3)


def hh_size4plus(ctx: Context) -> Result:
    return _hh_band(ctx, 4, 1e9)


def persons_all(ctx: Context) -> Result:
    return _pair(ctx.persons.total())


def age_under16(ctx: Context) -> Result:
    return _age_band(ctx, 0, 15)


def age_16_19(ctx: Context) -> Result:
    return _age_band(ctx, 16, 19)


def age_20_34(ctx: Context) -> Result:
    return _age_band(ctx, 20, 34)


def age_35_64(ctx: Context) -> Result:
    return _age_band(ctx, 35, 64)


def age_65plus(ctx: Context) -> Result:
    return _age_band(ctx, 65, 1e9)


def age_16plus(ctx: Context) -> Result:
    return _age_band(ctx, 16, 1e9)


def drivers(ctx: Context) -> Result:
    return _pair(ctx.persons.total(domain=ctx.persons.rows["DRIVER"] == "01"))


def workers(ctx: Context) -> Result:
    return _pair(ctx.persons.total(domain=ctx.persons.rows["WORKER"] == "01"))


def _per_hh(ctx: Context, variable: str) -> Result:
    return _pair(ratio_across(ctx.person_travel, variable, ctx.households))


def trips_per_hh(ctx: Context) -> Result:
    return _per_hh(ctx, "ntrips")


def pmt_per_hh(ctx: Context) -> Result:
    return _per_hh(ctx, "pmt")


def vtrips_per_hh(ctx: Context) -> Result:
    return _per_hh(ctx, "vtrips")


def vmt_per_hh(ctx: Context) -> Result:
    return _per_hh(ctx, "vmt")


def trips_per_person(ctx: Context) -> Result:
    return _pair(ctx.person_travel.mean("ntrips"))


def pmt_per_person(ctx: Context) -> Result:
    return _pair(ctx.person_travel.mean("pmt"))


def person_trip_length(ctx: Context) -> Result:
    return _pair(ctx.trips.mean("TRPMILES"))


def vtrips_per_driver(ctx: Context) -> Result:
    return _pair(ctx.person_travel.ratio("vtrips", "is_driver"))


def vmt_per_driver(ctx: Context) -> Result:
    return _pair(ctx.person_travel.ratio("vmt", "is_driver"))


def vehicle_trip_length(ctx: Context) -> Result:
    return _pair(ctx.person_travel.ratio("vmt", "vtrips"))


COMPUTE: dict[str, Callable[[Context], Result]] = {
    f.__name__: f
    for f in (
        hh_all, hh_size1, hh_size2, hh_size3, hh_size4plus, persons_all, age_under16, age_16_19,
        age_20_34, age_35_64, age_65plus, age_16plus, drivers, workers, trips_per_hh,
        pmt_per_hh, vtrips_per_hh, vmt_per_hh, trips_per_person, pmt_per_person,
        person_trip_length, vtrips_per_driver, vmt_per_driver, vehicle_trip_length,
    )
}
