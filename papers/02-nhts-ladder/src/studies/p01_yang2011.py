"""P01 Yang, Diez Roux & Bingham (2011): logistic regression of 'any active trip on the travel day' by age group, NHTS 2001.

Published: weighted logistic regression, odds ratios (Table 2), one model per age group.
Here: the same specification fitted under the three regimes of engine.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine  # noqa: E402

engine.setup()
import pynhts  # noqa: E402

PAPER = "P01"
PUBLISHED = {  # age group -> {term: published odds ratio}; from Table 2
    "18-64": {"female": 1.12, "race_Black": 0.88, "race_Asian": 0.82, "race_Hispanic": 0.83,
              "inc_20-40k": 0.67, "inc_40-80k": 0.69, "inc_>80k": 0.86, "reg_Midwest": 0.67,
              "reg_South": 0.56, "reg_West": 0.73, "urb_Town": 1.24, "urb_Suburban": 1.39,
              "urb_Second city": 1.84, "urb_Urban": 3.00, "m5": 1.46, "m7": 1.27},
    "11-17": {"female": 0.87, "race_Black": 1.50, "inc_>80k": 0.53, "reg_South": 0.58, "urb_Urban": 1.91},
}


def build(d):
    p = d.persons(["R_AGE", "R_SEX", "HHR_RACE", "HHFAMINC", "HHINCTTL", "CENSUS_R", "HBHUR", "TDAYDATE"],
                  missing="keep", skip="keep")
    age = pd.to_numeric(p["R_AGE"])
    miss = (age < 5) | p["HHFAMINC"].isin(["-1", "-7", "-8", "-9"]) | p["R_SEX"].isin(["-7", "-8", "-9"]) | p["HBHUR"].eq("-9")
    p["race"] = p["HHR_RACE"].map({"01": "White", "02": "Black", "03": "Asian", "06": "Hispanic"}).fillna("other")
    s = p[~(miss | p["race"].eq("other"))].copy()
    s["age"] = pd.to_numeric(s["R_AGE"])
    s["grp"] = pd.cut(s["age"], bins=[5, 11, 18, 65, 200], right=False, labels=["5-10", "11-17", "18-64", "65+"])
    inc = pd.to_numeric(s["HHINCTTL"])
    s["income"] = np.select([inc <= 4, inc <= 8, inc <= 16], ["<20k", "20-40k", "40-80k"], default=">80k")
    s["sex"] = np.where(s["R_SEX"].eq("1"), "Male", "Female")
    s["region"] = s["CENSUS_R"].map({"1": "Northeast", "2": "Midwest", "3": "South", "4": "West"})
    s["urb"] = s["HBHUR"].map({"R": "Rural", "T": "Town", "S": "Suburban", "C": "Second city", "U": "Urban"})
    s["month"] = pd.to_numeric(s["TDAYDATE"].astype(str).str[4:6])
    t = d.trips(["TRPTRANS"], missing="keep", skip="keep")
    t["active"] = t["TRPTRANS"].isin(["25", "26"])
    per = t.groupby(["HOUSEID", "PERSONID"]).agg(nact=("active", "sum")).reset_index()
    s = s.merge(per, on=["HOUSEID", "PERSONID"], how="left")
    s["nact"] = s["nact"].fillna(0)
    s["pat"] = (s["nact"] > 0).astype(float)
    return s


def design_matrix(sub):
    X = pd.DataFrame({"const": 1.0}, index=sub.index)
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


def run(groups=("18-64", "11-17"), replicates=True) -> pd.DataFrame:
    d = pynhts.load(2001, replicates=True)
    s = build(d)
    out = []
    for g in groups:
        sub = s[s["grp"] == g].reset_index(drop=True)
        des = engine.design_for(d, sub[["HOUSEID", "PERSONID"]], "person")
        res = engine.fit_regimes(design_matrix(sub), sub["pat"].to_numpy(), des, "binomial", replicates=replicates)
        res = engine.odds(res)
        res.insert(0, "group", g)
        res["published_or"] = res["term"].map(PUBLISHED.get(g, {}))
        out.append(res)
    return pd.concat(out, ignore_index=True)


if __name__ == "__main__":
    with engine.Timer() as t:
        r = run()
    r.to_csv(engine.RESULTS / "tables" / "p01_models.csv", index=False)
    print(f"{t.dt:.0f} s")
    with pd.option_context("display.width", 250, "display.max_rows", 100):
        print(r[r["published_or"].notna()][["group", "term", "published_or", "or_naive", "or_weighted", "or_design", "p_naive", "p_weighted", "p_design"]].round(3))
