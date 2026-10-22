"""P02 - Zhou & Wang (2014), Transp. Res. A 70: online shopping and shopping trips, NHTS 2009 (SEM).

pynhts builds the person-level file (person + household + trip aggregates). The paper's 'invalid
record' rule is not stated, so the complete-case sample below is an inference; the check is whether the
published Table 2 means come out of it.
"""

from __future__ import annotations

import pandas as pd

import common

common.setup()
import pynhts  # noqa: E402

a = common.Audit("p02_zhou_wang2014")
d = pynhts.load(2009)

p = d.persons(
    ["R_AGE", "R_SEX", "EDUC", "WKFTPT", "WEBUSE", "PURCHASE", "HHFAMINC", "HHSIZE", "HHVEHCNT", "HBHUR",
     "URBAN", "HBHTNRNT", "WTPERFIN"],
    missing="nan", skip="keep",
)
a.check("persons (2009 person file)", 308901, len(p))
t = d.trips(["WHYTRP1S", "TRPTRANS", "TRVL_MIN", "DWELTIME", "STRTTIME", "TDWKND", "GASPRICE"], missing="nan", skip="auto")
a.check("trips (2009 trip file)", 1167321, len(t))

t["shop"] = (t["WHYTRP1S"] == "40").astype(float)  # Shopping/Errands
t["late"] = (pd.to_numeric(t["STRTTIME"]) >= 1800).astype(float)
t["wknd"] = (t["TDWKND"] == "01").astype(float)
t["mv"] = t["TRPTRANS"].isin(["01", "02", "03", "04", "05", "06", "07"]).astype(float)
t["aw"] = t["TRPTRANS"].isin(["22", "23"]).astype(float)  # bicycle, walk
g = t.groupby(["HOUSEID", "PERSONID"]).agg(
    cnttdtr=("shop", "size"), shoptrp=("shop", "sum"), trvlmin=("TRVL_MIN", "mean"), dweltime=("DWELTIME", "sum"),
    strttime_pct=("late", "mean"), mode1_pct=("mv", "mean"), mode2_pct=("aw", "mean"), tdwknd=("wknd", "max"),
    gasprice=("GASPRICE", "mean"),
).reset_index()
g["dweltime"] = g["dweltime"] / 60.0  # hours
g["gasprice"] = g["gasprice"] / 100.0  # dollars
s = p.merge(g, on=["HOUSEID", "PERSONID"], how="inner")
a.info("persons with at least one trip on the travel day", len(s))

for col in ("WKFTPT", "EDUC", "WEBUSE", "HHFAMINC", "HBHUR", "URBAN"):
    s[col] = s[col].where(~s[col].astype("string").str.startswith("-"))
s["PURCHASE"] = pd.to_numeric(s["PURCHASE"]).where(lambda x: x >= 0)
for col in ("R_AGE", "HHSIZE", "HHVEHCNT", "HBHTNRNT"):
    s[col] = pd.to_numeric(s[col])
ok = (
    (s["R_AGE"] >= 18) & s["WKFTPT"].notna() & s["PURCHASE"].notna() & s["WEBUSE"].notna() & s["EDUC"].notna()
    & s["HHFAMINC"].notna() & s["HBHUR"].notna() & s["URBAN"].notna()
)
z = s[ok].copy()
a.check("final sample (complete-case workers aged 18+ with trips)", 85663, len(z),
        "rule for 'invalid records' is not stated; this is the most natural complete-case reading")

z["webuse1"] = (z["WEBUSE"] == "01").astype(float)
z["webuse2"] = (z["WEBUSE"] == "02").astype(float)
z["hhfaminc1"] = (pd.to_numeric(z["HHFAMINC"]) <= 10).astype(float)  # < $50,000
z["educ1"] = z["EDUC"].isin(["01", "02"]).astype(float)
z["wkftpt"] = (z["WKFTPT"] == "01").astype(float)
z["urban"] = z["URBAN"].eq("01").astype(float)

T2 = {  # variable: (mean, published)
    "R_AGE": 47.85, "PURCHASE": 2.277, "cnttdtr": 4.844, "shoptrp": 0.824, "trvlmin": 21.78, "dweltime": 7.793,
    "strttime_pct": 0.171, "mode1_pct": 0.915, "mode2_pct": 0.070, "tdwknd": 0.298, "gasprice": 2.859,
    "HHSIZE": 2.909, "HHVEHCNT": 2.593, "HBHTNRNT": 22.44, "webuse1": 0.815, "webuse2": 0.117,
    "hhfaminc1": 0.224, "educ1": 0.202, "wkftpt": 0.807, "urban": 0.629,
}
for v, pub in T2.items():
    a.check(f"T2 mean {v}", pub, float(z[v].mean()))
a.info("not in NHTS: state GDP per capita and state population density (need BEA / Census tables)", "external join")
a.save()
