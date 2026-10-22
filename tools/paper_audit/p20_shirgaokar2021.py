"""P20 - Shirgaokar & Nobler (2021), Transport Policy 105: daily trips of immigrants and US-born, NHTS 2017.

Weighted person-level summary (Table 1): daily trips by purpose, age cohorts, race, education years, driver status,
household and home-location variables, immigrants (14 %) against the US-born (86 %). Built with pynhts.aggregate (trips
to persons, true zeros for persons without trips) and the person weight. The paper's 203,890 observations are not
recovered (the rule that removes ~50,000 of 264,234 persons is not written); weighted means do not depend on it much.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import common

common.setup()
import pynhts  # noqa: E402
from pynhts import aggregate as A  # noqa: E402

a = common.Audit("p20_shirgaokar2021")
d = pynhts.load(2017)

PURPOSE = {  # the paper's note to Fig. 1, WHYTO codes
    "social": ("05", "13", "17", "19"), "recreation": ("15",), "exercise": ("16",),
    "errand": ("06", "07", "09", "10", "11", "12", "14", "18"), "education": ("08",), "work": ("02", "03", "04"),
}
specs = {k: A.Agg.n(A.Where("WHYTO", "in", v)) for k, v in PURPOSE.items()}
trips = A.aggregate(d, "trip", "person", specs)

cols = ["BORNINUS", "R_AGE", "R_SEX", "R_RACE", "EDUC", "DRIVER", "HHSIZE", "LIF_CYC", "HHFAMINC", "HHVEHCNT", "HBPPOPDN", "URBRUR"]
p = d.persons(cols, missing="nan", skip="keep")
p = p.merge(trips[["HOUSEID", "PERSONID", *PURPOSE]], on=["HOUSEID", "PERSONID"], how="left")
n = lambda c: pd.to_numeric(p[c], errors="coerce")  # noqa: E731

p = p[p["BORNINUS"].isin(["01", "02"]) & (n("R_AGE") >= 5)]
n = lambda c: pd.to_numeric(p[c], errors="coerce")  # noqa: E731
p = p[(n("HHFAMINC") >= 0) & (n("R_RACE") >= 0) & (n("HHSIZE") >= 0) & (n("HHVEHCNT") >= 0) & (n("HBPPOPDN") >= 0)].copy()
a.info("persons 5+ with immigrant status and complete household variables", len(p), "paper: 203,890 (not recovered)")
p["imm"] = p["BORNINUS"] == "02"
a.info("immigrants in this sample", int(p["imm"].sum()), "paper: 21,043 of 203,890 (10.3 %)")
w = p["WTPERFIN"]
a.check("weighted immigrant share, %", 14, float(w[p["imm"]].sum() / w.sum() * 100))

age = pd.to_numeric(p["R_AGE"])
EDYEARS = {1: 10, 2: 12, 3: 14, 4: 16, 5: 18}   # recovered: the printed min 10 and max 18 and mean 14.1-14.4
inc = pd.to_numeric(p["HHFAMINC"]).map({1: 5, 2: 12.5, 3: 20, 4: 30, 5: 42.5, 6: 62.5, 7: 87.5, 8: 112.5, 9: 137.5, 10: 175, 11: 250})
x = pd.DataFrame({
    **{k: pd.to_numeric(p[k]).fillna(0) for k in PURPOSE},
    "child": (age < 16), "early": age.between(16, 35), "mid": age.between(36, 64), "old": age > 64,
    "female": p["R_SEX"] == "02", "nonwhite": p["R_RACE"] != "01",
    "educ_years": pd.to_numeric(p["EDUC"]).map(EDYEARS),
    "driver": (p["DRIVER"] == "01").where(p["DRIVER"].isin(["01", "02"])),
    "hhsize": pd.to_numeric(p["HHSIZE"]), "kid_hh": pd.to_numeric(p["LIF_CYC"]).between(3, 6),
    "income_k": inc, "veh": pd.to_numeric(p["HHVEHCNT"]), "urban": p["URBRUR"] == "01",
    "dens10k": pd.to_numeric(p["HBPPOPDN"]) / 10000,
}).astype(float)


def wmean(col: str, mask: pd.Series) -> float:
    v = x.loc[mask, col]
    ww = w[mask][v.notna()]
    return float((v.dropna() * ww).sum() / ww.sum())


def wsd(col: str, mask: pd.Series) -> float:
    m = wmean(col, mask)
    v = x.loc[mask, col]
    ww = w[mask][v.notna()]
    return float(np.sqrt(((v.dropna() - m) ** 2 * ww).sum() / ww.sum()))


T1 = [  # variable, (mean imm, sd imm, mean US-born, sd US-born) as printed; props as fractions
    ("social", 0.40, 0.73, 0.55, 0.87), ("recreation", 0.10, 0.38, 0.13, 0.42), ("exercise", 0.13, 0.40, 0.11, 0.36),
    ("errand", 1.00, 1.42, 1.01, 1.42), ("education", 0.09, 0.32, 0.13, 0.37), ("work", 0.52, 0.80, 0.48, 0.95),
    ("child", 0.07, None, 0.18, None), ("early", 0.27, None, 0.29, None), ("mid", 0.51, None, 0.38, None),
    ("old", 0.15, None, 0.15, None), ("female", 0.53, None, 0.51, None), ("nonwhite", 0.56, None, 0.24, None),
    ("educ_years", 14.4, 2.8, 14.1, 2.5), ("driver", 0.77, None, 0.85, None), ("hhsize", 3.3, 1.5, 3.2, 1.6),
    ("kid_hh", 0.44, None, 0.43, None), ("income_k", 74.7, 57.4, 78.4, 55.8), ("veh", 1.9, 1.2, 2.2, 1.3),
    ("urban", 0.95, None, 0.81, None), ("dens10k", 0.81, 0.85, 0.44, 0.62),
]
for var, mi, si, mu, su in T1:
    a.check(f"T1 {var} mean, immigrants", mi, wmean(var, p["imm"]))
    a.check(f"T1 {var} mean, US-born", mu, wmean(var, ~p["imm"]))
    if si is not None:
        a.check(f"T1 {var} sd, immigrants", si, wsd(var, p["imm"]))
        a.check(f"T1 {var} sd, US-born", su, wsd(var, ~p["imm"]))
a.info("sample rules tried for the 203,890 persons (all / >= 1 trip / education answered, and combinations)", None,
       "none reproduces the printed means: all persons give errand trips 0.93 (paper 1.00) and persons with a trip 1.13; the paper's sample lies "
       "between them, so every trip mean is about 7 % low here; the paper's rule for dropping ~50,000 persons is not written")
a.info("income used the midpoints of the NHTS bands (top band 250k)", None, "the paper's max is 200 (top-coded at 200k) and min 10")
a.save()
