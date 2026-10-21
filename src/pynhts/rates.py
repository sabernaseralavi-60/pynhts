"""Daily travel rates by the route each wave's documentation uses, with units in the result.

>>> import pynhts
>>> from pynhts import rates
>>> rates.daily_rate(pynhts.load(2009, replicates=True), "trips", per="person")   # doctest: +SKIP

A total from the travel-day weight is ANNUAL (the weight is 365 x the person weight), so a daily
rate is ``total trips / 365 / total persons``. The numerator uses the trip weights (the
official route; in 2022 they contain the methods adjustment, so the rate is 2.275 trips per
person and day, not the 2.078 that ``CNTTDTR`` x the person weight gives) and the denominator the
person or household weights, with a ratio variance across the two weight systems.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import pandas as pd

from pynhts.stats.survey import ratio_across

if TYPE_CHECKING:
    from pynhts.core.data import NHTSData

DAYS = 365.0


def daily_rate(
    data: NHTSData,
    quantity: Literal["trips", "miles"] = "trips",
    *,
    per: Literal["person", "household"] = "person",
    min_age: int | None = None,
    level: float = 0.95,
) -> pd.DataFrame:
    """Person trips or person miles per day, per person or per household.

    Args:
        data: An opened wave.
        quantity: ``"trips"`` (person trips) or ``"miles"`` (``TRPMILES``; trips without a
            distance add 0 miles, as FHWA's tables do).
        per: Divide by persons or by households.
        min_age: Count only persons (and their trips) of at least this age. The 2001 file
            holds children 0-4, the other waves do not: ``min_age=5`` makes the rates comparable.
            Persons of unknown age (2001: 2,399) are left out when ``min_age`` is given. The
            published 2001 per-person rate without children (3.74) divides by all persons and is
            reproduced by the recipe ``stt2001``, not by this option.
        level: Confidence level.

    Returns:
        One row (``estimate``, ``se``, ``moe``, ``ci_low``, ``ci_high``, ``cv``, ``n``) with
        ``attrs["pynhts"]`` naming the unit ("daily person trips per person", ...).
    """
    cols = ["R_AGE"] if min_age is not None else []
    trips = data.survey("trip", [*cols, *(["TRPMILES"] if quantity == "miles" else [])],
                        level=level)
    denominator = data.survey("person" if per == "person" else "household",
                              cols if per == "person" else [], level=level)
    var = "TRPMILES" if quantity == "miles" else None
    num_domain = den_domain = None
    if min_age is not None:
        num_domain = trips.rows["R_AGE"] >= min_age
        den_domain = (denominator.rows["R_AGE"] >= min_age) if per == "person" else None
    if quantity == "miles":
        trips.rows["TRPMILES"] = trips.rows["TRPMILES"].fillna(0.0)
    res = ratio_across(trips, var, denominator, None, num_domain=num_domain,
                       den_domain=den_domain)
    for c in ("estimate", "se", "moe", "ci_low", "ci_high"):
        res[c] = res[c] / DAYS
    meta = dict(res.attrs["pynhts"])
    meta["unit"] = f"daily person {quantity} per {per}"
    res.attrs["pynhts"] = meta
    return res
