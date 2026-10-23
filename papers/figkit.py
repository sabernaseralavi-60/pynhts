"""Shared figure kit for the NHTS papers (journal-grade figures; rule 2026-10-13/14).

Import: sys.path.insert(0, <repo>/papers); import figkit as fk
* fk.style(): common rcParams (Okabe-Ito palette, light grid, 200 dpi PNG + SVG).
* fk.letter(ax, 'A'): panel letter outside the axes corner (same letter as the caption).
* fk.badge(ax, x, y, 'R', coords='data'|'axes'): reference letter in a circle; the caption and a sentence of the text cite it.
* fk.band(ax, lo, hi, axis='y'|'x', ...): light highlight region behind the data.
* fk.callout(ax, text, xy, xytext): short annotation with a thin leader line.
* fk.save(fig, figdir, name): PNG (200 dpi) + SVG.
Flowcharts: papers/flowkit.py (copy of the research-kit engine with decision diamonds, YES/NO arrows, Persian twin).
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

OI = dict(black="#000000", orange="#D55E00", blue="#0072B2", green="#009E73", yellow="#E69F00", sky="#56B4E9", pink="#CC79A7", grey="#6A7B8C", light="#B8C2CC")
HL = "#FDEBD3"      # highlight fill
HL_EDGE = "#D55E00"


def style(base=9):
    plt.rcParams.update({"font.size": base, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.22,
                         "grid.linewidth": 0.6, "figure.dpi": 150, "savefig.bbox": "tight", "axes.titlesize": base, "axes.labelsize": base,
                         "legend.frameon": False, "axes.axisbelow": True})


def letter(ax, s, dx=-0.01, dy=1.03, size=11):
    ax.text(dx, dy, s, transform=ax.transAxes, fontsize=size, fontweight="bold", ha="right", va="bottom")


def badge(ax, x, y, s, coords="data", color=HL_EDGE, r=0.032, size=7.5):
    """Circled reference letter. coords='axes' puts it in axes fraction (robust against log axes)."""
    tr = ax.transAxes if coords == "axes" else ax.transData
    # radius in axes fraction on both axes so that it stays a circle for equal-aspect-free axes: draw as text in a bbox instead
    ax.text(x, y, s, transform=tr, ha="center", va="center", fontsize=size, fontweight="bold", color=color, zorder=8,
            bbox=dict(boxstyle="circle,pad=0.22", fc="white", ec=color, lw=1.2))


def band(ax, lo, hi, axis="y", color=HL, edge=HL_EDGE, alpha=0.9, lw=0.0):
    f = ax.axhspan if axis == "y" else ax.axvspan
    f(lo, hi, facecolor=color, edgecolor=edge, linewidth=lw, alpha=alpha, zorder=0)


def callout(ax, text, xy, xytext, coords="data", color="#333333", size=7.5, ha="left"):
    ax.annotate(text, xy=xy, xytext=xytext, xycoords=coords, textcoords=coords, fontsize=size, color=color, ha=ha, va="center",
                arrowprops=dict(arrowstyle="-", color=color, lw=0.7, shrinkA=2, shrinkB=2))


def save(fig, figdir, name):
    fig.savefig(figdir / f"{name}.png", dpi=200)
    fig.savefig(figdir / f"{name}.svg")
    plt.close(fig)
