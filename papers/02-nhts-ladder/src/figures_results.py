"""Result figures 3-7 of paper 02 (called from make_figures.py)."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parent))
import figkit as fk  # noqa: E402

TAB, FIG = HERE / "results" / "tables", HERE / "results" / "figures"
OI = fk.OI


def _ci(b, se):
    return b - 1.96 * se, b + 1.96 * se


def fig_weights() -> None:
    """Quinn et al. (2016), cycling commuters: published odds ratios against the regimes (reference letter H = education)."""
    c = pd.read_csv(TAB / "census_coefficients.csv")
    d = c[(c["study"] == "P03 Quinn 2016") & (c["model"] == "bike_commute") & c["pub"].notna()].reset_index(drop=True)
    labels = {"edu_HS": "Education: high school", "edu_SC": "Education: some college", "edu_BA": "Education: bachelor",
              "edu_GR": "Education: graduate", "age_25_44": "Age 25-44", "age_45_64": "Age 45-64", "age_65": "Age 65+",
              "male": "Male", "race_Black": "Black", "race_Hisp": "Hispanic", "race_Other": "Other race",
              "inc_25_49": "Income 25-49k", "inc_50_74": "Income 50-74k", "inc_75": "Income 75k+", "urban": "Urban"}
    fk.style(8.5)
    fig, ax = plt.subplots(figsize=(6.8, 5.6))
    n = len(d)
    for i, r in d.iterrows():
        y = n - 1 - i
        lo, hi = _ci(r["b_naive"], r["se_naive"])
        ax.plot([np.exp(lo), np.exp(hi)], [y + 0.18, y + 0.18], color=OI["grey"], lw=2.4, solid_capstyle="round", zorder=2)
        ax.plot(np.exp(r["b_naive"]), y + 0.18, "o", color=OI["grey"], ms=5, zorder=3)
        lo, hi = _ci(r["b_design"], r["se_design"])
        ax.plot([np.exp(lo), np.exp(hi)], [y - 0.18, y - 0.18], color=OI["blue"], lw=2.4, solid_capstyle="round", zorder=2)
        ax.plot(np.exp(r["b_design"]), y - 0.18, "o", color=OI["blue"], ms=5, zorder=3)
        ax.plot(r["pub"], y, "D", mfc="white", mec=OI["orange"], mew=1.5, ms=6, zorder=4)
    edu_rows = [n - 1 - i for i, r in d.iterrows() if str(r["term"]).startswith("edu_")]
    fk.band(ax, min(edu_rows) - 0.5, max(edu_rows) + 0.5, axis="y")
    ax.axvline(1, color="#555555", lw=0.8)
    ax.set_xscale("log")
    ax.set_yticks(range(n))
    ax.set_yticklabels([labels.get(t, t) for t in d["term"]][::-1])
    ax.set_xlabel("Odds ratio of cycling to work (log scale)")
    ax.set_xlim(0.08, 10)
    ax.set_ylim(-0.6, n - 0.4)
    fk.badge(ax, 0.94, (min(edu_rows) + max(edu_rows)) / 2 / n + 0.03, "H", coords="axes", size=8)
    ax.plot([], [], "D", mfc="white", mec=OI["orange"], mew=1.5, label="published (weighted)")
    ax.plot([], [], "o-", color=OI["grey"], label="our fit, unweighted (95 % interval)")
    ax.plot([], [], "o-", color=OI["blue"], label="our fit, weighted, replicate variance (95 % interval)")
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), fontsize=7.5, ncol=1)
    fk.save(fig, FIG, "fig_weights")


def fig_se() -> None:
    """Where the standard-error difference comes from (panel A) and which verdicts change under each study's declared inference (B)."""
    c = pd.read_csv(TAB / "census_coefficients.csv")
    by = pd.read_csv(TAB / "census_by_study.csv")
    fk.style(8.5)
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.6, 3.5), gridspec_kw=dict(width_ratios=[1.05, 1.15]))
    cols = [("r_weights", "Weighting"), ("r_cluster", "Clustering\n(given\nweights)"), ("r_formula", "Replicate\nformula (given\nclustering)"),
            ("r_unw_cl", "Clustering,\nunweighted\nfit")]
    rng = np.random.default_rng(1)
    for i, (k, lab) in enumerate(cols):
        v = c[k].dropna().to_numpy()
        a.scatter(i + rng.uniform(-0.18, 0.18, len(v)), v, s=7, color=OI["sky"], alpha=0.55, linewidths=0, zorder=2)
        a.plot([i - 0.28, i + 0.28], [np.median(v)] * 2, color=OI["orange"], lw=2.2, zorder=3)
        a.text(i + 0.31, np.median(v), f"{np.median(v):.2f}", va="center", fontsize=7.5, color=OI["orange"])
    a.axhline(1, color="#555555", lw=0.9)
    a.set_yscale("log")
    a.set_yticks([0.5, 1, 2, 3, 5])
    a.set_yticklabels(["0.5", "1", "2", "3", "5"])
    a.yaxis.set_minor_formatter(plt.NullFormatter())
    a.set_xticks(range(len(cols)))
    a.set_xticklabels([lab for _, lab in cols], fontsize=6.8)
    a.set_ylabel("Ratio of standard errors")
    a.set_xlim(-0.5, len(cols) - 0.2)
    fk.letter(a, "A")
    by = by[by["sig_style"] > 0].copy()
    by["share"] = by["lost_style"] / by["sig_style"]
    by = by.sort_values("share").reset_index(drop=True)
    b.barh(range(len(by)), by["share"] * 100, color=OI["orange"], height=0.62)
    for yy, row in by.iterrows():
        txt = f"{int(row['lost_style'])} of {int(row['sig_style'])}" + (f"; {int(row['sign_flips'])} sign flip" + ("s" if row["sign_flips"] > 1 else "") if row["sign_flips"] else "")
        b.text(row["share"] * 100 + 1, yy, txt, va="center", fontsize=7)
    b.set_yticks(range(len(by)))
    b.set_yticklabels(by["study"], fontsize=7.5)
    b.set_xlabel("Significant coefficients (declared inference)\nthat lose significance under the design (%)")
    b.set_xlim(0, 80)
    fk.letter(b, "B")
    fig.tight_layout()
    fk.save(fig, FIG, "fig_se")


