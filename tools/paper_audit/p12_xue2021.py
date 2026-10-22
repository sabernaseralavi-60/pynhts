"""P12 - Xue et al. (2021), Complexity 2021: e-shopping and shopping trips, NHTS 2017 (SEM).

Builds the person-level file (person + household + trip aggregates, age >= 16, complete cases) and checks the
sample size (173,500) and the descriptive statistics of Section 4.1 / Table 4.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import common

common.setup()
import pynhts  # noqa: E402

a = common.Audit("p12_xue2021")
d = pynhts.load(2017)
a.check("persons", 264234, len(d.persons(["R_AGE"])))
a.check("households", 129696, d.households(["HHSIZE"])["HOUSEID"].nunique())
a.check("trips", 923572, len(d.trips(["TRPMILES"])))
a.check("vehicles", 256115, len(d.vehicles(["VEHAGE"])))

p = d.persons(["R_AGE", "R_SEX", "EDUC", "WKFTPT", "DRIVER", "DELIVER", "WORKER", "WRK_HOME"], missing="nan", skip="keep")
hh = d.households(["HHFAMINC", "HHSIZE", "HHVEHCNT", "WEBUSE17", "URBRUR", "HBPPOPDN", "LIF_CYC"], missing="nan", skip="keep")
hh = hh.drop(columns=["WTHHFIN"], errors="ignore")
t = d.trips(["TRPMILES", "TRVLCMIN", "WHYTRP1S", "TRPTRANS"], missing="nan", skip="auto")
t["shop"] = (t["WHYTRP1S"] == "40").astype(float)
t["smiles"] = t["TRPMILES"].where(t["shop"] == 1)
t["smin"] = t["TRVLCMIN"].where(t["shop"] == 1)
g = t.groupby(["HOUSEID", "PERSONID"]).agg(
    dist=("TRPMILES", "sum"), dur=("TRVLCMIN", "sum"), shoptrp=("shop", "sum"), shopmile=("smiles", "sum"), shopmin=("smin", "sum")
).reset_index()
s = p.merge(hh, on="HOUSEID", how="left").merge(g, on=["HOUSEID", "PERSONID"], how="left")
for c in ("dist", "dur", "shoptrp", "shopmile", "shopmin"):
    s[c] = s[c].fillna(0)
s["R_AGE"] = pd.to_numeric(s["R_AGE"])
s["DELIVER"] = pd.to_numeric(s["DELIVER"])
a.info("persons aged 16+", int((s["R_AGE"] >= 16).sum()))

# education / work / driver / web use must be answered; skip codes (-1) are not answers
need = ["EDUC", "DRIVER", "HHFAMINC", "WEBUSE17", "URBRUR", "R_SEX"]
ok = (s["R_AGE"] >= 16) & s["DELIVER"].ge(0)
for c in need:
    ok &= s[c].notna() & ~s[c].astype("string").str.startswith("-").fillna(True)
z = s[ok].copy()
a.check("final sample (age >= 16, complete cases)", 173500, len(z), "paper: 'observations with missing data and respondents younger than 16 omitted'")
z2 = z[z["WKFTPT"].isin(["01", "02"])]
a.info("of which with a work status (full/part time)", len(z2))

z["female"] = (z["R_SEX"] == "02").astype(float)
z["bach"] = z["EDUC"].isin(["04", "05"]).astype(float)
z["full"] = (z["WKFTPT"] == "01").astype(float)
z["driver"] = (z["DRIVER"] == "01").astype(float)
inc = pd.to_numeric(z["HHFAMINC"])
z["inc75"] = (inc >= 7).astype(float)
z["noch"] = (z["LIF_CYC"] == "01").astype(float)
z["urban"] = (z["URBRUR"] == "01").astype(float)
checks = [("R_AGE", 56.8, 16.5, "age"), ("female", 56.4, None, "% female"), ("bach", 45.7, None, "% bachelor or higher"),
          ("full", 32.4, None, "% full-time"), ("driver", 94.6, None, "% drivers"), ("inc75", 43.1, None, "% income > $75,000"),
          ("HHSIZE", 2.3, None, "household members"), ("HHVEHCNT", 2.1, None, "household vehicles"),
          ("urban", 76.5, None, "% urban"), ("dist", 41.8, None, "total travel distance (miles)"),
          ("dur", 77.6, None, "total travel duration (min)"), ("DELIVER", 2.7, None, "online purchases in 30 days"),
          ("shoptrp", 3.3, None, "shopping trips"), ("shopmile", 15.5, None, "shopping trip miles"), ("shopmin", 36.6, None, "shopping trip duration")]
for col, pub, sd, lab in checks:
    x = pd.to_numeric(z[col])
    val = float(x.mean()) * (100 if "%" in lab else 1)
    a.check(f"mean {lab}", pub, val)
a.info("persons with at least one shopping trip: mean shopping trips (paper's 3.3 is plausible only for this group)",
       float(z.loc[z["shoptrp"] > 0, "shoptrp"].mean()))
a.save()
