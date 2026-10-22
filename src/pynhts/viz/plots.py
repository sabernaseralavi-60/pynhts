"""Honest default charts: every figure states its weighting, sample size and missing values.

Needs the optional ``matplotlib`` dependency (``pip install pynhts[viz]``). The styling is plain and
colour-blind-safe (Okabe-Ito); pass ``ax=`` to draw into your own figure and restyle freely.

>>> from pynhts.viz import plots                                                  # doctest: +SKIP
>>> fig = plots.histogram(hh["hh_miles"], weight=hh["WTHHFIN"], xlabel="miles/day")   # doctest: +SKIP
>>> plots.save(fig, "fig1.svg")                                                      # doctest: +SKIP

A chart built from a weight is labelled "weighted"; one built without is labelled "unweighted
sample". There is no way to get a weighted-looking chart from unweighted data.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from pynhts.eda import CorrelationResult

OKABE_ITO = ("#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000")


def _plt() -> Any:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover
        raise ImportError("plots need matplotlib: pip install pynhts[viz]") from exc
    return plt


def _foot(ax: Any, n: int, weighted: bool, n_missing: int = 0, extra: str = "") -> None:
    how = "weighted" if weighted else "unweighted sample"
    text = (
        f"{how}; n = {n:,}"
        + (f"; {n_missing:,} missing excluded" if n_missing else "")
        + (f"; {extra}" if extra else "")
    )
    ax.annotate(text, xy=(0, -0.2), xycoords="axes fraction", fontsize=7, color="#444444", va="top")


def histogram(
    values: pd.Series,
    *,
    weight: pd.Series | None = None,
    bins: int = 40,
    xlabel: str = "",
    title: str = "",
    ax: Any = None,
    density: bool = False,
    clip_quantile: float | None = 0.995,
) -> Any:
    """Histogram of a numeric series (weighted when ``weight`` is given)."""
    plt = _plt()
    x = pd.to_numeric(values, errors="coerce")
    w = (
        pd.to_numeric(weight, errors="coerce")
        if weight is not None
        else pd.Series(1.0, index=x.index)
    )
    ok = x.notna() & w.notna() & (w > 0)
    xv: np.ndarray[Any, Any] = x[ok].to_numpy(float)
    wv: np.ndarray[Any, Any] = w[ok].to_numpy(float)
    note = ""
    if clip_quantile is not None and len(xv):
        hi = float(np.quantile(xv, clip_quantile))
        keep = xv <= hi
        note = (
            f"values above {hi:.3g} (top {100 * (1 - clip_quantile):.1f}%) not drawn"
            if (~keep).any()
            else ""
        )
        xv, wv = xv[keep], wv[keep]
    fig = None
    if ax is None:
        fig, ax = plt.subplots(figsize=(5.2, 3.6))
    ax.hist(
        xv,
        bins=bins,
        weights=wv,
        density=density,
        color=OKABE_ITO[0],
        edgecolor="white",
        linewidth=0.3,
    )
    ax.set_xlabel(xlabel or str(values.name or ""))
    ax.set_ylabel(
        "density" if density else ("population (weighted)" if weight is not None else "records")
    )
    ax.set_title(title, fontsize=10)
    _foot(ax, int(ok.sum()), weight is not None, int((~ok).sum()), note)
    return fig or ax.figure


def bar_share(
    categories: pd.Series,
    shares: pd.Series,
    *,
    err: pd.Series | None = None,
    n: int | None = None,
    weighted: bool = True,
    xlabel: str = "",
    title: str = "",
    ax: Any = None,
    horizontal: bool = True,
) -> Any:
    """Bar chart of shares (0-1) with optional margins of error; ``n`` is the unweighted record count."""
    plt = _plt()
    fig = None
    if ax is None:
        fig, ax = plt.subplots(figsize=(5.2, 3.6))
    order = np.argsort(-np.asarray(shares, float))
    cat = [str(c) for c in np.asarray(categories)[order]]
    val = np.asarray(shares, float)[order] * 100
    e = None if err is None else np.asarray(err, float)[order] * 100
    if horizontal:
        ax.barh(cat, val, xerr=e, color=OKABE_ITO[0], capsize=2)
        ax.invert_yaxis()
        ax.set_xlabel(xlabel or "share (%)")
    else:
        ax.bar(cat, val, yerr=e, color=OKABE_ITO[0], capsize=2)
        ax.set_ylabel(xlabel or "share (%)")
    ax.set_title(title, fontsize=10)
    _foot(
        ax,
        n or 0,
        weighted,
        0,
        "bars: estimate; whiskers: margin of error" if err is not None else "",
    )
    return fig or ax.figure


def wave_trend(
    frame: pd.DataFrame,
    *,
    x: str = "wave",
    y: str = "share",
    group: str = "category",
    err: str | None = "moe",
    title: str = "",
    ylabel: str = "share",
    ax: Any = None,
) -> Any:
    """Lines per group across waves (the output of :func:`pynhts.trends.trip_shares`), waves as categories."""
    plt = _plt()
    fig = None
    if ax is None:
        fig, ax = plt.subplots(figsize=(5.6, 3.8))
    waves = sorted(frame[x].unique())
    pos = {w: i for i, w in enumerate(waves)}
    for i, (g, sub) in enumerate(frame.groupby(group)):
        sub = sub.sort_values(x)
        xs = [pos[w] for w in sub[x]]
        ax.errorbar(
            xs,
            sub[y],
            yerr=sub[err] if err else None,
            marker="o",
            ms=3,
            lw=1,
            capsize=2,
            color=OKABE_ITO[i % len(OKABE_ITO)],
            label=str(g),
        )
    ax.set_xticks(range(len(waves)), [str(w) for w in waves])
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=10)
    ax.legend(fontsize=7, frameon=False, ncol=2)
    n = int(frame["n"].sum()) if "n" in frame else 0
    _foot(ax, n, True, 0, "each wave estimated separately with its own weights; not pooled")
    return fig or ax.figure


def corr_heatmap(
    result: CorrelationResult, *, title: str = "", ax: Any = None, annotate: bool = True
) -> Any:
    """Heat map of a :class:`pynhts.eda.CorrelationResult` (diverging scale fixed to -1..1)."""
    plt = _plt()
    fig = None
    if ax is None:
        k = len(result.r)
        fig, ax = plt.subplots(figsize=(1.0 + 0.8 * k, 0.8 + 0.7 * k))
    im = ax.imshow(result.r.to_numpy(float), vmin=-1, vmax=1, cmap="RdBu_r")
    ax.set_xticks(range(len(result.r)), result.r.columns, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(result.r)), result.r.index, fontsize=8)
    if annotate:
        for i in range(len(result.r)):
            for j in range(len(result.r)):
                v = float(result.r.to_numpy(float)[i, j])
                if np.isfinite(v):
                    ax.text(
                        j,
                        i,
                        f"{v:.2f}",
                        ha="center",
                        va="center",
                        fontsize=7,
                        color="white" if abs(v) > 0.6 else "black",
                    )
    (fig or ax.figure).colorbar(im, ax=ax, fraction=0.046)
    ax.set_title(title or f"{result.method} correlation", fontsize=10)
    ax.annotate(
        f"{'weighted' if result.weighted else 'unweighted'}; pairwise n {int(result.n.min().min()):,}-{int(result.n.max().max()):,}; "
        "association, not causation",
        xy=(0, -0.28),
        xycoords="axes fraction",
        fontsize=7,
        color="#444444",
    )
    return fig or ax.figure


def save(fig: Any, path: str, *, dpi: int = 300) -> None:
    """Save as PNG, SVG or PDF according to the extension (tight bounding box, white background)."""
    if not str(path).lower().endswith((".png", ".svg", ".pdf")):
        raise ValueError("path must end in .png, .svg or .pdf")
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
