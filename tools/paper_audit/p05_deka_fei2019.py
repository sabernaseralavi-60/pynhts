"""P05 - Deka & Fei (2019), J. Transport Geography 76: ridesourcing, transit and driving, NHTS 2017.

Part A (NHTS public file): the person-level dataset, weighted totals and the NHTS-only columns of Tables 1-2.
Part B (not in the public file): ACS block-group variables and transit stop counts need the block-group
identifier of the home address, which only the restricted/DOT files carry. Reported as NOT_COMPUTABLE.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import common

common.setup()
import pynhts  # noqa: E402

a = common.Audit("p05_deka_fei2019")
d = pynhts.load(2017)

cols = ["R_AGE", "R_SEX", "R_RACE", "R_HISP", "EDUC", "WORKER", "DRIVER", "HHVEHCNT", "HHFAMINC", "RIDESHARE", "PTUSED",
        "YEARMILE", "MSASIZE", "HBRESDN", "HTEEMPDN"]
p = d.persons(cols, missing="nan", skip="auto")
a.check("persons", 264234, len(p))
a.check("households", 129696, d.households(["HHSIZE"])["HOUSEID"].nunique())
a.check("trips", 923572, len(d.trips(["TRPMILES"])))

w = "WTPERFIN"
age = pd.to_numeric(p["R_AGE"])
rs = pd.to_numeric(p["RIDESHARE"])
adult = (age >= 16) & rs.notna()
N16 = float(p.loc[age >= 16, w].sum())
a.check("population aged 16+ (millions)", 255.9, N16 / 1e6)
users = adult & (rs > 0)
a.check("share not using ridesourcing in 30 days, %", 90.2, float(p.loc[adult & (rs == 0), w].sum() / p.loc[adult, w].sum() * 100))
a.check("ridesourcing users (millions)", 25.1, float(p.loc[users, w].sum() / 1e6))
ut = p.loc[users, w].sum()
for lab, lo, hi, pub in (("1-4", 1, 4, 69.4), ("5-9", 5, 9, 18.0), ("10-19", 10, 19, 9.6), ("20+", 20, 999, 3.0)):
    m = users & rs.between(lo, hi)
    a.check(f"users with {lab} rides, %", pub, float(p.loc[m, w].sum() / ut * 100))

# ---- Table 1 (scaled weights n/N * w; all NHTS variables)
s = p[adult].copy()
s["rs"] = rs[adult]
# the paper says Table 1 uses weights scaled to the sample size, but only UNWEIGHTED statistics reproduce
# its printed means (mean rides 0.297 vs 0.299; weighted gives 0.433), so ws = 1 here
s["ws"] = 1.0
s["male"] = (s["R_SEX"] == "01").astype(float)
for lab, lo, hi in (("a1624", 16, 24), ("a2534", 25, 34), ("a3544", 35, 44), ("a4554", 45, 54)):
    s[lab] = pd.to_numeric(s["R_AGE"]).between(lo, hi).astype(float)
s["white"] = (s["R_RACE"] == "01").astype(float)
s["hisp"] = (s["R_HISP"] == "01").astype(float)
s["nhwhite"] = ((s["R_RACE"] == "01") & (s["R_HISP"] == "02")).astype(float)
s["somecol"] = (s["EDUC"] == "03").astype(float)
s["bach"] = (s["EDUC"] == "04").astype(float)
s["post"] = (s["EDUC"] == "05").astype(float)
s["worker"] = (s["WORKER"] == "01").astype(float)
s["driver"] = (s["DRIVER"] == "01").astype(float)
s["veh"] = pd.to_numeric(s["HHVEHCNT"])
inc = pd.to_numeric(s["HHFAMINC"])
s["i25"] = (inc <= 3).astype(float)
s["i49"] = inc.between(4, 5).astype(float)
s["i74"] = (inc == 6).astype(float)
s["i99"] = (inc == 7).astype(float)
s["i149"] = inc.between(8, 9).astype(float)
a.info("analysis sample (16+, rideshare answered)", len(s), "paper does not print N in the text I read; ZINB N is in Table 3")


def wmean(x):
    return float((x * s["ws"]).sum() / s["ws"].sum())


def wsd(x):
    m = wmean(x)
    return float(np.sqrt(((x - m) ** 2 * s["ws"]).sum() / s["ws"].sum()))


def wcorr(x, y):
    mx, my = wmean(x), wmean(y)
    cov = ((x - mx) * (y - my) * s["ws"]).sum() / s["ws"].sum()
    return float(cov / (wsd(x) * wsd(y)))


T1 = {  # var: (mean, sd, r with ridesourcing)
    "rs": (0.299, 1.713, None), "male": (0.469, 0.499, 0.0168), "a1624": (0.079, 0.270, 0.0248),
    "a2534": (0.120, 0.325, 0.1256), "a3544": (0.123, 0.329, 0.0470), "a4554": (0.154, 0.361, -0.0034),
    "white": (0.827, 0.378, -0.0231), "hisp": (0.081, 0.273, 0.0110), "nhwhite": (0.774, 0.418, -0.0261),
    "somecol": (0.294, 0.456, -0.0434), "bach": (0.236, 0.425, 0.0607), "post": (0.207, 0.405, 0.0643),
    "worker": (0.549, 0.498, 0.0955), "driver": (0.920, 0.271, -0.0176), "veh": (2.242, 1.239, -0.0622),
    "i25": (0.156, 0.363, -0.0333), "i49": (0.205, 0.403, -0.0449), "i74": (0.180, 0.384, -0.0269),
    "i99": (0.144, 0.351, -0.0127), "i149": (0.180, 0.384, 0.0157),
}
for v, (m, sd, r) in T1.items():
    a.check(f"T1 mean {v}", m, wmean(s[v]))
    a.check(f"T1 sd {v}", sd, wsd(s[v]))
    if r is not None:
        a.check(f"T1 r(ridesourcing, {v})", r, wcorr(s[v], s["rs"]))

# ---- Table 2 columns that come from NHTS
msa = pd.to_numeric(s["MSASIZE"])
for lab, code, pub in (("MSA <250K", 1, 0.165), ("250-499K", 2, 0.102), ("500-999K", 3, 0.142), ("1000-2999K", 4, 0.150), ("3000K+", 5, 0.286)):
    a.check(f"T2 mean MSA {lab}", pub, wmean((msa == code).astype(float)))
hb = pd.to_numeric(s["HBRESDN"])
for lab, v, pub in (("500-999", 750, 0.147), ("1000-1999", 1500, 0.195), ("2000-3999", 3000, 0.152),
                    ("4000-9999", 7000, 0.055), ("10000-24999", 17000, 0.014), ("25000+", 30000, 0.006)):
    a.check(f"T2 mean housing density {lab}", pub, wmean((hb == v).astype(float)))
ht = pd.to_numeric(s["HTEEMPDN"])
for lab, v, pub in (("100-249", 150, 0.105), ("250-499", 350, 0.099), ("500-999", 750, 0.139), ("1000-1999", 1500, 0.178),
                    ("2000-3999", 3000, 0.158), ("4000+", 5000, 0.075)):
    a.check(f"T2 mean job density {lab}", pub, wmean((ht == v).astype(float)))
for v in ("share of households with no vehicle (ACS BG)", "median household income (ACS BG)", "median building age (ACS BG)",
          "share single detached (ACS BG)", "share rented (ACS BG)", "share bus commuters (ACS BG)",
          "share walking commuters (ACS BG)", "rail stations in BG (HIFLD)", "stations/stops in BG (NTMD)"):
    a.rows.append({"item": f"T2 {v}", "published": None, "pynhts": None, "status": "NOT_COMPUTABLE",
                   "note": "needs the home block-group ID (restricted NHTS file) + ACS 2016 5-year / BTS-HIFLD join"})
a.save()
