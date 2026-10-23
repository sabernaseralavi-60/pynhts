"""Collect every study's model table into the paper's numbers: ladder grades, design-effect census, verdict shifts.

Reads results/tables/p*_models.csv (written by src/studies/*.py), writes
results/tables/ladder_L2.csv        one row per published coefficient: published value, our three regimes, grades
results/tables/census_coefficients.csv   every reproduced coefficient with SE ratio, sign flip, significance change
results/numbers/summary.json        the headline numbers used in the manuscript
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
TAB = HERE / "results" / "tables"
NUM = HERE / "results" / "numbers"
NUM.mkdir(parents=True, exist_ok=True)
EXCLUDE_TERMS = {"const", "log_alpha"}


def ulp(x: float) -> float:
    d = Decimal(repr(float(x)))
    return 10.0 ** d.as_tuple().exponent


def grade(pub: float, ours: float) -> str:
    if pub is None or ours is None or not np.isfinite(ours) or not np.isfinite(pub):
        return "NA"
    diff = abs(ours - pub)
    u = ulp(pub)
    if diff <= 0.5001 * u:
        return "EXACT"
    if diff <= max(0.02 * abs(pub), 2 * u):
        return "CLOSE"
    if diff <= max(0.05 * abs(pub), 5 * u):
        return "ACCEPTABLE"
    return "GAP"


def load(name, study, scale):
    f = TAB / name
    if not f.exists():
        return pd.DataFrame()
    d = pd.read_csv(f)
    d["study"] = study
    d["scale"] = scale
    return d


def main():
    parts = []
    parts.append(load("p01_models.csv", "P01 Yang 2011", "or"))
    parts.append(load("p03_models.csv", "P03 Quinn 2016", "or"))
    for nm, st in (("p11_models.csv", "P11 Alberini 2021"), ("p14_models.csv", "P14 Zhang 2018"),
                   ("p18_models.csv", "P18 Jiao 2020"), ("p20_models.csv", "P20 Shirgaokar 2021"),
                   ("p13_p15_models.csv", "P13/P15 Zhang 2018")):
        d = load(nm, st, "b")
        if len(d) and "paper" in d:
            d["study"] = d["paper"].map({"P13": "P13 Zhang 2018 (bike)", "P15": "P15 Zhang 2018 (ride)"})
        parts.append(d)
    allm = pd.concat([p for p in parts if len(p)], ignore_index=True)
    allm["pub"] = allm.get("published_or", pd.Series(np.nan, index=allm.index)).fillna(allm.get("published"))
    rows = []
    for _, r in allm.iterrows():
        if r["term"] in EXCLUDE_TERMS:
            continue
        sc = r["scale"]
        get = (lambda k: r.get(("or_" if sc == "or" else "b_") + k))
        part = r.get("part", "")
        rows.append({"study": r["study"], "model": r.get("model", r.get("group", r.get("paper", ""))), "part": part, "term": r["term"],
                     "pub": r["pub"], "naive": get("naive"), "weighted": get("weighted"), "b_naive": r["b_naive"], "b_design": r["b_design"],
                     "se_naive": r["se_naive"], "se_design": r["se_design"], "p_naive": r["p_naive"], "p_design": r["p_design"],
                     "se_wrob": r.get("se_weighted_robust"), "p_wrob": r.get("p_weighted"), "b_weighted": r.get("b_weighted")})
    c = pd.DataFrame(rows)
    c["se_ratio"] = c["se_design"] / c["se_naive"]
    c["sign_flip"] = np.sign(c["b_naive"]) != np.sign(c["b_design"])
    c["sig_naive"] = c["p_naive"] < 0.05
    c["sig_design"] = c["p_design"] < 0.05
    c["sig_lost"] = c["sig_naive"] & ~c["sig_design"]
    c["sig_gained"] = ~c["sig_naive"] & c["sig_design"]
    c["se_ratio_wrob"] = c["se_design"] / c["se_wrob"]
    c["sig_wrob"] = c["p_wrob"] < 0.05
    c["sig_lost_wrob"] = c["sig_wrob"] & ~c["sig_design"]
    c["g_naive"] = [grade(p, x) if pd.notna(p) else "" for p, x in zip(c["pub"], c["naive"])]
    c["g_weighted"] = [grade(p, x) if pd.notna(p) else "" for p, x in zip(c["pub"], c["weighted"])]
    c.to_csv(TAB / "census_coefficients.csv", index=False)
    pubd = c[c["pub"].notna()].copy()
    pubd.to_csv(TAB / "ladder_L2.csv", index=False)

    num = {"n_coef": int(len(c)), "n_coef_published": int(len(pubd)), "median_se_ratio": float(c["se_ratio"].median()),
           "q25_se_ratio": float(c["se_ratio"].quantile(0.25)), "q75_se_ratio": float(c["se_ratio"].quantile(0.75)),
           "share_se_ratio_gt_1_5": float((c["se_ratio"] > 1.5).mean()), "share_se_ratio_gt_2": float((c["se_ratio"] > 2).mean()),
           "share_sig_lost": float(c["sig_lost"].sum() / max(c["sig_naive"].sum(), 1)),
           "n_sig_lost": int(c["sig_lost"].sum()), "n_sig_naive": int(c["sig_naive"].sum()), "n_sig_gained": int(c["sig_gained"].sum()),
           "share_sign_flip": float(c["sign_flip"].mean()), "n_sign_flip": int(c["sign_flip"].sum()),
           "median_se_ratio_wrob": float(c["se_ratio_wrob"].median()), "n_sig_wrob": int(c["sig_wrob"].sum()),
           "n_sig_lost_wrob": int(c["sig_lost_wrob"].sum()), "share_sig_lost_wrob": float(c["sig_lost_wrob"].sum() / max(c["sig_wrob"].sum(), 1))}
    by = []
    for st, g in c.groupby("study"):
        gp = g[g["pub"].notna()]
        by.append({"study": st, "n_coef": len(g), "n_pub": len(gp),
                   "naive_exact_close": int(gp["g_naive"].isin(["EXACT", "CLOSE"]).sum()),
                   "weighted_exact_close": int(gp["g_weighted"].isin(["EXACT", "CLOSE"]).sum()),
                   "median_se_ratio": float(g["se_ratio"].median()), "sig_lost": int(g["sig_lost"].sum()),
                   "sig_naive": int(g["sig_naive"].sum()), "sign_flips": int(g["sign_flip"].sum())})
    pd.DataFrame(by).to_csv(TAB / "census_by_study.csv", index=False)
    num["by_study"] = by
    (NUM / "summary.json").write_text(json.dumps(num, indent=1), encoding="utf-8")
    with pd.option_context("display.width", 220):
        print(pd.DataFrame(by).round(2).to_string())
    print({k: v for k, v in num.items() if k != "by_study"})


if __name__ == "__main__":
    main()
