"""P20 Shirgaokar & Nobler (2021): negative binomial models of daily trips by purpose, immigrants versus US-born, NHTS 2017.

Published: Table 2 (social trips, full sample, Stata robust nbreg; weights not stated). The other three discretionary
purposes use the same specification; only the social model has printed coefficients read here.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import countmodels as cm  # noqa: E402
import engine  # noqa: E402

engine.setup()
import pynhts  # noqa: E402
from pynhts import aggregate as A  # noqa: E402

PURPOSE = {"social": ("05", "13", "17", "19"), "recreation": ("15",), "exercise": ("16",),
           "errand": ("06", "07", "09", "10", "11", "12", "14", "18")}
PUB_SOCIAL = {"const": -1.36, "immigrant": -0.27, "child": 0.05, "early": -0.18, "mid": -0.17, "female": 0.07,
              "nonwhite": -0.03, "educ_years": 0.02, "driver": 0.51, "ln_hhsize": -0.25, "kid_hh": 0.04,
              "ln_income": 0.05, "ln_veh1": 0.09, "urban": 0.00, "dens10k": 0.04}
EDYEARS = {1: 10, 2: 12, 3: 14, 4: 16, 5: 18}
INC = {1: 5, 2: 12.5, 3: 20, 4: 30, 5: 42.5, 6: 62.5, 7: 87.5, 8: 112.5, 9: 137.5, 10: 175, 11: 250}


def build(d):
    specs = {k: A.Agg.n(A.Where("WHYTO", "in", v)) for k, v in PURPOSE.items()}
    trips = A.aggregate(d, "trip", "person", specs)
    cols = ["BORNINUS", "R_AGE", "R_SEX", "R_RACE", "EDUC", "DRIVER", "HHSIZE", "LIF_CYC", "HHFAMINC", "HHVEHCNT",
            "HBPPOPDN", "URBRUR"]
    p = d.persons(cols, missing="nan", skip="keep")
    p = p.merge(trips[["HOUSEID", "PERSONID", *PURPOSE]], on=["HOUSEID", "PERSONID"], how="left")
    n = lambda c: pd.to_numeric(p[c], errors="coerce")  # noqa: E731
    p = p[p["BORNINUS"].isin(["01", "02"]) & (n("R_AGE") >= 5)]
    n = lambda c: pd.to_numeric(p[c], errors="coerce")  # noqa: E731
    p = p[(n("HHFAMINC") >= 0) & (n("R_RACE") >= 0) & (n("HHSIZE") >= 0) & (n("HHVEHCNT") >= 0) & (n("HBPPOPDN") >= 0)
          & p["DRIVER"].isin(["01", "02"]) & n("EDUC").between(1, 5)].copy().reset_index(drop=True)
    n = lambda c: pd.to_numeric(p[c], errors="coerce")  # noqa: E731
    age = n("R_AGE")
    X = pd.DataFrame({
        "const": 1.0, "immigrant": (p["BORNINUS"] == "02").astype(float), "child": (age < 16).astype(float),
        "early": age.between(16, 35).astype(float), "mid": age.between(36, 64).astype(float),
        "female": (p["R_SEX"] == "02").astype(float), "nonwhite": (p["R_RACE"] != "01").astype(float),
        "educ_years": n("EDUC").map(EDYEARS), "driver": (p["DRIVER"] == "01").astype(float),
        "ln_hhsize": np.log(n("HHSIZE")), "kid_hh": n("LIF_CYC").between(3, 6).astype(float),
        "ln_income": np.log(n("HHFAMINC").map(INC)), "ln_veh1": np.log1p(n("HHVEHCNT")),
        "urban": (p["URBRUR"] == "01").astype(float), "dens10k": n("HBPPOPDN") / 10000})
    for k in PURPOSE:
        p[k] = p[k].fillna(0)
    ok = X.notna().all(axis=1)
    return p[ok].reset_index(drop=True), X[ok].reset_index(drop=True)


def run(purposes=("social", "recreation", "exercise", "errand"), replicates=True) -> pd.DataFrame:
    d = pynhts.load(2017, replicates=True)
    p, X = build(d)
    des = engine.design_for(d, p[["HOUSEID", "PERSONID"]], "person")
    out = []
    for k in purposes:
        res = cm.fit_regimes(X, None, p[k].to_numpy(float), des, replicates=replicates)
        res.insert(0, "model", k)
        res["published"] = [PUB_SOCIAL.get(t) if (k == "social" and part == "count") else None
                            for part, t in zip(res["part"], res["term"])]
        res["n"] = len(p)
        out.append(res)
    return pd.concat(out, ignore_index=True)


if __name__ == "__main__":
    with engine.Timer() as t:
        r = run()
    r.to_csv(engine.RESULTS / "tables" / "p20_models.csv", index=False)
    print(f"{t.dt:.0f} s")
    with pd.option_context("display.width", 250, "display.max_rows", 100):
        print(r[r.model == "social"][["term", "published", "b_naive", "b_weighted", "b_design", "se_naive", "se_design", "p_naive", "p_design"]].round(3).to_string())