def fig_case() -> None:
    """Jiao et al. (2020): shared-mobility terms of the weekday and weekend trip models (reference letter R = ridesharing)."""
    c = pd.read_csv(TAB / "census_coefficients.csv")
    d = c[(c["study"] == "P18 Jiao 2020") & c["term"].isin(["RIDESHARE", "BIKESHARE", "CARSHARE"])]
    fk.style(8.5)
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.9), sharey=True)
    order = ["RIDESHARE", "BIKESHARE", "CARSHARE"]
    for ax, mod, let in zip(axes, ("weekday", "weekend"), "AB"):
        sub = d[d["model"] == mod].set_index("term").loc[order]
        for i, (_, r) in enumerate(sub.iterrows()):
            y = len(order) - 1 - i
            for off, bk, sk, col in ((0.16, "b_naive", "se_naive", OI["grey"]), (-0.16, "b_design", "se_design", OI["blue"])):
                lo, hi = _ci(r[bk], r[sk])
                ax.plot([lo * 100, hi * 100], [y + off, y + off], color=col, lw=2.6, solid_capstyle="round")
                ax.plot(r[bk] * 100, y + off, "o", color=col, ms=5)
        ax.axvline(0, color="#555555", lw=0.8)
        ax.set_yticks(range(3))
        ax.set_yticklabels(["Carsharing", "Bikesharing", "Ridesharing"])
        ax.set_xlabel("Change in daily trips per extra use in 30 days (%)")
        ax.set_title(mod.capitalize() + " model", fontsize=8.5)
        fk.letter(ax, let)
        if mod == "weekday":
            fk.band(ax, 1.5, 2.5, axis="y")
            fk.badge(ax, 0.93, 0.85, "R", coords="axes", size=8)
    axes[0].plot([], [], "o-", color=OI["grey"], label="unweighted, model-based variance")
    axes[0].plot([], [], "o-", color=OI["blue"], label="weighted, replicate-weight variance")
    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=2, fontsize=7.5, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fk.save(fig, FIG, "fig_case")


