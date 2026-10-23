"""Case-study register: one row per study with the rung each reached (L0 sample, L1 descriptive tables, L2 model, L3 design-aware).

L0/L1 come from the data audit (docs/paper_data_audit/results/summary*.csv, graded values EXACT/CLOSE/ACCEPTABLE/GAP);
L2/L3 from this paper's models (results/tables/census_coefficients.csv, ml tables). Output: results/tables/studies.csv and
results/numbers/ladder.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
AUDIT = HERE.parents[1] / "docs" / "paper_data_audit" / "results"
TAB, NUM = HERE / "results" / "tables", HERE / "results" / "numbers"

# id, short name, wave, model family, L0 verdict of the audit, L2 attempted?, reason if not
STUDIES = [
    ("P01", "Yang 2011", "2001", "logit", "SUFFICIENT", "yes", ""),
    ("P02", "Zhou 2014", "2009", "SEM", "PARTIAL", "yes", ""),
    ("P03", "Quinn 2016", "2009", "logit", "PARTIAL", "yes", ""),
    ("P05", "Deka 2019", "2017", "ZINB", "PARTIAL", "no", "neighbourhood variables come from a restricted file"),
    ("P06", "Jia 2019", "2017", "ML classifiers", "SUFFICIENT", "yes", ""),
    ("P07", "Krizek 2019", "2017", "descriptive", "PARTIAL", "no", "descriptive study without a model"),
    ("P09", "Fu 2020", "2017", "simulation", "INSUFFICIENT", "no", "population and simulation rules not stated"),
    ("P10", "Lidbe 2021", "2001/2017", "descriptive", "SUFFICIENT", "no", "descriptive tables only"),
    ("P11", "Alberini 2021", "2017", "OLS", "SUFFICIENT", "yes", ""),
    ("P12", "Xue 2021", "2017", "SEM", "INSUFFICIENT", "no", "analysis sample not recovered"),
    ("P13", "Zhang 2018a", "2017", "ZINB", "PARTIAL", "yes", ""),
    ("P14", "Zhang 2018b", "2017", "ZINB", "SUFFICIENT", "yes", ""),
    ("P15", "Zhang 2018c", "2017", "ZINB", "SUFFICIENT", "yes", ""),
    ("P16", "Sabouri 2020", "2017", "multilevel Poisson", "PARTIAL", "no", "built-environment variables are external"),
    ("P17", "Jia 2020", "2017", "ML classifiers", "SUFFICIENT", "yes", ""),
    ("P18", "Jiao 2020", "2017", "NB", "SUFFICIENT", "yes", ""),
    ("P19", "Sadeghvaziri 2020", "2009/2017", "descriptive", "PARTIAL", "no", "bar charts only"),
    ("P20", "Shirgaokar 2021", "2017", "NB", "PARTIAL", "yes", ""),
    ("P21", "Barua 2021", "2009/2017", "GBM", "PARTIAL", "yes", ""),
    ("P22", "Wu 2021", "2017", "PSM", "SUFFICIENT", "yes", ""),
    ("P23", "Su 2021", "2017", "motif clustering", "PARTIAL", "no", "origin-destination identifiers are not public"),
    ("P24", "Naseralavi 2025", "2017", "ML per state", "PARTIAL", "no", "reserved for a separate paper (state heterogeneity)"),
]
SCRIPT = {"P01": "p01_yang2011", "P02": "p02_zhou_wang2014", "P03": "p03_quinn2016", "P05": "p05_deka_fei2019", "P06": "p06_jia2019_afv",
          "P07": "p07_krizek_mcguckin2019", "P09": "p09_fu2020_evchain", "P10": "p10_lidbe2021", "P11": "p11_alberini2021",
          "P12": "p12_xue2021", "P13": "p13_zhang2018_bikeshare", "P14": "p14_zhang2018_vehicle_rideshare",
          "P15": "p15_zhang2018_rideshare_transit", "P16": "p16_sabouri2020", "P17": "p17_jia2020_ev", "P18": "p18_jiao2020",
          "P19": "p19_sadeghvaziri2020", "P20": "p20_shirgaokar2021", "P21": "p21_barua2021", "P22": "p22_wu2021",
          "P23": "p23_su2021", "P24": "p24_naseralavi2025"}


def main() -> None:
    summ = pd.read_csv(AUDIT / "summary.csv").set_index("script")
    rec = pd.read_csv(AUDIT / "summary_recheck.csv").set_index("script")
    rows = []
    for sid, name, wave, fam, l0, l2, why in STUDIES:
        s = summ.loc[SCRIPT[sid]]
        if sid == "P10":
            s = rec.loc["recheck_p10_lidbe2021"]
        ex, cl, ac, gp = (float(s[k]) for k in ("EXACT", "CLOSE", "ACCEPTABLE", "GAP"))
        graded = ex + cl + ac + gp
        rows.append({"id": sid, "study": name, "wave": wave, "family": fam, "L0_verdict": l0, "L1_graded": int(graded),
                     "L1_exact": int(ex), "L1_close": int(cl), "L1_acceptable": int(ac), "L1_gap": int(gp),
                     "L1_share_exact_close": (ex + cl) / graded if graded else float("nan"), "L2_attempted": l2, "L2_reason": why})
    df = pd.DataFrame(rows)
    cen = pd.read_csv(TAB / "census_coefficients.csv") if (TAB / "census_coefficients.csv").exists() else pd.DataFrame()
    ids = {"P01 Yang 2011": "P01", "P03 Quinn 2016": "P03", "P11 Alberini 2021": "P11", "P14 Zhang 2018": "P14", "P18 Jiao 2020": "P18",
           "P20 Shirgaokar 2021": "P20", "P13 Zhang 2018 (bike)": "P13", "P15 Zhang 2018 (ride)": "P15"}
    if len(cen):
        cen["id"] = cen["study"].map(ids)
        g = cen.groupby("id").agg(L3_coef=("term", "size"), L3_sig_naive=("sig_naive", "sum"), L3_sig_lost=("sig_lost", "sum"),
                                  L3_sign_flips=("sign_flip", "sum"), L3_median_se_ratio=("se_ratio", "median"))
        pub = cen[cen["pub"].notna()]
        g["L2_pub"] = pub.groupby("id").size()
        g["L2_naive_ok"] = pub[pub["g_naive"].isin(["EXACT", "CLOSE"])].groupby("id").size()
        g["L2_weighted_ok"] = pub[pub["g_weighted"].isin(["EXACT", "CLOSE"])].groupby("id").size()
        df = df.merge(g.reset_index(), on="id", how="left")
    # L2 grade: share of printed values reproduced (EXACT/CLOSE) by the better regime; models without a coefficient table are
    # judged from their printed headline (see the paper); P13 and P15 have no valid printed target
    override = {"P02": "bad", "P06": "bad", "P17": "bad", "P21": "bad", "P22": "bad", "P13": "none", "P15": "none"}

    def grade2(r):
        if r["L2_attempted"] != "yes":
            return "na"
        if r["id"] in override:
            return override[r["id"]]
        pubn = r.get("L2_pub", np.nan)
        top = np.nanmax([r.get("L2_weighted_ok", np.nan), r.get("L2_naive_ok", np.nan)])
        share = top / pubn if pubn == pubn and pubn > 0 and top == top else 0.0
        return "good" if share >= 0.7 else "mid" if share >= 0.25 else "bad"

    df["L2_grade"] = df.apply(grade2, axis=1)
    df.to_csv(TAB / "studies.csv", index=False)
    num = {"n_studies": len(df), "n_sufficient": int((df["L0_verdict"] == "SUFFICIENT").sum()),
           "n_partial": int((df["L0_verdict"] == "PARTIAL").sum()), "n_insufficient": int((df["L0_verdict"] == "INSUFFICIENT").sum()),
           "n_l2_attempted": int((df["L2_attempted"] == "yes").sum()), "n_l2_good": int((df["L2_grade"] == "good").sum()), "n_l2_mid": int((df["L2_grade"] == "mid").sum()), "n_l2_bad": int((df["L2_grade"] == "bad").sum()), "n_l2_none": int((df["L2_grade"] == "none").sum()), "n_l1_graded": int(df["L1_graded"].sum()),
           "n_l1_exact": int(df["L1_exact"].sum()), "n_l1_close": int(df["L1_close"].sum()),
           "n_l1_acceptable": int(df["L1_acceptable"].sum()), "n_l1_gap": int(df["L1_gap"].sum()),
           "share_l1_exact_close": float((df["L1_exact"].sum() + df["L1_close"].sum()) / df["L1_graded"].sum())}
    (NUM / "ladder.json").write_text(json.dumps(num, indent=1), encoding="utf-8")
    print(df[["id", "study", "L0_verdict", "L1_graded", "L1_share_exact_close", "L2_attempted"]].round(2).to_string(index=False))
    print(num)


if __name__ == "__main__":
    main()
