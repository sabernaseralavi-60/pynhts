"""Parameters of tour formation. Every undefined detail of the literature is an explicit option."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TourConfig:
    """How trips are cut into tours and tours are classified.

    Attributes:
        home_codes: Trip-purpose codes (``WHYFROM``/``WHYTO``) whose location is home. A trip
            that arrives at one of them closes a tour. ``"01"`` is "regular home activities";
            ``"02"`` is "work from home (paid)", which takes place at home. The default treats
            both as home because the location is home.
        day_home_codes: Codes that count as home for the *day-level* rule (the first trip of the
            day leaves home and the last trip arrives home). ``None`` means ``home_codes``.
        work_codes: Destination purposes that are work activities. Only ``"03"`` (work) by
            default; adding ``"04"`` (work-related meeting) moves the McNally-Rafiq tour count
            (adults, transit) from 2,456 to 2,535.
        dwell_threshold: Optional stop length in minutes for :func:`pynhts.tours.chain_ids`
            (FHWA's 2001 chained-trip definition uses 30). It does not affect the tours.
        drop_invalid: Drop tours that contain a trip with an invalid (NA or negative) origin or
            destination purpose. They are always flagged in ``has_invalid``.
    """

    home_codes: frozenset[str] = frozenset({"01", "02"})
    day_home_codes: frozenset[str] | None = None
    work_codes: frozenset[str] = frozenset({"03"})
    dwell_threshold: float | None = None
    drop_invalid: bool = False

    @property
    def day_home(self) -> frozenset[str]:
        """Home codes used by the day-level completeness rule."""
        return self.home_codes if self.day_home_codes is None else self.day_home_codes

    @classmethod
    def mcnally_rafiq(cls) -> TourConfig:
        """Rules that rebuild McNally & Rafiq (2021).

        Day level: work-from-home counts as home. Tour level: ``01`` only. This is the
        combination that matches their published counts best.
        """
        return cls(home_codes=frozenset({"01"}), day_home_codes=frozenset({"01", "02"}))

    @classmethod
    def fhwa_chained(cls) -> TourConfig:
        """FHWA's 2001 chained-trip convention: stops of 30 minutes or less stay inside a chain."""
        return cls(dwell_threshold=30.0)
