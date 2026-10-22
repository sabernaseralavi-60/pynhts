"""P11 - Alberini, Burra, Cirillo, Shen (2021), Transp. Res. D 98: counting VMT with the NHTS 2017.

Part A (vehicle file): sample (195,251 passenger vehicles in the contiguous US), Tables 1-5 descriptive statistics
(fuel type, MPG, CO2 rate, BESTMILE/ANNMILES, vintage).  The two paper-built measures (MILESDRIVEN from the odometer,
TRIPANNMILES from the one-day diary) are regression constructions; their building blocks (odometer, vehicle age,
survey-day vehicle miles from the trip file) are checked here, the elasticity regressions are out of scope.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import common

common.setup()
import pynhts  # noqa: E402

a = common.Audit("p11_alberini2021")
d = pynhts.load(2017)
cols = ["HFUEL", "FUELTYPE", "FEGEMPG", "FEGEMPGA", "BESTMILE", "ANNMILES", "OD_READ", "VEHAGE", "VEHTYPE", "HHSTATE", "VEHYEAR", "GSCOST"]
v = d.vehicles(cols, missing="nan", skip="auto")
w = "WTHHFIN"
a.check("vehicles in the vehicle file", 256115, len(v))
a.check("pickup trucks share of vehicles (VEHTYPE 4), %", 18.0, float((v["VEHTYPE"] == "04").mean() * 100))
s = v[v["VEHTYPE"].isin(["01", "02", "03"]) & ~v["HHSTATE"].isin(["AK", "HI"])].copy()
a.check("passenger vehicles (cars, minivans, SUVs) in the contiguous US", 195251, len(s))

# ---- powertrain classes
h = s["HFUEL"].astype("string").fillna("")
f = s["FUELTYPE"].astype("string").fillna("")
s["pt"] = np.select(
    [h == "03", h == "02", h == "04", h == "01", (h == "97") | (f == "97"), f == "02", f == "01"],
    ["BEV", "PHEV", "HEV", "Hybrid biodiesel", "Unspecified alt. fuel", "Diesel", "Gasoline"], default="Missing")
T1 = {"Gasoline": 96.57, "HEV": 2.61, "Diesel": 0.75, "PHEV": 0.20, "BEV": 0.19, "Unspecified alt. fuel": 0.11,
      "Hybrid biodiesel": 0.01, "Missing": 0.02}
sh = s.groupby("pt")[w].sum() / s[w].sum() * 100
for k, pub in T1.items():
    a.check(f"Table 1 fuel share {k} %", pub, float(sh.get(k, np.nan)))

# ---- Table 2: MPG by powertrain (counts) and overall weighted mean/percentiles
T2n = {"BEV": 465, "Diesel": 1669, "Gasoline": 187324, "HEV": 4953, "Hybrid biodiesel": 25, "Missing": 28,
       "PHEV": 464, "Unspecified alt. fuel": 239}
cnt = s.groupby("pt").size()
for k, pub in T2n.items():
    a.check(f"Table 2 N {k}", pub, int(cnt.get(k, 0)))
mp = s[s["FEGEMPG"].notna()]
a.check("Table 2 N overall (valid MPG)", 195167, len(mp))


def wq(x, ww, q):
    o = np.argsort(x.values)
    xs, cs = x.values[o], np.cumsum(ww.values[o])
    return float(xs[np.searchsorted(cs, q * cs[-1])])


a.check("Table 2 overall weighted mean MPG", 22.89, float((mp["FEGEMPG"] * mp[w]).sum() / mp[w].sum()))
for q, pub in ((0.25, 19), (0.5, 22), (0.75, 25), (0.9, 30)):
    a.check(f"Table 2 overall MPG p{int(q * 100)}", pub, wq(mp["FEGEMPG"], mp[w], q))

# ---- Table 3: CO2 g/km (8.89 kg/gal gasoline, 10.084 kg/gal diesel, BEV = 0)
mp = mp.copy()
gpm = np.where(mp["pt"] == "Diesel", 10.084e3 / mp["FEGEMPG"], 8.89e3 / mp["FEGEMPG"])
mp["co2"] = np.where(mp["pt"] == "BEV", 0.0, gpm) / 1.609344
mp = mp[mp["pt"] != "PHEV"]  # PHEV rates come from fueleconomy.gov in the paper, not in the NHTS file
a.info("CO2 PHEV rates", "from fueleconomy.gov (external), excluded from this check")
g = mp[mp["pt"] == "Gasoline"]
a.check("Table 3 gasoline mean CO2 g/km", 259.40, float((g["co2"] * g[w]).sum() / g[w].sum()))
a.check("Table 3 gasoline p50 CO2 g/km", 251.09, wq(g["co2"], g[w], 0.5))
dz = mp[mp["pt"] == "Diesel"]
a.check("Table 3 diesel mean CO2 g/km", 257.26, float((dz["co2"] * dz[w]).sum() / dz[w].sum()))

# ---- Table 4: BESTMILE and ANNMILES
for var, nvalid, mean, p25, p50, p75, p90 in (
    ("BESTMILE", 194777, 11603.99, 5358.78, 9551.44, 14842.79, 21633.91),
    ("ANNMILES", 144229, 10806.79, 4000, 9000, 13326, 20000),
):
    x = s[s[var].notna()]
    a.check(f"Table 4A N valid {var}", nvalid, len(x))
    a.check(f"Table 4A mean {var}", mean, float((x[var] * x[w]).sum() / x[w].sum()))
    for q, pub in ((0.25, p25), (0.5, p50), (0.75, p75), (0.9, p90)):
        a.check(f"Table 4A p{int(q * 100)} {var}", pub, wq(x[var], x[w], q))
a.check("BESTMILE = 200,000 (top-coded) count", 131, int((s["BESTMILE"] == 200000).sum()))
a.check("ANNMILES = 200,000 (top-coded) count", 202, int((s["ANNMILES"] == 200000).sum()))
# trimmed samples (Table 4B): drop bottom/top 1 % of each measure
for var, n_pub, mean_pub in (("BESTMILE", 190881, 10901.51), ("ANNMILES", 140961, 9469.41)):
    x = s[s[var].notna()]
    lo, hi = x[var].quantile(0.01), x[var].quantile(0.99)
    y = x[x[var].between(lo, hi)]
    a.check(f"Table 4B N {var} (trim 1 %/99 %)", n_pub, len(y), "trim rule: unweighted 1st and 99th percentile")
    a.check(f"Table 4B mean {var}", mean_pub, float((y[var] * y[w]).sum() / y[w].sum()))
a.check("BESTMILE trim bounds, lower", 221.41, float(s["BESTMILE"].quantile(0.01)))
a.check("BESTMILE trim bounds, upper", 42776.39, float(s["BESTMILE"].quantile(0.99)))

# ---- Section 4.2: vehicle count and vintage groups
a.check("passenger vehicles (millions, household weight)", 176.4, float(s[w].sum() / 1e6))
a.info("odometer readings available (OD_READ) for the MILESDRIVEN construction", int(s["OD_READ"].notna().sum()))

# survey-day vehicle miles from the trip file (TDVEHMILES building block for TRIPANNMILES)
t = d.trips(["TRPMILES", "HHSTATE", "VEHID", "DRVR_FLG", "TRPTRANS"], missing="nan", skip="auto")
tv = t[(t["DRVR_FLG"] == "01") & t["TRPTRANS"].isin(["03", "04", "05", "06"]) & t["VEHID"].notna()]
tv = tv.groupby(["HOUSEID", "VEHID"])["TRPMILES"].sum().rename("tdvehmiles").reset_index()
sv = d.vehicles(["VEHTYPE", "HHSTATE"], missing="nan", skip="auto").merge(tv, on=["HOUSEID", "VEHID"], how="left")
sv = sv[sv["VEHTYPE"].isin(["01", "02", "03"]) & ~sv["HHSTATE"].isin(["AK", "HI"])]
a.info("vehicles with any survey-day driving recorded in the trip file", int(sv["tdvehmiles"].notna().sum()))
a.check("mean survey-day distance of vehicles driven, miles (paper: ~36)", 36.0, float(sv["tdvehmiles"].mean()))
a.save()
