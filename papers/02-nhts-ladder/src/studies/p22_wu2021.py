"""P22 Wu & MacKenzie (2021): propensity-score matching of ridesourcing user groups, daily VMT, NHTS 2017.

Published: occasional / frequent / non-users matched within CBSA and area class on eight covariates plus density,
caliper 0.1 SD of the propensity score; matched means of daily VMT (drivers with household vehicle access: frequent 24.82,
occasional 25.86, non-user 25.41; others: 6.25, 5.03, 4.37) and pairwise vehicle-ownership differences.
Here: greedy nearest-neighbour matching (not optimal), the same covariates, then the matched differences with the
paper-style paired-t standard error and with replicate-weight (design) standard errors.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import engine  # noqa: E402

engine.setup()
import pynhts  # noqa: E402
from pynhts import aggregate as A  # noqa: E402

warnings.filterwarnings("ignore")
PV = ["03", "04", "05", "06", "08", "09", "18"]
TR = ["17"]
ALPHA = 0.6
PUB_VMT = {"access": {"frequent": 24.82, "occasional": 25.86, "non": 25.41},
           "none": {"frequent": 6.25, "occasional": 5.03, "non": 4.37}}
PUB_VEH_DIFF = {("non", "occasional"): -0.065, ("occasional", "frequent"): -0.125, ("non", "frequent"): -0.190}


def build(d):
    t = d.trips(["TRPTRANS", "TRPMILES", "NUMONTRP"], missing="nan", skip="keep", weight=False)
    tt = pd.to_numeric(t["TRPMILES"])
    x = t[["HOUSEID", "PERSONID", "TRPTRANS"]].copy()
    dist = tt.where((tt >= 0) & (tt <= 500))
    vo = pd.to_numeric(t["NUMONTRP"]).where(lambda s: s >= 1)
    x["pv"], x["tr"] = x["TRPTRANS"].isin(PV), x["TRPTRANS"].isin(TR)
    x["vmt_pv"] = np.where(x["pv"], dist / vo, 0.0)
    x["vmt_tr"] = np.where(x["tr"], dist / vo, 0.0)
    x["vmt_dead"] = ALPHA * x["vmt_tr"]
    x.loc[(x["pv"] | x["tr"]) & dist.isna(), ["vmt_pv", "vmt_tr", "vmt_dead"]] = np.nan
    day = A.aggregate(d, x, "person", {
        "n_auto_pv": A.Agg.n(A.Where("pv", "==", True)), "n_auto_tr": A.Agg.n(A.Where("tr", "==", True)),
        "mi_pv": A.Agg.sum("vmt_pv"), "mi_tr": A.Agg.sum("vmt_tr"), "mi_dead": A.Agg.sum("vmt_dead")},
        missing="skip", orphans="report")
    pp = d.persons(["R_AGE", "R_SEX", "R_RACE", "EDUC", "WKFTPT", "RIDESHARE", "DRIVER", "HHVEHCNT", "HOMEOWN", "HHSIZE",
                    "HHFAMINC", "HBPPOPDN", "URBAN", "HH_CBSA"], missing="nan", skip="keep")
    p = pp.merge(day[["HOUSEID", "PERSONID", "n_auto_pv", "n_auto_tr", "mi_pv", "mi_tr", "mi_dead"]], on=["HOUSEID", "PERSONID"], how="left")
    rs = pd.to_numeric(p["RIDESHARE"])
    p = p[(pd.to_numeric(p["R_AGE"]) >= 16) & rs.ge(0)].copy()
    p["group"] = pd.cut(rs[p.index], [-1, 0, 3, 1000], labels=["non", "occasional", "frequent"]).astype(str)
    p["auto_trips"] = p["n_auto_pv"].fillna(0) + p["n_auto_tr"].fillna(0)
    p = p[p["auto_trips"] > 0].copy()
    p["vmt"] = p["mi_pv"] + p["mi_tr"] + p["mi_dead"]
    p["veh"] = pd.to_numeric(p["HHVEHCNT"])
    p["access"] = np.where((p["DRIVER"] == "01") & (p["veh"] > 0), "access", "none")
    p = p.dropna(subset=["vmt", "R_AGE", "R_SEX", "EDUC", "WKFTPT", "HOMEOWN", "HHSIZE", "HHFAMINC", "HBPPOPDN", "URBAN", "HH_CBSA", "R_RACE"]).copy()
    for c in ("R_AGE", "HHSIZE", "HBPPOPDN"):
        p[c] = pd.to_numeric(p[c])
    return p.reset_index(drop=True)


def covariates(p):
    X = pd.DataFrame({"age": p["R_AGE"], "age2": p["R_AGE"] ** 2, "female": (p["R_SEX"] == "02").astype(float),
                      "ft": (p["WKFTPT"] == "01").astype(float), "own": (p["HOMEOWN"] == "01").astype(float),
                      "hhsize": p["HHSIZE"], "dens": np.log(p["HBPPOPDN"].clip(lower=1))})
    for col in ("R_RACE", "EDUC", "HHFAMINC"):
        X = X.join(pd.get_dummies(p[col], prefix=col, drop_first=True, dtype=float))
    return X


def match(p, treated="frequent", control="non", caliper_sd=0.1, seed=0):
    """Greedy 1:1 nearest-neighbour matching without replacement within CBSA x area class; returns index pairs."""
    sub = p[p["group"].isin([treated, control])].copy()
    X = covariates(sub)
    X = (X - X.mean()) / X.std().replace(0, 1)
    lr = LogisticRegression(max_iter=500, C=1e6)
    lr.fit(X, (sub["group"] == treated).astype(int))
    ps = lr.decision_function(X)
    sub["ps"] = ps
    cal = caliper_sd * ps.std()
    rng = np.random.default_rng(seed)
    pairs = []
    sub["cell"] = sub["HH_CBSA"].astype(str) + "|" + sub["URBAN"].astype(str)
    for cell, g in sub.groupby("cell"):
        tr = g[g["group"] == treated]
        co = g[g["group"] == control]
        if tr.empty or co.empty:
            continue
        co_ps = co["ps"].to_numpy()
        used = np.zeros(len(co), dtype=bool)
        for i in rng.permutation(len(tr)):
            d_ = np.abs(co_ps - tr["ps"].iloc[i])
            d_[used] = np.inf
            j = int(np.argmin(d_))
            if d_[j] <= cal:
                used[j] = True
                pairs.append((tr.index[i], co.index[j]))
    return pairs


def run(replicates=True) -> pd.DataFrame:
    d = pynhts.load(2017, replicates=True)
    p = build(d)
    des = engine.design_for(d, p[["HOUSEID", "PERSONID"]], "person")
    w, R = des.w, des.reps.astype(np.float64)
    rows = []
    for acc in ("access", "none"):
        q = p[p["access"] == acc]
        pos = {i: k for k, i in enumerate(p.index)}
        pf_o = match(q, "frequent", "occasional")
        pf_n = match(q, "frequent", "non")
        fo = {a: b for a, b in pf_o}
        fn = {a: b for a, b in pf_n}
        triples = [(f, fo[f], fn[f]) for f in fo if f in fn]
        T = np.array(triples)
        print(acc, "pairs F-O", len(pf_o), "F-N", len(pf_n), "triples", len(T), flush=True)
        for g, col in (("frequent", 0), ("occasional", 1), ("non", 2)):
            ix = T[:, col]
            ww = w[[pos[i] for i in ix]]
            vm = p.loc[ix, "vmt"].to_numpy()
            ve = p.loc[ix, "veh"].to_numpy()
            rows.append({"scope": acc, "group": g, "n_matched": len(T), "vmt_unweighted": vm.mean(),
                         "vmt_weighted": np.average(vm, weights=ww), "veh_unweighted": ve.mean(),
                         "published_vmt": PUB_VMT[acc][g]})
        for a_, b_, ca, cb in (("occasional", "frequent", 1, 0), ("non", "occasional", 2, 1), ("non", "frequent", 2, 0)):
            for outcome in ("vmt", "veh"):
                ya = p.loc[T[:, ca], outcome].to_numpy()
                yb = p.loc[T[:, cb], outcome].to_numpy()
                dif = yb - ya  # J - I as in the paper's Table 4 style: later group minus earlier group
                ia = [pos[i] for i in T[:, ca]]
                ib = [pos[i] for i in T[:, cb]]
                est_w = np.average(yb, weights=w[ib]) - np.average(ya, weights=w[ia])
                se_naive = dif.std(ddof=1) / np.sqrt(len(dif))
                rep = np.array([np.average(yb, weights=R[ib, r]) - np.average(ya, weights=R[ia, r]) for r in range(R.shape[1])])
                se_design = np.sqrt(des.factor * np.sum((rep - est_w) ** 2))
                rows.append({"scope": acc, "contrast": f"{a_}->{b_}", "outcome": outcome, "n_matched": len(T),
                             "diff_unweighted": dif.mean(), "se_paired": se_naive, "diff_weighted": est_w, "se_design": se_design,
                             "published_veh_diff": PUB_VEH_DIFF.get((a_, b_)) if (outcome == "veh" and acc == "access") else np.nan})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    r = run()
    r.to_csv(engine.RESULTS / "tables" / "p22_models.csv", index=False)
    with pd.option_context("display.width", 250):
        print(r.round(3).to_string())
