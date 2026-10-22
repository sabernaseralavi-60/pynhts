"""P03 - Quinn et al. (2016), JECH: demographic/workplace factors and active transportation, NHTS 2009.

Builds the adult sample (no travel-limiting medical condition), the walker/biker flags from trips of >= 10 min,
the commuter flags from WRKTRANS, and checks the weighted prevalences (with jackknife CIs) and the sample flow.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import common

common.setup()
import pynhts  # noqa: E402

a = common.Audit("p03_quinn2016")
d = pynhts.load(2009)

cols = ["R_AGE", "R_SEX", "MEDCOND", "WRKTRANS", "WKFTPT", "FLEXTIME", "WKRMHM", "TIMETOWK", "DISTTOWK",
        "WRKTIME", "EDUC", "HH_RACE", "HHFAMINC", "HBHUR"]
p = d.persons(cols, missing="keep", skip="keep")
n_all = len(p)
a.check("persons in 2009 person file", 324184, n_all, "paper says 324,184; the public file has 308,901 (paper-internal)")
age = pd.to_numeric(p["R_AGE"])
a.check("children < 18 excluded", 45329, int((age < 18).sum()))
a.check("persons with travel-limiting medical condition", 33757, int((p["MEDCOND"] == "01").sum()))
a.check("persons not working (excluded from commuting)", 109408, int((p["WKFTPT"].isin(["-1"])).sum()))
adult = (age >= 18)
base = adult & (p["MEDCOND"] != "01")
a.check("active-transportation sample", 152573, int(base.sum()), "adults without condition; sequential counts in the paper do not add up")
a.info("adults >= 18", int(adult.sum()))
a.info("adults >= 18 with MEDCOND = missing/skip (not excluded)", int((adult & p["MEDCOND"].isin(["-1", "-7", "-8", "-9"])).sum()))

# ---- trips: walking / biking trips of >= 10 minutes, exercise trips (purpose 51) excluded
t = d.trips(["TRPTRANS", "TRVL_MIN", "WHYTO"], missing="nan", skip="auto")
t["ex"] = t["WHYTO"] == "51"
a.check("exercise trips (WHYTO 51) excluded", 33836, int(t["ex"].sum()), "paper counts trips for 'exercise (jogging, walking, biking)'")
ok = ~t["ex"] & (t["TRVL_MIN"] >= 10)
walk = t[ok & (t["TRPTRANS"] == "23")].groupby(["HOUSEID", "PERSONID"]).size().rename("nwalk")
bike = t[ok & (t["TRPTRANS"] == "22")].groupby(["HOUSEID", "PERSONID"]).size().rename("nbike")
p = p.join(walk, on=["HOUSEID", "PERSONID"]).join(bike, on=["HOUSEID", "PERSONID"])
p["walker"] = (p["nwalk"].fillna(0) > 0)
p["biker"] = (p["nbike"].fillna(0) > 0)
wt = pd.to_numeric(p["WRKTRANS"])
p["wwalk"] = p["WRKTRANS"].eq("23")
p["wbike"] = p["WRKTRANS"].eq("22")
worker = p["WRKTRANS"].isin([f"{i:02d}" for i in range(1, 30)])
a.info("adults without condition who report a usual commute mode (WRKTRANS)", int((base & worker).sum()), "paper: 111,808")
com = base & worker

# ---- design-based prevalence with the replicate-weight jackknife (pynhts.survey)
s = d.survey("person", ["R_AGE", "MEDCOND", "WRKTRANS"], missing="keep", skip="keep")
rows = s.rows
key = rows[["HOUSEID", "PERSONID"]].merge(p[["HOUSEID", "PERSONID", "walker", "biker", "wwalk", "wbike"]], on=["HOUSEID", "PERSONID"], how="left")
dom_at = ((pd.to_numeric(rows["R_AGE"]) >= 18) & (rows["MEDCOND"] != "01")).to_numpy()
dom_c = (dom_at & rows["WRKTRANS"].isin([f"{i:02d}" for i in range(1, 30)])).to_numpy()


def prev(flag, dom):
    r = s.proportion(key[flag].to_numpy().astype(bool), domain=dom)
    return r


for flag, dom, label, pub in [
    ("biker", dom_at, "Active transportation, biking", (1.11, 1.0, 1.3)),
    ("walker", dom_at, "Active transportation, walking", (11.74, 11.2, 12.3)),
    ("wbike", dom_c, "Active commuting, biking", (0.80, 0.7, 1.0)),
    ("wwalk", dom_c, "Active commuting, walking", (2.76, 2.5, 3.1)),
]:
    r = prev(flag, dom)
    est = float(r.iloc[0, 0]) if r.shape[1] else float("nan")
    a.info(f"{label}: columns returned", ", ".join(map(str, r.columns)))
    row = r.iloc[0]
    # take the first numeric column as the estimate; convert a share to percent
    val = float(row.iloc[0]) * (100 if row.iloc[0] <= 1 else 1)
    a.check(f"{label} prevalence %", pub[0], val)

# variant: denominator = adults with at least one trip on the travel day (unspecified in the paper)
nt = t.groupby(["HOUSEID", "PERSONID"]).size().rename("nt")
rr = rows[["HOUSEID", "PERSONID"]].join(nt, on=["HOUSEID", "PERSONID"])
dom_t = dom_at & (rr["nt"].fillna(0) > 0).to_numpy()
for flag, label, pub in (("biker", "biking", 1.11), ("walker", "walking", 11.74)):
    r = prev(flag, dom_t).iloc[0]
    a.check(f"Active transportation, {label}, denominator = persons with trips (variant)", pub, float(r.iloc[0]) * 100)

# ---- Table 1 composition among the active-transportation sample (weighted)
b = p[base].copy()
b["age"] = pd.to_numeric(b["R_AGE"])
b["ageg"] = pd.cut(b["age"], [18, 25, 45, 65, 200], right=False, labels=["18-24", "25-44", "45-64", "65+"])
T1 = {"18-24": 14.0, "25-44": 38.8, "45-64": 34.5, "65+": 12.7}
sh = b.groupby("ageg", observed=True)["WTPERFIN"].sum() / b["WTPERFIN"].sum() * 100
for k, v in T1.items():
    a.check(f"T1 age {k} % (active transportation sample)", v, sh[k])
b["female"] = b["R_SEX"].astype(str).isin(["2", "02"])
a.check("T1 female % (active transportation sample)", 50.1, float((b["female"] * b["WTPERFIN"]).sum() / b["WTPERFIN"].sum() * 100))
inc = pd.to_numeric(b["HHFAMINC"])
b["inc"] = np.select([inc <= 0, inc <= 5, inc <= 10, inc <= 15], ["miss", "0-24k", "25-49k", "50-74k"], default="75k+")
si = b.groupby("inc")["WTPERFIN"].sum() / b["WTPERFIN"].sum() * 100
for k, v in {"0-24k": 16.8, "25-49k": 24.0, "50-74k": 18.0, "75k+": 36.0}.items():
    a.check(f"T1 income {k} % (active transportation sample)", v, si.get(k, np.nan))
b["urban"] = b["HBHUR"].isin(["U", "C", "S"])
a.info("share in urban block-group classes U/C/S (paper's urban/rural split is 76.3 / 23.7)", float((b["urban"] * b["WTPERFIN"]).sum() / b["WTPERFIN"].sum() * 100))
a.save()