def fig_leak() -> None:
    d = pd.read_csv(TAB / "p06_p17_models.csv")
    tuned = pd.read_csv(TAB / "p06_p17_tuned.csv") if (TAB / "p06_p17_tuned.csv").exists() else None
    fk.style(8.5)
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.6), sharey=True)
    order = ["resample_then_split", "split_then_resample", "grouped", "grouped_weighted"]
    names = {"resample_then_split": "oversample,\nthen split rows", "split_then_resample": "split rows,\nthen oversample",
             "grouped": "split households,\nthen oversample", "grouped_weighted": "split households,\nno oversampling"}
    cols = {"LR": OI["grey"], "NB": OI["sky"], "DT": OI["yellow"], "RF": OI["blue"], "SVM": OI["pink"]}
    for ax, lab, let in zip(axes, ("AFV", "EV"), "AB"):
        sub = d[d["label"] == lab]
        for m, col in cols.items():
            ys = [sub[(sub["scheme"] == s) & (sub["model"] == m)]["auc"].mean() for s in order]
            ax.plot(range(4), ys, "o-", color=col, label=m, ms=5, lw=1.4)
            if tuned is not None:
                tb = tuned[(tuned["label"] == lab) & (tuned["model"] == m)]
                ax.plot(range(4), [tb[tb["scheme"] == s]["auc"].mean() for s in order], "^--", color=col, ms=4.5, lw=0.9, mfc="white")
        ax.axhline(0.5, color="#555555", lw=0.7, ls=":")
        ax.set_xticks(range(4))
        ax.set_xticklabels([names[s] for s in order], fontsize=6.6)
        ax.set_title({"AFV": "Alternative-fuel vehicles", "EV": "Electric vehicles"}[lab], fontsize=8.5)
        fk.letter(ax, let)
        if lab == "AFV":
            fk.band(ax, 0.90, 0.93, axis="y")
            fk.badge(ax, 0.93, 0.80, "L", coords="axes", size=8)
    axes[0].set_ylabel("Area under the ROC curve (held-out rows)")
    axes[1].legend(loc="center right", fontsize=7, bbox_to_anchor=(1.0, 0.42))
    fig.tight_layout()
    fk.save(fig, FIG, "fig_leak")


def fig_r2() -> None:
    d = pd.read_csv(TAB / "p21_models.csv")
    g = d.groupby(["wave", "scheme", "model"])[["r2", "published_r2"]].mean().reset_index()
    fk.style(8.5)
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 3.2), sharey=True)
    for ax, w, let in zip(axes, (2009, 2017), "AB"):
        sub = g[g["wave"] == w]
        for i, m in enumerate(["lr", "svm", "rf", "gbm"]):
            pub = sub[sub["model"] == m]["published_r2"].iloc[0]
            ax.plot(i, pub, "D", mfc="white", mec=OI["orange"], mew=1.5, ms=7)
            for sc, col, dx in (("random", OI["blue"], -0.08), ("state_holdout", OI["green"], 0.08)):
                ax.plot(i + dx, sub[(sub["model"] == m) & (sub["scheme"] == sc)]["r2"].iloc[0], "o", color=col, ms=6)
        ax.set_xticks(range(4))
        ax.set_xticklabels(["linear", "SVM", "forest", "boosting"])
        ax.set_title(str(w), fontsize=8.5)
        fk.letter(ax, let)
    axes[0].set_ylabel("Held-out R-squared")
    axes[0].plot([], [], "D", mfc="white", mec=OI["orange"], mew=1.5, label="published")
    axes[0].plot([], [], "o", color=OI["blue"], label="ours, random households")
    axes[0].plot([], [], "o", color=OI["green"], label="ours, whole states held out")
    axes[0].legend(loc="center left", fontsize=7)
    fig.tight_layout()
    fk.save(fig, FIG, "fig_r2")


def fig_holdout() -> None:
    """Supplement: frequency histogram of the rare class in all / training / held-out rows of the household splits."""
    import os

    root = HERE.parents[1]
    sys.path.insert(0, str(root / "src"))
    sys.path.insert(0, str(HERE / "src" / "studies"))
    os.environ.setdefault("PYNHTS_CACHE_DIR", str(root / "local_data" / "cache"))
    import p06_p17_jia as J
    import pynhts
    from pynhts.validate import group_split

    k = J.build(pynhts.load(2017))
    fk.style(8.5)
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 2.9), sharey=False)
    for ax, lab, let, title in zip(axes, ("AFV", "EV"), "AB", ("Alternative-fuel vehicles", "Electric vehicles")):
        y = k[lab].to_numpy()
        xs, vals, cols = [], [], []
        xs.append(0); vals.append(y.mean() * 100); cols.append(OI["grey"])
        for s in (0, 1, 2):
            tr, te = group_split(k["HOUSEID"].to_numpy(), test_size=0.3, seed=s)
            xs += [1 + 2 * s, 2 + 2 * s]
            vals += [y[tr].mean() * 100, y[te].mean() * 100]
            cols += [OI["blue"], OI["orange"]]
        ax.bar(xs, vals, color=cols, width=0.8)
        ax.set_xticks([0, 1.5, 3.5, 5.5])
        ax.set_xticklabels(["all", "split 1", "split 2", "split 3"])
        ax.set_ylabel("Share of rows in the rare class (%)")
        ax.set_title(title, fontsize=8.5)
        fk.letter(ax, let)
    axes[0].bar([], [], color=OI["blue"], label="training households")
    axes[0].bar([], [], color=OI["orange"], label="held-out households")
    axes[0].legend(fontsize=7, loc="upper right")
    fig.tight_layout()
    fk.save(fig, FIG, "fig_holdout")
