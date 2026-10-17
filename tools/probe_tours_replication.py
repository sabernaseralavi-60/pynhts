"""Feasibility probe for pynhts.tours: rebuild the sample of McNally & Rafiq (2021) from the public
2017 NHTS files and compare with the numbers printed in their open final report.

    PYNHTS_CACHE_DIR=... python tools/probe_tours_replication.py

Target report: McNally, M. G. and Rafiq, R. (2021). Analysis of Activity-Travel Patterns and Tour
Formation of Transit Users. Final Report PSR-19-33, METRANS / ITS-Irvine, section 2.1-2.5
(https://www.metrans.org/assets/research/psr-19-33_to-033_mcnally_finalreport.pdf).

This is a throw-away probe, not the future library API. It uses unweighted counts, as the report
does, and one reading of every undefined detail (see docs/tours_design_notes.md).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import pynhts

HOME = {"01", "02"}           # regular home activities, work from home (destination is home)
TRANSIT = {"11", "14", "15", "16"}   # public bus, city-to-city bus, Amtrak/commuter rail, subway/light rail
PK = ["HOUSEID", "PERSONID"]


def trips_frame(data: pynhts.NHTSData) -> pd.DataFrame:
    t = data.trips(["WHYFROM", "WHYTO", "TRPMILES", "TRPTRANS"], weight=False, missing="keep")
    t["n"] = t["TDTRPNUM"].astype(int)
    t = t.sort_values([*PK, "n"]).reset_index(drop=True)
    t["transit"] = t["TRPTRANS"].isin(TRANSIT)
    return t


def transit_user_sample(t: pd.DataFrame) -> pd.DataFrame:
    """Person-days that start and end at home and use transit on at least one trip."""
    g = t.groupby(PK)
    ok = g["WHYFROM"].transform("first").isin(HOME) & g["WHYTO"].transform("last").isin(HOME)
    return t[ok & g["transit"].transform("any")]


def add_tours(t: pd.DataFrame, home: set[str]) -> pd.DataFrame:
    """Number the tours of each person-day: a tour ends with every trip that arrives at home."""
    arrive_home = t["WHYTO"].isin(home).astype(int)
    out = t.copy()
    out["tour"] = arrive_home.groupby([t["HOUSEID"], t["PERSONID"]]).cumsum() - arrive_home
    g = out.groupby([*PK, "tour"])
    out["complete"] = g["WHYFROM"].transform("first").isin(home) & g["WHYTO"].transform("last").isin(home)
    return out


def work_pattern(destinations: list[str]) -> tuple[int, int, int, int] | None:
    """(stops before work, stops after work, stops between work activities, number of work stops)."""
    s = "".join("H" if d == "01" else "W" if d == "03" else "N" for d in destinations).rstrip("H")
    if "W" not in s:
        return None
    first, last = s.index("W"), s.rindex("W")
    return s[:first].count("N"), s[last + 1:].count("N"), s[first:last + 1].count("N"), s.count("W")


def main() -> None:
    data = pynhts.load(2017, offline=True)
    t = trips_frame(data)

    users = transit_user_sample(t)
    print("Transit-user sample (day starts and ends at home, >= 1 transit trip)")
    print(f"  persons {users.groupby(PK).ngroup().nunique():,}   published 4,994")
    print(f"  trips   {len(users):,}   published 20,222")
    print(f"  transit trips {int(users['transit'].sum()):,}   published 10,011")

    age = data.persons(["R_AGE"], weight=False)[[*PK, "R_AGE"]]
    # home = {01} for the tour step reproduces the published tour counts best (2,456 vs 2,454)
    tours = add_tours(t, {"01"})
    c = tours[tours["complete"]].merge(age, on=PK)
    c = c[c["R_AGE"] >= 18]
    key = [*PK, "tour"]
    pattern = c.groupby(key)["WHYTO"].apply(lambda s: work_pattern(list(s))).dropna()
    on_transit = c.groupby(key)["transit"].any()
    hbw = pattern.index.intersection(on_transit[on_transit].index)
    print("\nHome-based work tours of adults with a transit trip on the tour")
    print(f"  tours   {len(hbw):,}   published 2,454")
    print(f"  persons {hbw.droplevel('tour').nunique():,}   published 2,448")

    p = pattern.loc[hbw]
    share = p.map(lambda x: (x[0], x[1], x[2])).value_counts(normalize=True) * 100
    print(f"  pattern (0,0,0) simple work tour: {share.get((0, 0, 0), 0):.1f} %   published 49 %")
    kinds = p.map(lambda x: "work-based" if x[2] > 0 else "simple" if x[:3] == (0, 0, 0) else "complex")
    print("  simple / complex / work-based (%):",
          (kinds.value_counts(normalize=True) * 100).round(1).to_dict(), "  published 49 / 32 / 19")
    print(f"  tours with two or more work stops and no other stop: "
          f"{int(((p.map(lambda x: x[3]) > 1) & (p.map(lambda x: x[:3]) == (0, 0, 0))).sum())}"
          "   published 70 (2.8 %)")


if __name__ == "__main__":
    main()
