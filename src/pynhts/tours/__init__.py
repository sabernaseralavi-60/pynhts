"""Tour formation and trip chaining.

>>> import pynhts                                                       # doctest: +SKIP
>>> from pynhts import tours                                            # doctest: +SKIP
>>> data = pynhts.load(2017)                                          # doctest: +SKIP
>>> trips = data.trips(["WHYFROM", "WHYTO", "TRPTRANS"], missing="keep")  # doctest: +SKIP
>>> result = tours.build_tours(trips, tours.TourConfig.mcnally_rafiq())   # doctest: +SKIP
>>> result.tours["tour_class"].value_counts()                           # doctest: +SKIP
"""

from pynhts.tours.config import TourConfig
from pynhts.tours.formation import TourResult, build_tours, chain_ids

__all__ = ["TourConfig", "TourResult", "build_tours", "chain_ids"]
