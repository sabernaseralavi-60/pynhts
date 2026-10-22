"""P09 - Fu, Liu, Zhu, Yuan (2020), IEEE APPEEC: EV trip-chain simulation fitted on NHTS.

The paper names only 'the latest NHTS' and never says which trips are 'EV' trips (EVs are a handful of
vehicles in the sample), so several readings are tested against its Table 1 (9 trip categories H/W/O -> H/W/O),
the chain-length distribution (2-6 trips = 94.4 %, mean about 3.3) and the share of chains that start at home
(93.5 %). Nothing is tuned: each reading is reported and the best-matching one is named in the verdict.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import common

common.setup()
import pynhts  # noqa: E402

a = common.Audit("p09_fu2020_evchain")
d = pynhts.load(2017)
t = d.trips(["WHYFROM", "WHYTO", "TRPTRANS", "STRTTIME", "ENDTIME", "TRPMILES", "TRVLCMIN", "DWELTIME", "DRVR_FLG", "VEHID", "TDTRPNUM"],
            missing="nan", skip="auto")
t = t.sort_values(["HOUSEID", "PERSONID", "TDTRPNUM"]).reset_index(drop=True)


def loc(code, home=("01",), work=("03", "04")):
    if pd.isna(code):
        return np.nan
    return "H" if code in home else ("W" if code in work else "O")


T1 = {"H-H": 10.83, "H-W": 11.08, "H-O": 24.74, "W-H": 9.97, "W-W": 2.55, "W-O": 2.80, "O-H": 26.16, "O-W": 1.51, "O-O": 10.35}
pv = t["TRPTRANS"].isin(["03", "04", "05", "06"])
subsets = {"all trips": pd.Series(True, index=t.index), "private-vehicle trips (car/SUV/van/pickup)": pv,
           "private-vehicle trips as driver": pv & (t["DRVR_FLG"] == "01")}
variants = {"home={01}, work={03,04}": dict(home=("01",), work=("03", "04")),
            "home={01,02}, work={03,04}": dict(home=("01", "02"), work=("03", "04"))}
best = None
for vlab, kw in variants.items():
    cat = t["WHYFROM"].map(lambda c: loc(c, **kw)) + "-" + t["WHYTO"].map(lambda c: loc(c, **kw))
    for slab, m in subsets.items():
        s = cat[m].dropna()
        share = s.value_counts(normalize=True) * 100
        err = float(np.mean([abs(share.get(k, 0) - v) for k, v in T1.items()]))
        a.info(f"mean abs error of the nine shares | {slab} | {vlab}", round(err, 2))
        if best is None or err < best[0]:
            best = (err, slab, vlab, share)
err, slab, vlab, share = best
a.info("best reading for Table 1", f"{slab} | {vlab} | mean abs error {err:.2f} pts")
for k, v in T1.items():
    a.check(f"Table 1 share {k} % ({slab}; {vlab})", v, float(share.get(k, 0)))

# chain length = number of trips of a person-day (private-vehicle subset, driver)
m = pv & (t["DRVR_FLG"] == "01")
n = t[m].groupby(["HOUSEID", "PERSONID"]).size()
a.check("mean chain length (trips per person-day, private-vehicle drivers)", 3.3, float(n.mean()), "paper: 'average trip chain length of EV users in NHTS about 3.3'")
a.check("share of chains with 2-6 trips %", 94.4, float(n.between(2, 6).mean() * 100))
a.check("most frequent chain length", 2, int(n.value_counts().idxmax()))
first = t[m].groupby(["HOUSEID", "PERSONID"]).first()
a.check("share of chains starting at home %", 93.5, float((first["WHYFROM"] == "01").mean() * 100))
a.info("electric vehicles in the 2017 vehicle file (FUELTYPE 03 'hybrid, electric or alternative')",
       int((d.vehicles(["FUELTYPE"])["FUELTYPE"] == "03").sum()),
       "no separate BEV flag in the public file: an 'EV' subset cannot be isolated, so the paper's population is ambiguous")
a.save()
