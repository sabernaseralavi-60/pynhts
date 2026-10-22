"""Probe (not a graded audit): is the state-to-state variation of trip-generation coefficients larger than sampling noise?

Motivation: the 2025 paper (P24) fits one linear model per state (33 of 51 states have < 500 households in the rebuilt sample) and
reads the spread of the state coefficients as spatial heterogeneity. Here a DELIBERATELY SMALL model (10 predictors, so that
every state has many more households than parameters) is fitted by OLS state by state, and the spread of each coefficient is
compared with (i) its sampling error (Cochran Q, I^2, DerSimonian-Laird tau^2) and (ii) a permutation null in which the state
labels are shuffled among households (no real state effect). The household sample is the one of p24_naseralavi2025.py, variant A.
This is a feasibility probe for a possible paper, not a replication of the paper's 25-variable models.
Output: docs/paper_data_audit/results/probe_p24_heterogeneity.csv
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import common

common.setup()
import pynhts  # noqa: E402

RNG = np.random.default_rng(20261022)
N_PERM = 300

d = pynhts.load(2017)
h = d.households(["CNTTDHH", "HHSIZE", "HHFAMINC", "HH_RACE", "HOMEOWN", "LIF_CYC", "HHVEHCNT", "URBRUR", "HHSTATE", "DRVRCNT"],
                 missing="keep", skip="keep", weight=False)
p = d.persons(["R_AGE", "PTUSED", "RIDESHARE"], missing="keep", skip="keep", weight=False)


def num(s: pd.Series) -> pd.Series:
    x = pd.to_numeric(s, errors="coerce")
    return x.where(x >= 0)


pp = pd.DataFrame({"HOUSEID": p["HOUSEID"], "age": num(p["R_AGE"]), "pt": num(p["PTUSED"]).fillna(0), "ride": num(p["RIDESHARE"]).fillna(0)})
g = pp.groupby("HOUSEID")
agg = pd.DataFrame({"age": g["age"].mean(), "pt": g["pt"].sum(), "ride": g["ride"].sum()}).reset_index()
x = h.merge(agg, on="HOUSEID", how="left")
for c in ("CNTTDHH", "HHSIZE", "HHVEHCNT", "DRVRCNT"):
    x[c] = pd.to_numeric(x[c], errors="coerce")
ok = ((x["HHVEHCNT"] >= 1) & x["HHFAMINC"].isin([f"{i:02d}" for i in range(1, 12)]) & x["HH_RACE"].isin(["01", "02", "03", "04", "05"])
      & x["LIF_CYC"].isin([f"{i:02d}" for i in range(1, 11)]) & x["HOMEOWN"].isin(["01", "02"]) & (x["CNTTDHH"] >= 1) & x["age"].notna())
x = x[ok].copy()
x["inc"] = pd.to_numeric(x["HHFAMINC"])
x["rural"] = (x["URBRUR"] == "02").astype(float)
x["owner"] = (x["HOMEOWN"] == "01").astype(float)
x["drv"] = x["DRVRCNT"] / x["HHSIZE"]
X_COLS = ["HHSIZE", "age", "drv", "HHVEHCNT", "inc", "rural", "owner", "pt", "ride"]
print("households:", len(x), "| states:", x["HHSTATE"].nunique(), "| predictors:", len(X_COLS))

states = sorted(x["HHSTATE"].unique())
y = x["CNTTDHH"].to_numpy(float)
Xall = np.column_stack([np.ones(len(x))] + [x[c].to_numpy(float) for c in X_COLS])
lab = x["HHSTATE"].to_numpy()


def fit(idx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """OLS coefficients and HC1 standard errors for the rows idx."""
    X, yy = Xall[idx], y[idx]
    n, k = X.shape
    xtx_inv = np.linalg.pinv(X.T @ X)
    b = xtx_inv @ X.T @ yy
    e = yy - X @ b
    meat = (X * e[:, None]).T @ (X * e[:, None])
    v = xtx_inv @ meat @ xtx_inv * n / (n - k)
    return b, np.sqrt(np.clip(np.diag(v), 0, None))


def spread(labels: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Per coefficient: Cochran Q, degrees of freedom, DL tau^2, I^2 over the states in which the coefficient is estimable
    (a state with no variation in a predictor, e.g. no rural household, is left out of that coefficient)."""
    B, S = [], []
    for s in states:
        idx = np.flatnonzero(labels == s)
        b, se = fit(idx)
        B.append(b)
        S.append(se)
    B, S = np.array(B), np.array(S)
    good = np.isfinite(S) & (S > 1e-9)
    w = np.where(good, 1 / np.where(good, S, 1) ** 2, 0.0)
    bbar = (w * B).sum(0) / w.sum(0)
    q = (w * (B - bbar) ** 2).sum(0)
    df = good.sum(0) - 1
    c = w.sum(0) - (w**2).sum(0) / w.sum(0)
    tau2 = np.maximum((q - df) / c, 0)
    i2 = np.maximum((q - df) / q, 0)
    return q, df, tau2, i2


q, df, tau2, i2 = spread(lab)
perm_q = np.empty((N_PERM, len(q)))
for i in range(N_PERM):
    perm_q[i] = spread(RNG.permutation(lab))[0]
pval = (1 + (perm_q >= q).sum(0)) / (1 + N_PERM)
names = ["intercept"] + X_COLS
rows = pd.DataFrame({"coefficient": names, "Q": q.round(1), "df": df, "I2_pct": (100 * i2).round(1), "tau2": tau2.round(5),
                     "null_Q_mean": perm_q.mean(0).round(1), "p_permutation": pval.round(4)})
rows["states"] = len(states)
rows["households"] = len(x)
rows.to_csv(common.RESULTS / "probe_p24_heterogeneity.csv", index=False)
print(rows.to_string(index=False))
