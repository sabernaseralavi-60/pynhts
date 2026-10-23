"""P03 Quinn et al. (2016): adjusted odds of walking / cycling for transport and for commuting, NHTS 2009.

Published: Table 2 (Stata logistic regression with population weights and the jackknife of the User's Guide).
Four models (transport walkers, transport bikers, commute walkers, commute bikers). Refused / not ascertained is a
separate category, as the paper states.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import engine  # noqa: E402

engine.setup()
import pynhts  # noqa: E402

PUB = {  # outcome -> {term: OR}
    "walk_transport": {"edu_HS": .67, "edu_SC": .77, "edu_BA": 1.01, "edu_GR": 1.34, "age_25_44": 1.03, "age_45_64": 1.04,
                       "age_65": .84, "male": .90, "race_Black": 1.02, "race_Hisp": 1.17, "race_Other": 1.17,
                       "inc_25_49": .63, "inc_50_74": .58, "inc_75": .58, "urban": 2.14},
    "bike_transport": {"edu_HS": .63, "edu_SC": .46, "edu_BA": 1.06, "edu_GR": .98, "age_25_44": 1.02, "age_45_64": .89,
                       "age_65": .41, "male": 3.49, "race_Black": .53, "race_Hisp": .61, "race_Other": .64,
                       "inc_25_49": .78, "inc_50_74": .62, "inc_75": .74, "urban": 1.52},
    "walk_commute": {"edu_HS": .55, "edu_SC": .53, "edu_BA": .66, "edu_GR": 1.21, "age_25_44": .61, "age_45_64": .59,
                     "age_65": .76, "male": 1.17, "race_Black": .92, "race_Hisp": .70, "race_Other": 1.11,
                     "inc_25_49": .61, "inc_50_74": .30, "inc_75": .21, "urban": 1.39},
    "bike_commute": {"edu_HS": .20, "edu_SC": .23, "edu_BA": .41, "edu_GR": .41, "age_25_44": 1.24, "age_45_64": .77,
                     "age_65": .30, "male": 3.09, "race_Black": .68, "race_Hisp": .53, "race_Other": .49,
                     "inc_25_49": .52, "inc_50_74": .61, "inc_75": .72, "urban": 2.80},
}


def build(d):
    cols = ["R_AGE", "R_SEX", "MEDCOND", "WRKTRANS", "EDUC", "HH_RACE", "HHFAMINC", "URBRUR"]
    p = d.persons(cols, missing="keep", skip="keep")
    age = pd.to_numeric(p["R_AGE"])
    base = (age >= 18) & (p["MEDCOND"] != "01")
    t = d.trips(["TRPTRANS", "TRVL_MIN", "WHYTO"], missing="nan", skip="auto")
    ok = (t["WHYTO"] != "51") & (t["TRVL_MIN"] >= 10)
    for name, code in (("walker", "23"), ("biker", "22")):
        k = t[ok & (t["TRPTRANS"] == code)].groupby(["HOUSEID", "PERSONID"]).size().rename("n_" + name)
        p = p.join(k, on=["HOUSEID", "PERSONID"])
        p[name] = p["n_" + name].fillna(0) > 0
    p["cwalk"] = p["WRKTRANS"].eq("23")
    p["cbike"] = p["WRKTRANS"].eq("22")
    worker = p["WRKTRANS"].isin([f"{i:02d}" for i in range(1, 30)])
    p["base"], p["commuter"] = base, base & worker
    return p


def design_matrix(s):
    edu = pd.to_numeric(s["EDUC"], errors="coerce")
    inc = pd.to_numeric(s["HHFAMINC"], errors="coerce")
    age = pd.to_numeric(s["R_AGE"])
    race = s["HH_RACE"]
    X = pd.DataFrame({"const": 1.0}, index=s.index)
    for k, c in (("HS", 2), ("SC", 3), ("BA", 4), ("GR", 5)):
        X["edu_" + k] = (edu == c).astype(float)
    X["edu_missing"] = (~edu.between(1, 5)).astype(float)
    X["age_25_44"] = age.between(25, 44).astype(float)
    X["age_45_64"] = age.between(45, 64).astype(float)
    X["age_65"] = (age >= 65).astype(float)
    X["male"] = s["R_SEX"].eq("01").astype(float)
    X["race_Black"] = race.eq("02").astype(float)
    X["race_Hisp"] = race.eq("07").astype(float)
    X["race_Other"] = race.isin(["03", "04", "05", "06", "97"]).astype(float)
    X["race_missing"] = (~race.isin(["01", "02", "03", "04", "05", "06", "07", "97"])).astype(float)
    X["inc_25_49"] = inc.between(6, 10).astype(float)
    X["inc_50_74"] = inc.between(11, 15).astype(float)
    X["inc_75"] = inc.between(16, 18).astype(float)
    X["inc_missing"] = (~inc.between(1, 18)).astype(float)
    X["urban"] = s["URBRUR"].eq("01").astype(float)
    return X


def run(replicates=True) -> pd.DataFrame:
    d = pynhts.load(2009, replicates=True)
    p = build(d)
    out = []
    for name, y, dom in (("walk_transport", "walker", "base"), ("bike_transport", "biker", "base"),
                         ("walk_commute", "cwalk", "commuter"), ("bike_commute", "cbike", "commuter")):
        s = p[p[dom]].dropna(subset=["WTPERFIN"]).reset_index(drop=True)
        X = design_matrix(s)
        des = engine.design_for(d, s[["HOUSEID", "PERSONID"]], "person")
        res = engine.odds(engine.fit_regimes(X, s[y].to_numpy(float), des, "binomial", replicates=replicates))
        res.insert(0, "model", name)
        res["published_or"] = res["term"].map(PUB[name])
        res["n"] = len(s)
        out.append(res)
    return pd.concat(out, ignore_index=True)


if __name__ == "__main__":
    with engine.Timer() as t:
        r = run()
    r.to_csv(engine.RESULTS / "tables" / "p03_models.csv", index=False)
    print(f"{t.dt:.0f} s")
    with pd.option_context("display.width", 250, "display.max_rows", 200):
        print(r[r["published_or"].notna()][["model", "term", "published_or", "or_naive", "or_weighted", "p_naive", "p_design", "n"]].round(3).to_string())
