"""Figures of the SoftwareX paper, generated from the repository's own audit results (no hand-drawn numbers).

Fig. 1 architecture (drawn), Fig. 2 outcome of the 22-paper audit per paper (first-audit results, never edited after the fact),
Fig. 3 published against pynhts values for the Lidbe et al. tables (recheck_p10 results).
Run: python paper/softwarex/make_figures.py   (needs pandas and matplotlib)
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "docs" / "paper_data_audit" / "results"
OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(exist_ok=True)
COL = {"EXACT": "#1b6ca8", "CLOSE": "#7fb7de", "ACCEPTABLE": "#e8a33d", "GAP": "#c0392b"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
NL = chr(10)


def n_graded() -> int:
    """Graded printed values of the audit (first-audit files p??_*.csv), the same count as in content.py."""
    import csv
    return sum(r["status"] in COL for f in sorted(RES.glob("p[0-9][0-9]_*.csv")) for r in csv.DictReader(f.open(encoding="utf8")))


def box(ax, x, y, w, h, title, body="", fc="#eef3f8", ec="#1b6ca8", fs=7.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06", fc=fc, ec=ec, lw=1.2))
    n = len(body.split("|")) if body else 0
    top = y + h / 2 + 0.17 * n
    ax.text(x + w / 2, top, title, ha="center", va="center", fontsize=fs + 1, fontweight="bold")
    if body:
        ax.text(x + w / 2, top - 0.2 - 0.17 * n, body.replace("|", NL), ha="center", va="center", fontsize=fs, linespacing=1.25)


def arrow(ax, x0, y0, x1, y1):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="-|>", color="#444", lw=1.1))


def fig1() -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis("off")
    grey = dict(fc="#f4f4f4", ec="#777")
    box(ax, 0.2, 6.9, 11.6, 0.9, "Official NHTS public-use files: 2001, 2009, 2017, 2022 (FHWA, ORNL)",
        "SHA-256 of every archive and member is pinned in a registry", **grey)
    box(ax, 0.2, 5.4, 3.6, 1.2, "pynhts.io", "fetch, verify (SHA-256),|convert to typed Parquet")
    box(ax, 4.2, 5.4, 3.6, 1.2, "pynhts.core", "schema from the codebook,|lazy loader, validated joins")
    box(ax, 8.2, 5.4, 3.6, 1.2, "pynhts.stats", "jackknife (2001, 2009, 2017)|Taylor series (2022)")
    for x in (2.0, 6.0, 10.0):
        arrow(ax, x, 6.9, x, 6.6)
    amber = dict(fc="#fdf3e1", ec="#e8a33d")
    box(ax, 0.2, 3.8, 5.7, 1.3, "pynhts.concepts + pynhts.harmonize",
        "44 concepts, 19 crosswalks between waves;|guards for top-codes and national-only columns", **amber)
    box(ax, 6.3, 3.8, 5.5, 1.3, "analysis layer", "aggregate, features, study, trends,|tables, viz, leakage-safe splits", **amber)
    for x, xt in ((2.0, 2.6), (6.0, 6.0), (10.0, 9.2)):
        arrow(ax, x, 5.4, xt, 5.1)
    green = dict(fc="#e8f4ea", ec="#3a8a4f")
    box(ax, 0.2, 2.1, 3.6, 1.2, "pynhts.recipes", "5 sources, 175 figures,|expected status for each", **green)
    box(ax, 4.2, 2.1, 3.6, 1.2, "tools/paper_audit", f"22 published papers rebuilt,|{n_graded():,} printed values graded", **green)
    box(ax, 8.2, 2.1, 3.6, 1.2, "pynhts.ml and CLI", "arrays, tensors, graphs;|fetch | register | docs".replace(" | ", " / "), **green)
    for x in (2.0, 6.0, 10.0):
        arrow(ax, x, 3.8, x, 3.3)
    box(ax, 0.2, 0.2, 11.6, 1.3, "Every result says what it is",
        "attrs['pynhts'] holds wave, table, weight, variance design and unit;|PynhtsWarning names annual totals, top-coded values and|2001 national-sample-only columns; docs/guards.md lists each trap", **grey)
    arrow(ax, 6.0, 2.1, 6.0, 1.5)
    fig.savefig(OUT / "fig1_architecture.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT / "fig1_architecture.pdf", bbox_inches="tight")
    plt.close(fig)


def fig2() -> None:
    d = pd.read_csv(RES / "recheck_p10_lidbe2021.csv")
    d = d[d["status"].isin(COL) & ~d["item"].str.contains("race reading v2|TDWKND flag")]
    d = d[(d["published"] > 0) & (d["pynhts"] > 0)]
    fig, ax = plt.subplots(figsize=(5.2, 4.6))
    lo, hi = 0.02, 5e4
    ax.plot([lo, hi], [lo, hi], color="#999", lw=0.8, zorder=0)
    for st in ("GAP", "ACCEPTABLE", "CLOSE", "EXACT"):
        s = d[d["status"] == st]
        ax.scatter(s["published"], s["pynhts"], s=14, color=COL[st], alpha=0.85, label=f"{st} ({len(s)})", linewidths=0)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel("Value printed in the paper (log scale; % or million trips)")
    ax.set_ylabel("Value computed with pynhts")
    ax.legend(frameon=False, loc="upper left", title=f"{len(d)} cells of Tables 3 and 4")
    fig.savefig(OUT / "fig3_agreement_lidbe.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT / "fig3_agreement_lidbe.pdf", bbox_inches="tight")
    plt.close(fig)


def fig3() -> None:
    rows = []
    for f in sorted(RES.glob("p[0-9][0-9]_*.csv")):
        t = pd.read_csv(f)
        t = t[t["status"].isin(COL)]
        n = len(t)
        rows.append({"paper": f.stem[:3].upper(), **{s: (t["status"] == s).sum() / n * 100 for s in COL}, "n": n})
    d = pd.DataFrame(rows).sort_values(["EXACT", "CLOSE"], ascending=True)
    fig, ax = plt.subplots(figsize=(5.2, 5.4))
    left = np.zeros(len(d))
    for st in COL:
        ax.barh(d["paper"] + "  (n=" + d["n"].astype(str) + ")", d[st], left=left, color=COL[st], label=st, height=0.75)
        left += d[st].values
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of the paper's printed numbers (%)")
    ax.legend(frameon=False, ncol=4, loc="lower center", bbox_to_anchor=(0.45, 1.0), handlelength=1, columnspacing=1)
    fig.savefig(OUT / "fig2_audit_overview.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT / "fig2_audit_overview.pdf", bbox_inches="tight")
    plt.close(fig)
    print(d[["paper", "n", "EXACT", "CLOSE", "ACCEPTABLE", "GAP"]].round(1).to_string(index=False))


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
