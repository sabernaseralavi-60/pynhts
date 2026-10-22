"""Exploratory statistics that know about skip codes and survey weights.

>>> from pynhts import eda                                           # doctest: +SKIP
>>> eda.missing_report(data.persons(["EDUC"], missing="keep"))        # doctest: +SKIP
>>> eda.describe(persons, weight="WTPERFIN")                          # doctest: +SKIP
>>> eda.correlation_matrix(hh, ["hh_n_trips", "HHVEHCNT"], weight="WTHHFIN")   # doctest: +SKIP

Everything here is **descriptive**: weighted point estimates describe the population the weights
represent, they are not hypothesis tests. Standard errors and confidence intervals that respect the
survey design come only from :mod:`pynhts.stats` (replicate weights, 2001-2017; Taylor series, 2022).
Where this module prints an interval (Pearson r of an unweighted sample) it says so, and it never
returns a design-ignorant p-value for weighted data.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd

from pynhts.core.flags import PynhtsWarning
from pynhts.core.validity import answer_status
from pynhts.stats.distributions import t_ppf

Method = Literal["pearson", "spearman", "kendall"]


# ---- weighted building blocks ----------------------------------------------------------------
def _clean(
    x: pd.Series, w: pd.Series | None = None
) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    xv = pd.to_numeric(x, errors="coerce").to_numpy(dtype=float)
    wv = np.ones(len(xv)) if w is None else pd.to_numeric(w, errors="coerce").to_numpy(dtype=float)
    ok = np.isfinite(xv) & np.isfinite(wv) & (wv > 0)
    return xv[ok], wv[ok]


def weighted_quantile(
    x: pd.Series, w: pd.Series | None, q: float | list[float]
) -> float | list[float]:
    """Weighted quantile (the smallest value whose cumulative weight share reaches ``q``)."""
    scalar = isinstance(q, (int, float))
    qs = [float(q)] if isinstance(q, (int, float)) else [float(v) for v in q]
    xv, wv = _clean(x, w)
    if len(xv) == 0:
        out = [float("nan")] * len(qs)
    else:
        o = np.argsort(xv, kind="stable")
        xs, cs = xv[o], np.cumsum(wv[o])
        out = [
            float(xs[min(int(np.searchsorted(cs, p * cs[-1], side="left")), len(xs) - 1)])
            for p in qs
        ]
    return out[0] if scalar else out


def weighted_mean_sd(x: pd.Series, w: pd.Series | None = None) -> tuple[float, float]:
    """Weighted mean and (frequency-weight-free) weighted standard deviation."""
    xv, wv = _clean(x, w)
    if len(xv) == 0:
        return float("nan"), float("nan")
    m = float(np.average(xv, weights=wv))
    return m, float(np.sqrt(np.average((xv - m) ** 2, weights=wv)))


# ---- describe / missing ------------------------------------------------------------------------
def missing_report(frame: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    """Per column: answered, skip (-1), non-answer (-7/-8/-9...) and blank (NaN) counts and shares.

    Load with ``missing="keep"`` (and ``skip="keep"``) to see the reasons; a frame loaded with the
    default masks non-answers to NaN, and they are then reported as ``blank``.
    """
    cols = columns or [c for c in frame.columns if not c.startswith("WT")]
    rows = []
    for c in cols:
        st = answer_status(frame[c]).value_counts()
        n = len(frame)
        r: dict[str, Any] = {"column": c, "n": n}
        for k in ("answered", "skip", "nonanswer", "blank"):
            r[k] = int(st.get(k, 0))
            r[f"{k}_pct"] = round(100.0 * r[k] / n, 2) if n else float("nan")
        rows.append(r)
    out = pd.DataFrame(rows).set_index("column")
    out.attrs["note"] = (
        "skip = the question did not apply; nonanswer = refused/don't know/not ascertained; "
        "blank = NaN (may be a masked non-answer if the frame was loaded with missing='nan')"
    )
    return out


def describe(
    frame: pd.DataFrame,
    columns: list[str] | None = None,
    *,
    weight: str | None = None,
    max_levels: int = 12,
) -> pd.DataFrame:
    """Numeric and categorical summaries, weighted when ``weight`` names a column.

    Numeric columns give one row (n, n_missing, mean, sd, min, quartiles, max); categorical columns
    one row per level (the ``max_levels`` most frequent) with count and share. Weighted figures are
    population estimates; the unweighted count ``n`` is always reported next to them.
    """
    w = frame[weight] if weight else None
    cols = columns or [c for c in frame.columns if c != weight and not c.startswith("WT")]
    rows: list[dict[str, Any]] = []
    for c in cols:
        s = frame[c]
        if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
            xv, _ = _clean(s, w)
            q = list(weighted_quantile(s, w, [0.25, 0.5, 0.75]))  # type: ignore[arg-type]
            m, sd = weighted_mean_sd(s, w)
            rows.append(
                {
                    "column": c,
                    "kind": "numeric",
                    "level": "",
                    "n": int(len(xv)),
                    "n_missing": int(len(s) - len(xv)),
                    "mean": m,
                    "sd": sd,
                    "min": float(np.nanmin(xv)) if len(xv) else np.nan,
                    "p25": q[0],
                    "p50": q[1],
                    "p75": q[2],
                    "max": float(np.nanmax(xv)) if len(xv) else np.nan,
                    "count": np.nan,
                    "share": np.nan,
                }
            )
        else:
            ss = s.astype("string")
            ww = (
                pd.to_numeric(w, errors="coerce")
                if w is not None
                else pd.Series(1.0, index=s.index)
            )
            tot = float(ww[ss.notna()].sum())
            agg = ww.groupby(ss).sum().sort_values(ascending=False).head(max_levels)
            cnt = ss.value_counts()
            for lev, val in agg.items():
                rows.append(
                    {
                        "column": c,
                        "kind": "categorical",
                        "level": lev,
                        "n": int(cnt.get(lev, 0)),
                        "n_missing": int(ss.isna().sum()),
                        "mean": np.nan,
                        "sd": np.nan,
                        "min": np.nan,
                        "p25": np.nan,
                        "p50": np.nan,
                        "p75": np.nan,
                        "max": np.nan,
                        "count": float(val),
                        "share": float(val / tot) if tot else np.nan,
                    }
                )
    out = pd.DataFrame(rows)
    out.attrs["weighted"] = weight is not None
    out.attrs["weight"] = weight
    return out


# ---- correlation / association ---------------------------------------------------------------------
@dataclass
class CorrelationResult:
    """Correlation matrix with pairwise sample sizes and honest notes."""

    r: pd.DataFrame
    n: pd.DataFrame
    method: str
    weighted: bool
    ci_low: pd.DataFrame | None = None
    ci_high: pd.DataFrame | None = None
    notes: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        head = f"{self.method} correlation ({'weighted' if self.weighted else 'unweighted'}); pairwise n {int(self.n.min().min()):,} to {int(self.n.max().max()):,}"
        return "\n".join([head, self.r.round(3).to_string(), *[f"note: {x}" for x in self.notes]])


def _weighted_rank(x: np.ndarray[Any, Any], w: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    """Average weighted rank (mid-rank of the cumulative weight), ties share the mid-rank."""
    o = np.argsort(x, kind="stable")
    xs, ws = x[o], w[o]
    cs = np.cumsum(ws)
    mid = cs - ws / 2.0
    r = np.empty(len(x))
    start = 0
    for end in np.flatnonzero(np.r_[xs[1:] != xs[:-1], True]) + 1:
        r[o[start:end]] = mid[start:end].mean()
        start = int(end)
    return r


def _wcorr(x: np.ndarray[Any, Any], y: np.ndarray[Any, Any], w: np.ndarray[Any, Any]) -> float:
    mx, my = np.average(x, weights=w), np.average(y, weights=w)
    cov = np.average((x - mx) * (y - my), weights=w)
    vx, vy = np.average((x - mx) ** 2, weights=w), np.average((y - my) ** 2, weights=w)
    return float(cov / np.sqrt(vx * vy)) if vx > 0 and vy > 0 else float("nan")


def _kendall(x: np.ndarray[Any, Any], y: np.ndarray[Any, Any]) -> float:
    dx = np.sign(x[:, None] - x[None, :])
    dy = np.sign(y[:, None] - y[None, :])
    num = float((dx * dy).sum())
    den = np.sqrt(float((dx != 0).sum()) * float((dy != 0).sum()))
    return num / den if den else float("nan")


def correlation_matrix(
    frame: pd.DataFrame,
    columns: list[str],
    *,
    method: Method = "pearson",
    weight: str | None = None,
    level: float = 0.95,
    kendall_max: int = 4000,
    seed: int = 0,
) -> CorrelationResult:
    """Pairwise correlations of numeric columns with pairwise n and notes.

    * ``pearson`` and ``spearman`` accept a weight (weighted Pearson; Spearman = Pearson of weighted
      mid-ranks). The result is a descriptive population estimate: **no confidence interval** is
      returned for weighted data because the sampling variance depends on the survey design.
    * Without weights, Pearson gets a Fisher-z interval that assumes a simple random sample (the
      NHTS is not one: treat it as optimistic).
    * ``kendall`` is unweighted; samples above ``kendall_max`` pairs are subsampled with ``seed``.
    * Nominal columns are refused: use :func:`association_matrix` (Cramér's V).
    """
    if method not in ("pearson", "spearman", "kendall"):
        raise ValueError("method must be pearson, spearman or kendall")
    if method == "kendall" and weight:
        raise ValueError(
            "Kendall's tau is implemented unweighted only; drop weight= or use spearman"
        )
    for c in columns:
        s = frame[c]
        if not (pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s)):
            raise TypeError(
                f"{c!r} is not numeric: correlation of a nominal variable is meaningless; "
                "use association_matrix (Cramér's V) or recode to an ordered numeric scale"
            )
    w = frame[weight] if weight else None
    k = len(columns)
    r = pd.DataFrame(np.eye(k), index=columns, columns=columns)
    n = pd.DataFrame(0, index=columns, columns=columns, dtype="int64")
    lo = pd.DataFrame(np.nan, index=columns, columns=columns)
    hi = lo.copy()
    notes = [
        "correlation does not establish causation; with n this large a tiny r can be 'significant' "
        "and still negligible, judge the size of r"
    ]
    rng = np.random.default_rng(seed)
    tcrit = None
    for i, a in enumerate(columns):
        for j in range(i, k):
            b = columns[j]
            xa = pd.to_numeric(frame[a], errors="coerce").to_numpy(float)
            xb = pd.to_numeric(frame[b], errors="coerce").to_numpy(float)
            ww = (
                np.ones(len(frame))
                if w is None
                else pd.to_numeric(w, errors="coerce").to_numpy(float)
            )
            ok = np.isfinite(xa) & np.isfinite(xb) & np.isfinite(ww) & (ww > 0)
            xa, xb, ww = xa[ok], xb[ok], ww[ok]
            n.iloc[i, j] = n.iloc[j, i] = len(xa)
            if len(xa) < 3:
                val = float("nan")
            elif method == "pearson":
                val = _wcorr(xa, xb, ww)
            elif method == "spearman":
                val = _wcorr(_weighted_rank(xa, ww), _weighted_rank(xb, ww), ww)
            else:
                if len(xa) > kendall_max:
                    idx = rng.choice(len(xa), kendall_max, replace=False)
                    xa, xb = xa[idx], xb[idx]
                    if i == 0 and j == 1:
                        notes.append(
                            f"Kendall computed on a random subsample of {kendall_max} rows (seed {seed})"
                        )
                val = _kendall(xa, xb)
            r.iloc[i, j] = r.iloc[j, i] = val
            if (
                method == "pearson"
                and w is None
                and i != j
                and len(xa) > 3
                and np.isfinite(val)
                and abs(val) < 1
            ):
                z, se = np.arctanh(val), 1.0 / np.sqrt(len(xa) - 3)
                tcrit = t_ppf(0.5 + level / 2, 1e6)
                lo.iloc[i, j] = lo.iloc[j, i] = np.tanh(z - tcrit * se)
                hi.iloc[i, j] = hi.iloc[j, i] = np.tanh(z + tcrit * se)
    if weight:
        notes.append(
            "weighted: no interval is given; use a replicate-weight estimate (pynhts.stats) for inference"
        )
    elif method == "pearson":
        notes.append(
            "Fisher-z interval assumes simple random sampling and is too narrow for a clustered survey"
        )
    return CorrelationResult(
        r=r,
        n=n,
        method=method,
        weighted=weight is not None,
        ci_low=lo if method == "pearson" and not weight else None,
        ci_high=hi if method == "pearson" and not weight else None,
        notes=notes,
    )


def cramers_v(x: pd.Series, y: pd.Series, weight: pd.Series | None = None) -> float:
    """Bias-corrected Cramér's V (Bergsma 2013) between two categorical series, optionally weighted."""
    d = pd.DataFrame(
        {
            "x": x.astype("string"),
            "y": y.astype("string"),
            "w": 1.0 if weight is None else pd.to_numeric(weight, errors="coerce"),
        }
    ).dropna()
    d = d[d["w"] > 0]
    if d.empty:
        return float("nan")
    tab = d.pivot_table(index="x", columns="y", values="w", aggfunc="sum", fill_value=0.0)
    if tab.shape[0] < 2 or tab.shape[1] < 2:
        return float("nan")
    # the chi-square statistic uses weights rescaled to the unweighted sample size
    t = tab.to_numpy() * (len(d) / tab.to_numpy().sum())
    exp = t.sum(1, keepdims=True) * t.sum(0, keepdims=True) / t.sum()
    chi2 = float(((t - exp) ** 2 / exp).sum())
    n = t.sum()
    r_, k_ = t.shape
    phi2 = max(0.0, chi2 / n - (k_ - 1) * (r_ - 1) / (n - 1))
    rc = r_ - (r_ - 1) ** 2 / (n - 1)
    kc = k_ - (k_ - 1) ** 2 / (n - 1)
    den = min(kc - 1, rc - 1)
    return float(np.sqrt(phi2 / den)) if den > 0 else float("nan")


def association_matrix(
    frame: pd.DataFrame, columns: list[str], *, weight: str | None = None
) -> pd.DataFrame:
    """Cramér's V for every pair of categorical columns (0 = none, 1 = perfect association)."""
    w = frame[weight] if weight else None
    k = len(columns)
    out = pd.DataFrame(np.eye(k), index=columns, columns=columns)
    for i in range(k):
        for j in range(i + 1, k):
            out.iloc[i, j] = out.iloc[j, i] = cramers_v(frame[columns[i]], frame[columns[j]], w)
    out.attrs["note"] = "Cramér's V (bias-corrected); descriptive, the survey design is ignored"
    return out


# ---- comparisons ------------------------------------------------------------------------------------
def compare_groups(
    frame: pd.DataFrame,
    value: str,
    by: str,
    *,
    weight: str | None = None,
    reference: str | None = None,
) -> pd.DataFrame:
    """Weighted mean, sd and n of ``value`` per group, with the difference to a reference group.

    The standardized difference is (mean - mean_ref) / pooled weighted sd, an effect size, not a test.
    For a design-based standard error of group means use ``survey.mean(value, by=...)``.
    """
    w = frame[weight] if weight else None
    rows = []
    for g, sub in frame.groupby(by, observed=True, dropna=True):
        m, sd = weighted_mean_sd(sub[value], sub[weight] if weight else None)
        xv, _ = _clean(sub[value], sub[weight] if weight else None)
        rows.append({by: g, "n": len(xv), "mean": m, "sd": sd})
    out = pd.DataFrame(rows).set_index(by)
    ref = reference if reference is not None else out.index[0]
    _, sd_all = weighted_mean_sd(frame[value], w)
    ref_mean = float(out["mean"].to_numpy(float)[list(out.index).index(ref)])
    out["diff_vs_ref"] = out["mean"].to_numpy(float) - ref_mean
    out["std_diff"] = out["diff_vs_ref"] / sd_all if sd_all else np.nan
    out.attrs["reference"] = ref
    out.attrs["weighted"] = weight is not None
    return out


def compare_distributions(
    a: pd.Series,
    b: pd.Series,
    *,
    weight_a: pd.Series | None = None,
    weight_b: pd.Series | None = None,
    quantiles: tuple[float, ...] = (0.1, 0.25, 0.5, 0.75, 0.9),
) -> pd.DataFrame:
    """Quantiles of two samples side by side, plus the weighted Kolmogorov-Smirnov distance D.

    D is the largest gap between the weighted empirical distribution functions (0 to 1). It is a
    descriptive distance; no p-value is given because it would assume independent observations.
    """
    qa = weighted_quantile(a, weight_a, list(quantiles))
    qb = weighted_quantile(b, weight_b, list(quantiles))
    out = pd.DataFrame(
        {"a": qa, "b": qb, "diff": np.subtract(qb, qa)},
        index=[f"p{int(q * 100)}" for q in quantiles],
    )
    xa, wa = _clean(a, weight_a)
    xb, wb = _clean(b, weight_b)
    grid = np.unique(np.concatenate([xa, xb]))
    oa, ob = np.argsort(xa), np.argsort(xb)
    fa = np.searchsorted(xa[oa], grid, side="right")
    fb = np.searchsorted(xb[ob], grid, side="right")
    ca = np.r_[0, np.cumsum(wa[oa])] / wa.sum()
    cb = np.r_[0, np.cumsum(wb[ob])] / wb.sum()
    out.attrs["ks_distance"] = float(np.max(np.abs(ca[fa] - cb[fb]))) if len(grid) else float("nan")
    return out


def warn_if_unweighted(frame: pd.DataFrame, weight: str | None) -> None:
    """Issue a PynhtsWarning when a frame that carries a weight column is analysed without it."""
    present = [c for c in frame.columns if c.startswith("WT")]
    if weight is None and present:
        warnings.warn(
            f"the frame carries weight column(s) {present} but none was used: the result describes "
            "the sample, not the population",
            PynhtsWarning,
            stacklevel=3,
        )
