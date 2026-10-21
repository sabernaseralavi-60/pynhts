"""Replication of Tables 1 and 3 of FHWA's *Summary of Travel Trends* for NHTS 2009 and 2001.

The 2009 report (McGuckin and Fucci style, Table 1 and Table 3) and the 2001 report (Table 1 and
Table 3) use the same definitions as the 2017 report, with these wave-specific points:

* Codes differ between waves in format: yes/no and sex are ``"01"``/``"02"`` in 2009 but
  ``"1"``/``"2"`` in 2001; the recipe takes them from :data:`CODES`.
* Persons: the 2009 file has no children under 5. The 2001 file has them (their trips are
  imputed by the survey contractor), and the 2001 report prints two columns: "2001" (persons and
  trips of age 5 and older, age unknown included) and "2001 (includes 0-4)". ``Context.keep_person``
  selects the first; the targets with the suffix ``_all_ages`` are the second.
* Household vehicles in the 2009 report are vehicles of types 01-07 (cars, vans, SUVs, pickups,
  other trucks, RVs, motorcycles); golf carts, "other" and unknown type are left out.
* Person trips and person miles are all trips and ``TRPMILES``; trips with unknown distance
  count as trips and add 0 miles. Vehicle trips are the trips on which the respondent drove
  (``DRVR_FLG`` yes) a car, van, SUV, pickup, other truck, RV or motorcycle (``TRPTRANS`` 01-07;
  a driven golf cart, 2009 code 08, is not a household vehicle trip); vehicle miles are
  ``VMT_MILE`` in 2009 and ``TRPMILES`` of driver trips in 2001 (the 2001 file has no
  ``VMT_MILE``).
* Per-household rates divide person-weighted totals by household-weighted households.
* Table 3 rates (reverse-engineered from the printed 2001 values, see ``docs/data_notes.md``):
  the numerators count only the trips and miles of persons whose age is known and at least 5,
  while per-person rates divide by *all* persons (children 0-4 and unknown age included), and
  the average vehicle trip length uses only driver trips that have a distance.
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

# yes/no and sex codes by wave
CODES: dict[int, dict[str, str]] = {
    2009: {"yes": "01", "male": "01", "female": "02"},
    2001: {"yes": "1", "male": "1", "female": "2"},
}
HOUSEHOLD_VEHICLE_TYPES = {"01", "02", "03", "04", "05", "06", "07"}


def _jkn(survey: Survey | TaylorSurvey) -> Survey:
    if not isinstance(survey, Survey):
        raise TypeError("this recipe needs a wave with replicate weights")
    return survey


class Context:
    """Lazily built surveys shared by all targets of the recipe (one wave)."""

    def __init__(self, data: NHTSData) -> None:
        """Bind the context to an opened :class:`~pynhts.NHTSData` of 2001 or 2009."""
        if data.wave not in CODES:
            raise ValueError("recipes stt2001 and stt2009 need NHTS 2001 or 2009")
        self.data = data
        self.c = CODES[data.wave]

    @cached_property
    def households(self) -> Survey:
        return _jkn(self.data.survey("household", ["HHSIZE"]))

    @cached_property
    def persons(self) -> Survey:
        return _jkn(self.data.survey("person", ["R_AGE", "R_SEX", "DRIVER", "WORKER"]))

    @cached_property
    def trips(self) -> Survey:
        """Trip survey with vehicle trips and vehicle miles per trip."""
        # skip="nan": 181 trips of 2009 carry the skip code -1 in TRPMILES; they add 0 miles
        svy = _jkn(self.data.survey(
            "trip", ["R_AGE", "TRPMILES", "DRVR_FLG", "TRPTRANS", *self._vmt_cols], skip="nan"
        ))
        rows = svy.rows
        # a vehicle trip is a trip the respondent drove in a household-type vehicle (modes 01-07;
        # 08 is a golf cart in 2009, whose 63 million driver trips the report leaves out)
        is_driver = rows["DRVR_FLG"] == self.c["yes"]
        vehicle_trip = (is_driver & rows["TRPTRANS"].isin(HOUSEHOLD_VEHICLE_TYPES)).fillna(False)
        driven = vehicle_trip.to_numpy(dtype=bool)
        miles = rows["VMT_MILE"] if self.data.wave == 2009 else rows["TRPMILES"]
        valid = driven & (miles >= 0).fillna(False).to_numpy(dtype=bool)
        rows["vtrip"] = driven.astype(float)
        rows["vmt"] = np.where(valid, miles, 0.0)
        rows["vtrip_valid"] = valid.astype(float)  # driver trips that have a distance
        return svy

    @property
    def _vmt_cols(self) -> list[str]:
        return ["VMT_MILE"] if self.data.wave == 2009 else []

    @cached_property
    def person_travel(self) -> Survey:
        """Person survey carrying each person's daily trip and mile totals."""
        rows = self.trips.rows
        frame = pd.DataFrame({
            "HOUSEID": rows["HOUSEID"], "PERSONID": rows["PERSONID"],
            "ntrips": 1.0,
            "pmt": rows["TRPMILES"].fillna(0.0).astype(float),
            "vtrips": rows["vtrip"], "vmt": rows["vmt"], "vtrips_valid": rows["vtrip_valid"],
        })
        per = frame.groupby(["HOUSEID", "PERSONID"], as_index=False).sum()
        base = self.persons
        merged = base.rows.merge(per, on=["HOUSEID", "PERSONID"], how="left", validate="1:1")
        cols = ["ntrips", "pmt", "vtrips", "vmt", "vtrips_valid"]
        merged[cols] = merged[cols].fillna(0.0)
        known5 = (merged["R_AGE"] >= 5).fillna(False).to_numpy(dtype=float)
        merged["ntrips_k5"] = merged["ntrips"] * known5  # trips of persons of known age >= 5
        merged["pmt_k5"] = merged["pmt"] * known5
        merged["one"] = 1.0
        merged["is_driver"] = (merged["DRIVER"] == self.c["yes"]).fillna(False).astype(float)
        return Survey(merged, base._unit, base._w, base._r, level=base.level, df=base.df,
                      factor=base.factor)

    # -- domains --------------------------------------------------------------------------
    @cached_property
    def keep_person(self) -> pd.Series:
        """Persons of age 5+ or unknown age (the report's "2001" column; all of 2009)."""
        age = self.persons.rows["R_AGE"]
        keep: pd.Series = (age >= 5) | age.isna()
        return keep

    @cached_property
    def keep_trip(self) -> pd.Series:
        age = self.trips.rows["R_AGE"]
        keep: pd.Series = (age >= 5) | age.isna()
        return keep

    @cached_property
    def known5_trip(self) -> pd.Series:
        """Trips of persons whose age is known and at least 5 (the Table 3 numerators)."""
        known: pd.Series = self.trips.rows["R_AGE"] >= 5
        return known


