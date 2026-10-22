"""P07 - Krizek & McGuckin (2019), Transport Findings: 'little vehicles' (LV) in large US metros, NHTS 2017.

Checks trip counts by mode, the Table 1 mode shares for 1-6 km trips in MSAs >= 1 million and the
distance/purpose statements. The 503 scooter/skateboard trips are a write-in category that the public file
does not expose (TRPTRANS 97 'Something else' has 3,515 trips).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import common

common.setup()
import pynhts  # noqa: E402

a = common.Audit("p07_krizek_mcguckin2019")
d = pynhts.load(2017)
t = d.trips(["TRPTRANS", "TRPMILES", "WHYTRP1S", "MSASIZE", "R_AGE", "R_SEX"], missing="nan", skip="auto")
w = "WTTRDFIN"

a.check("bicycle trips", 8034, int((t["TRPTRANS"] == "02").sum()))
a.check("Segway / golf cart trips", 826, int((t["TRPTRANS"] == "07").sum()))
a.rows.append({"item": "scooter / skateboard trips", "published": 503, "pynhts": None, "status": "NOT_COMPUTABLE",
               "note": "write-in category, not separable in the public file ('Something else' = 3,515 trips)"})

# large metros (> 1 million) and the 1-6 km band
big = t["MSASIZE"].isin(["04", "05"])
km = t["TRPMILES"] * 1.609344
mid = big & km.between(1, 6)
a.info("trips in MSAs >= 1 million", int(big.sum()))
a.info("trips 1-6 km in those MSAs (unweighted n)", int(mid.sum()))


def group(code):
    if pd.isna(code):
        return "All other"
    if code in ("03", "04", "05", "06"):
        return "Private vehicle"
    if code == "01":
        return "Walk"
    if code in ("11", "15", "16", "12"):
        return "Transit"
    if code in ("02", "07"):
        return "Little vehicles"
    if code == "17":
        return "Taxi/Rideshare"
    return "All other"


t["grp"] = t["TRPTRANS"].map(group)
sub = t[mid]
sh = sub.groupby("grp")[w].sum() / sub[w].sum() * 100
for k, pub in {"Private vehicle": 76.8, "Walk": 12.6, "Transit": 5.0, "Little vehicles": 1.8, "Taxi/Rideshare": 1.5, "All other": 2.3}.items():
    a.check(f"Table 1 mode share, 1-6 km trips, {k} %", pub, float(sh.get(k, np.nan)))


# variant: 'large metropolitan area' = MSACAT 01 (MSA >= 1 million with rail) - closest to the printed shares
t2 = d.trips(["MSACAT"], missing="nan", skip="auto")["MSACAT"]
sub2 = t[(t2 == "01") & km.between(1, 6)]
sh2 = sub2.groupby("grp")[w].sum() / sub2[w].sum() * 100
for k, pub in {"Private vehicle": 76.8, "Walk": 12.6, "Transit": 5.0, "Little vehicles": 1.8, "Taxi/Rideshare": 1.5, "All other": 2.3}.items():
    a.check(f"variant MSACAT=01: mode share 1-6 km, {k} %", pub, float(sh2.get(k, np.nan)),
            "'large metro' is not defined in the paper; MSACAT=01 is the closest reading")


def wq(x, ww, q):
    o = np.argsort(x.values)
    xs, cs = x.values[o], np.cumsum(ww.values[o])
    return float(xs[np.searchsorted(cs, q * cs[-1])])


lv = t[big & t["TRPTRANS"].isin(["02", "07"]) & t["TRPMILES"].notna()]
a.check("LV trips: median distance (km) in large metros", 2.0, wq(lv["TRPMILES"] * 1.609344, lv[w], 0.5))
a.check("LV trips: 75th percentile (km)", 4.0, wq(lv["TRPMILES"] * 1.609344, lv[w], 0.75))
car = t[big & t["TRPTRANS"].isin(["03", "04", "05", "06"]) & t["TRPMILES"].notna()]
a.check("private-vehicle trips: 25th percentile (km)", 3.0, wq(car["TRPMILES"] * 1.609344, car[w], 0.25))
wk = t[big & (t["TRPTRANS"] == "01") & t["TRPMILES"].notna()]
a.check("walk trips: 75th percentile (km)", 1.0, wq(wk["TRPMILES"] * 1.609344, wk[w], 0.75))

# purposes of mid-distance LV trips versus all modes (Figure 3)
pur = {"10": "Work", "40": "Shopping/errands", "50": "Social/recreational"}
for g, lab in ((sub["grp"] == "Little vehicles", "LV"), (sub["grp"].notna(), "all modes")):
    s2 = sub[g]
    p = s2.groupby("WHYTRP1S")[w].sum() / s2[w].sum() * 100
    for code, name in pur.items():
        a.info(f"purpose share {name}, {lab}, 1-6 km, large MSAs (%)", round(float(p.get(code, np.nan)), 1),
               "paper: LV recreational 32.8, work 28.8, shopping+errands 28; all modes work 11.9, shopping ~50")
a.save()
