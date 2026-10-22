"""Persian twins of the three figures of the pynhts manuscript (same numbers as make_figures.py; only the text is Persian).

Run with a Python that has arabic-reshaper and python-bidi:  python paper/softwarex/make_figures_fa.py
Output: figures/fig1_architecture_fa.{png,pdf}, fig2_audit_overview_fa.*, fig3_agreement_lidbe_fa.*
Latin identifiers (module names, status codes, study codes) stay Latin; Persian lines are reshaped and reordered for matplotlib.
"""

from __future__ import annotations

import arabic_reshaper
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from bidi.algorithm import get_display
from matplotlib import font_manager

import make_figures as M

font_manager.fontManager.addfont("C:/Windows/Fonts/tahoma.ttf")
font_manager.fontManager.addfont("C:/Windows/Fonts/tahomabd.ttf")
plt.rcParams.update({"font.family": "Tahoma", "axes.unicode_minus": False})

_RESHAPER = arabic_reshaper.ArabicReshaper(configuration={"delete_harakat": False, "support_ligatures": True})
_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa(s: str) -> str:
    """Persian digits, reshaping and visual (bidi) order for one line of text."""
    s = s.translate(_PERSIAN_DIGITS)
    return get_display(_RESHAPER.reshape(s))


def fa_lines(s: str) -> str:
    """Several lines separated by '|' (the box helper of make_figures splits on it)."""
    return "|".join(fa(x) for x in s.split("|"))


def fig1() -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis("off")
    grey = dict(fc="#f4f4f4", ec="#777")
    M.box(ax, 0.2, 6.9, 11.6, 0.9, fa("پرونده‌های عمومی رسمی NHTS: 2001، 2009، 2017، 2022 (FHWA، ORNL)"),
          fa("درهم‌ساز SHA-256 هر بایگانی و هر عضو آن در یک ثبت‌نامه نگهداری می‌شود"), **grey)
    M.box(ax, 0.2, 5.4, 3.6, 1.2, "pynhts.io", fa_lines("دریافت، راستی‌آزمایی (SHA-256)|و تبدیل به Parquet نوع‌دار"))
    M.box(ax, 4.2, 5.4, 3.6, 1.2, "pynhts.core", fa_lines("طرح‌واره از کتاب‌کد، بارگذار تنبل|و پیوندهای اعتبارسنجی‌شده"))
    M.box(ax, 8.2, 5.4, 3.6, 1.2, "pynhts.stats", fa_lines("جک‌نایف (2001، 2009، 2017)|سری تیلور (2022)"))
    for x in (2.0, 6.0, 10.0):
        M.arrow(ax, x, 6.9, x, 6.6)
    amber = dict(fc="#fdf3e1", ec="#e8a33d")
    M.box(ax, 0.2, 3.8, 5.7, 1.3, "pynhts.concepts + pynhts.harmonize",
          fa_lines("44 مفهوم، 19 جدول تناظر بین موج‌ها؛|نگهبان مقدارهای سقف‌گذاری‌شده"), **amber)
    M.box(ax, 6.3, 3.8, 5.5, 1.3, fa("لایهٔ تحلیل"), fa_lines("aggregate، features، study، trends،|tables، viz و تقسیم بدون نشت"), **amber)
    for x, xt in ((2.0, 2.6), (6.0, 6.0), (10.0, 9.2)):
        M.arrow(ax, x, 5.4, xt, 5.1)
    green = dict(fc="#e8f4ea", ec="#3a8a4f")
    M.box(ax, 0.2, 2.1, 3.6, 1.2, "pynhts.recipes", fa_lines("5 منبع، 175 عدد چاپ‌شده|با وضعیت مورد انتظار هر عدد"), **green)
    M.box(ax, 4.2, 2.1, 3.6, 1.2, "tools/paper_audit", fa_lines(f"22 مقالهٔ منتشرشده بازسازی شد|{M.n_graded():,} عدد چاپ‌شده نمره گرفت"), **green)
    M.box(ax, 8.2, 2.1, 3.6, 1.2, "pynhts.ml / CLI", fa_lines("آرایه، تانسور، گراف؛|fetch / register / docs"), **green)
    for x in (2.0, 6.0, 10.0):
        M.arrow(ax, x, 3.8, x, 3.3)
    M.box(ax, 0.2, 0.2, 11.6, 1.3, fa("هر نتیجه می‌گوید چگونه محاسبه شده است"),
          fa_lines("attrs['pynhts']: موج، جدول، وزن، طرح واریانس و یکا؛|PynhtsWarning: جمع‌های سالانه و مقدارهای سقف‌گذاری‌شده؛|docs/guards.md هر تله را فهرست می‌کند"),
          **grey)
    M.arrow(ax, 6.0, 2.1, 6.0, 1.5)
    fig.savefig(M.OUT / "fig1_architecture_fa.png", dpi=300, bbox_inches="tight")
    fig.savefig(M.OUT / "fig1_architecture_fa.pdf", bbox_inches="tight")
    plt.close(fig)