def _pair(frame: pd.DataFrame) -> Result:
    row = frame.iloc[0]
    return float(row["estimate"]), float(row["moe"])


def _hh_band(ctx: Context, lo: float, hi: float) -> Result:
    size = ctx.households.rows["HHSIZE"]
    return _pair(ctx.households.total(domain=size.between(lo, hi)))


def _persons(ctx: Context, mask: pd.Series) -> Result:
    return _pair(ctx.persons.total(domain=mask))


def _age(ctx: Context, lo: float, hi: float) -> pd.Series:
    band: pd.Series = ctx.persons.rows["R_AGE"].between(lo, hi)
    return band


def _sex(ctx: Context, which: str) -> pd.Series:
    mask: pd.Series = ctx.persons.rows["R_SEX"] == ctx.c[which]
    return mask


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
    return _persons(ctx, _age(ctx, 0, 15))


def age_16_19(ctx: Context) -> Result:
    return _persons(ctx, _age(ctx, 16, 19))


def age_20_34(ctx: Context) -> Result:
    return _persons(ctx, _age(ctx, 20, 34))


def age_35_64(ctx: Context) -> Result:
    return _persons(ctx, _age(ctx, 35, 64))


def age_65plus(ctx: Context) -> Result:
    return _persons(ctx, _age(ctx, 65, 1e9))


def age_16plus(ctx: Context) -> Result:
    return _persons(ctx, _age(ctx, 16, 1e9))


def persons_5plus(ctx: Context) -> Result:
    return _persons(ctx, ctx.keep_person)


def male(ctx: Context) -> Result:
    return _persons(ctx, _sex(ctx, "male"))


def female(ctx: Context) -> Result:
    return _persons(ctx, _sex(ctx, "female"))


def male_16plus(ctx: Context) -> Result:
    return _persons(ctx, _sex(ctx, "male") & _age(ctx, 16, 1e9))


def female_16plus(ctx: Context) -> Result:
    return _persons(ctx, _sex(ctx, "female") & _age(ctx, 16, 1e9))


def male_5plus(ctx: Context) -> Result:
    return _persons(ctx, _sex(ctx, "male") & ctx.keep_person)


def female_5plus(ctx: Context) -> Result:
    return _persons(ctx, _sex(ctx, "female") & ctx.keep_person)


def _flag(ctx: Context, column: str, sex: str | None = None) -> Result:
    mask = ctx.persons.rows[column] == ctx.c["yes"]
    if sex is not None:
        mask = mask & _sex(ctx, sex)
    return _persons(ctx, mask)


def drivers(ctx: Context) -> Result:
    return _flag(ctx, "DRIVER")


def drivers_male(ctx: Context) -> Result:
    return _flag(ctx, "DRIVER", "male")


