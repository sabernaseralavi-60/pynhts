"""Collect every study's model table into the paper's numbers: ladder grades, variance decomposition, verdict shifts.

Reads results/tables/p*_models.csv (written by src/studies/*.py), writes
results/tables/ladder_L2.csv            one row per printed coefficient: published value, our regimes, grades
results/tables/census_coefficients.csv  every re-estimated coefficient with the standard-error chain and verdict changes
results/tables/census_by_study.csv      per-study summary
results/numbers/summary.json            the headline numbers used in the manuscript

Standard-error chain (all ratios of standard errors of the same coefficient):
  r_weights  = weighted sandwich (each observation a cluster) / unweighted model-based   (what the unequal weights cost)
  r_cluster  = weighted household-clustered / weighted sandwich (each observation a cluster)   (what clustering adds)
  r_formula  = replicate-weight (design) / weighted household-clustered   (what the replicate formula adds)
  r_unw_cl   = unweighted household-clustered / unweighted model-based    (understatement of an unweighted analysis)
  r_total    = design / unweighted model-based
Paper-style inference (the analysis plan's H3): the regime a study declared (STYLE below); P03 declared the jackknife itself,
so it is excluded from the H3 count.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
TAB = HERE / "results" / "tables"
NUM = HERE / "results" / "numbers"
NUM.mkdir(parents=True, exist_ok=True)
EXCLUDE_TERMS = {"const", "log_alpha"}
# printed decimals of the coefficient or odds ratio of each study (the published values lose trailing zeros as floats)
DEC = {"P01 Yang 2011": 2, "P03 Quinn 2016": 2, "P11 Alberini 2021": 4, "P14 Zhang 2018": 3, "P18 Jiao 2020": 3,
       "P20 Shirgaokar 2021": 2}
# declared inference of each study: "naive" (unweighted, model-based), "wrob" (weighted, clustered), "design" (replicate weights)
STYLE = {"P01 Yang 2011": "wrob", "P03 Quinn 2016": "design", "P11 Alberini 2021": "naive", "P13 Zhang 2018 (bike)": "naive",
         "P14 Zhang 2018": "naive", "P15 Zhang 2018 (ride)": "naive", "P18 Jiao 2020": "naive", "P20 Shirgaokar 2021": "naive"}


def grade(pub: float, ours: float, dec: int) -> str:
    if pub is None or ours is None or not np.isfinite(ours) or not np.isfinite(pub):
        return "NA"
    u = 10.0 ** (-dec)
    diff = abs(ours - pub)
    if round(float(ours), dec) == round(float(pub), dec):
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


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    from scipy.stats import beta

    lo = 0.0 if k == 0 else float(beta.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - alpha / 2, k + 1, n - k))
    return lo, hi


def main():
    parts = [load("p01_models.csv", "P01 Yang 2011", "or"), load("p03_models.csv", "P03 Quinn 2016", "or")]
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
        rows.append({"study": r["study"], "model": r.get("model", r.get("group", r.get("paper", ""))), "part": r.get("part", ""),
                     "term": r["term"], "pub": r["pub"], "naive": get("naive"), "weighted": get("weighted"),
                     "b_naive": r["b_naive"], "b_weighted": r.get("b_weighted"), "b_design": r["b_design"],
                     "se_naive": r["se_naive"], "se_naive_cl": r.get("se_naive_cluster"), "se_wmodel": r.get("se_weighted_model"), "se_whc": r.get("se_weighted_hc"),
                     "se_wrob": r.get("se_weighted_robust"), "se_design": r["se_design"],
                     "p_naive": r["p_naive"], "p_wrob": r.get("p_weighted"), "p_design": r["p_design"]})
    c = pd.DataFrame(rows)
    c["r_weights"] = c["se_whc"] / c["se_naive"]
    c["r_cluster"] = c["se_wrob"] / c["se_whc"]
    c["r_formula"] = c["se_design"] / c["se_wrob"]
    c["r_unw_cl"] = c["se_naive_cl"] / c["se_naive"]
    c["se_ratio"] = c["se_design"] / c["se_naive"]
    c["se_ratio_wrob"] = c["r_formula"]
    c["sign_flip"] = np.sign(c["b_naive"]) != np.sign(c["b_design"])
    c["sig_naive"] = c["p_naive"] < 0.05
    c["sig_wrob"] = c["p_wrob"] < 0.05
    c["sig_design"] = c["p_design"] < 0.05
    c["sig_lost"] = c["sig_naive"] & ~c["sig_design"]
    c["sig_gained"] = ~c["sig_naive"] & c["sig_design"]
    c["sig_lost_wrob"] = c["sig_wrob"] & ~c["sig_design"]
    c["style"] = c["study"].map(STYLE)
    c["sig_style"] = np.where(c["style"] == "naive", c["sig_naive"], np.where(c["style"] == "wrob", c["sig_wrob"], c["sig_design"]))
    c["sig_lost_style"] = c["sig_style"] & ~c["sig_design"]
    dec = c["study"].map(DEC)
    c["g_naive"] = [grade(p, x, int(d)) if pd.notna(p) and pd.notna(d) else "" for p, x, d in zip(c["pub"], c["naive"], dec)]
    c["g_weighted"] = [grade(p, x, int(d)) if pd.notna(p) and pd.notna(d) else "" for p, x, d in zip(c["pub"], c["weighted"], dec)]
    c.to_csv(TAB / "census_coefficients.csv", index=False)
    c[c["pub"].notna()].to_csv(TAB / "ladder_L2.csv", index=False)

    h3 = c[c["style"] != "design"]
    n_sig_style, n_lost_style = int(h3["sig_style"].sum()), int(h3["sig_lost_style"].sum())
    lo, hi = clopper_pearson(n_lost_style, n_sig_style)
    flips = c[c["sign_flip"]]
    num = {
        "n_coef": int(len(c)), "n_coef_published": int(c["pub"].notna().sum()),
        "median_se_ratio": float(c["se_ratio"].median()), "q25_se_ratio": float(c["se_ratio"].quantile(0.25)),
        "q75_se_ratio": float(c["se_ratio"].quantile(0.75)),
        "share_se_ratio_gt_1_5": float((c["se_ratio"] > 1.5).mean()),
        "median_r_weights": float(c["r_weights"].median()), "median_r_cluster": float(c["r_cluster"].median()),
        "median_r_formula": float(c["r_formula"].median()), "median_r_unw_cl": float(c["r_unw_cl"].median()),
        "q25_r_unw_cl": float(c["r_unw_cl"].quantile(0.25)), "q75_r_unw_cl": float(c["r_unw_cl"].quantile(0.75)),
        "q05_r_formula": float(c["r_formula"].quantile(0.05)), "q95_r_formula": float(c["r_formula"].quantile(0.95)),
        "n_sig_naive": int(c["sig_naive"].sum()), "n_sig_lost": int(c["sig_lost"].sum()),
        "share_sig_lost": float(c["sig_lost"].sum() / max(c["sig_naive"].sum(), 1)),
        "n_sig_gained": int(c["sig_gained"].sum()),
        "n_sign_flip": int(c["sign_flip"].sum()), "share_sign_flip": float(c["sign_flip"].mean()),
        "n_flip_sig_naive": int(flips["sig_naive"].sum()), "n_flip_sig_both": int((flips["sig_naive"] & flips["sig_design"]).sum()),
        "n_sig_wrob": int(c["sig_wrob"].sum()), "n_sig_lost_wrob": int(c["sig_lost_wrob"].sum()),
        "share_sig_lost_wrob": float(c["sig_lost_wrob"].sum() / max(c["sig_wrob"].sum(), 1)),
        "median_se_ratio_wrob": float(c["r_formula"].median()),
        "h3_n_coef": int(len(h3)), "h3_n_sig": n_sig_style, "h3_n_lost": n_lost_style,
        "h3_share": n_lost_style / max(n_sig_style, 1), "h3_ci_lo": lo, "h3_ci_hi": hi,
        "h3_studies": int(h3["study"].nunique()),
    }
    by = []
    for st, g in c.groupby("study"):
        gp = g[g["pub"].notna()]
        gs = g[g["style"] != "design"]
        by.append({"study": st, "n_coef": len(g), "n_pub": len(gp),
                   "naive_exact_close": int(gp["g_naive"].isin(["EXACT", "CLOSE"]).sum()),
                   "weighted_exact_close": int(gp["g_weighted"].isin(["EXACT", "CLOSE"]).sum()),
                   "median_se_ratio": float(g["se_ratio"].median()), "r_weights": float(g["r_weights"].median()),
                   "r_cluster": float(g["r_cluster"].median()), "r_formula": float(g["r_formula"].median()),
                   "r_unw_cl": float(g["r_unw_cl"].median()),
                   "sig_lost": int(g["sig_lost"].sum()), "sig_naive": int(g["sig_naive"].sum()),
                   "sig_style": int(gs["sig_style"].sum()), "lost_style": int(gs["sig_lost_style"].sum()),
                   "sign_flips": int(g["sign_flip"].sum())})
    pd.DataFrame(by).to_csv(TAB / "census_by_study.csv", index=False)
    num["by_study"] = by
    (NUM / "summary.json").write_text(json.dumps(num, indent=1), encoding="utf-8")
    with pd.option_context("display.width", 240):
        print(pd.DataFrame(by).round(2).to_string())
    print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in num.items() if k != "by_study"})


if __name__ == "__main__":
    main()