STATUS_FA = {"EXACT": "دقیق", "CLOSE": "نزدیک", "ACCEPTABLE": "قابل‌قبول", "GAP": "شکاف"}


def fig_lidbe() -> None:
    d = pd.read_csv(M.RES / "recheck_p10_lidbe2021.csv")
    d = d[d["status"].isin(M.COL) & ~d["item"].str.contains("race reading v2|TDWKND flag")]
    d = d[(d["published"] > 0) & (d["pynhts"] > 0)]
    fig, ax = plt.subplots(figsize=(5.2, 4.6))
    lo, hi = 0.02, 5e4
    ax.plot([lo, hi], [lo, hi], color="#999", lw=0.8, zorder=0)
    for st in ("GAP", "ACCEPTABLE", "CLOSE", "EXACT"):
        s = d[d["status"] == st]
        ax.scatter(s["published"], s["pynhts"], s=14, color=M.COL[st], alpha=0.85, label=fa(f"{STATUS_FA[st]} ({len(s)})"), linewidths=0)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel(fa("مقدار چاپ‌شده در مقاله (مقیاس لگاریتمی؛ درصد یا میلیون سفر)"))
    ax.set_ylabel(fa("مقدار محاسبه‌شده با pynhts"))
    ax.legend(frameon=False, loc="upper left", title=fa(f"{len(d)} خانه از جدول‌های 3 و 4"))
    fig.savefig(M.OUT / "fig3_agreement_lidbe_fa.png", dpi=300, bbox_inches="tight")
    fig.savefig(M.OUT / "fig3_agreement_lidbe_fa.pdf", bbox_inches="tight")
    plt.close(fig)


def fig_audit() -> None:
    rows = []
    for f in sorted(M.RES.glob("p[0-9][0-9]_*.csv")):
        t = pd.read_csv(f)
        t = t[t["status"].isin(M.COL)]
        n = len(t)
        rows.append({"paper": f.stem[:3].upper(), **{s: (t["status"] == s).sum() / n * 100 for s in M.COL}, "n": n})
    d = pd.DataFrame(rows).sort_values(["EXACT", "CLOSE"], ascending=True)
    fig, ax = plt.subplots(figsize=(5.2, 5.4))
    left = np.zeros(len(d))
    labels = d["paper"] + "  (n=" + d["n"].astype(str) + ")"
    for st in M.COL:
        ax.barh(labels, d[st], left=left, color=M.COL[st], label=fa(STATUS_FA[st]), height=0.75)
        left += d[st].values
    ax.set_xlim(0, 100)
    ax.set_xlabel(fa("سهم عددهای چاپ‌شدهٔ هر مقاله (٪)"))
    ax.legend(frameon=False, ncol=4, loc="lower center", bbox_to_anchor=(0.45, 1.0), handlelength=1, columnspacing=1)
    fig.savefig(M.OUT / "fig2_audit_overview_fa.png", dpi=300, bbox_inches="tight")
    fig.savefig(M.OUT / "fig2_audit_overview_fa.pdf", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    fig1()
    fig_audit()
    fig_lidbe()
