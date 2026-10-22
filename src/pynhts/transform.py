"""Transparent, leakage-safe transformations with before/after diagnostics.

Nothing here is applied automatically. A transformation is a *decision* about scale and
interpretability; skewness alone is not a reason (a long right tail of trip distances is the data,
not a defect). Use :func:`diagnostics` to look, then fit a :class:`Transformer` on the **training**
rows only and apply it to the others, so that no information from held-out rows leaks into the
parameters. The original columns are never overwritten: results are new columns ``<col>__<method>``.

>>> from pynhts import transform                                                  # doctest: +SKIP
>>> tr = transform.Transformer({"hh_miles": "log1p", "HHSIZE": "standardize"})   # doctest: +SKIP
>>> train, test = transform.split_by_household(frame, test_size=0.2, seed=1)     # doctest: +SKIP
>>> tr.fit(train, weight="WTHHFIN"); test_t = tr.transform(test)                 # doctest: +SKIP
>>> tr.to_json()   # parameters, to reproduce the transformation                  # doctest: +SKIP
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

import numpy as np
import pandas as pd

from pynhts.eda import weighted_mean_sd, weighted_quantile

METHODS = (
    "log",
    "log1p",
    "sqrt",
    "boxcox",
    "yeojohnson",
    "standardize",
    "robust",
    "winsorize",
    "bins",
)


def diagnostics(
    before: pd.Series, after: pd.Series | None = None, weight: pd.Series | None = None
) -> pd.DataFrame:
    """Skewness, excess kurtosis, range and share of non-finite values, before and after."""
    rows: dict[str, dict[str, float]] = {}
    for name, s in (("before", before), ("after", after)):
        if s is None:
            continue
        x = pd.to_numeric(s, errors="coerce").to_numpy(float)
        w = (
            np.ones(len(x))
            if weight is None
            else pd.to_numeric(weight, errors="coerce").to_numpy(float)
        )
        ok = np.isfinite(x) & np.isfinite(w) & (w > 0)
        xv, wv = x[ok], w[ok]
        if len(xv) < 3:
            rows[name] = {"n": float(len(xv))}
            continue
        m = float(np.average(xv, weights=wv))
        v = float(np.average((xv - m) ** 2, weights=wv))
        sd = float(np.sqrt(v)) if v > 0 else float("nan")
        rows[name] = {
            "n": float(len(xv)),
            "share_nonfinite": float(1 - ok.mean()),
            "min": float(xv.min()),
            "max": float(xv.max()),
            "mean": m,
            "sd": sd,
            "skewness": float(np.average((xv - m) ** 3, weights=wv) / sd**3)
            if sd == sd
            else float("nan"),
            "excess_kurtosis": float(np.average((xv - m) ** 4, weights=wv) / sd**4 - 3)
            if sd == sd
            else float("nan"),
        }
    return pd.DataFrame(rows)


def _golden(f: Callable[[float], float], lo: float, hi: float, tol: float = 1e-6) -> float:
    g = (np.sqrt(5) - 1) / 2
    a, b = lo, hi
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = f(c), f(d)
    while abs(b - a) > tol:
        if fc > fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = f(d)
    return float((a + b) / 2)


def _bc(x: np.ndarray[Any, Any], lam: float) -> np.ndarray[Any, Any]:
    return np.log(x) if abs(lam) < 1e-9 else (x**lam - 1) / lam


def _yj(x: np.ndarray[Any, Any], lam: float) -> np.ndarray[Any, Any]:
    out = np.empty_like(x)
    p, n = x >= 0, x < 0
    out[p] = np.log1p(x[p]) if abs(lam) < 1e-9 else ((x[p] + 1) ** lam - 1) / lam
    out[n] = -np.log1p(-x[n]) if abs(lam - 2) < 1e-9 else -((1 - x[n]) ** (2 - lam) - 1) / (2 - lam)
    return out


def _loglik(y: np.ndarray[Any, Any], w: np.ndarray[Any, Any], jac: float) -> float:
    m = np.average(y, weights=w)
    var = np.average((y - m) ** 2, weights=w)
    return float(-0.5 * w.sum() * np.log(var) + jac) if var > 0 else -np.inf


def _bc_objective(x: np.ndarray[Any, Any], w: np.ndarray[Any, Any], jac: float) -> Callable[[float], float]:
    def f(lam: float) -> float:
        return _loglik(_bc(x, lam), w, (lam - 1) * jac)

    return f


def _yj_objective(x: np.ndarray[Any, Any], w: np.ndarray[Any, Any], jac: float) -> Callable[[float], float]:
    def f(lam: float) -> float:
        return _loglik(_yj(x, lam), w, (lam - 1) * jac)

    return f


class Transformer:
    """Fit on training rows, apply anywhere; parameters are stored for reproducibility."""

    def __init__(self, spec: Mapping[str, str | Mapping[str, Any]]) -> None:
        """``spec`` maps a column to a method name, or to ``{"method": ..., **options}``.

        Options: ``winsorize`` takes ``lower`` and ``upper`` quantiles (default 0.01, 0.99);
        ``bins`` takes ``edges`` (and optional ``labels``, ``right``).
        """
        self.spec: dict[str, dict[str, Any]] = {}
        for col, m in spec.items():
            d: dict[str, Any] = {"method": m} if isinstance(m, str) else dict(m)
            if d.get("method") not in METHODS:
                raise ValueError(f"method for {col!r} must be one of {METHODS}")
            self.spec[col] = d
        self.params: dict[str, dict[str, Any]] = {}
        self.fitted = False

    def fit(self, frame: pd.DataFrame, weight: str | None = None) -> Transformer:
        """Learn the parameters from ``frame`` (the training rows)."""
        w = frame[weight] if weight else None
        for col, d in self.spec.items():
            m = d["method"]
            xv = pd.to_numeric(frame[col], errors="coerce").to_numpy(float)
            wv = (
                np.ones(len(xv)) if w is None else pd.to_numeric(w, errors="coerce").to_numpy(float)
            )
            ok = np.isfinite(xv) & np.isfinite(wv) & (wv > 0)
            xv, wv = xv[ok], wv[ok]
            p: dict[str, Any] = {"n_fit": int(len(xv)), "weighted": weight is not None}
            if m == "log" and (xv <= 0).any():
                raise ValueError(
                    f"log of {col!r}: {(xv <= 0).sum()} values are zero or negative; "
                    "log1p keeps zeros, but check what a zero means before transforming"
                )
            if m == "log1p" and (xv <= -1).any():
                raise ValueError(f"log1p of {col!r} needs values > -1")
            if m == "sqrt" and (xv < 0).any():
                raise ValueError(f"sqrt of {col!r} has negative values")
            if m == "boxcox":
                if (xv <= 0).any():
                    raise ValueError(
                        f"Box-Cox of {col!r} needs strictly positive values (use yeojohnson)"
                    )
                jac_bc = float(np.sum(wv * np.log(xv)))
                p["lambda"] = _golden(
                    _bc_objective(xv, wv, jac_bc), -5, 5
                )
            elif m == "yeojohnson":
                jac_yj = float(np.sum(wv * np.sign(xv) * np.log1p(np.abs(xv))))
                p["lambda"] = _golden(
                    _yj_objective(xv, wv, jac_yj), -5, 5
                )
            elif m == "standardize":
                p["mean"], p["sd"] = weighted_mean_sd(pd.Series(xv), pd.Series(wv))
            elif m == "robust":
                q = weighted_quantile(pd.Series(xv), pd.Series(wv), [0.25, 0.5, 0.75])
                assert isinstance(q, list)
                p["median"], p["iqr"] = q[1], q[2] - q[0]
            elif m == "winsorize":
                q = weighted_quantile(
                    pd.Series(xv), pd.Series(wv), [d.get("lower", 0.01), d.get("upper", 0.99)]
                )
                assert isinstance(q, list)
                p["low"], p["high"] = q[0], q[1]
            elif m == "bins" and "edges" not in d:
                raise ValueError("bins needs edges=[...]")
            self.params[col] = p
        self.fitted = True
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Return ``frame`` with the new ``<col>__<method>`` columns added (originals untouched)."""
        if not self.fitted:
            raise RuntimeError("fit the Transformer on the training rows before transforming")
        out = frame.copy()
        for col, d in self.spec.items():
            m, p = d["method"], self.params[col]
            x = pd.to_numeric(frame[col], errors="coerce")
            name = f"{col}__{m}"
            if m == "log":
                out[name] = np.log(x.where(x > 0))
            elif m == "log1p":
                out[name] = np.log1p(x.where(x > -1))
            elif m == "sqrt":
                out[name] = np.sqrt(x.where(x >= 0))
            elif m == "boxcox":
                v = x.where(x > 0).to_numpy(float)
                out[name] = np.where(
                    np.isfinite(v), _bc(np.where(np.isfinite(v), v, 1.0), p["lambda"]), np.nan
                )
            elif m == "yeojohnson":
                v = x.to_numpy(float)
                out[name] = np.where(
                    np.isfinite(v), _yj(np.where(np.isfinite(v), v, 0.0), p["lambda"]), np.nan
                )
            elif m == "standardize":
                out[name] = (x - p["mean"]) / p["sd"]
            elif m == "robust":
                out[name] = (x - p["median"]) / p["iqr"]
            elif m == "winsorize":
                out[name] = x.clip(p["low"], p["high"])
            else:
                out[name] = pd.cut(
                    x, d["edges"], labels=d.get("labels"), right=d.get("right", False)
                )
        return out

    def fit_transform(self, frame: pd.DataFrame, weight: str | None = None) -> pd.DataFrame:
        """Fit on ``frame`` and transform it (use on the training rows only)."""
        return self.fit(frame, weight).transform(frame)

    def to_json(self) -> str:
        """The specification and fitted parameters as JSON."""
        spec = {
            k: {a: (list(map(float, b)) if a == "edges" else b) for a, b in v.items()}
            for k, v in self.spec.items()
        }
        return json.dumps({"spec": spec, "params": self.params}, indent=2, default=float)

    @classmethod
    def from_json(cls, text: str) -> Transformer:
        """Rebuild a fitted transformer from :meth:`to_json` output."""
        d = json.loads(text)
        t = cls(d["spec"])
        t.params = d["params"]
        t.fitted = True
        return t


