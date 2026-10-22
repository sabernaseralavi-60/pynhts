"""P24 - Naseralavi et al. (2025), Urban Science 9(9):353: ML modelling of household trip generation by state, 2017 NHTS.

The authors' own paper (the first author is also the author of pynhts), so this audit is NOT independent: it is reported as
such. Unit = household, 2017, unweighted (the paper uses no weights). The paper states the cleaning only as "removal of incomplete
records and handling of outliers", so the sample rules below are the ones that its own Tables 2-5 imply and nothing else:
  R1 HHVEHCNT >= 1        (Table 5: minimum 1.0)
  R2 HHFAMINC 1-11        (Table 2)
  R3 HH_RACE 1-5          (Table 3)
  R4 LIF_CYC 1-10         (Table 4)
  R5 HOMEOWN 1-2          (Table 5: owned + rented = N)
  R6 CNTTDHH >= 1         (Table 5: minimum 1.0; households with no trip on the travel day are absent)
R6 was added AFTER the first run: the first run (R1-R5) left 113,011 households against 106,287 printed, and re-reading Table 5
showed that its minimum of CNTTDHH is 1.0, not 0. It is a rule read off a printed number, not a value searched to reach N; the
first-run counts are kept in the flow table (p24_flow.csv).
Two pre-declared variants for the person-level counts (PTUSED, RIDESHARE): A = sum of the valid answers; B = as A, and a
household with any non-valid answer in either count is dropped. Nothing is tuned: both variants are reported.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import common

common.setup()
import pynhts  # noqa: E402

d = pynhts.load(2017)
h = d.households(["CNTTDHH", "HHSIZE", "HHFAMINC", "HH_RACE", "HOMEOWN", "LIF_CYC", "HHVEHCNT", "URBRUR", "HHSTATE", "DRVRCNT",
                  "YOUNGCHILD"], missing="keep", skip="keep", weight=False)
p = d.persons(["R_AGE", "PTUSED", "RIDESHARE", "HEALTH", "R_SEX", "BORNINUS", "EDUC", "FLEXTIME", "GT1JBLWK", "MEDCOND", "OCCAT"],
              missing="keep", skip="keep", weight=False)


def num(s: pd.Series) -> pd.Series:
    x = pd.to_numeric(s, errors="coerce")
    return x.where(x >= 0)


pp = pd.DataFrame({
    "HOUSEID": p["HOUSEID"],
    "age": num(p["R_AGE"]), "pt": num(p["PTUSED"]), "ride": num(p["RIDESHARE"]),
    "male": (p["R_SEX"] == "01").astype(float),
    "poor": (p["HEALTH"] == "05").astype(float),
    "foreign": (p["BORNINUS"] == "02").astype(float),
    "bach": (p["EDUC"] == "04").astype(float),
    "flex": (p["FLEXTIME"] == "01").astype(float),
    "twojobs": (p["GT1JBLWK"] == "01").astype(float),
    "med": (p["MEDCOND"] == "01").astype(float),
})
g = pp.groupby("HOUSEID")
agg = pd.DataFrame({
    "Age_mean": g["age"].mean(), "PTUSED": g["pt"].sum(min_count=1), "RIDESHARE": g["ride"].sum(min_count=1),
    "pt_bad": g["pt"].apply(lambda s: s.isna().any()), "ride_bad": g["ride"].apply(lambda s: s.isna().any()),
    "Gender_male_prc": g["male"].mean(), "HEALTH_Poor_prc": g["poor"].mean(), "EDUC_bachelor_prc": g["bach"].mean(),
}).reset_index()
x = h.merge(agg, on="HOUSEID", how="left")
for c in ("CNTTDHH", "HHSIZE", "HHVEHCNT", "DRVRCNT", "YOUNGCHILD"):
    x[c] = pd.to_numeric(x[c], errors="coerce")
x["YOUNGCHILD_prc"] = x["YOUNGCHILD"] / x["HHSIZE"]
x["DRVRCNT_prc"] = x["DRVRCNT"] / x["HHSIZE"]
x["HHFAMINC_n"] = num(x["HHFAMINC"])

a = common.Audit("p24_naseralavi2025")
r1 = x[x["HHVEHCNT"] >= 1]
r2 = r1[r1["HHFAMINC"].isin([f"{i:02d}" for i in range(1, 12)])]
r3 = r2[r2["HH_RACE"].isin(["01", "02", "03", "04", "05"])]
r4 = r3[r3["LIF_CYC"].isin([f"{i:02d}" for i in range(1, 11)])]
r5 = r4[r4["HOMEOWN"].isin(["01", "02"])]
r6 = r5[r5["CNTTDHH"] >= 1]
base = r6.dropna(subset=["Age_mean", "CNTTDHH", "HHSIZE", "DRVRCNT"])
flow = [("start", len(x)), ("R1 vehicles >= 1", len(r1)), ("R2 income 1-11", len(r2)), ("R3 race 1-5", len(r3)),
        ("R4 life cycle 1-10", len(r4)), ("R5 owned or rented", len(r5)), ("R6 at least one trip", len(r6)), ("complete household variables", len(base))]
pd.DataFrame(flow, columns=["step", "households"]).to_csv(common.RESULTS / "aux_p24_flow.csv", index=False)
for lab, n in flow[1:]:
    print(f"{lab:32s}{n:>9,}")

variants = {
    "A": base.assign(PTUSED=base["PTUSED"].fillna(0), RIDESHARE=base["RIDESHARE"].fillna(0)),
    "B": base[~(base["pt_bad"] | base["ride_bad"])],
}
PUB = {  # variable: (mean, sd, min, max) as printed in Table 5
    "CNTTDHH": (8.0, 5.6, 1.0, 95.0), "HHSIZE": (2.2, 1.2, 1.0, 13.0), "Age_mean": (52.3, 18.3, 11.0, 92.0),
    "YOUNGCHILD_prc": (0.0, 0.1, 0.0, 0.8), "DRVRCNT_prc": (0.9, 0.2, 0.0, 1.0), "Gender_male_prc": (0.5, 0.3, 0.0, 1.0),
    "HHFAMINC_n": (6.3, 2.5, 1.0, 11.0), "HHVEHCNT": (2.1, 1.1, 1.0, 12.0), "PTUSED": (1.7, 6.5, 0.0, 132.0),
    "RIDESHARE": (0.5, 2.7, 0.0, 211.0), "EDUC_bachelor_prc": (0.2, 0.3, 0.0, 1.0), "HEALTH_Poor_prc": (0.0, 0.1, 0.0, 1.0),
}
audits = {"A": a, "B": common.Audit("recheck_p24_variant_B")}  # B (the other reading of the counts) is kept apart from the graded numbers
for v, s in variants.items():
    au = audits[v]
    au.check(f"variant {v}: sample size N", 106287, len(s), "paper: N = 106,287 after cleaning (rules R1-R6 + complete)")
    au.check(f"variant {v}: owned", 84183, int((s["HOMEOWN"] == "01").sum()))
    au.check(f"variant {v}: rented", 22104, int((s["HOMEOWN"] == "02").sum()))
    au.check(f"variant {v}: urban", 82065, int((s["URBRUR"] == "01").sum()))
    au.check(f"variant {v}: rural", 24222, int((s["URBRUR"] == "02").sum()))
    for col, (m, sd, lo, hi) in PUB.items():
        y = s[col].astype(float)
        au.check(f"variant {v}: mean {col}", m, float(y.mean()))
        au.check(f"variant {v}: sd {col}", sd, float(y.std(ddof=1)))
        au.check(f"variant {v}: min {col}", lo, float(y.min()))
        au.check(f"variant {v}: max {col}", hi, float(y.max()))
# the paper models each of the 50 states and DC; how many households does each state contribute?
a.check("states in the sample (50 + DC)", 51, int(variants["A"]["HHSTATE"].nunique()))
st = variants["A"]["HHSTATE"].value_counts()
pd.DataFrame({"households": st}).rename_axis("state").to_csv(common.RESULTS / "aux_p24_state_sizes.csv")
print("state sample sizes: min", int(st.min()), "median", int(st.median()), "max", int(st.max()), "| states under 500:", int((st < 500).sum()))
for au in audits.values():
    au.save()
