"""Every number of the manuscript, derived from results/tables (no typed numbers in the text).

Writes results/numbers/{cases,ml,p21,p22,p02,design}.json next to summary.json and ladder.json (made by summarize.py and
studies_table.py).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
TAB, NUM = HERE / "results" / "tables", HERE / "results" / "numbers"


def dump(name: str, obj: dict) -> None:
    (NUM / f"{name}.json").write_text(json.dumps(obj, indent=1, default=float), encoding="utf-8")


def cases() -> dict:
    c = pd.read_csv(TAB / "census_coefficients.csv")
    out: dict = {}

    def row(study, model, term, part=None):
        d = c[(c["study"] == study) & (c["term"] == term)]
        if model is not None:
            d = d[d["model"] == model]
        if part is not None:
            d = d[d["part"] == part]
        return d.iloc[0]

    r = row("P03 Quinn 2016", "bike_commute", "edu_GR")
    out["quinn_edu_gr"] = dict(pub=r["pub"], naive=r["naive"], weighted=r["weighted"], p_naive=r["p_naive"], p_design=r["p_design"])
    r = row("P03 Quinn 2016", "bike_commute", "age_25_44")
    out["quinn_age"] = dict(pub=r["pub"], naive=r["naive"], weighted=r["weighted"])
    q = c[(c["study"] == "P03 Quinn 2016") & c["pub"].notna()]
    out["quinn_n"] = int(len(q))
    out["quinn_weighted_ok"] = int(q["g_weighted"].isin(["EXACT", "CLOSE"]).sum())
    out["quinn_naive_ok"] = int(q["g_naive"].isin(["EXACT", "CLOSE"]).sum())
    out["quinn_weighted_share"] = out["quinn_weighted_ok"] / out["quinn_n"]
    out["quinn_naive_share"] = out["quinn_naive_ok"] / out["quinn_n"]
    out["quinn_commute_ok"] = int(q[q["model"].isin(["walk_commute", "bike_commute"])]["g_weighted"].isin(["EXACT", "CLOSE"]).sum())
    out["quinn_commute_n"] = int(len(q[q["model"].isin(["walk_commute", "bike_commute"])]))
    for mod in ("weekday", "weekend"):
        r = row("P18 Jiao 2020", mod, "RIDESHARE")
        out[f"jiao_ride_{mod}"] = dict(b=r["b_design"], se_naive=r["se_naive"], se_design=r["se_design"], p_naive=r["p_naive"],
                                       p_design=r["p_design"], pct=(np.exp(r["b_design"]) - 1) * 100)
    j = c[(c["study"] == "P18 Jiao 2020") & c["pub"].notna()]
    out["jiao_n"] = int(len(j))
    out["jiao_naive_exact"] = int((j["g_naive"] == "EXACT").sum())
    out["jiao_naive_ok"] = int(j["g_naive"].isin(["EXACT", "CLOSE"]).sum())
    out["jiao_weighted_ok"] = int(j["g_weighted"].isin(["EXACT", "CLOSE"]).sum())
    r = row("P14 Zhang 2018", None, "driver", "count")
    out["zhang_driver"] = dict(b_naive=r["b_naive"], b_design=r["b_design"], p_naive=r["p_naive"], p_design=r["p_design"], pub=r["pub"])
    z = c[(c["study"] == "P14 Zhang 2018") & c["pub"].notna()]
    out["zhang_n"] = int(len(z))
    out["zhang_naive_ok"] = int(z["g_naive"].isin(["EXACT", "CLOSE"]).sum())
    out["zhang_naive_acc"] = int(z["g_naive"].isin(["EXACT", "CLOSE", "ACCEPTABLE"]).sum())
    r = row("P01 Yang 2011", None, "reg_Midwest")
    out["yang_midwest"] = dict(pub=r["pub"], naive=r["naive"], weighted=r["weighted"])
    y = c[(c["study"] == "P01 Yang 2011") & c["pub"].notna()]
    out["yang_n"] = int(len(y))
    out["yang_weighted_ok"] = int(y["g_weighted"].isin(["EXACT", "CLOSE"]).sum())
    out["yang_naive_ok"] = int(y["g_naive"].isin(["EXACT", "CLOSE"]).sum())
    a = c[(c["study"] == "P11 Alberini 2021") & (c["term"] == "lppm")]
    out["alberini"] = {r_["model"]: dict(pub=r_["pub"], naive=r_["naive"], weighted=r_["weighted"], se_naive=r_["se_naive"],
                                         se_design=r_["se_design"]) for _, r_ in a.iterrows()}
    out["alberini_a_ann"] = out["alberini"]["A_ANNMILES"]
    out["alberini_matches_naive"] = int(a["g_naive"].isin(["EXACT", "CLOSE"]).sum())
    out["alberini_matches_weighted"] = int(a["g_weighted"].isin(["EXACT", "CLOSE"]).sum())
    out["alberini_n"] = int(len(a))
    for mod in ("weekday", "weekend"):
        r = row("P18 Jiao 2020", mod, "RIDESHARE")
        out[f"jiao_ride_{mod}"].update(dict(pct_naive=(np.exp(r["b_naive"]) - 1) * 100, p_wrob=r["p_wrob"], se_wrob=r["se_wrob"],
                                           pct_change=(r["b_design"] / r["b_naive"] - 1) * 100))
    r = row("P14 Zhang 2018", None, "driver", "count")
    out["zhang_driver"].update(dict(p_wrob=r["p_wrob"], pct_change=(r["b_design"] / r["b_naive"] - 1) * 100))
    st = pd.read_csv(TAB / "census_by_study.csv")
    out["r_formula_min"] = float(st["r_formula"].min())
    out["r_formula_max"] = float(st["r_formula"].max())
    out["h1_discriminating"] = int(((st["naive_exact_close"] - st["weighted_exact_close"]).abs() >= 3).sum())

    # who published weighted and who unweighted: where the regime that reproduces most printed values is
    by = pd.read_csv(TAB / "census_by_study.csv")
    out["n_studies_reproduced_by_naive"] = int((by["naive_exact_close"] > by["weighted_exact_close"]).sum())
    out["n_studies_reproduced_by_weighted"] = int((by["weighted_exact_close"] > by["naive_exact_close"]).sum())
    return out


def ml() -> dict:
    d = pd.read_csv(TAB / "p06_p17_models.csv")
    g = d.groupby(["label", "scheme", "model"])["auc"].mean()
    gw = d[d["scheme"] == "grouped_weighted"].groupby(["label", "model"])["auc_w"].mean()
    ga = d.groupby(["label", "scheme", "model"])["acc"].mean()
    out: dict = {"n": int(d["n"].iloc[0]), "afv_pos": int(d[d["label"] == "AFV"]["pos"].iloc[0]),
                 "ev_pos": int(d[d["label"] == "EV"]["pos"].iloc[0])}
    key = {"resample_then_split": "leaky", "split_then_resample": "rows", "grouped": "grouped", "grouped_weighted": "weighted"}
    for lab in ("AFV", "EV"):
        for sc, k in key.items():
            for m in ("LR", "NB", "DT", "RF", "SVM"):
                v = float(gw[(lab, m)]) if sc == "grouped_weighted" else float(g[(lab, sc, m)])
                out.setdefault(lab.lower(), {}).setdefault(k, {})[m.lower()] = v
                out.setdefault("acc", {}).setdefault(lab.lower(), {}).setdefault(k, {})[m.lower()] = float(ga[(lab, sc, m)])
        # the unweighted score of the no-oversampling pipeline, kept for the table of default settings
        out[lab.lower()]["unweighted_noover"] = {m.lower(): float(g[(lab, "grouped_weighted", m)]) for m in ("LR", "NB", "DT", "RF", "SVM")}
    for lab in ("afv", "ev"):
        L, G = out[lab]["leaky"], out[lab]["grouped"]
        out[lab]["infl_rf"] = L["rf"] - G["rf"]
        out[lab]["infl_dt"] = L["dt"] - G["dt"]
        out[lab]["infl_lr"] = L["lr"] - G["lr"]
        out[lab]["infl_nb"] = L["nb"] - G["nb"]
        out[lab]["infl_svm"] = L["svm"] - G["svm"]
        out[lab]["rows_vs_grouped_rf"] = out[lab]["rows"]["rf"] - G["rf"]
        out[lab]["dt_grouped"] = G["dt"]
        out[lab]["n_models_infl_gt_015"] = int(sum(L[m] - G[m] > 0.15 for m in ("lr", "nb", "dt", "rf", "svm")))
    out["pub"] = dict(rf=0.924, dt=0.908, acc=0.9)
    sd = d.groupby(["label", "scheme", "model"])["auc"].std()
    out["seed_sd"] = float(sd.max())
    tf = TAB / "p06_p17_tuned.csv"
    if tf.exists():
        t = pd.read_csv(tf)
        tg = t.groupby(["label", "scheme", "model"])["auc"].mean()
        tgw = t[t["scheme"] == "grouped_weighted"].groupby(["label", "model"])["auc_w"].mean()
        out["tuned"] = {}
        for lab in ("AFV", "EV"):
            for sc, k in key.items():
                for m in ("LR", "NB", "DT", "RF", "SVM"):
                    if (lab, sc, m) in tg.index:
                        v = float(tgw[(lab, m)]) if sc == "grouped_weighted" else float(tg[(lab, sc, m)])
                        out["tuned"].setdefault(lab.lower(), {}).setdefault(k, {})[m.lower()] = v
        out["tuned_infl_rf_afv"] = out["tuned"]["afv"]["leaky"]["rf"] - out["tuned"]["afv"]["grouped"]["rf"]
        out["tuned_infl_rf_ev"] = out["tuned"]["ev"]["leaky"]["rf"] - out["tuned"]["ev"]["grouped"]["rf"]
        out["seed_sd_tuned"] = float(t.groupby(["label", "scheme", "model"])["auc"].std().max())
        out["seed_sd_tuned_w"] = float(t[t["scheme"] == "grouped_weighted"].groupby(["label", "model"])["auc_w"].std().max())
    return out


def p21() -> dict:
    d = pd.read_csv(TAB / "p21_models.csv")
    g = d.groupby(["wave", "scheme", "model"])[["r2", "r2_w", "published_r2", "r2_train"]].mean()
    out: dict = {"n09": int(d[d["wave"] == 2009]["n"].iloc[0]), "n17": int(d[d["wave"] == 2017]["n"].iloc[0])}
    for w in (2009, 2017):
        for m in ("lr", "svm", "rf", "gbm"):
            out.setdefault(f"w{w}", {})[m] = dict(random=float(g.loc[(w, "random", m), "r2"]), state=float(g.loc[(w, "state_holdout", m), "r2"]),
                                                  pub=float(g.loc[(w, "random", m), "published_r2"]),
                                                  weighted=float(g.loc[(w, "random", m), "r2_w"]), train=float(g.loc[(w, "random", m), "r2_train"]))
    out["gbm17_gap"] = out["w2017"]["gbm"]["pub"] - out["w2017"]["gbm"]["random"]
    out["state_drop17"] = out["w2017"]["gbm"]["random"] - out["w2017"]["gbm"]["state"]
    return out


def p22() -> dict:
    f = TAB / "p22_models.csv"
    if not f.exists():
        return {}
    d = pd.read_csv(f)
    out: dict = {}
    a = d[(d["scope"] == "access") & d["group"].notna()].set_index("group")
    out["triples"] = int(a["n_matched"].iloc[0])
    out["triples_none"] = int(d[(d["scope"] == "none") & d["group"].notna()]["n_matched"].iloc[0])
    for g in ("frequent", "occasional", "non"):
        out[f"vmt_{g}"] = float(a.loc[g, "vmt_unweighted"])
        out[f"pub_{g}"] = float(a.loc[g, "published_vmt"])
    c = d[(d["scope"] == "access") & d["contrast"].notna() & (d["outcome"] == "veh")].set_index("contrast")
    for k, lab in (("non->occasional", "no"), ("occasional->frequent", "of"), ("non->frequent", "nf")):
        out[f"veh_{lab}"] = dict(naive=float(c.loc[k, "diff_unweighted"]), se_paired=float(c.loc[k, "se_paired"]),
                                 weighted=float(c.loc[k, "diff_weighted"]), se_design=float(c.loc[k, "se_design"]),
                                 pub=float(c.loc[k, "published_veh_diff"]))
        out[f"veh_{lab}"]["t_paired"] = abs(out[f"veh_{lab}"]["naive"]) / out[f"veh_{lab}"]["se_paired"]
        out[f"veh_{lab}"]["t_design"] = abs(out[f"veh_{lab}"]["weighted"]) / out[f"veh_{lab}"]["se_design"]
    v = d[(d["scope"] == "access") & d["contrast"].notna() & (d["outcome"] == "vmt")]
    out["n_vmt_contrasts_sig_paired"] = int((v["diff_unweighted"].abs() / v["se_paired"] > 1.96).sum())
    out["n_vmt_contrasts_sig_design"] = int((v["diff_weighted"].abs() / v["se_design"] > 1.96).sum())
    return out


def p02() -> dict:
    d = pd.read_csv(TAB / "p02_models.csv")
    r = d.set_index(["lval", "rval"])
    out = {"n": int(d["n"].iloc[0])}
    for k, key in (("prop_purchase", "prop_shoptrp"), ("prop_shoptrp", "prop_purchase")):
        x = r.loc[(k, key)]
        out[f"{k}_est"] = dict(naive=float(x["est_naive"]), weighted=float(x["est_weighted"]), pub=float(x["published"]), se=float(x["se_design"]))
    return out


def holdout() -> dict:
    import os
    import sys

    root = HERE.parents[1]
    sys.path.insert(0, str(root / "src"))
    sys.path.insert(0, str(HERE / "src"))
    sys.path.insert(0, str(HERE / "src" / "studies"))
    os.environ.setdefault("PYNHTS_CACHE_DIR", str(root / "local_data" / "cache"))
    import p06_p17_jia as J
    import pynhts
    from pynhts.validate import group_split

    k = J.build(pynhts.load(2017))
    out: dict = {"n": int(len(k)), "households": int(k["HOUSEID"].nunique())}
    out["share_rows_shared_household"] = float((k.groupby("HOUSEID")["HOUSEID"].transform("size") > 1).mean())
    for lab in ("AFV", "EV"):
        y = k[lab].to_numpy()
        rows = []
        for s in (0, 1, 2):
            tr, te = group_split(k["HOUSEID"].to_numpy(), test_size=0.3, seed=s)
            rows.append((len(tr), len(te), y[tr].mean(), y[te].mean(), int(y[te].sum())))
        r = np.array(rows)
        out[lab.lower()] = dict(share_all=float(y.mean()), n_train=float(r[:, 0].mean()), n_test=float(r[:, 1].mean()),
                                share_train=float(r[:, 2].mean()), share_test=float(r[:, 3].mean()), pos_test=float(r[:, 4].mean()),
                                share_test_min=float(r[:, 3].min()), share_test_max=float(r[:, 3].max()))
    return out


def newton() -> dict:
    f = TAB / "newton_check.csv"
    if not f.exists():
        return {}
    d = pd.read_csv(f)
    return {"max_rel_se_diff": float(d["rel_diff"].abs().max()), "median_rel_se_diff": float(d["rel_diff"].abs().median()), "n_terms": int(len(d))}


def design() -> dict:
    return {"jk_2017": 98, "jk_2009": 100, "jk_2001": 99, "trials": 10, "newton_steps": 3, "seeds": 2, "golden_se_pct": 0.2, "printed_sem_n": 85663}


def main() -> None:
    NUM.mkdir(parents=True, exist_ok=True)
    for name, fn in (("cases", cases), ("ml", ml), ("p21", p21), ("p22", p22), ("p02", p02), ("holdout", holdout), ("newton", newton), ("design", design)):
        dump(name, fn())
        print("wrote", name)


if __name__ == "__main__":
    main()
