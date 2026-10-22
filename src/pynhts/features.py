"""Documented derived features for persons, households, trips and vehicles, with lineage.

Every feature is described in a registry (:func:`registry`): scientific meaning, unit of analysis,
source variables, exact formula, who is eligible, what happens to missing values, the denominator,
the weight to use, the waves in which it exists and how it is validated. The creators compute only
what you ask for, never modify the downloaded data, and record the provenance in
``frame.attrs["pynhts_features"]``.

>>> import pynhts
>>> from pynhts import features
>>> hh = features.create_household_features(pynhts.load(2017), groups=["composition", "travel"])  # doctest: +SKIP
>>> features.registry(level="household").head()                                                   # doctest: +SKIP

Conventions that matter:

* **Zero is not missing.** A household with no workers has ``hh_n_workers == 0``; a household
  whose worker status is unknown for a member has ``hh_n_workers_unknown > 0`` and, with
  ``strict=True``, ``hh_n_workers`` is NaN instead of a lower bound.
* **Eligibility is explicit.** ``hh_share_univ`` divides by the members whose education was
  *answered* (the survey asks adults only); members with a skip or a non-answer are neither in the
  numerator nor in the denominator, and are counted in ``hh_n_edu_unknown`` / ``..._na``.
* **The person file is not always a complete roster.** It lists the persons that were interviewed
  (2009 and later: aged 5 and over). Member counts built from it (workers, drivers, adults,
  university members) are lower bounds whenever ``hh_n_unlisted`` (``HHSIZE`` minus listed persons) is
  positive: 14.5 % of 2001, 19.8 % of 2009, 7.0 % of 2017 and 9.1 % of 2022 households. In
  households with ``hh_n_unlisted == 0`` the counts equal the survey's own ``WRKCOUNT`` and
  ``DRVRCNT`` in all four waves (tests/data/test_features_real.py); elsewhere prefer the official
  household columns (``WRKCOUNT``, ``DRVRCNT``, ``NUMADLT``, ``YOUNGCHILD``) and treat ours as
  a check.
* **Survey-day quantities are observed, not annual.** Household trips and miles are the sums of the
  members' trips on the (shared) travel day. Weight them with the household weight carried in the
  result; the trip weight belongs to trips.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
import pandas as pd

from pynhts import harmonize
from pynhts.aggregate import Agg, Where, aggregate
from pynhts.core.validity import answer_status

if TYPE_CHECKING:
    from pynhts.core.data import NHTSData

ALL_WAVES = (2001, 2009, 2017, 2022)
MODE_GROUPS = (
    "walk",
    "bike",
    "private_vehicle",
    "other_vehicle",
    "school_bus",
    "public_transit",
    "other_transit",
    "other",
)
PURPOSES = (
    "home",
    "work",
    "school_daycare_religious",
    "medical",
    "shopping_errands",
    "social_recreational",
    "transport_someone",
    "meals",
    "other",
)
DISTANCE_BINS = (0.0, 1.0, 3.0, 5.0, 10.0, 25.0, 50.0, np.inf)
DISTANCE_LABELS = ("<1", "1-3", "3-5", "5-10", "10-25", "25-50", "50+")
DURATION_BINS = (0.0, 10.0, 20.0, 30.0, 60.0, np.inf)
DURATION_LABELS = ("<10", "10-20", "20-30", "30-60", "60+")


@dataclass(frozen=True)
class Feature:
    """The full definition of a derived feature (what a methods section needs)."""

    name: str
    level: str
    group: str
    description: str
    sources: tuple[str, ...]
    formula: str
    eligibility: str = "all rows"
    missing: str = "NaN when an input is missing"
    denominator: str = "-"
    weighting: str = ""
    waves: tuple[int, ...] = ALL_WAVES
    validation: str = ""
    unit: str = ""


def _w(level: str) -> str:
    return {
        "person": "person weight (WTPERFIN); a person-day quantity",
        "household": "household weight (WTHHFIN); never the trip or person weight",
        "trip": "trip weight (WTTRDFIN) = 365 x person weight: totals are annual, rates need the "
        "person/household denominator (pynhts.rates)",
        "vehicle": "household weight (WTHHFIN)",
    }[level]


def _defs() -> list[Feature]:
    P, H, T, V = "person", "household", "trip", "vehicle"
    f: list[Feature] = []

    def add(
        name: str, level: str, group: str, desc: str, src: Sequence[str], formula: str, **kw: Any
    ) -> None:
        kw.setdefault("weighting", _w(level))
        f.append(Feature(name, level, group, desc, tuple(src), formula, **kw))

    # -- person
    add(
        "p_age_band",
        P,
        "demographics",
        "Age in the bands of pynhts.harmonize.age_bands",
        ["person.R_AGE"],
        "harmonize.age_bands(R_AGE, wave)",
        missing="NaN for unknown age; top-coded ages are inside the top band",
        validation="band counts sum to the person count",
    )
    add(
        "p_edu_cat",
        P,
        "demographics",
        "Education: less_than_hs, hs_grad, some_college_assoc, bachelor, graduate",
        ["person.EDUC"],
        'harmonize.apply(EDUC, "education")',
        eligibility="persons asked (adults)",
        missing="NaN for skip (-1: not asked) and non-answers; see p_edu_status",
        validation="cross-wave: 2001 code 7 maps to bachelor (approximate)",
    )
    add(
        "p_edu_status",
        P,
        "demographics",
        "answered / not_applicable / unknown for the education question",
        ["person.EDUC"],
        "answer_status(EDUC)",
        validation="the three classes partition the persons",
    )
    add(
        "p_worker",
        P,
        "demographics",
        "Worker status: yes / no / not_applicable / unknown",
        ["person.WORKER"],
        "WORKER code 1 -> yes, 2 -> no, -1 -> not_applicable, -7/-8/-9 -> unknown",
    )
    add(
        "p_driver",
        P,
        "demographics",
        "Driver status: yes / no / not_applicable / unknown",
        ["person.DRIVER"],
        "DRIVER code 1 -> yes, 2 -> no, -1 -> not_applicable, -7/-8/-9 -> unknown",
    )
    add(
        "p_n_trips",
        P,
        "travel",
        "Number of trips on the travel day (0 for persons without trips)",
        ["trip rows"],
        "count of the person's trip rows",
        denominator="persons, including those with no trips",
        unit="trips/day",
        validation="sum over persons equals the number of trips",
    )
    add(
        "p_miles",
        P,
        "travel",
        "Distance travelled on the travel day (TRPMILES summed)",
        ["trip.TRPMILES"],
        "sum of TRPMILES over the person's trips",
        missing="NaN if any trip has no distance (miles_missing='skip' ignores them as FHWA does)",
        unit="miles/day",
    )
    add(
        "p_minutes",
        P,
        "travel",
        "Travel time on the travel day (TRVLCMIN summed)",
        ["trip.TRVLCMIN"],
        "sum of TRVLCMIN over the person's trips",
        unit="minutes/day",
    )
    add(
        "p_any_trip",
        P,
        "travel",
        "At least one trip on the travel day",
        ["trip rows"],
        "p_n_trips > 0",
    )
    for g in MODE_GROUPS:
        add(
            f"p_trips_mode_{g}",
            P,
            "modes",
            f"Trips by mode group {g}",
            ["trip.TRPTRANS"],
            f'count of trips whose harmonize.apply(TRPTRANS, "mode", level="summary") == "{g}"',
            unit="trips/day",
            missing="trips with an unknown mode are in no group",
        )
    add(
        "p_work_trips",
        P,
        "purposes",
        "Trips whose purpose summary is work",
        ["trip.WHYTRP1S"],
        'count of trips with purpose_summary == "work"',
        unit="trips/day",
    )
    add(
        "p_nonwork_trips",
        P,
        "purposes",
        "Trips with a known purpose other than work",
        ["trip.WHYTRP1S"],
        'count of trips with a purpose_summary that is not "work"',
        unit="trips/day",
    )

    # -- household
    for c, d in (
        ("hh_n_persons_listed", "Persons of the household listed in the person file"),
        ("hh_n_unlisted", "HHSIZE minus listed persons (children under 5 in 2009 and later)"),
        ("hh_n_adults", "Listed members aged 18 or more"),
        ("hh_n_children", "Listed members under 18"),
        ("hh_n_older", "Listed members aged 65 or more"),
    ):
        add(
            c,
            H,
            "composition",
            d,
            ["person.R_AGE", "household.HHSIZE"],
            "see description",
            missing="members with unknown age are in none of the age counts; see hh_n_age_unknown",
            unit="persons",
        )
    for c, d, col in (
        ("hh_n_workers", "Members who are workers", "WORKER"),
        ("hh_n_drivers", "Members who are drivers", "DRIVER"),
    ):
        add(
            c,
            H,
            "composition",
            d,
            [f"person.{col}"],
            f"count of members with {col} == yes",
            missing=f"members with unknown {col}: counted in {c}_unknown; strict=True makes {c} NaN",
            unit="persons",
            validation="compare with the survey's own WRKCOUNT / DRVRCNT",
        )
        add(
            f"{c}_unknown",
            H,
            "composition",
            f"Members whose {col} is a non-answer",
            [f"person.{col}"],
            f"count of members with {col} in (-7, -8, -9)",
            unit="persons",
        )
    add(
        "hh_n_univ",
        H,
        "composition",
        "Members with a bachelor's or graduate degree",
        ["person.EDUC"],
        'count of members with p_edu_cat in ("bachelor", "graduate")',
        unit="persons",
        eligibility="members who answered EDUC",
    )
    add(
        "hh_n_edu_answered",
        H,
        "composition",
        "Members who answered the education question",
        ["person.EDUC"],
        "count of members with answer_status(EDUC) == answered",
        unit="persons",
    )
    add(
        "hh_n_edu_unknown",
        H,
        "composition",
        "Members with a refused / unknown education",
        ["person.EDUC"],
        "count of members with answer_status(EDUC) == nonanswer",
        unit="persons",
    )
    add(
        "hh_share_univ",
        H,
        "composition",
        "Share of members who answered with a university degree",
        ["person.EDUC"],
        "hh_n_univ / hh_n_edu_answered",
        denominator="members who answered EDUC",
        missing="NaN when nobody answered; unknowns are excluded from numerator and denominator",
    )
    add(
        "hh_veh_per_person",
        H,
        "resources",
        "Vehicles per household member",
        ["household.HHVEHCNT", "household.HHSIZE"],
        "HHVEHCNT / HHSIZE",
        denominator="HHSIZE (all members, incl. under 5)",
    )
    add(
        "hh_veh_per_driver",
        H,
        "resources",
        "Vehicles per driver",
        ["household.HHVEHCNT", "person.DRIVER"],
        "HHVEHCNT / hh_n_drivers",
        denominator="drivers",
        missing="NaN when the household has no (known) driver",
    )
    add(
        "hh_zero_vehicle",
        H,
        "resources",
        "No vehicle in the household",
        ["household.HHVEHCNT"],
        "HHVEHCNT == 0",
    )
    add(
        "hh_n_trips",
        H,
        "travel",
        "Trips of all members on the travel day",
        ["trip rows"],
        "count of the household's trip rows",
        unit="trips/day",
        validation="sum equals the trip count",
    )
    add(
        "hh_zero_trip",
        H,
        "travel",
        "No member made a trip on the travel day",
        ["trip rows"],
        "hh_n_trips == 0",
    )
    add(
        "hh_miles",
        H,
        "travel",
        "Distance travelled by all members on the travel day",
        ["trip.TRPMILES"],
        "sum of TRPMILES over the household's trips",
        unit="miles/day",
        missing="NaN if any trip has no distance (miles_missing='skip' ignores them)",
    )
    add(
        "hh_vmt",
        H,
        "travel",
        "Vehicle miles driven by members on the travel day",
        ["trip.TRPMILES", "trip.DRVR_FLG", "trip.TRPTRANS"],
        'sum of TRPMILES of trips with DRVR_FLG == yes and mode group "private_vehicle"',
        unit="vehicle miles/day",
        validation="driver trips only: passengers' miles are not vehicle miles; trips whose driver flag is a "
        "non-answer are not counted (2009: 4.9 % of trips), so hh_vmt is a lower bound there",
    )
    for g in MODE_GROUPS:
        add(
            f"hh_trips_mode_{g}",
            H,
            "modes",
            f"Household trips by mode group {g}",
            ["trip.TRPTRANS"],
            f'count of household trips with mode group "{g}"',
            unit="trips/day",
        )
    add(
        "hh_trips_unknown_mode",
        H,
        "modes",
        "Household trips whose mode is unknown",
        ["trip.TRPTRANS"],
        "hh_n_trips minus trips in any mode group",
        unit="trips/day",
    )
    for g in MODE_GROUPS:
        add(
            f"hh_mode_share_{g}",
            H,
            "modes",
            f"Share of the household's known-mode trips in {g}",
            ["trip.TRPTRANS"],
            f"hh_trips_mode_{g} / trips with a known mode",
            denominator="trips with a known mode",
            missing="NaN for zero-trip households",
        )
    add(
        "hh_n_modes",
        H,
        "modes",
        "Number of different mode groups used",
        ["trip.TRPTRANS"],
        "number of mode groups with at least one trip",
        unit="modes",
    )
    add(
        "hh_multimodal",
        H,
        "modes",
        "Two or more mode groups used on the travel day",
        ["trip.TRPTRANS"],
        "hh_n_modes >= 2",
        missing="False for zero-trip households (nothing was used)",
    )
    add(
        "hh_mode_entropy",
        H,
        "modes",
        "Shannon entropy (natural log) of the mode-group trip shares",
        ["trip.TRPTRANS"],
        "-sum(p ln p) over mode groups, 0 ln 0 = 0",
        missing="NaN for zero-trip households",
        denominator="trips with a known mode",
    )
    for g in PURPOSES:
        add(
            f"hh_trips_purpose_{g}",
            H,
            "purposes",
            f"Household trips with purpose {g}",
            ["trip.WHYTRP1S"],
            f'count of household trips with purpose_summary "{g}"',
            unit="trips/day",
        )
    add(
        "hh_n_vehicles_listed",
        H,
        "fleet",
        "Vehicles listed in the vehicle file",
        ["vehicle rows"],
        "count of vehicle rows",
        validation="can differ from HHVEHCNT (vehicles not described)",
    )
    add(
        "hh_fleet_median_age",
        H,
        "fleet",
        "Median vehicle age in years (top-coded ages stay at the code)",
        ["vehicle.VEHAGE"],
        "median of VEHAGE",
        missing="NaN when no vehicle age is known; median, not mean, because of the top code",
        unit="years",
    )
    add(
        "hh_n_vehicles_new",
        H,
        "fleet",
        "Vehicles aged 5 years or less",
        ["vehicle.VEHAGE"],
        "count of VEHAGE <= 5",
        unit="vehicles",
    )
    for g in ("car", "suv", "van", "pickup"):
        add(
            f"hh_n_veh_{g}",
            H,
            "fleet",
            f"Vehicles of type {g}",
            ["vehicle.VEHTYPE"],
            f'count of vehicles with harmonize.apply(VEHTYPE, "vehicle_type") == "{g}"',
            unit="vehicles",
        )

    # -- trip
    add(
        "t_distance_band",
        T,
        "distance_time",
        "Trip distance band in miles (<1, 1-3, 3-5, 5-10, 10-25, 25-50, 50+)",
        ["trip.TRPMILES"],
        "pd.cut(TRPMILES, bins) with right-open bins",
        missing="NaN if TRPMILES unknown",
    )
    add(
        "t_duration_band",
        T,
        "distance_time",
        "Trip duration band in minutes",
        ["trip.TRVLCMIN"],
        "pd.cut(TRVLCMIN, bins)",
    )
    add(
        "t_depart_period",
        T,
        "distance_time",
        "Departure period: am_peak 6-9, midday 9-15, pm_peak 15-19, evening 19-22, night",
        ["trip.STRTTIME"],
        "hour of STRTTIME (HHMM)",
    )
    add(
        "t_mode",
        T,
        "purpose_mode",
        "Mode category of the cross-wave crosswalk",
        ["trip.TRPTRANS"],
        'harmonize.apply(TRPTRANS, "mode")',
    )
    add(
        "t_mode_group",
        T,
        "purpose_mode",
        "Mode summary group",
        ["trip.TRPTRANS"],
        'harmonize.apply(TRPTRANS, "mode", level="summary")',
    )
    add(
        "t_purpose",
        T,
        "purpose_mode",
        "Trip purpose summary (home, work, ...)",
        ["trip.WHYTRP1S"],
        'harmonize.apply(WHYTRP1S, "purpose_summary")',
        validation="WHYTRP1S has two code systems; the crosswalk is per wave",
    )
    add(
        "t_is_work",
        T,
        "purpose_mode",
        "Purpose summary is work",
        ["trip.WHYTRP1S"],
        't_purpose == "work"',
    )
    add(
        "t_is_long_distance",
        T,
        "distance_time",
        "Trip of 50 miles or more",
        ["trip.TRPMILES"],
        "TRPMILES >= 50",
        missing="NaN if TRPMILES unknown",
    )
    add(
        "t_order",
        T,
        "sequence",
        "Position of the trip within the person's travel day (1 = first)",
        ["trip key"],
        "rank by the trip number (TDTRPNUM / TRIPID) within person",
        validation="max equals the person's trip count",
    )
    add("t_is_first", T, "sequence", "First trip of the person's day", ["trip key"], "t_order == 1")
    add(
        "t_is_last",
        T,
        "sequence",
        "Last trip of the person's day",
        ["trip key"],
        "t_order == number of trips of the person",
    )

    # -- vehicle
    add(
        "v_age_band",
        V,
        "vehicle",
        "Vehicle age band 0-2, 3-5, 6-10, 11-15, 16+ (the top code falls in 16+)",
        ["vehicle.VEHAGE"],
        "pd.cut(VEHAGE, bins)",
        missing="NaN if age unknown",
    )
    add(
        "v_type",
        V,
        "vehicle",
        "Vehicle type category",
        ["vehicle.VEHTYPE"],
        'harmonize.apply(VEHTYPE, "vehicle_type")',
    )
    add(
        "v_fuel",
        V,
        "vehicle",
        "Fuel category (gasoline, diesel, alt_fuel, other)",
        ["vehicle.FUELTYPE"],
        'harmonize.apply(FUELTYPE, "fuel")',
        waves=(2001, 2009, 2017),
        missing="2022 has no fuel crosswalk",
    )
    return f


_REGISTRY: dict[str, Feature] | None = None


def _registry() -> dict[str, Feature]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = {x.name: x for x in _defs()}
    return _REGISTRY


def registry(level: str | None = None, group: str | None = None) -> pd.DataFrame:
    """The feature registry as a table (one row per feature), optionally filtered."""
    rows = [
        vars(x) | {"sources": "; ".join(x.sources), "waves": ",".join(map(str, x.waves))}
        for x in _registry().values()
    ]
    df = pd.DataFrame(rows)
    if level is not None:
        df = df[df["level"] == level]
    if group is not None:
        df = df[df["group"] == group]
    return df.reset_index(drop=True)


def describe_feature(name: str) -> Feature:
    """The definition of one feature (``KeyError`` with the closest names when unknown)."""
    reg = _registry()
    if name not in reg:
        close = [n for n in reg if name.split("_")[-1] in n][:8]
        raise KeyError(f"unknown feature {name!r}; similar: {close}")
    return reg[name]


# ---- building blocks -----------------------------------------------------------------------
def _canon(s: pd.Series) -> pd.Series:
    """Zero-unpadded code strings: '01' and '1' both become '1'."""
    return s.astype("string").str.replace(r"^(-?)0+(?=\d)", r"\1", regex=True)


def _yes_no(s: pd.Series) -> pd.Series:
    """Yes / no / not_applicable / unknown from a yes-no coded column loaded with raw codes."""
    c = _canon(s)

    def arr(m: pd.Series) -> Any:
        return m.fillna(False).to_numpy(dtype=bool)

    out = np.select(
        [arr(c == "1"), arr(c == "2"), arr(c == "-1"), arr(c.str.startswith("-"))],
        ["yes", "no", "not_applicable", "unknown"],
        default="unknown",
    )
    return pd.Series(out, index=s.index, dtype="string")


def _person_frame(data: NHTSData, extra: Sequence[str] = ()) -> pd.DataFrame:
    p = data.persons(["R_AGE", "EDUC", "WORKER", "DRIVER", *extra], missing="keep", skip="keep")
    age = pd.to_numeric(p["R_AGE"], errors="coerce")
    p["age"] = age.where(age >= 0)
    p["p_age_band"] = harmonize.age_bands(p["age"], data.wave)
    p["p_edu_status"] = answer_status(p["EDUC"]).replace(
        {"skip": "not_applicable", "nonanswer": "unknown", "blank": "unknown"}
    )
    p["p_edu_cat"] = harmonize.apply(p["EDUC"], "education", data.wave)
    p["p_worker"] = _yes_no(p["WORKER"])
    p["p_driver"] = _yes_no(p["DRIVER"])
    p["univ"] = p["p_edu_cat"].isin(["bachelor", "graduate"]).astype("int64")
    return p


def _trip_frame(data: NHTSData, miles_cols: bool = True) -> pd.DataFrame:
    cols = ["TRPMILES", "TRVLCMIN", "STRTTIME", "DRVR_FLG", "TRPTRANS", "WHYTRP1S"]
    t = data.trips(cols, missing="nan", skip="keep")
    t["t_mode"] = harmonize.apply(t["TRPTRANS"], "mode", data.wave)
    t["t_mode_group"] = harmonize.apply(t["TRPTRANS"], "mode", data.wave, level="summary")
    t["t_purpose"] = harmonize.apply(t["WHYTRP1S"], "purpose_summary", data.wave)
    t["drv"] = _yes_no(t["DRVR_FLG"])
    return t


def _check_groups(groups: Sequence[str] | None, allowed: Sequence[str]) -> list[str]:
    sel = list(allowed) if groups is None else list(groups)
    bad = [g for g in sel if g not in allowed]
    if bad:
        raise ValueError(f"unknown group(s) {bad}; choose from {list(allowed)}")
    return sel


def _merge(base: pd.DataFrame, part: pd.DataFrame, keys: Sequence[str]) -> pd.DataFrame:
    drop = [c for c in part.columns if c in base.columns and c not in keys]
    return base.merge(part.drop(columns=drop), on=list(keys), how="left", validate="one_to_one")


def _stamp(
    out: pd.DataFrame, base: pd.DataFrame, level: str, names: list[str], reports: list[Any]
) -> pd.DataFrame:
    reg = _registry()
    out.attrs["pynhts"] = {**base.attrs["pynhts"], "unit": f"{level} features"}
    out.attrs["pynhts_features"] = {
        "level": level,
        "features": {
            n: {"sources": reg[n].sources, "formula": reg[n].formula, "missing": reg[n].missing}
            for n in names
            if n in reg
        },
        "reports": reports,
    }
    return out


# ---- person ----------------------------------------------------------------------------------
PERSON_GROUPS = ("demographics", "travel", "modes", "purposes")


def create_person_features(
    data: NHTSData,
    groups: Sequence[str] | None = None,
    *,
    miles_missing: Literal["propagate", "skip"] = "propagate",
) -> pd.DataFrame:
    """Person-level features (one row per person, with ``WTPERFIN``)."""
    sel = _check_groups(groups, PERSON_GROUPS)
    keys = list(data.key("person"))
    base = data.persons([])
    out = base
    names: list[str] = []
    reports: list[Any] = []
    if "demographics" in sel:
        p = _person_frame(data)
        cols = ["p_age_band", "p_edu_cat", "p_edu_status", "p_worker", "p_driver"]
        out = _merge(out, p[[*keys, *cols]], keys)
        names += cols
    if {"travel", "modes", "purposes"} & set(sel):
        t = _trip_frame(data)
        specs: dict[str, Agg] = {}
        if "travel" in sel:
            specs |= {
                "p_n_trips": Agg.n(),
                "p_miles": Agg.sum("TRPMILES"),
                "p_minutes": Agg.sum("TRVLCMIN"),
            }
        if "modes" in sel:
            specs |= {
                f"p_trips_mode_{g}": Agg.n(Where("t_mode_group", "==", g)) for g in MODE_GROUPS
            }
        if "purposes" in sel:
            specs |= {
                "p_work_trips": Agg.n(Where("t_purpose", "==", "work")),
                "p_nonwork_trips": Agg.n(Where("t_purpose", "!=", "work")),
            }
        a = aggregate(data, t, "person", specs, missing=miles_missing)
        reports.append(a.attrs["pynhts_aggregate"])
        if "travel" in sel:
            a["p_any_trip"] = a["p_n_trips"] > 0
        out = _merge(out, a, keys)
        names += [c for c in a.columns if c.startswith("p_")]
    return _stamp(out, base, "person", names, reports)


# ---- household -------------------------------------------------------------------------------
HOUSEHOLD_GROUPS = ("composition", "resources", "travel", "modes", "purposes", "fleet")


def create_household_features(
    data: NHTSData,
    groups: Sequence[str] | None = None,
    *,
    strict: bool = False,
    miles_missing: Literal["propagate", "skip"] = "propagate",
) -> pd.DataFrame:
    """Household-level features (one row per household, with ``WTHHFIN``).

    Args:
        data: An opened wave.
        groups: Subset of ``composition, resources, travel, modes, purposes, fleet`` (default all).
        strict: Make member counts (workers, drivers) NaN when any member's value is unknown, instead
            of reporting the lower bound plus a ``..._unknown`` companion column.
        miles_missing: ``"propagate"`` (a household with a missing trip distance has no known
            distance) or ``"skip"`` (ignore such trips, as FHWA does).
    """
    sel = _check_groups(groups, HOUSEHOLD_GROUPS)
    keys = list(data.key("household"))
    base = data.households(["HHSIZE", "HHVEHCNT"])
    out = base
    names: list[str] = []
    reports: list[Any] = []

    if "composition" in sel or "resources" in sel:
        p = _person_frame(data)
        specs = {
            "hh_n_persons_listed": Agg.n(),
            "hh_n_adults": Agg.n(Where("age", ">=", 18)),
            "hh_n_children": Agg.n(Where("age", "<", 18)),
            "hh_n_older": Agg.n(Where("age", ">=", 65)),
            "hh_n_age_unknown": Agg.n(Where("age", "isna")),
            "hh_n_workers": Agg.n(Where("p_worker", "==", "yes")),
            "hh_n_workers_unknown": Agg.n(Where("p_worker", "==", "unknown")),
            "hh_n_drivers": Agg.n(Where("p_driver", "==", "yes")),
            "hh_n_drivers_unknown": Agg.n(Where("p_driver", "==", "unknown")),
            "hh_n_univ": Agg.n(Where("univ", "==", 1)),
            "hh_n_edu_answered": Agg.n(Where("p_edu_status", "==", "answered")),
            "hh_n_edu_unknown": Agg.n(Where("p_edu_status", "==", "unknown")),
        }
        a = aggregate(data, p, "household", specs, base_columns=["HHSIZE", "HHVEHCNT"])
        reports.append(a.attrs["pynhts_aggregate"])
        a["hh_n_unlisted"] = a["HHSIZE"] - a["hh_n_persons_listed"]
        a["hh_share_univ"] = a["hh_n_univ"] / a["hh_n_edu_answered"].where(
            a["hh_n_edu_answered"] > 0
        )
        if strict:
            for c in ("hh_n_workers", "hh_n_drivers"):
                a[c] = a[c].where(a[f"{c}_unknown"] == 0)
        a["hh_veh_per_person"] = a["HHVEHCNT"] / a["HHSIZE"].where(a["HHSIZE"] > 0)
        a["hh_veh_per_driver"] = a["HHVEHCNT"] / a["hh_n_drivers"].where(a["hh_n_drivers"] > 0)
        a["hh_zero_vehicle"] = a["HHVEHCNT"] == 0
        keep = [c for c in a.columns if c.startswith("hh_")]
        if "composition" not in sel:
            keep = [
                c
                for c in keep
                if c
                in (
                    "hh_veh_per_person",
                    "hh_veh_per_driver",
                    "hh_zero_vehicle",
                    "hh_n_drivers",
                    "hh_n_drivers_unknown",
                )
            ]
        out = _merge(out, a[[*keys, *keep]], keys)
        names += keep

    if {"travel", "modes", "purposes"} & set(sel):
        t = _trip_frame(data)
        specs = {"hh_n_trips": Agg.n()}
        if "travel" in sel:
            specs["hh_miles"] = Agg.sum("TRPMILES")
            specs["hh_vmt"] = Agg.sum(
                "TRPMILES",
                Where("drv", "==", "yes") & Where("t_mode_group", "==", "private_vehicle"),
            )
        if "modes" in sel:
            specs |= {
                f"hh_trips_mode_{g}": Agg.n(Where("t_mode_group", "==", g)) for g in MODE_GROUPS
            }
        if "purposes" in sel:
            specs |= {f"hh_trips_purpose_{g}": Agg.n(Where("t_purpose", "==", g)) for g in PURPOSES}
        a = aggregate(data, t, "household", specs, missing=miles_missing)
        reports.append(a.attrs["pynhts_aggregate"])
        a["hh_zero_trip"] = a["hh_n_trips"] == 0
        if "modes" in sel:
            cnt = a[[f"hh_trips_mode_{g}" for g in MODE_GROUPS]]
            known = cnt.sum(axis=1)
            a["hh_trips_unknown_mode"] = a["hh_n_trips"] - known
            for g in MODE_GROUPS:
                a[f"hh_mode_share_{g}"] = cnt[f"hh_trips_mode_{g}"] / known.where(known > 0)
            a["hh_n_modes"] = (cnt > 0).sum(axis=1)
            a["hh_multimodal"] = a["hh_n_modes"] >= 2
            share = cnt.div(known.where(known > 0), axis=0)
            a["hh_mode_entropy"] = 0.0 - (share * np.log(share.where(share > 0))).sum(
                axis=1, min_count=1
            ).where(known > 0)
        keep = [c for c in a.columns if c.startswith("hh_")]
        out = _merge(out, a[[*keys, *keep]], keys)
        names += keep

    if "fleet" in sel:
        v = data.vehicles(["VEHAGE", "VEHTYPE"], missing="nan", skip="keep")
        v["vage"] = pd.to_numeric(v["VEHAGE"], errors="coerce")
        v["vtype"] = harmonize.apply(v["VEHTYPE"], "vehicle_type", data.wave)
        specs = {
            "hh_n_vehicles_listed": Agg.n(),
            "hh_fleet_median_age": Agg.median("vage"),
            "hh_n_vehicles_new": Agg.n(Where("vage", "<=", 5)),
        }
        specs |= {
            f"hh_n_veh_{g}": Agg.n(Where("vtype", "==", g)) for g in ("car", "suv", "van", "pickup")
        }
        a = aggregate(data, v, "household", specs, missing="skip")
        reports.append(a.attrs["pynhts_aggregate"])
        keep = [c for c in a.columns if c.startswith("hh_")]
        out = _merge(out, a[[*keys, *keep]], keys)
        names += keep
    return _stamp(out, base, "household", names, reports)


# ---- trip -------------------------------------------------------------------------------------
TRIP_GROUPS = ("distance_time", "purpose_mode", "sequence")


def create_trip_features(
    data: NHTSData,
    groups: Sequence[str] | None = None,
    *,
    distance_bins: Sequence[float] = DISTANCE_BINS,
    distance_labels: Sequence[str] = DISTANCE_LABELS,
) -> pd.DataFrame:
    """Trip-level features (one row per trip, with ``WTTRDFIN``; bins are configurable)."""
    sel = _check_groups(groups, TRIP_GROUPS)
    keys = list(data.key("trip"))
    base = data.trips([])
    out = base
    names: list[str] = []
    if "distance_time" in sel:
        t = data.trips(["TRPMILES", "TRVLCMIN", "STRTTIME"], missing="nan", skip="auto")
        part = t[keys].copy()
        part["t_distance_band"] = pd.cut(
            t["TRPMILES"], list(distance_bins), labels=list(distance_labels), right=False
        )
        part["t_duration_band"] = pd.cut(
            t["TRVLCMIN"], list(DURATION_BINS), labels=list(DURATION_LABELS), right=False
        )
        hour = pd.to_numeric(t["STRTTIME"], errors="coerce") // 100
        part["t_depart_period"] = pd.cut(
            hour,
            [-1, 5, 8, 14, 18, 21, 24],
            labels=["night", "am_peak", "midday", "pm_peak", "evening", "night_late"],
        ).astype("string")
        part["t_depart_period"] = part["t_depart_period"].replace({"night_late": "night"})
        part["t_is_long_distance"] = (
            (t["TRPMILES"] >= 50).where(t["TRPMILES"].notna()).astype("boolean")
        )
        out = _merge(out, part, keys)
        names += [c for c in part.columns if c.startswith("t_")]
    if "purpose_mode" in sel:
        t = _trip_frame(data)
        part = t[[*keys, "t_mode", "t_mode_group", "t_purpose"]].copy()
        part["t_is_work"] = (
            (part["t_purpose"] == "work").where(part["t_purpose"].notna()).astype("boolean")
        )
        out = _merge(out, part, keys)
        names += [c for c in part.columns if c.startswith("t_")]
    if "sequence" in sel:
        pk = list(data.key("person"))
        t = data.trips([], weight=False)
        t = t.reset_index(drop=True)
        order = pd.to_numeric(t[keys[-1]], errors="coerce")
        t["_o"] = order if order.notna().all() else t[keys[-1]].rank(method="first")
        t = t.sort_values([*pk, "_o"], kind="stable")
        t["t_order"] = t.groupby(pk, sort=False).cumcount() + 1
        n = t.groupby(pk, sort=False)["t_order"].transform("max")
        t["t_is_first"] = t["t_order"] == 1
        t["t_is_last"] = t["t_order"] == n
        out = _merge(out, t[[*keys, "t_order", "t_is_first", "t_is_last"]], keys)
        names += ["t_order", "t_is_first", "t_is_last"]
    return _stamp(out, base, "trip", names, [])


# ---- vehicle ----------------------------------------------------------------------------------
def create_vehicle_features(data: NHTSData) -> pd.DataFrame:
    """Vehicle-level features (one row per vehicle, with ``WTHHFIN``)."""
    keys = list(data.key("vehicle"))
    base = data.vehicles([])
    v = data.vehicles(
        ["VEHAGE", "VEHTYPE", *(["FUELTYPE"] if data.wave != 2022 else [])],
        missing="nan",
        skip="keep",
    )
    part = v[keys].copy()
    part["v_age_band"] = pd.cut(
        pd.to_numeric(v["VEHAGE"], errors="coerce"),
        [-1, 2, 5, 10, 15, np.inf],
        labels=["0-2", "3-5", "6-10", "11-15", "16+"],
    )
    part["v_type"] = harmonize.apply(v["VEHTYPE"], "vehicle_type", data.wave)
    names = ["v_age_band", "v_type"]
    if data.wave != 2022:
        part["v_fuel"] = harmonize.apply(v["FUELTYPE"], "fuel", data.wave)
        names.append("v_fuel")
    return _stamp(_merge(base, part, keys), base, "vehicle", names, [])