def drivers_female(ctx: Context) -> Result:
    return _flag(ctx, "DRIVER", "female")


def workers(ctx: Context) -> Result:
    return _flag(ctx, "WORKER")


def workers_male(ctx: Context) -> Result:
    return _flag(ctx, "WORKER", "male")


def workers_female(ctx: Context) -> Result:
    return _flag(ctx, "WORKER", "female")


def household_vehicles(ctx: Context) -> Result:
    """Vehicles of types 01-07 (2009 report); every vehicle row in the 2001 report."""
    svy = _jkn(ctx.data.survey("vehicle", ["VEHTYPE"]))
    if ctx.data.wave == 2009:
        return _pair(svy.total(domain=svy.rows["VEHTYPE"].isin(HOUSEHOLD_VEHICLE_TYPES)))
    return _pair(svy.total())


def vehicles_all_rows(ctx: Context) -> Result:
    return _pair(_jkn(ctx.data.survey("vehicle", ["VEHID"])).total())


def person_trips_total(ctx: Context) -> Result:
    return _pair(ctx.trips.total(domain=ctx.keep_trip))


def person_trips_total_all_ages(ctx: Context) -> Result:
    return _pair(ctx.trips.total())


def pmt_total(ctx: Context) -> Result:
    return _pair(ctx.trips.total("TRPMILES", domain=ctx.keep_trip))


def pmt_total_all_ages(ctx: Context) -> Result:
    return _pair(ctx.trips.total("TRPMILES"))


def hh_vehicle_trips_total(ctx: Context) -> Result:
    return _pair(ctx.trips.total("vtrip"))


def vmt_total(ctx: Context) -> Result:
    return _pair(ctx.trips.total("vmt"))


# -- Table 3: rates ----------------------------------------------------------------------
def _per_hh(ctx: Context, variable: str) -> Result:
    return _pair(ratio_across(ctx.person_travel, variable, ctx.households))


def trips_per_hh(ctx: Context) -> Result:
    return _per_hh(ctx, "ntrips_k5")


def pmt_per_hh(ctx: Context) -> Result:
    return _per_hh(ctx, "pmt_k5")


def trips_per_hh_all_ages(ctx: Context) -> Result:
    return _per_hh(ctx, "ntrips")


def pmt_per_hh_all_ages(ctx: Context) -> Result:
    return _per_hh(ctx, "pmt")


def vtrips_per_hh(ctx: Context) -> Result:
    return _per_hh(ctx, "vtrips")


def vmt_per_hh(ctx: Context) -> Result:
    return _per_hh(ctx, "vmt")


def trips_per_person(ctx: Context) -> Result:
    return _pair(ctx.person_travel.ratio("ntrips_k5", "one"))


def pmt_per_person(ctx: Context) -> Result:
    return _pair(ctx.person_travel.ratio("pmt_k5", "one"))


def trips_per_person_all_ages(ctx: Context) -> Result:
    return _pair(ctx.person_travel.mean("ntrips"))


def pmt_per_person_all_ages(ctx: Context) -> Result:
    return _pair(ctx.person_travel.mean("pmt"))


def vtrips_per_driver(ctx: Context) -> Result:
    return _pair(ctx.person_travel.ratio("vtrips", "is_driver"))


def vmt_per_driver(ctx: Context) -> Result:
    return _pair(ctx.person_travel.ratio("vmt", "is_driver"))


def person_trip_length(ctx: Context) -> Result:
    return _pair(ctx.trips.mean("TRPMILES", domain=ctx.known5_trip))


def person_trip_length_all_ages(ctx: Context) -> Result:
    return _pair(ctx.trips.mean("TRPMILES"))


def vehicle_trip_length(ctx: Context) -> Result:
    return _pair(ctx.person_travel.ratio("vmt", "vtrips_valid"))


COMPUTE: dict[str, Callable[[Context], Result]] = {
    f.__name__: f
    for f in (
        hh_all, hh_size1, hh_size2, hh_size3, hh_size4plus, persons_all, age_under16, age_16_19,
        age_20_34, age_35_64, age_65plus, age_16plus, persons_5plus, male, female, male_16plus,
        female_16plus, male_5plus, female_5plus, drivers, drivers_male, drivers_female,
        workers, workers_male, workers_female, household_vehicles, vehicles_all_rows,
        person_trips_total, person_trips_total_all_ages, pmt_total, pmt_total_all_ages,
        hh_vehicle_trips_total, vmt_total, trips_per_hh, pmt_per_hh, trips_per_hh_all_ages,
        pmt_per_hh_all_ages, vtrips_per_hh, vmt_per_hh, trips_per_person, pmt_per_person,
        trips_per_person_all_ages, pmt_per_person_all_ages, vtrips_per_driver, vmt_per_driver,
        person_trip_length, person_trip_length_all_ages, vehicle_trip_length,
    )
}
