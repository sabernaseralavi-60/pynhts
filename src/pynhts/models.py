"""Design-aware regression for NHTS rows: weights and the wave's own variance design in one call.

Most published NHTS regressions are fitted unweighted with model-based standard errors. This module fits the same
models four ways so that the difference becomes a number instead of a debate:

* ``"naive"``     unweighted, model-based (iid) standard errors;
* ``"clustered"`` unweighted point estimates, household-clustered sandwich standard errors;
* ``"weighted"``  survey-weighted point estimates, household-clustered sandwich standard errors;
* ``"design"``    survey-weighted point estimates with the variance design of the wave: the jackknife over the
  replicate weights (2001, 2009, 2017) or the Taylor linearisation over strata and households (2022).

Families: ``"gaussian"`` (OLS), ``"binomial"`` (logit), ``"poisson"`` need only NumPy. ``"nb"`` (negative
binomial, NB2) additionally needs SciPy (``pip install scipy``) and, for the replicate variance, uses one-to-three
Newton steps from the full-sample optimum (validated against exact refits in the test suite).

>>> import pynhts                                                      # doctest: +SKIP
>>> d = pynhts.load(2017, replicates=True)                             # doctest: +SKIP
>>> p = d.persons(["R_AGE", "R_SEX", "CNTTDTR"])                       # doctest: +SKIP
>>> X = pd.DataFrame({"age": p["R_AGE"], "female": p["R_SEX"].eq("02")})   # doctest: +SKIP
>>> res = pynhts.models.fit(d, p, p["CNTTDTR"], X, family="poisson", level="person")   # doctest: +SKIP
>>> res.table()                                                        # doctest: +SKIP
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from math import erf, sqrt
from typing import Any, Literal

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from pynhts.core.flags import PynhtsWarning

Family = Literal["gaussian", "binomial", "poisson", "nb"]
Regime = Literal["naive", "clustered", "weighted", "design"]
Floats = NDArray[np.float64]

__all__ = ["ModelResult", "compare_regimes", "fit"]


# ------------------------------------------------------------------------------------------ result


@dataclass
class ModelResult:
    """Coefficients, standard errors and the design sentence of one fit."""

    terms: list[str]
    params: Floats
    se: Floats
    family: str
    regime: str
    n: int
    design: str
    df: float
    extra: dict[str, float] = field(default_factory=dict)

    def table(self, *, exp: bool = False, level: float = 0.95) -> pd.DataFrame:
        """One row per term: estimate, standard error, z, two-sided p-value (Student t on the degrees of freedom of the design, normal for the model-based fits) and a confidence interval."""
        from pynhts.stats.distributions import t_cdf, t_ppf

        z = self.params / self.se
        if np.isfinite(self.df) and self.df > 0:
            p = np.array([2.0 * (1.0 - t_cdf(abs(float(v)), self.df)) for v in z])
        else:
            p = np.array([1.0 - erf(abs(v) / sqrt(2.0)) for v in z])
        crit = t_ppf(0.5 + level / 2.0, self.df) if np.isfinite(self.df) and self.df > 0 else 1.96
        out: pd.DataFrame = pd.DataFrame(
            {
                "term": self.terms,
                "estimate": self.params,
                "se": self.se,
                "z": z,
                "p": p,
                "lower": self.params - crit * self.se,
                "upper": self.params + crit * self.se,
            }
        )
        if exp:
            for c in ("estimate", "lower", "upper"):
                out[c] = np.exp(out[c])
        out.attrs["pynhts"] = {
            "family": self.family,
            "regime": self.regime,
            "n": self.n,
            "design": self.design,
        }
        return out


# ------------------------------------------------------------------------------------------ GLM core


def _mean_funcs(family: str) -> tuple[Any, Any, Any]:
    if family == "gaussian":
        return (lambda e: e), (lambda m: np.ones_like(m)), (lambda m: np.ones_like(m))
    if family == "binomial":
        return (
            (lambda e: 1.0 / (1.0 + np.exp(-np.clip(e, -30, 30)))),
            (lambda m: m * (1.0 - m)),
            (lambda m: m * (1.0 - m)),
        )
    if family == "poisson":
        return (lambda e: np.exp(np.clip(e, -30, 30))), (lambda m: m), (lambda m: m)
    raise ValueError(f"unsupported family {family!r}")


def _irls(
    X: Floats,
    y: Floats,
    w: Floats,
    family: str,
    start: Floats | None = None,
    maxiter: int = 50,
    tol: float = 1e-9,
) -> Floats:
    mu_f, var_f, dmu_f = _mean_funcs(family)
    b = np.zeros(X.shape[1]) if start is None else start.copy()
    if start is None and family != "gaussian" and np.all(X[:, 0] == 1):
        m0 = float(np.average(y, weights=w))
        m0 = min(max(m0, 1e-3), 1 - 1e-3) if family == "binomial" else max(m0, 1e-3)
        b[0] = np.log(m0 / (1 - m0)) if family == "binomial" else np.log(m0)
    for _ in range(maxiter):
        eta = X @ b
        mu = mu_f(eta)
        dm = dmu_f(mu)
        wt = w * dm * dm / np.clip(var_f(mu), 1e-12, None)
        z = eta + (y - mu) / np.clip(dm, 1e-12, None)
        xtw = X.T * wt
        try:
            b_new = np.linalg.solve(xtw @ X, xtw @ z)
        except np.linalg.LinAlgError:
            b_new = np.linalg.lstsq(xtw @ X, xtw @ z, rcond=None)[0]
        step = float(np.max(np.abs(b_new - b)))
        b = b_new
        if step < tol:
            break
    return np.asarray(b, dtype=np.float64)


def _scores(X: Floats, y: Floats, b: Floats, family: str) -> Floats:
    mu_f, var_f, dmu_f = _mean_funcs(family)
    mu = mu_f(X @ b)
    s = dmu_f(mu) / np.clip(var_f(mu), 1e-12, None) * (y - mu)
    return np.asarray(X * s[:, None], dtype=np.float64)


def _information(X: Floats, b: Floats, w: Floats, family: str) -> Floats:
    mu_f, var_f, dmu_f = _mean_funcs(family)
    mu = mu_f(X @ b)
    dm = dmu_f(mu)
    wt = w * dm * dm / np.clip(var_f(mu), 1e-12, None)
    return np.asarray((X.T * wt) @ X, dtype=np.float64)


def _dispersion(family: str, X: Floats, y: Floats, w: Floats, b: Floats) -> float:
    if family != "gaussian":
        return 1.0
    r = y - X @ b
    return float(np.sum(w * r * r) / (len(y) - X.shape[1]))


# ------------------------------------------------------------------------------------------ NB2 (SciPy)


def _nb_parts(theta: Floats, X: Floats, y: Floats) -> tuple[Floats, Floats]:
    from scipy.special import digamma, gammaln

    b, la = theta[:-1], theta[-1]
    alpha = np.exp(la)
    r = 1.0 / alpha
    mu = np.exp(np.clip(X @ b, -30, 30))
    rm = r + mu
    ll = (
        gammaln(y + r)
        - gammaln(r)
        - gammaln(y + 1)
        + r * (np.log(r) - np.log(rm))
        + y * (np.log(mu) - np.log(rm))
    )
    sm = (y - mu) / (1.0 + alpha * mu)
    dl_dr = digamma(y + r) - digamma(r) + (np.log(r) - np.log(rm)) + (mu - y) / rm
    s = np.empty((len(y), X.shape[1] + 1))
    s[:, :-1] = X * sm[:, None]
    s[:, -1] = -r * dl_dr
    return np.asarray(ll), s


def _nb_fit(X: Floats, y: Floats, w: Floats, start: Floats | None = None) -> Floats:
    try:
        from scipy.optimize import minimize
    except ImportError as err:  # pragma: no cover
        raise ImportError("family='nb' needs SciPy: pip install scipy") from err
    w = w * (len(y) / w.sum())
    sd = X.std(axis=0)
    sd[sd < 1e-12] = 1.0
    scale = np.append(sd, 1.0)
    Xs = X / sd
    if start is None:
        start = np.zeros(X.shape[1] + 1)
        if np.all(X[:, 0] == 1):
            start[0] = np.log(max(float(np.average(y, weights=w)), 1e-3))

    def fg(t: Floats) -> tuple[float, Floats]:
        ll, s = _nb_parts(t, Xs, y)
        return -float(w @ ll), -(w @ s)

    res = minimize(
        fg,
        np.asarray(start) * scale,
        jac=True,
        method="L-BFGS-B",
        options={"maxiter": 500, "maxfun": 1000, "ftol": 1e-12, "gtol": 1e-8, "maxcor": 30},
    )
    theta = res.x / scale
    for _ in range(3):
        _, s = _nb_parts(theta, X, y)
        step = np.linalg.solve(_nb_info(theta, X, y, w), w @ s)
        theta = theta + step
        if float(np.max(np.abs(step))) < 1e-9:
            break
    return np.asarray(theta, dtype=np.float64)


def _nb_info(theta: Floats, X: Floats, y: Floats, w: Floats) -> Floats:
    p = len(theta)
    H = np.empty((p, p))
    for j in range(p):
        e = np.zeros(p)
        h = 1e-5 * max(1.0, abs(theta[j]))
        e[j] = h
        H[j] = -(w @ (_nb_parts(theta + e, X, y)[1] - _nb_parts(theta - e, X, y)[1])) / (2 * h)
    return np.asarray(0.5 * (H + H.T), dtype=np.float64)


def _nb_newton(theta: Floats, X: Floats, y: Floats, reps: Floats, steps: int = 3) -> Floats:
    """Replicate NB2 estimates: Newton step, then chord steps with the replicate information fixed."""
    p, g = len(theta), reps.shape[1]
    Hr = np.empty((g, p, p))
    for j in range(p):
        e = np.zeros(p)
        h = 1e-5 * max(1.0, abs(theta[j]))
        e[j] = h
        ds = (_nb_parts(theta + e, X, y)[1] - _nb_parts(theta - e, X, y)[1]) / (2 * h)
        Hr[:, :, j] = -(reps.T @ ds)
    Hsym = 0.5 * (Hr + Hr.transpose(0, 2, 1))
    hinv = np.linalg.inv(Hsym)
    est: Floats = theta + np.einsum("gij,gj->gi", hinv, reps.T @ _nb_parts(theta, X, y)[1])
    for _ in range(steps - 1):
        for r in range(g):
            est[r] = est[r] + hinv[r] @ (reps[:, r] @ _nb_parts(est[r], X, y)[1])
    return est


# ------------------------------------------------------------------------------------------ public API


def _design_arrays(survey: Any) -> tuple[Floats, Floats | None, str, float, Any]:
    """Row weights, row replicate weights (or None), factor, df and the design object."""
    unit = survey._unit
    w = np.asarray(survey._w[unit], dtype=np.float64)
    if hasattr(survey, "_r"):
        return (
            w,
            np.asarray(survey._r[unit], dtype=np.float64),
            "jackknife",
            float(survey.factor),
            survey,
        )
    return w, None, "taylor", 1.0, survey


def fit(
    data: Any,
    rows: pd.DataFrame,
    y: Any,
    X: pd.DataFrame,
    *,
    family: Family = "binomial",
    level: str = "person",
    regime: Regime = "design",
    intercept: bool = True,
    newton_steps: int = 3,
    cluster: Literal["household", "none"] = "household",
) -> ModelResult:
    """Fit ``y ~ X`` on ``rows`` under one of the four regimes.

    Args:
        data: The :class:`pynhts.NHTSData` the rows come from (gives the weights and the variance design).
        rows: Frame with the key columns of ``level`` (``HOUSEID``; plus ``PERSONID`` for person and trip rows).
        y: Outcome, aligned with ``rows``.
        X: Design matrix (numeric columns, no constant column).
        family: ``"gaussian"``, ``"binomial"``, ``"poisson"`` or ``"nb"``.
        level: Weight unit of the rows: ``"household"``, ``"person"`` or ``"trip"`` (person-day weight in 2017).
        regime: ``"naive"``, ``"weighted"`` or ``"design"``.
        intercept: Add a constant column named ``const`` (default).
        cluster: ``"household"`` (default) clusters the sandwich variance of the ``clustered`` and ``weighted`` regimes on
            ``HOUSEID``; ``"none"`` treats every observation as its own cluster (weights only).
        newton_steps: Negative binomial only: Newton/chord steps for each replicate.

    Raises:
        ValueError: rows with missing values in ``y`` or ``X`` (drop them first: the fit never drops silently).
    """
    if family not in ("gaussian", "binomial", "poisson", "nb"):
        raise ValueError(f"unsupported family {family!r}")
    Xd = X.copy()
    if intercept:
        Xd.insert(0, "const", 1.0)
    yv = np.asarray(pd.to_numeric(pd.Series(np.asarray(y)), errors="coerce"), dtype=np.float64)
    Xa = Xd.to_numpy(dtype=np.float64)
    if len(yv) != len(Xa) or len(rows) != len(yv):
        raise ValueError("rows, y and X must have the same length")
    if np.isnan(yv).any() or np.isnan(Xa).any():
        raise ValueError("missing values in y or X: drop or impute them explicitly before fitting")
    terms = list(Xd.columns)
    n = len(yv)
    if regime == "clustered":
        if cluster == "household" and "HOUSEID" not in rows.columns:
            raise KeyError("regime='clustered' needs a HOUSEID column in rows")
        w1 = np.ones(n)
        if family == "nb":
            th = _nb_fit(Xa, yv, w1)
            sc_rows, hess = _nb_parts(th, Xa, yv)[1], _nb_info(th, Xa, yv, w1)
            names = terms + ["log_alpha"]
            extra = {"alpha": float(np.exp(th[-1]))}
        else:
            th = _irls(Xa, yv, w1, family)
            sc_rows, hess = _scores(Xa, yv, th, family), _information(Xa, th, w1, family)
            names, extra = terms, {}
        cl = (
            np.asarray(pd.factorize(rows["HOUSEID"])[0], dtype=np.int64)
            if cluster == "household"
            else np.arange(n, dtype=np.int64)
        )
        tot = np.zeros((int(np.max(cl)) + 1, sc_rows.shape[1]))
        np.add.at(tot, cl, sc_rows)
        g = tot.shape[0]
        hi = np.linalg.inv(hess)
        cov = hi @ (tot.T @ tot * (g / (g - 1.0))) @ hi
        return ModelResult(
            names,
            th,
            np.sqrt(np.diag(cov)),
            family,
            regime,
            n,
            "unweighted, household-clustered sandwich variance",
            float(g - 1),
            extra,
        )
    if regime == "naive":
        w1 = np.ones(n)
        if family == "nb":
            th = _nb_fit(Xa, yv, w1)
            se = np.sqrt(np.diag(np.linalg.inv(_nb_info(th, Xa, yv, w1))))
            return ModelResult(
                terms + ["log_alpha"],
                th,
                se,
                family,
                regime,
                n,
                "unweighted, model-based variance",
                float("inf"),
                {"alpha": float(np.exp(th[-1]))},
            )
        b = _irls(Xa, yv, w1, family)
        se = np.sqrt(
            np.diag(np.linalg.inv(_information(Xa, b, w1, family)))
            * _dispersion(family, Xa, yv, w1, b)
        )
        return ModelResult(
            terms, b, se, family, regime, n, "unweighted, model-based variance", float("inf")
        )

    survey = data.survey_rows(rows, level)
    w, reps, kind, factor, svy = _design_arrays(survey)
    sc = n / w.sum()
    ws = w * sc
    if family == "nb":
        th = _nb_fit(Xa, yv, ws)
        b, nm = th, terms + ["log_alpha"]
    else:
        b, nm = _irls(Xa, yv, ws, family), terms
    if regime == "weighted":
        if family == "nb":
            s = _nb_parts(b, Xa, yv)[1]
            hess = _nb_info(b, Xa, yv, ws)
        else:
            s = _scores(Xa, yv, b, family)
            hess = _information(Xa, b, ws, family)
        cl = (
            np.asarray(pd.factorize(rows["HOUSEID"])[0], dtype=np.int64)
            if cluster == "household"
            else np.arange(n, dtype=np.int64)
        )
        c = np.zeros((int(np.max(cl)) + 1, s.shape[1]))
        np.add.at(c, cl, s * ws[:, None])
        g = c.shape[0]
        meat = c.T @ c * (g / (g - 1.0))
        hi = np.linalg.inv(hess)
        return ModelResult(
            nm,
            b,
            np.sqrt(np.diag(hi @ meat @ hi)),
            family,
            regime,
            n,
            "survey-weighted, household-clustered sandwich variance",
            float(g - 1),
        )
    if kind == "jackknife":
        assert reps is not None
        rs = (reps * sc).astype(np.float64)
        if family == "nb":
            full = _nb_newton(b, Xa, yv, ws[:, None], steps=newton_steps + 2)[0]
            bs = _nb_newton(full, Xa, yv, rs, steps=newton_steps)
            est = full
        else:
            est = _irls(Xa, yv, ws, family)
            bs = np.vstack(
                [
                    _irls(Xa, yv, rs[:, r], family, start=est, maxiter=8, tol=1e-7)
                    for r in range(rs.shape[1])
                ]
            )
        se = np.sqrt(factor * np.sum((bs - est) ** 2, axis=0))
        return ModelResult(
            nm,
            est,
            se,
            family,
            regime,
            n,
            svy.meta.design,
            float(svy.df),
            {"alpha": float(np.exp(est[-1]))} if family == "nb" else {},
        )
    # Taylor (2022): cluster totals of the weighted scores, stratified
    if family == "nb":
        s = _nb_parts(b, Xa, yv)[1]
        hess = _nb_info(b, Xa, yv, ws)
    else:
        s = _scores(Xa, yv, b, family)
        hess = _information(Xa, b, ws, family)
    cl_unit = svy._cluster[svy._unit]
    z = np.zeros((svy.n_clusters, s.shape[1]))
    np.add.at(z, cl_unit, s * ws[:, None])
    hi = np.linalg.inv(hess)
    cov = hi @ _taylor_cov(z, svy._stratum) @ hi
    return ModelResult(
        nm, b, np.sqrt(np.diag(cov)), family, regime, n, svy.meta.design, float(svy.df)
    )


def _taylor_cov(z: Floats, stratum: NDArray[np.int64]) -> Floats:
    n_h = np.bincount(stratum)
    k = z.shape[1]
    cov = np.zeros((k, k))
    for h in range(len(n_h)):
        zh = z[stratum == h]
        d = zh - zh.mean(axis=0)
        cov += n_h[h] / (n_h[h] - 1.0) * (d.T @ d)
    return cov


def compare_regimes(
    data: Any,
    rows: pd.DataFrame,
    y: Any,
    X: pd.DataFrame,
    *,
    family: Family = "binomial",
    level: str = "person",
    alpha: float = 0.05,
    **kw: Any,
) -> pd.DataFrame:
    """The four regimes side by side, with the verdict shifts a reader needs.

    Columns: ``b_*`` / ``se_*`` / ``p_*`` for ``naive``, ``clustered`` (unweighted, household-clustered), ``weighted``
    (weighted, household-clustered) and ``design``; ``se_ratio`` (design over naive), ``se_weighted_hc`` and ``se_ratio_weights`` (weighted sandwich with every
    observation its own cluster: the cost of unequal weights alone) and ``se_ratio_clustering`` (clustered over naive), ``sign_flip`` (naive and design disagree in sign) and ``sig_change``
    (significance at ``alpha`` differs between naive and design).

    A ``PynhtsWarning`` is raised when the design-aware fit changes the sign or the significance of a coefficient. The two
    fits estimate different things (an association in the sample against one in the population) and the design-aware
    standard errors also carry the cost of unequal weights; the warning asks for the design-aware result to be reported,
    not for the unweighted one to be called wrong.
    """
    fits = {
        r: fit(data, rows, y, X, family=family, level=level, regime=r, **kw).table()
        for r in ("naive", "clustered", "weighted", "design")
    }
    out: pd.DataFrame = pd.DataFrame({"term": fits["naive"]["term"]})
    for r, t in fits.items():
        out[f"b_{r}"], out[f"se_{r}"], out[f"p_{r}"] = (
            t["estimate"].to_numpy(),
            t["se"].to_numpy(),
            t["p"].to_numpy(),
        )
    hc = fit(
        data, rows, y, X, family=family, level=level, regime="weighted", cluster="none", **kw
    ).table()
    out["se_weighted_hc"] = hc["se"].to_numpy()
    out["se_ratio"] = out["se_design"] / out["se_naive"]
    out["se_ratio_weights"] = out["se_weighted_hc"] / out["se_naive"]
    out["se_ratio_clustering"] = out["se_clustered"] / out["se_naive"]
    out["sign_flip"] = np.sign(out["b_naive"]) != np.sign(out["b_design"])
    out["sig_change"] = (out["p_naive"] < alpha) != (out["p_design"] < alpha)
    flips = out[out["term"] != "const"]
    if bool(flips["sign_flip"].any() or flips["sig_change"].any()):
        warnings.warn(
            f"{int(flips['sign_flip'].sum())} sign flip(s) and {int(flips['sig_change'].sum())} significance change(s) "
            "between the unweighted and the design-aware fit: report the design-aware one for population claims",
            PynhtsWarning,
            stacklevel=2,
        )
    out.attrs["pynhts"] = {
        "family": family,
        "level": level,
        "design": fits["design"].attrs["pynhts"]["design"],
    }
    return out
