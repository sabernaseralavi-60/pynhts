"""Flowchart engine with real flowchart conventions (user rule 2026-10-13, JOURNAL_MANUSCRIPT_STANDARD section 16).

Node kinds: 'start'/'end' (terminator pill), 'process' (rectangle), 'decision' (diamond), 'data' (parallelogram), 'note' (dashed box).
Edges: (a, b, a_side, b_side, label) with sides 'l','r','t','b'; label 'YES'/'NO' (or any text) is drawn on the arrow.
Persian twin: pass lang='fa' (columns mirrored, RTL shaping via arabic-reshaper + python-bidi, Vazirmatn). Text is wrapped BEFORE shaping.

spec = dict(nodes={id: dict(kind, col, row, text, tag=None, color=0)}, edges=[...], fa_labels={'YES': 'بله', 'NO': 'خیر'})
Text of a node: 'Heading\nbody' (first line bold). `tag` is a small reference letter (e.g. 'F1') printed in a circle on the node corner
so the manuscript can cite it. draw(spec, texts, lang, path)."""
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon, Circle

COL = ["#dce9f5", "#e3f1df", "#fdf0d5", "#eadff0", "#fbe0dc", "#ececec"]
EDGE = ["#2f6690", "#3a7d44", "#b07d00", "#6a3d86", "#b23a2e", "#555555"]


def fa_font():
    for name in ("Vazirmatn-Regular.ttf", "Vazirmatn-VariableFont_wght.ttf"):
        for p in Path.home().glob(f"AppData/Local/Microsoft/Windows/Fonts/{name}"):
            font_manager.fontManager.addfont(str(p))
            return "Vazirmatn"
    for p in (Path("C:/Windows/Fonts/tahoma.ttf"),):
        if p.exists():
            font_manager.fontManager.addfont(str(p))
            return "Tahoma"
    return "DejaVu Sans"


def shape(s, lang):
    if lang != "fa":
        return s
    if tuple(int(x) for x in matplotlib.__version__.split(".")[:2]) >= (3, 11):
        return s  # matplotlib 3.11 shapes and reorders Arabic-script text itself: pre-shaping would double it
    import arabic_reshaper
    from bidi.algorithm import get_display
    return get_display(arabic_reshaper.reshape(s))


def wrap(s, width, lang):
    return "\n".join(shape(l, lang) for l in textwrap.wrap(s, width=width))


