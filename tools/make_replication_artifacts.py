"""Figure 1 and Table 1 of the McNally & Rafiq (2021) replication manuscript (NHTS 2017).

Figure 1: 24-hour activity diary of transit users (weighted person-days), rail vs bus-only users.
Table 1:  weighted characteristics of home-based work (HBW) tours with at least one transit trip.

Usage (data must already be in the pynhts cache; set PYNHTS_CACHE_DIR if it is elsewhere)::

    python tools/make_replication_artifacts.py [outdir]

Sample definitions are those of ``pynhts.recipes.mcnally_rafiq2021``: transit modes 11/14/15/16,
transit users = persons whose day starts and ends at home with >= 1 transit trip, HBW tours =
complete tours with a work stop, adults (18+), >= 1 transit trip on the tour.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

import pynhts
from pynhts import tables, viz
from pynhts.tours import TourConfig

PK = ["HOUSEID", "PERSONID"]
TRANSIT, RAIL = {"11", "14", "15", "16"}, {"15", "16"}
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("paper/replication")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = pynhts.load(2017, offline=True)
    t0 = time.time()
    res = data.tours(TourConfig.mcnally_rafiq())
    print(f"tours ready in {time.time() - t0:.1f} s: {len(res.tours):,} tours")
    trips = res.trips.assign(transit=lambda x: x["TRPTRANS"].isin(TRANSIT),
                             rail=lambda x: x["TRPTRANS"].isin(RAIL))

    # ---- Figure 1: transit users ---------------------------------------------------------
    user_ids = trips[trips["day_complete"] & trips.groupby(PK)["transit"].transform("any")]
    flags = user_ids.groupby(PK)["rail"].any().rename("rail_user").reset_index()
    persons = data.persons(["R_AGE"])[[*PK, "WTPERFIN"]]
    users = flags.merge(persons, on=PK, validate="1:1")
    users["User group"] = np.where(
        users["rail_user"], "Rail users (any rail trip)", "Bus-only users")
    print(f"transit users: {len(users):,} (recipe target 4,994)")
    profile = viz.activity_profile(trips, users, by="User group")
    fig = viz.plot_profile(
        profile,
        title="Activity of transit users over the day, NHTS 2017 (weighted persons)",
        ncols=1, savepath=[OUT / "figure1_activity_diary.png", OUT / "figure1_activity_diary.pdf"],
    )
    profile.to_csv(OUT / "figure1_activity_diary_data.csv", index=False)
    del fig

    # ---- Table 1: weighted HBW transit tours ---------------------------------------------
    cols = ["R_AGE", "R_SEX", "HHVEHCNT"]
    people = data.persons(cols, weight=False)[[*PK, *cols]]
    on_transit = trips.groupby([*PK, "tour"])[["transit", "rail"]].any()
    tours = (res.tours.merge(people, on=PK, validate="m:1")
             .merge(on_transit.reset_index(), on=[*PK, "tour"], validate="1:1"))
    keep = (tours["tour_class"] == "HBW") & tours["transit"] & (tours["R_AGE"] >= 18)
    tours = tours[keep].reset_index(drop=True)
    print(f"HBW transit tours of adults: {len(tours):,} (recipe target 2,454)")
    s = data.survey_rows(tours, "trip")

    wt = tours["work_type"]
    age = pd.cut(tours["R_AGE"], [17, 34, 54, 120], labels=["18-34", "35-54", "55+"])
    pct = {"scale": 100.0, "digits": 1}
    rows = [
        tables.Row("Annual HBW transit tours (millions)", s.total(), scale=1e-6, digits=1),
        tables.Row("Trips per tour, mean", s.mean(tours["n_trips"].astype(float)), digits=2),
        tables.Row("Simple (one work stop only), %", s.proportion(wt == "simple"), **pct),
        tables.Row("Complex, %", s.proportion(wt == "complex"), **pct),
        tables.Row("Work-based subtour, %", s.proportion(wt == "work_based"), **pct),
        tables.Row("Multiple work stops, %", s.proportion(wt == "multi_work"), **pct),
        tables.Row("Tour includes rail, %", s.proportion(tours["rail"]), **pct),
        tables.Row("Women, %", s.proportion(tours["R_SEX"] == "02"), **pct),
        tables.Row("Age 18-34, %", s.proportion(age == "18-34"), **pct),
        tables.Row("Age 35-54, %", s.proportion(age == "35-54"), **pct),
        tables.Row("Age 55+, %", s.proportion(age == "55+"), **pct),
        tables.Row("Zero-vehicle household, %", s.proportion(tours["HHVEHCNT"] == 0), **pct),
    ]
    table = tables.build(rows, show_n=False)
    notes = tables.note(table).replace(
        " $n$ is the unweighted number of records.",
        f" Unweighted sample: {len(tours):,} tours. Work-tour types are mutually exclusive.")
    caption = ("Weighted characteristics of home-based work tours with at least one transit trip, "
               "adults, NHTS 2017")
    (OUT / "table1.tex").write_text(
        tables.to_latex(table, caption=caption, label="tab:work-tours", notes=notes),
        encoding="utf-8")
    (OUT / "table1.md").write_text(tables.to_markdown(table, notes=notes), encoding="utf-8")
    print(tables.to_markdown(table, notes=notes))


if __name__ == "__main__":
    main()
