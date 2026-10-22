"""P10 - Lidbe et al. (2021), TRIP Perspectives 11: older Americans with medical conditions, NHTS 2001 vs 2017.

Checks Table 1 (national totals and trip rates), Table 2 (older vs non-older) and Table 3 (trip distribution
by distance class, age and medical condition) for both waves, with the weights and replicate variance of pynhts.
The paper analysed the daily trip file ('long-distance' = trips of 50 miles or more).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import common

common.setup()
import pynhts  # noqa: E402
from pynhts import rates  # noqa: E402

a = common.Audit("p10_lidbe2021")
waves = {2001: pynhts.load(2001), 2017: pynhts.load(2017)}

T1 = {  # wave: persons M, households M, trips B, trip miles B, HH rate, person rate
    2001: (277.20, 107.37, 407.26, 3972.75, 10.39, 4.03),
    2017: (301.60, 118.21, 371.15, 3970.29, 8.60, 3.37),
}
for wave, d in waves.items():
    per = d.persons(["R_AGE"], missing="nan")
    hh = d.households(["HHSIZE"])
    tr = d.trips(["TRPMILES"], missing="nan", skip="auto")
    pw = per["WTPERFIN"].sum() / 1e6
    hw = hh["WTHHFIN"].sum() / 1e6
    tw = tr["WTTRDFIN"].sum() / 1e9
    tm = float((tr["TRPMILES"].fillna(0) * tr["WTTRDFIN"]).sum() / 1e9)
    ex = T1[wave]
    a.check(f"T1 {wave} persons (millions)", ex[0], pw)
    a.check(f"T1 {wave} households (millions)", ex[1], hw)
    a.check(f"T1 {wave} trips (billions, annual)", ex[2], tw)
    a.check(f"T1 {wave} trip miles (billions, annual)", ex[3], tm)
    a.check(f"T1 {wave} household trip rate", ex[4], float(rates.daily_rate(d, "trips", per="household")["estimate"].iloc[0]))
    a.check(f"T1 {wave} person trip rate", ex[5], float(rates.daily_rate(d, "trips", per="person")["estimate"].iloc[0]),
            "published rate includes all ages (2001 includes children 0-4)" if wave == 2001 else "")

# ---- Table 2: older (>= 65) vs non-older
T2 = {2001: dict(pers=11.86, trips=10.06, r_non=4.11, r_old=3.42), 2017: dict(pers=15.78, trips=14.92, r_non=3.41, r_old=3.19)}
T3 = {  # (older, long, medical): percent of all trips; 2001 then 2017
    2001: {(False, False, True): 3.63, (False, True, True): 0.10, (True, False, True): 1.68, (True, True, True): 0.03,
           (False, False, False): 81.39, (False, True, False): 2.32, (True, False, False): 10.58, (True, True, False): 0.26},
    2017: {(False, False, True): 3.55, (False, True, True): 0.05, (True, False, True): 2.27, (True, True, True): 0.03,
           (False, False, False): 79.45, (False, True, False): 2.03, (True, False, False): 12.30, (True, True, False): 0.31},
}
for wave, d in waves.items():
    per = d.persons(["R_AGE", "MEDCOND"], missing="nan", skip="keep")
    tr = d.trips(["TRPMILES"], missing="nan", skip="auto")
    age = pd.to_numeric(per["R_AGE"])
    per["old"] = age >= 65
    per["med"] = per["MEDCOND"].isin(["01", "1"])
    known = age.notna() & (age >= 0)
    wsum = per.loc[known, "WTPERFIN"].sum()
    a.check(f"T2 {wave} older persons %", T2[wave]["pers"], float(per.loc[known & per["old"], "WTPERFIN"].sum() / wsum * 100))
    m = tr.merge(per[["HOUSEID", "PERSONID", "old", "med"]], on=["HOUSEID", "PERSONID"], how="left")
    ok = m["old"].notna()
    tt = m.loc[ok, "WTTRDFIN"].sum()
    a.check(f"T2 {wave} older trips %", T2[wave]["trips"], float(m.loc[ok & m["old"].astype(bool), "WTTRDFIN"].sum() / tt * 100))
    long_ = m["TRPMILES"] >= 50
    for (old, lg, med), pub in T3[wave].items():
        sel = ok & (m["old"].astype(bool) == old) & (long_ == lg) & (m["med"].astype(bool) == med)
        a.check(f"T3 {wave} older={old} long={lg} medical={med} % of trips", pub, float(m.loc[sel, "WTTRDFIN"].sum() / tt * 100))
a.save()
