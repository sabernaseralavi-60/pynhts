"""P02 Zhou & Wang (2014): structural equation model of online shopping and shopping trips, NHTS 2009.

Published: Table 4, standardised coefficients of a non-recursive model with two latent propensities (online purchasing,
shopping-trip making), ML estimation, n = 85,663, unweighted. Reported here: the two cross-effects and the two measurement
loadings that identify the latent scale. State GDP and state population density are external to NHTS and are left out;
the sample rule of the paper is not recoverable (our complete-case sample is larger, see the audit).
Three regimes: unweighted; weighted covariance; weighted covariance with a jackknife over the 100 replicate weights.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import semopy

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import engine  # noqa: E402

engine.setup()
import pynhts  # noqa: E402

warnings.filterwarnings("ignore")
SPEC = """
prop_purchase =~ purchase + webuse1
prop_shoptrp =~ cnttdtr + shoptrp
prop_purchase ~ prop_shoptrp + urban + hbhtnrnt + hhfaminc1 + hhsize + r_age + educ1 + educ2 + wkftpt
prop_shoptrp ~ prop_purchase + urban + hbhtnrnt + hhsize + r_age + wkftpt + trvlmin + tdwknd
"""
PUB = {("prop_purchase", "prop_shoptrp"): 0.125, ("prop_shoptrp", "prop_purchase"): 0.214}  # (lval, rval) of '~' rows; Table 4 reads: effect of shopping-trip propensity on online purchasing 0.125, reverse 0.214
KEEP = [("prop_purchase", "prop_shoptrp"), ("prop_shoptrp", "prop_purchase"), ("prop_purchase", "hhfaminc1"),
        ("prop_purchase", "educ1"), ("prop_purchase", "r_age"), ("prop_shoptrp", "trvlmin"), ("prop_shoptrp", "tdwknd"),
        ("purchase", "prop_purchase"), ("webuse1", "prop_purchase"), ("cnttdtr", "prop_shoptrp"), ("shoptrp", "prop_shoptrp")]


def build(d):
    p = d.persons(["R_AGE", "R_SEX", "EDUC", "WKFTPT", "WEBUSE", "PURCHASE", "HHFAMINC", "HHSIZE", "URBAN", "HBHTNRNT"],
                  missing="nan", skip="keep")
    t = d.trips(["WHYTRP1S", "TRVL_MIN", "TDWKND"], missing="nan", skip="auto")
    t["shop"] = (t["WHYTRP1S"] == "40").astype(float)
    t["wknd"] = (t["TDWKND"] == "01").astype(float)
    g = t.groupby(["HOUSEID", "PERSONID"]).agg(cnttdtr=("shop", "size"), shoptrp=("shop", "sum"),
                                                trvlmin=("TRVL_MIN", "mean"), tdwknd=("wknd", "max")).reset_index()
    s = p.merge(g, on=["HOUSEID", "PERSONID"], how="inner")
    for col in ("WKFTPT", "EDUC", "WEBUSE", "HHFAMINC", "URBAN"):
        s[col] = s[col].where(~s[col].astype("string").str.startswith("-"))
    s["PURCHASE"] = pd.to_numeric(s["PURCHASE"]).where(lambda x: x >= 0)
    for col in ("R_AGE", "HHSIZE", "HBHTNRNT"):
        s[col] = pd.to_numeric(s[col])
    ok = (s["R_AGE"] >= 18) & s[["WKFTPT", "PURCHASE", "WEBUSE", "EDUC", "HHFAMINC", "URBAN", "HBHTNRNT", "trvlmin"]].notna().all(axis=1)
    z = s[ok].reset_index(drop=True)
    X = pd.DataFrame({
        "purchase": z["PURCHASE"], "webuse1": (z["WEBUSE"] == "01").astype(float), "cnttdtr": z["cnttdtr"], "shoptrp": z["shoptrp"],
        "urban": (z["URBAN"] == "01").astype(float), "hbhtnrnt": z["HBHTNRNT"],
        "hhfaminc1": (pd.to_numeric(z["HHFAMINC"]) <= 10).astype(float), "hhsize": z["HHSIZE"], "r_age": z["R_AGE"],
        "educ1": z["EDUC"].isin(["01", "02"]).astype(float), "educ2": z["EDUC"].isin(["03", "04"]).astype(float),
        "wkftpt": (z["WKFTPT"] == "01").astype(float), "trvlmin": z["trvlmin"], "tdwknd": z["tdwknd"]})
    return z, X


def wcorr(X: np.ndarray, w: np.ndarray) -> np.ndarray:
    w = w / w.sum()
    mu = w @ X
    Xc = X - mu
    C = (Xc * w[:, None]).T @ Xc
    sd = np.sqrt(np.diag(C))
    return C / np.outer(sd, sd)


def fit_corr(R: pd.DataFrame, n: int) -> pd.DataFrame:
    m = semopy.Model(SPEC)
    m.fit(cov=R, n_samples=n)
    t = m.inspect(std_est=True)
    t = t[t["op"].isin(["~"])]
    return t.set_index(["lval", "rval"])["Est. Std"]


def run(replicates=True) -> pd.DataFrame:
    d = pynhts.load(2009, replicates=True)
    z, X = build(d)
    n = len(X)
    cols = list(X.columns)
    A = X.to_numpy(float)
    des = engine.design_for(d, z[["HOUSEID", "PERSONID"]], "person")
    naive = fit_corr(pd.DataFrame(np.corrcoef(A, rowvar=False), index=cols, columns=cols), n)
    wfull = fit_corr(pd.DataFrame(wcorr(A, des.w), index=cols, columns=cols), n)
    rows = []
    if replicates:
        B = []
        for r in range(des.n_reps):
            B.append(fit_corr(pd.DataFrame(wcorr(A, des.reps[:, r].astype(float)), index=cols, columns=cols), n))
        B = pd.concat(B, axis=1)
    for key in KEEP:
        row = {"lval": key[0], "rval": key[1], "n": n, "est_naive": naive.get(key, np.nan), "est_weighted": wfull.get(key, np.nan),
               "published": PUB.get(key, np.nan)}
        if replicates and key in B.index:
            dev = B.loc[key].to_numpy(float) - wfull.get(key)
            row["se_design"] = float(np.sqrt(des.factor * np.sum(dev ** 2)))
        rows.append(row)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    with engine.Timer() as t:
        r = run()
    r.to_csv(engine.RESULTS / "tables" / "p02_models.csv", index=False)
    print(f"{t.dt:.0f} s")
    print(r.round(3).to_string())
