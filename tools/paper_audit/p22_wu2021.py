"""P22 - Wu & MacKenzie (2021), Transportation Research Part D 94: the VMT effect of ridesourcing, NHTS 2017.

Table 1 (weighted): by ridesourcing user group (none / occasional < 4 uses / frequent >= 4 uses in 30 days), the household
vehicles, daily auto trips and occupancy-adjusted daily VMT of persons 16+, separately for "drivers with household vehicle
access" and "not a driver OR without a household vehicle". Built with pynhts.aggregate on a trip frame the script prepares
(distance / vehicle occupancy; a 60 % deadheading mark-up on taxi/ridesourcing trips; trips over 500 miles dropped).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import common

common.setup()
import pynhts  # noqa: E402
from pynhts import aggregate as A  # noqa: E402

a = common.Audit("p22_wu2021")
d = pynhts.load(2017)
ALPHA = 0.6
PV = ["03", "04", "05", "06", "08", "09", "18"]   # car, SUV, van, pickup, motorcycle, RV, rental car (recovered by testing)
TR = ["17"]                                          # taxi / limo including Uber and Lyft: the survey cannot separate them

t = d.trips(["TRPTRANS", "TRPMILES", "NUMONTRP", "HHSTATE"], missing="nan", skip="keep", weight=False)
tt = pd.to_numeric(t["TRPMILES"])
tr = t[t["TRPTRANS"].isin(TR)]
a.check("taxi/ridesourcing trips in the file", 2718, len(tr))
a.check("states with such trips", 44, tr["HHSTATE"].nunique())
tw = d.trips(["TRPTRANS"], missing="nan", skip="keep")
a.check("annual weighted taxi/ridesourcing trips (billions)", 1.85, float(tw.loc[tw["TRPTRANS"].isin(TR), "WTTRDFIN"].sum() / 1e9))
a.check("mode share of all weighted trips, %", 0.5, float(tw.loc[tw["TRPTRANS"].isin(TR), "WTTRDFIN"].sum() / tw["WTTRDFIN"].sum() * 100))

# ---- trip frame for the person-day aggregation
x = t[["HOUSEID", "PERSONID", "TRPTRANS"]].copy()
dist = tt.where((tt >= 0) & (tt <= 500))                         # single trips over 500 miles excluded
vo = pd.to_numeric(t["NUMONTRP"]).where(lambda s: s >= 1)       # people on the trip including the respondent
x["pv"] = x["TRPTRANS"].isin(PV)
x["tr"] = x["TRPTRANS"].isin(TR)
x["vmt_pv"] = np.where(x["pv"], dist / vo, 0.0)
x["vmt_tr"] = np.where(x["tr"], dist / vo, 0.0)
x["vmt_dead"] = ALPHA * x["vmt_tr"]
x.loc[(x["pv"] | x["tr"]) & dist.isna(), ["vmt_pv", "vmt_tr", "vmt_dead"]] = np.nan
day = A.aggregate(d, x, "person", {
    "trips_pv": A.Agg.n(A.Where("pv", "==", True)), "trips_tr": A.Agg.n(A.Where("tr", "==", True)),
    "mi_pv": A.Agg.sum("vmt_pv"), "mi_tr": A.Agg.sum("vmt_tr"), "mi_dead": A.Agg.sum("vmt_dead"),
}, missing="skip", orphans="report")

pp = d.persons(["R_AGE", "RIDESHARE", "DRIVER", "HHVEHCNT", "CNTTDTR"], missing="nan", skip="keep")
p = pp.merge(day[["HOUSEID", "PERSONID", "trips_pv", "trips_tr", "mi_pv", "mi_tr", "mi_dead"]], on=["HOUSEID", "PERSONID"], how="left")
rs = pd.to_numeric(p["RIDESHARE"])
p = p[(pd.to_numeric(p["R_AGE"]) >= 16) & rs.ge(0)].copy()
p["group"] = pd.cut(rs[p.index], [-1, 0, 3, 1000], labels=["non", "occasional", "frequent"])
everyone = p.copy()                                       # population shares and vehicles use everyone aged 16+
w = p["WTPERFIN"]
a.info("persons 16+ with a ridesourcing answer", len(p), "")
for g, pub in (("non", 90.19), ("occasional", 5.83), ("frequent", 3.97)):
    a.check(f"% of population, {g}", pub, float(w[p["group"] == g].sum() / w.sum() * 100))

# Table 1's trip and mileage rows are means over the persons who made at least one AUTO trip (private vehicle or taxi/ridesourcing)
# on the travel day. Recovered by testing: over all persons the 'not a driver' column is 63 % low (1.15 against 3.13 auto trips),
# over persons with any trip 45 % low (1.73), over persons with an auto trip it is exact (3.134), as is the drivers' column
# (4.030 against 4.03). pynhts.aggregate returns NaN, not 0, for persons without trips here (user-frame default), which
# makes the means below conditional on a trip record already; the explicit filter states the convention.
p["trips_auto"] = p["trips_pv"].fillna(0) + p["trips_tr"].fillna(0)
p = p[p["trips_auto"] > 0].copy()
w = p["WTPERFIN"]
a.info("persons 16+ with at least one auto trip (base of the trip and VMT rows)", len(p), "")
veh = pd.to_numeric(p["HHVEHCNT"])
drv = p["DRIVER"] == "01"
access = drv & (veh > 0)
p["trips_auto"] = p["trips_pv"] + p["trips_tr"]
p["vmt"] = p["mi_pv"] + p["mi_tr"] + p["mi_dead"]


def wm(col: str, mask: pd.Series) -> float:
    v = p.loc[mask, col]
    ww = w[mask][v.notna()]
    return float((v.dropna() * ww).sum() / ww.sum())


for g, veh_pub, has_pub in (("non", 2.24, 93.99), ("occasional", 2.00, 91.96), ("frequent", 1.61, 81.42), ("all", 2.20, 93.37)):
    ev = pd.to_numeric(everyone["HHVEHCNT"])
    ew = everyone["WTPERFIN"]
    m = (everyone["group"] == g) if g != "all" else pd.Series(True, index=everyone.index)
    a.check(f"avg household vehicles, {g}", veh_pub, float((ev[m] * ew[m]).sum() / ew[m].sum()))
    a.check(f"% with a household vehicle, {g}", has_pub, float(((ev[m] > 0) * ew[m]).sum() / ew[m].sum() * 100))

T1 = {  # (scope, group): (trips auto, trips PV, trips T/R, VMT, mi PV, mi T/R, deadheading)
    ("access", "non"): (4.03, 4.02, 0.01, 27.01, 26.96, 0.03, 0.02),
    ("access", "occasional"): (4.03, 3.99, 0.04, 30.02, 29.73, 0.18, 0.11),
    ("access", "frequent"): (3.77, 3.51, 0.26, 26.94, 24.92, 1.26, 0.76),
    ("access", "all"): (4.02, 4.00, 0.02, 27.19, 27.06, 0.08, 0.05),
    ("none", "non"): (3.13, 3.06, 0.07, 9.94, 9.46, 0.30, 0.18),
    ("none", "occasional"): (2.42, 2.27, 0.15, 14.78, 13.64, 0.71, 0.43),
    ("none", "frequent"): (2.55, 1.62, 0.93, 13.95, 9.02, 3.08, 1.85),
    ("none", "all"): (3.06, 2.92, 0.14, 10.46, 9.64, 0.51, 0.31),
}
cols = ("trips_auto", "trips_pv", "trips_tr", "vmt", "mi_pv", "mi_tr", "mi_dead")
labels = ("daily auto trips", "by private vehicle", "by T/R vehicle", "daily VMT", "miles by private vehicle", "miles by T/R vehicle",
          "T/R deadheading")
for (scope, g), pub in T1.items():
    base = access if scope == "access" else ~access
    m = base & ((p["group"] == g) if g != "all" else True)
    name = "drivers with household vehicle" if scope == "access" else "not driver or no vehicle"
    for col, lab, val in zip(cols, labels, pub, strict=True):
        a.check(f"[{name}] {g}: {lab}", val, wm(col, m))
a.save()
