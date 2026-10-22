"""P23 - Su, Xiao, McBride & Goulias (2021), J. Transport Geography 94: seniors' daily mobility motifs, California NHTS 2017.

The paper uses the California add-on of the 2017 NHTS (55,819 respondents, 20,707 aged 60+), seniors with at least one trip
on a "workday" (non-holiday weekday, n = 10,833) or a "non-workday" (weekend or California holiday, n = 4,577), and
Table 1 shares. The public file has HHSTATE but no holiday flag (only the travel-day month and weekday), so workdays are
Monday-Friday here and the split is approximate. The motif construction needs the origin/destination location IDs, which
the public file does not carry (only purpose codes), and the built-environment settings come from CalTrans data.
"""

from __future__ import annotations

import pandas as pd

import common

common.setup()
import pynhts  # noqa: E402

a = common.Audit("p23_su2021")
d = pynhts.load(2017)
cols = ["HHSTATE", "R_AGE", "CNTTDTR", "TRAVDAY", "R_SEX", "EDUC", "WKFTPT", "WRK_HOME", "OCCAT", "HHFAMINC", "LIF_CYC", "PRMACT"]
p = d.persons(cols, missing="keep", skip="keep", weight=False)
ca = p[p["HHSTATE"] == "CA"]
age = pd.to_numeric(ca["R_AGE"])
a.check("California respondents", 55819, len(ca), "the paper's count is 4 % higher: the CA add-on it used has more records than the public file")
a.check("California respondents aged 60+", 20707, int((age >= 60).sum()))
a.check("share aged 60+, %", 37.1, float((age >= 60).mean() * 100))
s = ca[age >= 60].copy()
trips = pd.to_numeric(s["CNTTDTR"])
wd = s["TRAVDAY"].isin(["02", "03", "04", "05", "06"])
a.check("seniors with a trip, workday", 10833, int(((trips > 0) & wd).sum()), "weekday = Monday-Friday; the paper also removes holidays")
a.check("seniors with a trip, non-workday", 4577, int(((trips > 0) & ~wd).sum()), "weekend (the paper adds California holidays)")
a.check("seniors without a trip, workday", 3350, int(((trips == 0) & wd).sum()))
a.check("seniors without a trip, non-workday", 1947, int(((trips == 0) & ~wd).sum()))
a.check("no-trip share on workdays, %", 23.62, float(((trips == 0) & wd).sum() / wd.sum() * 100))
a.check("no-trip share on non-workdays, %", 29.84, float(((trips == 0) & ~wd).sum() / (~wd).sum() * 100))

retired_code = [c["code"] for c in pynhts.describe("PRMACT", 2017)["codes"] if c["label"].lower().startswith("retired")][0]
n = lambda c: pd.to_numeric(s[c], errors="coerce")  # noqa: E731
inc = n("HHFAMINC")
lc = n("LIF_CYC")
ROWS = [  # label, workday %, non-workday %, mask on seniors
    ("female", 52.16, 52.13, s["R_SEX"] == "02"),
    ("age 60-64", 27.86, 28.23, n("R_AGE").between(60, 64)), ("age 65-69", 27.07, 25.78, n("R_AGE").between(65, 69)),
    ("age 70-74", 19.68, 19.64, n("R_AGE").between(70, 74)), ("age 75-79", 12.15, 12.56, n("R_AGE").between(75, 79)),
    ("age 80+", 13.09, 13.59, n("R_AGE") >= 80),
    ("education: high school or below", 16.95, 17.0, n("EDUC").between(1, 2)),
    ("education: some college / associate", 33.12, 32.62, n("EDUC") == 3),
    ("education: bachelor's or above", 49.76, 50.34, n("EDUC") >= 4),
    ("full-time worker", 18.47, 16.52, s["WKFTPT"] == "01"), ("part-time worker", 11.84, 11.71, s["WKFTPT"] == "02"),
    ("works from home", 7.66, 7.36, s["WRK_HOME"] == "01"), ("does not work from home", 22.7, 20.89, s["WRK_HOME"] == "02"),
    ("occupation: sales or service", 6.85, 6.6, s["OCCAT"] == "01"),
    ("occupation: clerical or administrative", 3.62, 3.02, s["OCCAT"] == "02"),
    ("occupation: manufacturing, construction, farming", 3.32, 3.54, s["OCCAT"] == "03"),
    ("occupation: professional, managerial, technical", 16.45, 15.05, s["OCCAT"] == "04"),
    ("retired", 65.39, 66.35, s["PRMACT"] == retired_code),
    ("income < 25k", 14.04, 13.92, inc.between(1, 3)), ("income 25-99.9k", 53.09, 51.72, inc.between(4, 7)),
    ("income 100-199.9k", 22.4, 23.36, inc.between(8, 10)), ("income 200k+", 6.58, 6.53, inc == 11),
    ("household: one adult", 8.23, 8.13, lc == 1), ("household: 2+ adults", 15.32, 14.59, lc == 2),
    ("household: one adult, retired", 18.67, 18.77, lc == 9), ("household: 2+ adults, retired", 53.45, 54.27, lc == 10),
    ("household: one adult with someone under 21", 0.35, 0.22, lc.isin([3, 5, 7])),
    ("household: 2+ adults with someone under 21", 3.97, 4.02, lc.isin([4, 6, 8])),
]
for scope, flag, col in (("workday", wd & (trips > 0), 1), ("non-workday", ~wd & (trips > 0), 2)):
    base = s[flag]
    for lab, w1, w2, mask in ROWS:
        a.check(f"T1 {scope}: {lab}, %", w1 if col == 1 else w2, float(mask[flag].mean() * 100))
a.rows.append({"item": "Table 1: residential setting (rural / suburban / urban neighbourhood / district / core)", "published": None,
               "pynhts": None, "status": "NOT_COMPUTABLE", "note": "CalTrans built-environment data at census-block level, home block is not in the public file"})
a.rows.append({"item": "daily mobility motifs (16 motifs cover 83.05 % of respondents)", "published": None, "pynhts": None,
               "status": "NOT_COMPUTABLE", "note": "the public trip file has no origin/destination location IDs, so a trip network (motif) cannot be built; "
                                                    "a purpose-sequence (home-work-home ...) proxy is the closest public analogue"})
a.save()
