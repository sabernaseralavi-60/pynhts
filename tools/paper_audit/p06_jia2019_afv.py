"""P06 (= P08, byte-identical duplicate PDF) - Jia (2019), IEEE Access 7: AFV adoption with ML, NHTS 2017.

pynhts builds the person-level analysis file: one (newest) vehicle per main driver, vehicle <= 2 model years old,
joined to the person and household variables. Checks Table 1 of the paper (N = 31,322; AFV share 4.2 %).
The ML models themselves (LR, NB, RF, SVM, DT with over/under-sampling) are out of scope for a data audit.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import common

common.setup()
import pynhts  # noqa: E402

a = common.Audit("p06_jia2019_afv")
d = pynhts.load(2017)
a.check("persons", 264234, len(d.persons(["R_AGE"])))
a.check("vehicles", 256115, len(d.vehicles(["VEHAGE"])))

v = d.vehicles(["FUELTYPE", "VEHAGE", "VEHTYPE", "HHFAMINC", "HHVEHCNT", "PERSONID"], missing="nan", skip="auto")
pp = d.persons(["R_AGE", "R_SEX", "R_RACE", "EDUC", "OCCAT", "CARSHARE", "TIMETOWK", "YEARMILE", "GT1JBLWK"],
               missing="nan", skip="keep").drop(columns=["WTPERFIN"], errors="ignore")
hh = d.households(["HOMEOWN", "YOUNGCHILD", "PRICE", "PLACE", "HBPPOPDN", "URBRUR", "HHSIZE"], missing="nan", skip="keep")
hh = hh.drop(columns=[c for c in ("WTHHFIN",) if c in hh.columns])
m = v.merge(pp, on=["HOUSEID", "PERSONID"], how="inner").merge(hh, on="HOUSEID", how="left")
a.info("vehicle records linked to a main driver in the person file", len(m), "of 256,115 vehicles")

# one vehicle per respondent: the newest; adopted within 3 years = vehicle < 3 model years old (VEHAGE <= 2;
# recovered: VEHAGE <= 3 would give 47,489 persons)
x = m[(m["VEHAGE"] <= 2) & m["FUELTYPE"].isin(["01", "02", "03"])].sort_values(["HOUSEID", "PERSONID", "VEHAGE"])
x = x.drop_duplicates(["HOUSEID", "PERSONID"])
for c in ("R_AGE", "HHVEHCNT", "HHSIZE", "YOUNGCHILD"):
    x[c] = pd.to_numeric(x[c])
x["PRICE"] = pd.to_numeric(x["PRICE"])
x["PLACE"] = pd.to_numeric(x["PLACE"])
req = ["FUELTYPE", "VEHAGE", "R_AGE", "R_SEX", "HHFAMINC", "HHVEHCNT", "VEHTYPE"]
k = x.dropna(subset=req + ["R_RACE", "EDUC", "PRICE", "PLACE", "HOMEOWN", "URBRUR", "HBPPOPDN"]).copy()
for c in ("R_RACE", "EDUC", "HOMEOWN", "R_SEX"):
    k = k[~k[c].astype("string").str.startswith("-")]
a.check("analysis sample (persons with one new vehicle, complete key variables)", 31322, len(k),
        "rule recovered by search; 'within 3 years' = VEHAGE <= 2")
a.check("AFV share (FUELTYPE 03)", 0.042, float((k["FUELTYPE"] == "03").mean()))

inc = pd.to_numeric(k["HHFAMINC"])
k["income"] = np.select([inc <= 3, inc <= 5, inc == 6, inc == 7], [1, 2, 3, 4], default=5)
k["homeown"] = (k["HOMEOWN"] == "01").astype(float)
k["urban"] = (k["URBRUR"] == "01").astype(float)
dens = {50: 1, 300: 2, 750: 3, 1500: 4, 3000: 5, 7000: 6, 17000: 7, 30000: 8}
k["popden"] = pd.to_numeric(k["HBPPOPDN"]).map(dens)
k["female"] = (k["R_SEX"] == "02").astype(float)
k["educ"] = pd.to_numeric(k["EDUC"])
k["race"] = pd.to_numeric(k["R_RACE"]).replace({97: 6})
k["multijob"] = (k["GT1JBLWK"] == "01").astype(float)
k["occ"] = np.where(k["OCCAT"].isin(["01", "02", "03", "04"]), pd.to_numeric(k["OCCAT"], errors="coerce"), 5)
k["carshare"] = (pd.to_numeric(k["CARSHARE"]).clip(lower=0) > 0).astype(float)
k["ttw"] = pd.to_numeric(k["TIMETOWK"]).clip(lower=0).fillna(0)
k["ymile"] = pd.to_numeric(k["YEARMILE"]).where(lambda s: s >= 0, 0)

T1 = [  # variable, published mean, published sd
    ("AFV", 0.042, 0.199), ("income", 3.824, 1.304), ("homeown", 0.851, 0.356), ("HHSIZE", 2.447, 1.173),
    ("YOUNGCHILD", 0.110, 0.391), ("HHVEHCNT", 2.426, 1.185), ("urban", 0.761, 0.426), ("popden", 3.843, 1.301),
    ("PRICE", 2.984, 1.283), ("PLACE", 3.003, 1.052), ("R_AGE", 53.372, 15.81), ("female", 0.536, 0.498),
    ("educ", 3.639, 1.069), ("race", 1.392, 1.196), ("multijob", 0.055, 0.227), ("occ", 3.835, 1.325),
    ("carshare", 0.005, 0.074), ("ttw", 14.772, 25.276), ("ymile", 10955.48, 11951.90),
]
k["AFV"] = (k["FUELTYPE"] == "03").astype(float)
for var, mu, sd in T1:
    a.check(f"T1 mean {var}", mu, float(pd.to_numeric(k[var]).mean()))
    a.check(f"T1 sd {var}", sd, float(pd.to_numeric(k[var]).std()))
a.info("states for the AFV penetration map need HHSTATE (present in the household table)", "ok")
a.save()
