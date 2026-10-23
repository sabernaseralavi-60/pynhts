"""All figures of paper 02, English and Persian twins where text is in the image (flowchart, ladder).

python src/make_figures.py [fig_flow fig_ladder fig_weights fig_se fig_case fig_leak fig_r2]

Panel letters in the image equal the letters in the captions; reference letters (circled) are cited by the text.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parent))  # papers/figkit.py, papers/flowkit.py
import figkit as fk  # noqa: E402
import flowkit  # noqa: E402
from figures_results import fig_case, fig_holdout, fig_leak, fig_r2, fig_se, fig_weights  # noqa: E402,F401

TAB, NUM, FIG = HERE / "results" / "tables", HERE / "results" / "numbers", HERE / "results" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
OI = fk.OI


# ------------------------------------------------------------------------------------------ Figure 1: flowchart
FLOW = dict(
    nodes={
        "start": dict(kind="start", col=1, row=0, text="start", color=0),
        "l0": dict(kind="process", col=1, row=1, text="l0", color=0, tag="L0"),
        "d0": dict(kind="decision", col=1, row=2, text="d0", color=2),
        "gap0": dict(kind="note", col=2, row=2, text="gap0", color=5),
        "l1": dict(kind="process", col=1, row=3, text="l1", color=1, tag="L1"),
        "l2": dict(kind="process", col=1, row=4, text="l2", color=1, tag="L2"),
        "d2": dict(kind="decision", col=1, row=5, text="d2", color=2),
        "gap2": dict(kind="note", col=2, row=5, text="gap2", color=5),
        "l3": dict(kind="process", col=1, row=6, text="l3", color=3, tag="L3"),
        "ml": dict(kind="process", col=0, row=6, text="ml", color=4, tag="V"),
        "d3": dict(kind="decision", col=1, row=7, text="d3", color=2),
        "robust": dict(kind="end", col=1, row=8, text="robust", color=1),
        "sens": dict(kind="end", col=2, row=8, text="sens", color=4),
    },
    edges=[("start", "l0", "b", "t"), ("l0", "d0", "b", "t"), ("d0", "l1", "b", "t", "YES"), ("d0", "gap0", "r", "l", "NO"),
           ("gap0", "l1", "b", "r", None, "vh"), ("l1", "l2", "b", "t"), ("l2", "d2", "b", "t"), ("d2", "l3", "b", "t", "YES"),
           ("d2", "gap2", "r", "l", "NO"), ("gap2", "l3", "b", "r", None, "vh"), ("l3", "d3", "b", "t"), ("ml", "d3", "b", "l", None, "vh"),
           ("l2", "ml", "l", "t", None, "hv"), ("d3", "robust", "b", "t", "NO"), ("d3", "sens", "r", "t", "YES", "hv")],
    fa_labels={"YES": "بله", "NO": "خیر"},
)
TEXT = {
    "en": {
        "start": "A published NHTS study\nPaper, printed numbers, public NHTS files",
        "l0": "Rebuild the sample\nUse the public files and the paper's rules in order; write the sample-flow table (pynhts.study)",
        "d0": "Printed sample size within 5 %?",
        "gap0": "Record the gap\nName the unwritten rule; keep the nearest defensible sample",
        "l1": "Rebuild the descriptive tables\nGrade every printed value: EXACT, CLOSE, ACCEPTABLE or GAP",
        "l2": "Fit the published model\nSame variables and same estimator (weighted or not)",
        "d2": "Printed coefficients or score reproduced?",
        "gap2": "Record the deviation\nCarry it into the interpretation",
        "l3": "Refit under the survey design\nNaive, weighted, and replicate-weight variance (pynhts.models)",
        "ml": "Rescore the classifier\nFour pipelines: resample before or after the split; rows or households (pynhts.validate)",
        "d3": "Does a sign, a significance or a score change?",
        "robust": "Design-robust\nConclusion survives",
        "sens": "Design-sensitive\nReport the design-aware result",
    },
    "fa": {
        "start": "یک مطالعهٔ منتشرشدهٔ NHTS\nمقاله، عددهای چاپی، فایل‌های عمومی NHTS",
        "l0": "بازسازی نمونه\nفایل‌های عمومی و قاعده‌های مقاله به‌ترتیب؛ جدول جریان نمونه (pynhts.study)",
        "d0": "آیا اندازهٔ نمونهٔ چاپی تا ۵٪ برمی‌گردد؟",
        "gap0": "ثبت شکاف\nقاعدهٔ نانوشته را نام ببر؛ نزدیک‌ترین نمونهٔ قابل‌دفاع را نگه دار",
        "l1": "بازسازی جدول‌های توصیفی\nهر عدد چاپی: EXACT، CLOSE، ACCEPTABLE یا GAP",
        "l2": "برازش مدل منتشرشده\nهمان متغیرها و همان برآوردگر (وزنی یا بدون وزن)",
        "d2": "آیا ضریب یا امتیاز چاپی بازتولید شد؟",
        "gap2": "ثبت انحراف\nدر تفسیر لحاظ شود",
        "l3": "برازش دوباره با طرح نمونه‌گیری\nساده، وزنی و واریانس با وزن‌های تکرار (pynhts.models)",
        "ml": "امتیازدهی دوبارهٔ طبقه‌بند\nچهار خط لوله: بازنمونه‌گیری پیش یا پس از تقسیم؛ ردیف یا خانوار (pynhts.validate)",
        "d3": "آیا علامت، معناداری یا امتیاز تغییر می‌کند؟",
        "robust": "پایدار نسبت به طرح\nنتیجه می‌ماند",
        "sens": "حساس به طرح\nنتیجهٔ طراحی‌آگاه گزارش شود",
    },
}


def fig_flow() -> None:
    for lang in ("en", "fa"):
        flowkit.draw(FLOW, TEXT[lang], lang, FIG / f"fig_flow_{lang}.png", cw=5.6, rh=2.35, bw=5.0, bh=1.65, dw=5.2, dh=1.6, fs=6.6,
                     wrapw=34, labels=FLOW["fa_labels"])


# ------------------------------------------------------------------------------------------ Figure 2: the ladder
def fig_ladder() -> None:
    st = pd.read_csv(TAB / "studies.csv")
    fk.style(8.5)
    cols = ["L0 sample", "L1 tables", "L2 model", "L3 design"]
    fig, ax = plt.subplots(figsize=(7.2, 7.6))
    cmap = {"good": OI["green"], "mid": OI["yellow"], "bad": OI["orange"], "na": "#D9DEE3", "done": OI["sky"]}
    for i, r in st.iterrows():
        y = len(st) - 1 - i
        l0 = {"SUFFICIENT": "good", "PARTIAL": "mid", "INSUFFICIENT": "bad"}[r["L0_verdict"]]
        l1 = "good" if r["L1_share_exact_close"] >= 0.85 else "mid" if r["L1_share_exact_close"] >= 0.5 else "bad"
        if r["L2_attempted"] == "yes":
            l2 = {"good": "good", "mid": "mid", "bad": "bad", "none": "na"}[r["L2_grade"]]
            l3 = "done"
        else:
            l2, l3 = "na", "na"
        for j, c in enumerate((l0, l1, l2, l3)):
            ax.add_patch(plt.Rectangle((j, y), 0.92, 0.82, fc=cmap[c], ec="white"))
        ax.text(-0.15, y + 0.41, f"{r['id']}  {r['study']}", ha="right", va="center", fontsize=8)
        if r["L2_attempted"] != "yes":
            ax.text(2.46, y + 0.41, "not run", ha="center", va="center", fontsize=6.5, color="#555555")
        if r["L2_grade"] == "none":
            ax.text(2.46, y + 0.41, "no valid target", ha="center", va="center", fontsize=6.5, color="#555555")
    ax.set_xlim(0, 4); ax.set_ylim(0, len(st)); ax.axis("off")
    for j, c in enumerate(cols):
        ax.text(j + 0.46, len(st) + 0.25, c, ha="center", va="bottom", fontsize=8.5, fontweight="bold")
    handles = [plt.Rectangle((0, 0), 1, 1, fc=cmap[k]) for k in ("good", "mid", "bad", "done", "na")]
    ax.legend(handles, ["reproduced", "partly", "not reproduced", "re-estimated", "not run"], loc="upper center",
              bbox_to_anchor=(0.45, -0.005), ncol=5, fontsize=7.5, frameon=False)
    fk.save(fig, FIG, "fig_ladder")


def main() -> None:
    names = sys.argv[1:] or ["fig_flow", "fig_ladder", "fig_weights", "fig_se", "fig_case", "fig_leak", "fig_r2", "fig_holdout"]
    for n in names:
        globals()[n]()
        print("done", n)


if __name__ == "__main__":
    main()
