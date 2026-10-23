"""Shared engine of paper 02: paper-style versus design-aware model fits on NHTS rows.

Three estimation regimes are compared for every regression the studies publish:

* ``naive``   - unweighted, model-based (iid) standard errors: what most of the studied papers report;
* ``weighted`` - survey-weighted point estimates, model-based standard errors treated as if the weights
  were frequency weights scaled to the sample size (what Stata ``[pweight]`` without svy gives, up to the
  robust correction);
* ``design``  - survey-weighted point estimates with replicate-weight (jackknife) standard errors from the
  wave's own variance design, i.e. what the NHTS User's Guide prescribes.

Only numpy is needed for the point estimates (IRLS with a warm start for the replicate refits), so a full
JKn refit of a 30-term logistic regression on 130,000 rows takes about half a minute.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parents[1]
RESULTS = HERE / "results"


def setup() -> None:
    """Use the working-tree package and the local parquet cache."""
    sys.path.insert(0, str(ROOT / "src"))
    os.environ.setdefault("PYNHTS_CACHE_DIR", str(ROOT / "local_data" / "cache"))
    (RESULTS / "tables").mkdir(parents=True, exist_ok=True)
    (RESULTS / "numbers").mkdir(parents=True, exist_ok=True)


# ----------------------------------------------------------------------------- designs

@dataclass
class Design:
    """Row-level weights and replicate weights bound to one analysis frame."""

    w: np.ndarray  # (n,) full-sample weight
    reps: np.ndarray  # (n, G) replicate weights (float32)
    factor: float  # variance multiplier (6/7 in 2017, 99/100 in 2009, 98/99 in 2001)
    df: float
    cluster: np.ndarray  # household code per row, for robust variance

    @property
    def n_reps(self) -> int:
        return self.reps.shape[1]


def design_for(data, rows: pd.DataFrame, level: str) -> Design:
    """Bind ``rows`` (must carry HOUSEID, and PERSONID for person rows) to the replicate design of ``data``."""
    s = data.survey_rows(rows, level)
    if not hasattr(s, "_r"):
        raise ValueError(f"wave {data.wave} has no replicate weights (Taylor design): use taylor_design_for")
    unit = s._unit
    reps = s._r[unit].astype(np.float32)
    w = s._w[unit].astype(np.float64)
    cl = pd.factorize(rows["HOUSEID"])[0]
    return Design(w=w, reps=reps, factor=float(s.factor), df=float(s.df), cluster=cl)


# ----------------------------------------------------------------------------- IRLS

def _link(family: str):
    if family == "gaussian":
        return (lambda eta: eta), (lambda mu: np.ones_like(mu)), (lambda mu: np.ones_like(mu))
    if family == "binomial":
        def mu_(eta):
            return 1.0 / (1.0 + np.exp(-np.clip(eta, -30, 30)))
        return mu_, (lambda mu: mu * (1 - mu)), (lambda mu: mu * (1 - mu))
    if family == "poisson":
        def mu_(eta):
            return np.exp(np.clip(eta, -30, 30))
        return mu_, (lambda mu: mu), (lambda mu: mu)
    raise ValueError(family)


def irls(X: np.ndarray, y: np.ndarray, w: np.ndarray, family: str, start: np.ndarray | None = None,
         maxiter: int = 50, tol: float = 1e-9, offset: np.ndarray | None = None):
    """Weighted GLM by IRLS. Returns (beta, XtWX-inverse-ready info matrix, converged)."""
    mu_f, var_f, dmu_f = _link(family)
    n, p = X.shape
    off = np.zeros(n) if offset is None else offset
    b = np.zeros(p) if start is None else start.copy()
    if start is None and family != "gaussian":
        m0 = (np.average(y, weights=w) + (0.5 if family == "binomial" else 0.1)) / (1.5 if family == "binomial" else 1.0)
        if family == "binomial":
            m0 = min(max(np.average(y, weights=w), 1e-3), 1 - 1e-3)
            b[0] = np.log(m0 / (1 - m0)) if np.all(X[:, 0] == 1) else 0.0
        else:
            b[0] = np.log(max(np.average(y, weights=w), 1e-3)) if np.all(X[:, 0] == 1) else 0.0
    ok = False
    for _ in range(maxiter):
        eta = X @ b + off
        mu = mu_f(eta)
        v = var_f(mu)
        dm = dmu_f(mu)
        W = w * dm * dm / np.clip(v, 1e-12, None)
        z = eta - off + (y - mu) / np.clip(dm, 1e-12, None)
        XtW = X.T * W
        A = XtW @ X
        try:
            b_new = np.linalg.solve(A, XtW @ z)
        except np.linalg.LinAlgError:
            b_new = np.linalg.lstsq(A, XtW @ z, rcond=None)[0]
        step = np.max(np.abs(b_new - b))
        b = b_new
        if step < tol:
            ok = True
            break
    return b, A, ok


def _dispersion(family: str, X, y, w, b, off=None) -> float:
    if family != "gaussian":
        return 1.0
    r = y - X @ b
    return float(np.sum(w * r * r) / (len(y) - X.shape[1]))


def fit_regimes(X: pd.DataFrame, y: np.ndarray, design: Design | None, family: str,
                weight_scale: str = "sample", replicates: bool = True, robust_cluster: bool = True,
                regimes: tuple[str, ...] = ("naive", "weighted", "design")) -> pd.DataFrame:
    """Fit ``y ~ X`` (X includes the constant column named ``const``) under the three regimes.

    Returns one row per term with b/se/p for each regime.
    """
    from math import erf, sqrt

    cols = list(X.columns)
    Xa = X.to_numpy(float)
    y = np.asarray(y, float)
    n = len(y)
    out = {"term": cols}

    def pval(z):
        return np.array([1 - erf(abs(v) / sqrt(2)) for v in z])

    if "naive" in regimes:
        b, A, _ = irls(Xa, y, np.ones(n), family)
        phi = _dispersion(family, Xa, y, np.ones(n), b)
        se = np.sqrt(np.diag(np.linalg.inv(A)) * phi)
        out.update({"b_naive": b, "se_naive": se, "p_naive": pval(b / se)})
    if design is not None and ("weighted" in regimes or "design" in regimes):
        w = design.w * (n / design.w.sum() if weight_scale == "sample" else 1.0)
        bw, Aw, _ = irls(Xa, y, w, family)
        if "weighted" in regimes:
            phi = _dispersion(family, Xa, y, w, bw)
            se = np.sqrt(np.diag(np.linalg.inv(Aw)) * phi)
            out.update({"b_weighted": bw, "se_weighted_model": se})
            # household-clustered sandwich (Stata svy, one stage)
            if robust_cluster:
                se_r = _sandwich_cluster(Xa, y, w, bw, family, design.cluster, Aw)
                out["se_weighted_robust"] = se_r
                out["p_weighted"] = pval(bw / se_r)
        if "design" in regimes and replicates:
            wf = design.w
            bw_full, _, _ = irls(Xa, y, wf, family)
            B = np.empty((design.n_reps, len(cols)))
            for g in range(design.n_reps):
                B[g], _, _ = irls(Xa, y, design.reps[:, g].astype(np.float64), family, start=bw_full, maxiter=8, tol=1e-7)
            var = design.factor * np.sum((B - bw_full) ** 2, axis=0)
            se_d = np.sqrt(var)
            out.update({"b_design": bw_full, "se_design": se_d, "p_design": pval(bw_full / se_d)})
    return pd.DataFrame(out)


def _sandwich_cluster(X, y, w, b, family, cl, A):
    mu_f, var_f, dmu_f = _link(family)
    eta = X @ b
    mu = mu_f(eta)
    v = var_f(mu)
    dm = dmu_f(mu)
    # score per row for weighted pseudo-likelihood: w * dm/v * (y - mu) * x
    sc = (w * dm / np.clip(v, 1e-12, None) * (y - mu))[:, None] * X
    G = int(cl.max()) + 1
    S = np.zeros((G, X.shape[1]))
    np.add.at(S, cl, sc)
    meat = S.T @ S * (G / (G - 1))
    Ai = np.linalg.inv(A)
    return np.sqrt(np.diag(Ai @ meat @ Ai))


# ----------------------------------------------------------------------------- reporting helpers

def odds(df: pd.DataFrame, suffixes=("naive", "weighted", "design")) -> pd.DataFrame:
    out = df.copy()
    for s in suffixes:
        if f"b_{s}" in out:
            out[f"or_{s}"] = np.exp(out[f"b_{s}"])
    return out


def verdict_shift(df: pd.DataFrame, a: str = "naive", b: str = "design", alpha: float = 0.05) -> pd.DataFrame:
    """Flag sign changes and significance changes between two regimes (constant excluded)."""
    d = df[df["term"] != "const"].copy()
    sa, sb = np.sign(d[f"b_{a}"]), np.sign(d[f"b_{b}"])
    d["sign_flip"] = (sa != sb) & (sa != 0)
    d["sig_a"] = d[f"p_{a}"] < alpha
    d["sig_b"] = d[f"p_{b}"] < alpha
    d["sig_change"] = d["sig_a"] != d["sig_b"]
    d["se_ratio"] = d[f"se_{b}"] / d[f"se_{a}"] if f"se_{a}" in d else np.nan
    d["b_shift_pct"] = (d[f"b_{b}"] - d[f"b_{a}"]) / d[f"b_{a}"].abs() * 100
    return d


class Timer:
    def __enter__(self):
        self.t0 = time.time()
        return self

    def __exit__(self, *a):
        self.dt = time.time() - self.t0
