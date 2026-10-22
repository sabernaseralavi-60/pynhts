"""P01 - Yang, Diez Roux, Bingham (2011), IJBNPA 8:96: active transportation and seasonality, NHTS 2001.

Builds the person-level analysis file (160,758 -> 130,222 persons) and checks Table 1, the text
(trips and active-trip rates) and, as an end-to-end test of the variable construction, the
odds ratios of Table 2 (weighted logistic regression, numpy IRLS).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import common

common.setup()
import pynhts  # noqa: E402

a = common.Audit("p01_yang2011")
d = pynhts.load(2001)

p = d.persons(
    ["R_AGE", "R_SEX", "HHR_RACE", "HHR_HISP", "HHFAMINC", "HHINCTTL", "CENSUS_R", "HBHUR", "TDAYDATE", "CNTTDTR"],
    missing="keep", skip="keep",
)
a.check("persons in 2001 person file", 160758, len(p))

age = pd.to_numeric(p["R_AGE"])
miss_age = age < 5  # ages 0-4 (9,743) and not-ascertained (2,399) are both outside the paper's age groups
miss_inc = p["HHFAMINC"].isin(["-1", "-7", "-8", "-9"])
miss_sex = p["R_SEX"].isin(["-7", "-8", "-9"])
miss_urb = p["HBHUR"].eq("-9")
a.check("missing household income", 12329, int(miss_inc.sum()))
a.check("missing age", 12142, int(miss_age.sum()))
a.check("missing urbanization", 48, int(miss_urb.sum()))
a.check("missing gender", 21, int(miss_sex.sum()))

# race/ethnicity = the single household-respondent race code (HHR_RACE): 01 White, 02 Black, 03 Asian,
# 06 "Hispanic/Mexican only"; every other code is excluded (recovered: gives n = 130,222 and the
# published shares; the Hispanic-origin flag HHR_HISP gives 12.5 % Hispanic and n = 133,533)
p["race"] = p["HHR_RACE"].map({"01": "White", "02": "Black", "03": "Asian", "06": "Hispanic"}).fillna("other")
keep = ~(miss_age | miss_inc | miss_sex | miss_urb | p["race"].eq("other"))
a.check("analysis sample (persons)", 130222, int(keep.sum()), "paper: 160,758 - 30,536 excluded")
s = p[keep].copy()
s["age"] = pd.to_numeric(s["R_AGE"])
s["grp"] = pd.cut(s["age"], bins=[5, 11, 18, 65, 200], right=False, labels=["5-10", "11-17", "18-64", "65+"])
s = s[s["age"] >= 5]
a.check("analysis sample age >= 5", 130222, len(s))

inc = pd.to_numeric(s["HHINCTTL"])  # recovered: HHINCTTL (not HHFAMINC) reproduces the published income shares
s["income"] = np.select([inc <= 4, inc <= 8, inc <= 16], ["<20k", "20-40k", "40-80k"], default=">80k")
s["sex"] = np.where(s["R_SEX"].eq("1"), "Male", "Female")
s["region"] = s["CENSUS_R"].map({"1": "Northeast", "2": "Midwest", "3": "South", "4": "West"})
s["urb"] = s["HBHUR"].map({"R": "Rural", "T": "Town", "S": "Suburban", "C": "Second city", "U": "Urban"})
s["month"] = pd.to_numeric(s["TDAYDATE"].astype(str).str[4:6])
w = "WTPERFIN"


def shares(df, col):
    return df.groupby(col, observed=True)[w].sum() / df[w].sum() * 100


# ---- Table 1: n and weighted % by age group
t_n = {"5-10": 12723, "11-17": 14442, "18-64": 87053, "65+": 16004}
t_pct = {"5-10": 9.8, "11-17": 11.1, "18-64": 66.9, "65+": 12.3}
sh = shares(s, "grp")
for g in t_n:
    a.check(f"T1 n, age {g}", t_n[g], int((s["grp"] == g).sum()),
            "paper-internal inconsistency: Table 2 prints other n for the same groups (see T2 n rows)")
    a.check(f"T1 % weighted, age {g}", t_pct[g], sh[g])

# ---- Table 1 composition (All column and the 5-10 / 65+ columns)
T1 = {
    "sex": {"Male": (51.8, 51.3, 49.2, 42.6, 48.9), "Female": (48.2, 48.7, 50.8, 57.4, 51.1)},
    "race": {"White": (70.9, 73.9, 77.1, 86.2, 77.3), "Black": (14.3, 16.6, 12.5, 10.5, 12.9),
             "Asian": (2.6, 2.1, 2.9, 1.1, 2.5), "Hispanic": (12.2, 7.4, 7.6, 2.2, 7.3)},
    "income": {"<20k": (15.7, 13.0, 12.6, 30.6, 15.2), "20-40k": (23.6, 21.8, 23.8, 36.3, 25.1),
               "40-80k": (36.9, 39.0, 38.0, 24.4, 36.4), ">80k": (23.9, 26.2, 25.5, 8.6, 23.4)},
    "region": {"Northeast": (18.1, 18.9, 18.7, 20.7, 18.9), "Midwest": (24.3, 24.6, 23.3, 24.5, 23.7),
               "South": (34.7, 35.3, 36.2, 36.5, 36.0), "West": (22.9, 21.2, 21.9, 18.2, 21.5)},
    "urb": {"Rural": (21.8, 24.0, 20.5, 21.6, 21.1), "Town": (24.1, 23.2, 22.3, 21.3, 22.4),
            "Suburban": (23.0, 24.3, 24.3, 22.7, 24.0), "Second city": (17.4, 15.8, 17.7, 21.0, 17.9),
            "Urban": (13.8, 12.7, 15.2, 13.3, 14.6)},
}
cols = ["5-10", "11-17", "18-64", "65+", "All"]
for var, cats in T1.items():
    for cat, vals in cats.items():
        for col, pub in zip(cols, vals):
            sub = s if col == "All" else s[s["grp"] == col]
            a.check(f"T1 {var}={cat}, {col}", pub, shares(sub, var).get(cat, np.nan))
mon = {1: 8.5, 2: 7.7, 3: 8.6, 4: 8.2, 5: 8.4, 6: 8.1, 7: 8.4, 8: 8.5, 9: 8.3, 10: 8.6, 11: 8.2, 12: 8.6}
shm = shares(s, "month")
for m, pub in mon.items():
    a.check(f"T1 month={m}, All", pub, shm.get(m, np.nan))

# ---- trip-based outcomes (walk 26, bicycle 25), person-day level
t = d.trips(["TRPTRANS", "TRPMILES", "WTPERFIN"], missing="keep", skip="keep")
t["active"] = t["TRPTRANS"].isin(["25", "26"])
t["miles"] = pd.to_numeric(t["TRPMILES"])
per = t.groupby(["HOUSEID", "PERSONID"]).agg(ntrips=("active", "size"), nact=("active", "sum")).reset_index()
s = s.merge(per, on=["HOUSEID", "PERSONID"], how="left")
s[["ntrips", "nact"]] = s[["ntrips", "nact"]].fillna(0)
s["pat"] = (s["nact"] > 0).astype(float)


def wmean(df, col):
    return float((df[col] * df[w]).sum() / df[w].sum())


for g, tr, act, pat, sub1 in [("18-64", 4.47, None, None, None), ("65+", None, 0.31, 15, 24),
                              ("11-17", None, 0.58, 26, None)]:
    sub = s[s["grp"] == g]
    if tr:
        a.check(f"mean daily trips, adults {g}", tr, wmean(sub, "ntrips"))
    if act:
        a.check(f"mean daily active trips, {g}", act, wmean(sub, "nact"))
    if pat:
        a.check(f"% with >=1 active trip (PAT), {g}", pat, wmean(sub, "pat") * 100)
for g in ("5-10", "11-17", "65+"):
    a.info(f"mean daily trips, {g} (paper: 3.49-3.60 for the three non-adult groups)", round(wmean(s[s["grp"] == g], "ntrips"), 3))

# share of trips under one mile that were active (person weights of the trip owner)
t2 = t.merge(s[["HOUSEID", "PERSONID", "grp"]], on=["HOUSEID", "PERSONID"], how="inner")
short = t2[t2["miles"].between(0, 1)]  # recovered: "less than one mile" = TRPMILES <= 1 (elderly 24.4 matches)
for g, pub in (("11-17", 43), ("65+", 24)):
    sg = short[short["grp"] == g]
    a.check(f"% of trips < 1 mile that are active, {g}", pub, float((sg["active"] * sg["WTPERFIN"]).sum() / sg["WTPERFIN"].sum() * 100))

# ---- Table 2: odds ratios of PAT by predictor, adolescents/adults (reference categories as in the paper)
def design(sub):
    X = pd.DataFrame(index=sub.index)
    X["female"] = (sub["sex"] == "Female").astype(float)
    for c in ("Black", "Asian", "Hispanic"):
        X["race_" + c] = (sub["race"] == c).astype(float)
    for c in ("20-40k", "40-80k", ">80k"):
        X["inc_" + c] = (sub["income"] == c).astype(float)
    for c in ("Midwest", "South", "West"):
        X["reg_" + c] = (sub["region"] == c).astype(float)
    for c in ("Town", "Suburban", "Second city", "Urban"):
        X["urb_" + c] = (sub["urb"] == c).astype(float)
    for m in range(2, 13):
        X[f"m{m}"] = (sub["month"] == m).astype(float)
    return X


T2 = {  # age group -> {term: published OR}
    "18-64": {"female": 1.12, "race_Black": 0.88, "race_Asian": 0.82, "race_Hispanic": 0.83,
              "inc_20-40k": 0.67, "inc_40-80k": 0.69, "inc_>80k": 0.86, "reg_Midwest": 0.67,
              "reg_South": 0.56, "reg_West": 0.73, "urb_Town": 1.24, "urb_Suburban": 1.39,
              "urb_Second city": 1.84, "urb_Urban": 3.00, "m5": 1.46, "m7": 1.27},
    "11-17": {"female": 0.87, "race_Black": 1.50, "inc_>80k": 0.53, "reg_South": 0.58, "urb_Urban": 1.91},
}
for g, pub_n in (("5-10", 11556), ("65+", 20303)):
    a.check(f"T2 sample n, {g}", pub_n, int((s["grp"] == g).sum()))
for g, terms in T2.items():
    sub = s[s["grp"] == g]
    X = design(sub)
    b = common.wlogit(X.values, sub["pat"].values, sub[w].values)
    orr = dict(zip(X.columns, np.exp(b[1:])))
    for term, pub in terms.items():
        a.check(f"T2 OR {term}, {g}", pub, orr[term])
    a.check(f"T2 sample n, {g}", {"18-64": 84712, "11-17": 13651}[g], len(sub))

a.save()
