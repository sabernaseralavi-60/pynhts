"""P18 - Jiao, Bischak & Hyden (2020), Travel Behaviour and Society 19: shared mobility and trip generation, NHTS 2017.

Person-level file (number of trips on the travel day), negative binomial models by weekday and weekend. Checks the final
sample (180,605; weekday 143,099, weekend 37,506) and the demographics of Table 4. The sample rule is not written in the
paper; it is recovered by testing (adults 18+, at least one trip, no non-answer in any model variable; skips kept).
"""

from __future__ import annotations

import pandas as pd

import common

common.setup()
import pynhts  # noqa: E402

a = common.Audit("p18_jiao2020")
d = pynhts.load(2017)
cols = ["R_AGE", "R_SEX", "EDUC", "WRK_HOME", "CARSHARE", "BIKESHARE", "RIDESHARE", "TIMETOWK", "HEALTH", "HBPPOPDN", "WORKER",
        "URBRUR", "HHFAMINC", "DRIVER", "WKFTPT", "LIF_CYC", "CNTTDTR", "TRAVDAY"]
p = d.persons(cols, missing="keep", skip="keep", weight=False)
n = lambda c: pd.to_numeric(p[c], errors="coerce")  # noqa: E731
age, trips = n("R_AGE"), n("CNTTDTR")
weekday = p["TRAVDAY"].isin(["02", "03", "04", "05", "06"])


def answered(c: str) -> pd.Series:
    """Not a non-answer; the skip code -1 ('does not apply', e.g. time to work of a non-worker) stays."""
    x = n(c)
    return ~((x < 0) & (x != -1))


a.info("persons", len(p), "")
a.info("persons with at least one trip", int((trips > 0).sum()), "")
ok = (age >= 18) & (trips > 0)
for c in ("HHFAMINC", "HEALTH", "WRK_HOME", "TIMETOWK", "WKFTPT", "EDUC", "CARSHARE", "BIKESHARE", "RIDESHARE", "HBPPOPDN", "R_SEX"):
    ok &= answered(c)
s = p[ok].copy()
s["wkday"] = weekday[ok]
a.check("final sample", 180605, len(s), "rule recovered: adults 18+, >= 1 trip, no non-answers; the paper's rule is not written")
a.check("weekday model N", 143099, int(s["wkday"].sum()))
a.check("weekend model N", 37506, int((~s["wkday"]).sum()))
a.info("ridesourcing users under 18 in the file (paper drops them)", int(((n("RIDESHARE") > 0) & (age < 18)).sum()), "none are left in an 18+ sample")
a.info("weekday share of the sample, %", float(s["wkday"].mean() * 100), "paper: 79.2 %")

N = len(s)
sn = lambda c: pd.to_numeric(s[c], errors="coerce")  # noqa: E731
inc = sn("HHFAMINC")
tw = sn("TIMETOWK")
rows = [  # (label, published %, published n, our mask)
    ("age 18-30", 13, 23317, sn("R_AGE").between(18, 30)),
    ("age 31-55", 38, 67888, sn("R_AGE").between(31, 55)),
    ("age 56+", 50, 85635, sn("R_AGE") >= 56),
    ("male", 48, 86014, s["R_SEX"] == "01"),
    ("income < 25k", 14, 34169, inc.between(1, 3)),
    ("income 25-74,999", 38, 68569, inc.between(4, 6)),
    ("income 75-99,999", 15, 26791, inc == 7),
    ("income 100k+", 33, 59566, inc >= 8),
    ("education: no bachelor's", 52, 93874, sn("EDUC").between(1, 3)),
    ("education: bachelor's", 25, 45953, sn("EDUC") == 4),
    ("education: graduate", 23, 40778, sn("EDUC") == 5),
    ("worker", 60, 107897, s["WORKER"] == "01"),
    ("health excellent", 25, 45893, sn("HEALTH") == 1),
    ("health very good", 39, 70582, sn("HEALTH") == 2),
    ("health good", 26, 47396, sn("HEALTH") == 3),
    ("health fair", 8, 13965, sn("HEALTH") == 4),
    ("health poor", 2, 2769, sn("HEALTH") == 5),
    ("works full time", 52, 94721, s["WKFTPT"] == "01"),
    ("works from home", 7, 13175, s["WRK_HOME"] == "01"),
    ("time to work 0-30 min (non-workers as 0)", 87, 157453, ~(tw > 30)),
    ("time to work 31-60 min", 10, 18938, tw.between(31, 60)),
    ("time to work 61+ min", 2, 4214, tw > 60),
    ("carshare used 0 times", 99, 179456, sn("CARSHARE") == 0),
]
for lab, pct, cnt, mask in rows:
    a.check(f"T4 {lab}, %", pct, float(mask.mean() * 100), "")
    a.check(f"T4 {lab}, n", cnt, int(mask.sum()))

# three rows whose labels look reversed: the printed 'Yes' share equals our 'No' share
urban = s["URBRUR"] == "01"
drv = s["DRIVER"] == "01"
child = sn("LIF_CYC").between(3, 8)
for lab, pct_yes, n_yes, mask in (("lives in an urban area", 22, 40560, urban), ("driver", 5, 9457, drv),
                                  ("has children (LIF_CYC 3-8)", 72, 129921, child)):
    a.check(f"T4 {lab}: printed 'Yes' vs our 'Yes', %", pct_yes, float(mask.mean() * 100), "reversed label?")
    a.check(f"T4 {lab}: printed 'Yes' vs our 'No', %", pct_yes, float((~mask).mean() * 100), "equal to the printed Yes: the Yes/No labels of this row are reversed")
a.info("table 4 income rows sum to", 34169 + 68569 + 26791 + 59566, "the paper's own total is 180,605: the four income rows exceed it by 8,490")
a.info("table 4: printed n of income < 25k as a share of 180,605, %", 34169 / 180605 * 100, "the printed percentage is 14: its own n and % disagree (our n 25,804 = 14.2 %)")
a.info("table 4 age rows sum to", 23317 + 67888 + 85635, "3,765 short of 180,605: the rows leave out another age group")
a.save()