def draw(spec, texts, lang, path, cw=5.2, rh=2.25, bw=4.6, bh=1.5, dw=5.2, dh=1.85, fs=7.0, wrapw=40, labels=None):
    """cw/rh: column/row pitch; bw,bh: process size; dw,dh: diamond size."""
    rtl = lang == "fa"
    plt.rcParams["font.family"] = fa_font() if rtl else "DejaVu Sans"
    nodes = spec["nodes"]
    chan = [float(e[5][2:]) for e in spec["edges"] if len(e) > 5 and e[5] and e[5].startswith("x=")]
    ncol = int(max([n["col"] for n in nodes.values()] + chan)) + 1
    nrow = max(n["row"] for n in nodes.values()) + 1
    W = (ncol - 1) * cw + bw + 0.8
    H = (nrow - 1) * rh + bh + 0.8
    fig, ax = plt.subplots(figsize=(W * 0.62, H * 0.62))
    ax.set_xlim(0, W); ax.set_ylim(0, H); ax.set_aspect("equal"); ax.axis("off")
    pos, size = {}, {}
    for k, n in nodes.items():
        c = (ncol - 1 - n["col"]) if rtl else n["col"]
        cx = 0.4 + bw / 2 + c * cw
        cy = H - 0.4 - bh / 2 - n["row"] * rh
        pos[k] = (cx, cy)
        size[k] = (dw, dh) if n["kind"] == "decision" else (bw * n.get("wscale", 1), bh * n.get("hscale", 1))
    for k, n in nodes.items():
        cx, cy = pos[k]; w, h = size[k]; ci = n.get("color", 0)
        fc, ec = COL[ci], EDGE[ci]; kind = n["kind"]
        if kind in ("start", "end"):
            p = FancyBboxPatch((cx - w / 2, cy - h / 2), w, h, boxstyle=f"round,pad=0.0,rounding_size={h / 2}", fc=fc, ec=ec, lw=1.6)
        elif kind == "decision":
            p = Polygon([(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)], closed=True, fc=fc, ec=ec, lw=1.4)
        elif kind == "data":
            s = 0.25
            p = Polygon([(cx - w / 2 + s, cy + h / 2), (cx + w / 2, cy + h / 2), (cx + w / 2 - s, cy - h / 2), (cx - w / 2, cy - h / 2)], closed=True, fc=fc, ec=ec, lw=1.2)
        elif kind == "note":
            p = FancyBboxPatch((cx - w / 2, cy - h / 2), w, h, boxstyle="round,pad=0.02,rounding_size=0.1", fc="white", ec=ec, lw=1.2, ls="--")
        else:
            p = FancyBboxPatch((cx - w / 2, cy - h / 2), w, h, boxstyle="round,pad=0.0,rounding_size=0.06", fc=fc, ec=ec, lw=1.2)
        ax.add_patch(p)
        head, _, body = texts[k].partition("\n")
        ww = wrapw if kind != "decision" else int(wrapw * 0.55)
        if kind in ("start", "end"): ww = int(wrapw * 0.75)
        if kind == "decision":
            ax.text(cx, cy, wrap(head + (" " + body if body else ""), ww, lang), ha="center", va="center", fontsize=fs, weight="bold", color=ec)
        elif body:
            nb = len(textwrap.wrap(body, width=ww))
            ax.text(cx, cy + h / 2 - 0.1, wrap(head, ww, lang), ha="center", va="top", fontsize=fs + 0.8, weight="bold", color=ec)
            ax.text(cx, cy + h / 2 - 0.48, wrap(body, ww, lang), ha="center", va="top", fontsize=fs, linespacing=1.25)
        else:
            ax.text(cx, cy, wrap(head, int(ww * 0.85), lang), ha="center", va="center", fontsize=fs + 0.8, weight="bold", color=ec)
        if n.get("tag"):
            tx, ty = cx - w / 2 + 0.05, cy + h / 2 - 0.02
            ax.add_patch(Circle((tx, ty), 0.2, fc="white", ec=ec, lw=1.2, zorder=5))
            ax.text(tx, ty, n["tag"], ha="center", va="center", fontsize=6.2, weight="bold", color=ec, zorder=6)

    def anchor(k, side):
        cx, cy = pos[k]; w, h = size[k]
        return {"t": (cx, cy + h / 2), "b": (cx, cy - h / 2), "l": (cx - w / 2, cy), "r": (cx + w / 2, cy)}[side]

    fl = labels or {}
    for e in spec["edges"]:
        a, b, sa, sb = e[:4]; lab = e[4] if len(e) > 4 else None
        via = e[5] if len(e) > 5 else None
        if rtl:
            sa = {"l": "r", "r": "l"}.get(sa, sa); sb = {"l": "r", "r": "l"}.get(sb, sb)
        p1, p2 = anchor(a, sa), anchor(b, sb)
        pts = [p1]
        if via == "hv":      # horizontal first, then vertical
            pts.append((p2[0], p1[1]))
        elif via == "vhv":      # down, across, down (branching to two boxes below)
            my = (p1[1] + p2[1]) / 2; pts += [(p1[0], my), (p2[0], my)]
        elif via == "vh":
            pts.append((p1[0], p2[1]))
        elif via and via.startswith("x="):      # vertical channel at x (relative column units), e.g. loop-back
            xv = 0.4 + bw / 2 + float(via[2:]) * cw
            if rtl:
                xv = 0.4 + bw / 2 + (ncol - 1 - float(via[2:])) * cw
            pts += [(xv, p1[1]), (xv, p2[1])]
        pts.append(p2)
        for i in range(len(pts) - 2):
            ax.plot([pts[i][0], pts[i + 1][0]], [pts[i][1], pts[i + 1][1]], color="#333333", lw=1.1, solid_capstyle="round", zorder=1)
        ax.add_patch(FancyArrowPatch(pts[-2], pts[-1], arrowstyle="-|>", mutation_scale=11, color="#333333", lw=1.1, shrinkA=0, shrinkB=0, zorder=2))
        if lab:
            txt = fl.get(lab, lab) if rtl else lab
            mx, my = (pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2
            if abs(pts[0][0] - pts[1][0]) < 1e-9:
                ox, oy = 0.32, 0.1
            else:
                ox, oy = 0, 0.22
            ax.text(mx + ox, my + oy, shape(txt, lang), ha="center", va="center", fontsize=7.2, weight="bold", color="#b23a2e" if lab.upper().startswith("N") or lab == "خیر" else "#2f6e3a",
                    bbox=dict(fc="white", ec="none", pad=0.6), zorder=6)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=300, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
