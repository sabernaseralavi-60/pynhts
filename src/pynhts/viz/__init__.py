"""Figures: the 24-hour activity diary (needs the optional ``matplotlib`` dependency).

>>> from pynhts import viz                                                   # doctest: +SKIP
>>> res = data.tours(columns=["TRPTRANS"])                                   # doctest: +SKIP
>>> persons = data.persons(["R_AGE"])                                        # doctest: +SKIP
>>> fig = viz.plot_activity_diary(res.trips, persons)                        # doctest: +SKIP
"""

from pynhts.viz.diary import (
    DEFAULT_GROUPS,
    TRANSIT,
    activity_profile,
    plot_activity_diary,
    plot_profile,
)

__all__ = [
    "DEFAULT_GROUPS",
    "TRANSIT",
    "activity_profile",
    "plot_activity_diary",
    "plot_profile",
]