def split_by_household(
    frame: pd.DataFrame, *, test_size: float = 0.2, seed: int = 0, group: str = "HOUSEID"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Train/test split that keeps all rows of a household together (no household in both sets).

    Persons and trips of one household are strongly dependent; a row-wise split leaks the
    household's characteristics from training into test and inflates every accuracy figure.
    """
    if not 0 < test_size < 1:
        raise ValueError("test_size must be in (0, 1)")
    ids = frame[group].drop_duplicates().to_numpy()
    rng = np.random.default_rng(seed)
    test_ids = set(rng.choice(ids, int(round(len(ids) * test_size)), replace=False))
    mask = frame[group].isin(test_ids)
    return frame[~mask].copy(), frame[mask].copy()


def recommend(series: pd.Series) -> list[str]:
    """Plain-language considerations (not a decision) for transforming ``series``."""
    x = pd.to_numeric(series, errors="coerce").dropna()
    if x.empty:
        return ["no numeric values"]
    notes = []
    if (x < 0).any():
        notes.append(
            "has negative values: log/sqrt/Box-Cox are undefined, consider yeojohnson or none"
        )
    if (x == 0).mean() > 0.05:
        notes.append(
            f"{(x == 0).mean():.0%} zeros: a log would drop them; log1p changes the meaning of zero; "
            "a two-part model may fit the zeros better than a transformation"
        )
    sd = x.std(ddof=0)
    sk = float(((x - x.mean()) ** 3).mean() / sd**3) if sd > 0 else 0.0
    if abs(sk) > 1:
        notes.append(
            f"skewness {sk:.1f}: a transformation can help a model that assumes symmetric errors, but "
            "skewness alone is not a reason; check the model residuals, not the marginal"
        )
    notes.append(
        "never fit on test rows; keep the original column; report results on the original scale"
    )
    return notes
