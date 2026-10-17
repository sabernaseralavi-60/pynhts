"""Tour formation: cut each person-day's trip sequence into tours and classify them.

A **tour** is the part of a person's day between two consecutive arrivals at home: every trip that
arrives at a home location closes the tour it belongs to. A tour is *complete* when its first trip
leaves home and its last trip arrives home. Each destination is typed ``H`` (home), ``W`` (work)
or ``N`` (any other activity), and a tour that contains work is described by McNally and Rafiq's
3-tuple (a, b, c): the number of other stops before the first work stop, after the last work stop
and between work stops.

``tour_class`` follows the trip-purpose convention of the NHTS: ``HBW`` (complete tour containing
work), ``HBO`` (complete tour without work) and ``NHB`` (tour that does not both start and end at
home).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from pynhts.tours.config import TourConfig

PK = ["HOUSEID", "PERSONID"]
TK = [*PK, "tour"]
REQUIRED = ["HOUSEID", "PERSONID", "TDTRPNUM", "WHYFROM", "WHYTO"]


@dataclass(frozen=True)
class TourResult:
    """Output of :func:`build_tours`.

    Attributes:
        trips: The input trips (sorted by person and trip number) plus ``tour`` (0-based number
            within the person-day), ``trip_in_tour``, ``tour_complete``, ``day_complete``,
            ``activity`` (``H``/``W``/``N`` of the destination) and ``invalid_purpose``.
        tours: One row per tour with its size, completeness, activity string, class, work-tour
            pattern and type.
        config: The parameters used.
    """

    trips: pd.DataFrame
    tours: pd.DataFrame
    config: TourConfig


def _invalid(series: pd.Series) -> pd.Series:
    """True where a purpose is missing or a survey code (negative number as text)."""
    s = series.astype("string")
    return (s.isna() | s.str.startswith("-").fillna(False)).astype(bool)


def build_tours(trips: pd.DataFrame, config: TourConfig | None = None) -> TourResult:
    """Form tours from a trip table.

    Args:
        trips: Trips with ``HOUSEID``, ``PERSONID``, ``TDTRPNUM``, ``WHYFROM`` and ``WHYTO``.
            Load purposes with ``missing="keep"`` (or ``"nan"``; both are handled, and invalid
            purposes are flagged either way). Extra columns are carried along.
        config: Tour parameters; the default treats work-from-home as home.

    Returns:
        A :class:`TourResult` with the tagged trips and the tour table.

    Raises:
        ValueError: a required column is missing.
    """
    cfg = config or TourConfig()
    missing = [c for c in REQUIRED if c not in trips.columns]
    if missing:
        raise ValueError(f"trips lack required columns: {missing}")

    df = trips.copy()
    df["_seq"] = pd.to_numeric(df["TDTRPNUM"], errors="raise").astype(int)
    df = df.sort_values([*PK, "_seq"], kind="stable").reset_index(drop=True)
    why_from, why_to = df["WHYFROM"].astype("string"), df["WHYTO"].astype("string")
    df["invalid_purpose"] = _invalid(df["WHYFROM"]) | _invalid(df["WHYTO"])

    home, work = list(cfg.home_codes), list(cfg.work_codes)
    arrives_home = why_to.isin(home).fillna(False).to_numpy()
    arrive = pd.Series(arrives_home.astype(int), index=df.index)
    df["tour"] = arrive.groupby([df["HOUSEID"], df["PERSONID"]]).cumsum() - arrive

    gt = df.groupby(TK, sort=False)
    df["trip_in_tour"] = gt.cumcount()
    first_from = why_from.groupby([df["HOUSEID"], df["PERSONID"], df["tour"]]).transform("first")
    last_to = why_to.groupby([df["HOUSEID"], df["PERSONID"], df["tour"]]).transform("last")
    df["tour_complete"] = (first_from.isin(home) & last_to.isin(home)).fillna(False).astype(bool)

    day_first = why_from.groupby([df["HOUSEID"], df["PERSONID"]]).transform("first")
    day_last = why_to.groupby([df["HOUSEID"], df["PERSONID"]]).transform("last")
    day_home = list(cfg.day_home)
    df["day_complete"] = (day_first.isin(day_home) & day_last.isin(day_home)).fillna(
        False).astype(bool)

    act = np.where(arrives_home, "H", np.where(why_to.isin(work).fillna(False), "W", "N"))
    df["activity"] = act
    is_w, is_n = df["activity"] == "W", df["activity"] == "N"
    pos = df["trip_in_tour"].astype(float)
    first_w = pos.where(is_w).groupby([df["HOUSEID"], df["PERSONID"], df["tour"]]).transform("min")
    last_w = pos.where(is_w).groupby([df["HOUSEID"], df["PERSONID"], df["tour"]]).transform("max")
    df["_before"] = (is_n & (pos < first_w)).astype(int)
    df["_after"] = (is_n & (pos > last_w)).astype(int)
    df["_during"] = (is_n & (pos > first_w) & (pos < last_w)).astype(int)
    df["_work"] = is_w.astype(int)

    gt = df.groupby(TK, sort=False)
    tours = gt.agg(
        n_trips=("_seq", "size"),
        first_trip=("_seq", "first"),
        last_trip=("_seq", "last"),
        complete=("tour_complete", "first"),
        day_complete=("day_complete", "first"),
        has_invalid=("invalid_purpose", "any"),
        n_work=("_work", "sum"),
        n_before=("_before", "sum"),
        n_after=("_after", "sum"),
        n_during=("_during", "sum"),
        activities=("activity", "".join),
    ).reset_index()

    has_work = tours["n_work"] > 0
    tours["tour_class"] = np.select(
        [~tours["complete"], has_work], ["NHB", "HBW"], default="HBO")
    wt = np.select(
        [tours["n_during"] > 0, (tours["n_before"] + tours["n_after"]) > 0, tours["n_work"] > 1],
        ["work_based", "complex", "multi_work"], default="simple")
    tours["work_type"] = pd.Series(wt, index=tours.index).where(has_work).astype("string")
    label = (
        "(" + tours["n_before"].astype(str) + "," + tours["n_after"].astype(str) + ","
        + tours["n_during"].astype(str) + ")"
    )
    tours["pattern"] = label.where(has_work).astype("string")

    drop = [c for c in df.columns if c.startswith("_")]
    df = df.drop(columns=drop)
    if cfg.drop_invalid:
        bad = tours.loc[tours["has_invalid"], TK]
        tours = tours[~tours["has_invalid"]].reset_index(drop=True)
        df = df.merge(bad.assign(_drop=1), on=TK, how="left")
        df = df[df.pop("_drop").isna()].reset_index(drop=True)
    return TourResult(df, tours, cfg)


def chain_ids(
    trips: pd.DataFrame, config: TourConfig | None = None, threshold: float | None = None
) -> pd.Series:
    """Number the *chains* of each person-day (FHWA's chained-trip idea).

    A chain is travel between two anchors with, at most, short stops in between: a chain ends after
    a trip that arrives at home or work, or after a stop longer than the dwell threshold (minutes,
    from the trip's ``DWELTIME``; FHWA's 2001 definition uses 30). Not validated against a
    published table yet.

    Args:
        trips: Trips with the columns of :func:`build_tours` and ``DWELTIME``.
        config: Provides the home and work codes.
        threshold: Dwell threshold in minutes; defaults to ``config.dwell_threshold`` or 30.

    Returns:
        Chain number (0-based within the person-day), indexed like the sorted trips.
    """
    cfg = config or TourConfig()
    thr = threshold if threshold is not None else (cfg.dwell_threshold or 30.0)
    if "DWELTIME" not in trips.columns:
        raise ValueError("trips need the DWELTIME column")
    df = trips.copy()
    df["_seq"] = pd.to_numeric(df["TDTRPNUM"]).astype(int)
    df = df.sort_values([*PK, "_seq"], kind="stable").reset_index(drop=True)
    anchors = list(cfg.home_codes | cfg.work_codes)
    long_stop = pd.to_numeric(df["DWELTIME"], errors="coerce") > thr
    ends = (df["WHYTO"].astype("string").isin(anchors).fillna(False) | long_stop.fillna(False))
    e = ends.astype(int)
    chain: pd.Series = e.groupby([df["HOUSEID"], df["PERSONID"]]).cumsum() - e
    return chain
