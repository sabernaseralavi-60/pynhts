"""P17 - Jia et al. (2020), IEEE Access 8: regional adoption of electric vehicles, NHTS 2017.

Same authors, sample size (31,322) and Table 1 as the AFV paper (P06). Here the vehicle class is EV (battery or plug-in
hybrid, HFUEL 02 and 03) against conventional (gasoline or diesel). Checks: the sample, the EV share (text: 1.29 % of
the vehicles; Table 1 mean 0.012) and whether Table 1 is the AFV table with the first mean replaced.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import common

common.setup()
import pynhts  # noqa: E402

a = common.Audit("p17_jia2020_ev")
d = pynhts.load(2017)

v = d.vehicles(["FUELTYPE", "HFUEL", "VEHAGE", "VEHTYPE", "HHFAMINC", "HHVEHCNT", "PERSONID"], missing="nan", skip="keep")
allv = d.vehicles(["HFUEL", "FUELTYPE"], missing="keep", skip="keep", weight=False)
ev_all = allv["HFUEL"].isin(["02", "03"])
a.info("EV (HFUEL 02 + 03) vehicles in the file", int(ev_all.sum()), "of 256,115 vehicles")
a.info("EV share of ALL vehicles, %", float(ev_all.mean() * 100), "the paper says 1.29 % of the surveyed vehicles (sample, see below)")

pp = d.persons(["R_AGE", "R_SEX", "R_RACE", "EDUC", "OCCAT", "CARSHARE", "TIMETOWK", "YEARMILE", "GT1JBLWK"],
               missing="nan", skip="keep").drop(columns=["WTPERFIN"], errors="ignore")
hh = d.households(["HOMEOWN", "YOUNGCHILD", "PRICE", "PLACE", "HBPPOPDN", "URBRUR", "HHSIZE"], missing="nan", skip="keep")
hh = hh.drop(columns=[c for c in ("WTHHFIN",) if c in hh.columns])
m = v.merge(pp, on=["HOUSEID", "PERSONID"], how="inner").merge(hh, on="HOUSEID", how="left")

# the sample rule recovered for P06: newest vehicle of each main driver, at most 2 model years old, gas/diesel/alternative
x = m[(m["VEHAGE"] <= 2) & m["FUELTYPE"].isin(["01", "02", "03"])].sort_values(["HOUSEID", "PERSONID", "VEHAGE"])
x = x.drop_duplicates(["HOUSEID", "PERSONID"])
for c in ("R_AGE", "HHVEHCNT", "HHSIZE", "YOUNGCHILD", "PRICE", "PLACE"):
    x[c] = pd.to_numeric(x[c])
req = ["FUELTYPE", "VEHAGE", "R_AGE", "R_SEX", "HHFAMINC", "HHVEHCNT", "VEHTYPE"]
k = x.dropna(subset=req + ["R_RACE", "EDUC", "PRICE", "PLACE", "HOMEOWN", "URBRUR", "HBPPOPDN"]).copy()
for c in ("R_RACE", "EDUC", "HOMEOWN", "R_SEX"):
    k = k[~k[c].astype("string").str.startswith("-")]
a.check("analysis sample (same rule as the AFV paper)", 31322, len(k), "the EV paper prints the same N as the AFV paper")

k["EV"] = k["HFUEL"].isin(["02", "03"]).astype(float)
k["CV"] = k["FUELTYPE"].isin(["01", "02"]).astype(float)
a.check("EV share in the sample, %", 1.29, float(k["EV"].mean() * 100), "text: 'only 1.29 % of the vehicles are EV'")
a.check("Table 1 mean of EV", 0.012, float(k["EV"].mean()))
a.check("Table 1 sd of EV", 0.199, float(k["EV"].std()), "sd 0.199 is the sd of a 4.2 % share (sqrt(.042*.958) = 0.2006), not of a 1.2 % share (0.109)")
a.info("AFV share (FUELTYPE 03) in the sample", float((k["FUELTYPE"] == "03").mean()), "AFV paper: 4.2 %; the EV paper's Table 1 reuses its sd")
a.info("sd implied by the EV share", float(np.sqrt(k["EV"].mean() * (1 - k["EV"].mean()))), "")
a.info("hybrids (HFUEL 04) that are neither EV nor CV in the paper's two classes", int((k["HFUEL"] == "04").sum()),
       "the paper does not say whether non-plug-in hybrids, biodiesel and 'other fuel' stay in the sample")

inc = pd.to_numeric(k["HHFAMINC"])
k["income"] = np.select([inc <= 3, inc <= 5, inc == 6, inc == 7], [1, 2, 3, 4], default=5)
k["homeown"] = (k["HOMEOWN"] == "01").astype(float)
k["urban"] = (k["URBRUR"] == "01").astype(float)
k["popden"] = pd.to_numeric(k["HBPPOPDN"]).map({50: 1, 300: 2, 750: 3, 1500: 4, 3000: 5, 7000: 6, 17000: 7, 30000: 8})
k["female"] = (k["R_SEX"] == "02").astype(float)
k["educ"] = pd.to_numeric(k["EDUC"])
k["race"] = pd.to_numeric(k["R_RACE"]).replace({97: 6})
k["multijob"] = (k["GT1JBLWK"] == "01").astype(float)
k["occ"] = np.where(k["OCCAT"].isin(["01", "02", "03", "04"]), pd.to_numeric(k["OCCAT"], errors="coerce"), 5)
k["carshare"] = (pd.to_numeric(k["CARSHARE"]).clip(lower=0) > 0).astype(float)
k["ttw"] = pd.to_numeric(k["TIMETOWK"]).clip(lower=0).fillna(0)
k["ymile"] = pd.to_numeric(k["YEARMILE"]).where(lambda s: s >= 0, 0)
T1 = [("income", 3.824, 1.304), ("homeown", 0.851, 0.356), ("HHSIZE", 2.447, 1.173), ("YOUNGCHILD", 0.110, 0.391),
      ("HHVEHCNT", 2.426, 1.185), ("urban", 0.761, 0.426), ("popden", 3.843, 1.301), ("PRICE", 2.984, 1.283),
      ("PLACE", 3.003, 1.052), ("R_AGE", 53.372, 15.81), ("female", 0.536, 0.498), ("educ", 3.639, 1.069),
      ("race", 1.392, 1.196), ("multijob", 0.055, 0.227), ("occ", 3.835, 1.325), ("carshare", 0.005, 0.074),
      ("ttw", 14.772, 25.276), ("ymile", 10955.48, 11951.90)]
for var, mu, sd in T1:
    a.check(f"T1 mean {var}", mu, float(pd.to_numeric(k[var]).mean()), "identical in the AFV paper")
    a.check(f"T1 sd {var}", sd, float(pd.to_numeric(k[var]).std()))
a.rows.append({"item": "Table 1 of this paper equals Table 1 of the AFV paper (P06) except the first row",
               "published": None, "pynhts": None, "status": "INFO",
               "note": "all 18 other means and sds, N = 31,322 and the rounding are identical; the AFV mean 0.042 was replaced by 0.012 and the sd 0.199 kept"})
a.rows.append({"item": "regional EV penetration map (state level)", "published": None, "pynhts": None, "status": "INFO",
               "note": "HHSTATE is in the public household table; the paper's agent-based regional model needs unstated synthetic population steps"})
a.save()
