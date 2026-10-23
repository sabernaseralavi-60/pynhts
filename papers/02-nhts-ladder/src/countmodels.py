"""Weighted negative-binomial (NB2) and zero-inflated negative-binomial (ZINB) models with analytic scores.

Parameters are packed as [beta (count part), gamma (logit inflation part, optional), log_alpha].
The same code serves the paper-style fit (unit weights), the survey-weighted fit and the
replicate-weight refits that give design-based standard errors.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import digamma, expit, gammaln

import engine


def _unpack(theta, kx, kz):
    b = theta[:kx]
    g = theta[kx:kx + kz] if kz else None
    la = theta[-1]
    return b, g, la


def row_scores(theta, X, Z, y):
    """Per-row log-likelihood and its gradient (n x p). Z is None for plain NB2."""
    kx = X.shape[1]
    kz = 0 if Z is None else Z.shape[1]
    b, g, la = _unpack(theta, kx, kz)
    alpha = np.exp(la)
    r = 1.0 / alpha
    mu = np.exp(np.clip(X @ b, -30, 30))
    n = len(y)
    rm = r + mu
    logp0 = r * (np.log(r) - np.log(rm))  # log NB(0)
    p0 = np.exp(logp0)
    ll_nb = gammaln(y + r) - gammaln(r) - gammaln(y + 1) + logp0 + y * (np.log(mu) - np.log(rm))
    score_mu = (y - mu) / (1.0 + alpha * mu)  # d ll_nb / d eta_mu
    dl_dr = digamma(y + r) - digamma(r) + (np.log(r) - np.log(rm)) + (mu - y) / rm
    dl_dla = -r * dl_dr  # d/dlog_alpha, valid for y > 0 (and for the NB part generally)
    # d logp0 / d log_alpha
    dlogp0_dr = np.log(r) - np.log(rm) + 1.0 - r / rm
    dlogp0_dla = -r * dlogp0_dr
    if Z is None:
        ll = ll_nb
        S = np.empty((n, kx + 1))
        S[:, :kx] = X * score_mu[:, None]
        S[:, -1] = dl_dla
        return ll, S
    pi = expit(np.clip(Z @ g, -30, 30))
    A = pi + (1.0 - pi) * p0
    pos = y > 0
    ll = np.where(pos, np.log(1.0 - pi) + ll_nb, np.log(np.clip(A, 1e-300, None)))
    # count-mean score
    d_eta_mu0 = (1.0 - pi) * (-p0 * mu / rm) / A  # y == 0 (note mu/(1+alpha mu) = mu*r/rm ... use exact form below)
    # exact: d p0 / d eta_mu = -p0 * mu / (1 + alpha mu)
    d_eta_mu0 = (1.0 - pi) * (-p0 * mu / (1.0 + alpha * mu)) / A
    sm = np.where(pos, score_mu, d_eta_mu0)
    sg = np.where(pos, -pi, pi * (1.0 - pi) * (1.0 - p0) / A)
    d_la0 = (1.0 - pi) * p0 * dlogp0_dla / A
    sla = np.where(pos, dl_dla, d_la0)
    S = np.empty((n, kx + kz + 1))
    S[:, :kx] = X * sm[:, None]
    S[:, kx:kx + kz] = Z * sg[:, None]
    S[:, -1] = sla
    return ll, S


def _col_scale(M):
    sd = M.std(0)
    sd[sd < 1e-12] = 1.0
    return sd


def fit(X, Z, y, w=None, start=None, maxiter=500, ftol=1e-12, polish=3):
    """Maximum likelihood: L-BFGS on standardised columns, then Newton polishing on the original scale."""
    X = np.asarray(X, float)
    Z = None if Z is None else np.asarray(Z, float)
    y = np.asarray(y, float)
    w = np.ones(len(y)) if w is None else np.asarray(w, float)
    w = w * (len(y) / w.sum())  # scale-free objective
    kx = X.shape[1]
    kz = 0 if Z is None else Z.shape[1]
    sx = _col_scale(X)
    sz = None if Z is None else _col_scale(Z)
    Xs, Zs = X / sx, (None if Z is None else Z / sz)
    scale = np.concatenate([sx, sz if sz is not None else [], [1.0]])
    if start is None:
        t0 = np.zeros(kx + kz + 1)
        if np.all(X[:, 0] == 1):
            t0[0] = np.log(max(np.average(y, weights=w), 1e-3))
        if Z is not None and np.all(Z[:, 0] == 1):
            t0[kx] = -1.0
        start = t0
    t_s = np.asarray(start, float) * scale  # theta_scaled = theta * scale

    def fg(theta):
        ll, S = row_scores(theta, Xs, Zs, y)
        return -(w @ ll), -(w @ S)

    res = minimize(fg, t_s, jac=True, method="L-BFGS-B",
                   options={"maxiter": maxiter, "maxfun": maxiter * 2, "ftol": ftol, "gtol": 1e-8, "maxcor": 30})
    theta = res.x / scale
    for _ in range(polish):
        _, S = row_scores(theta, X, Z, y)
        g = w @ S
        H = info_matrix(theta, X, Z, y, w)
        try:
            step = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            break
        theta = theta + step
        if np.max(np.abs(step)) < 1e-9:
            break
    res.x = theta
    return theta, res


def info_matrix(theta, X, Z, y, w):
    """Observed information by central differences of the analytic weighted gradient."""
    p = len(theta)
    H = np.empty((p, p))
    h = 1e-5
    for j in range(p):
        e = np.zeros(p)
        e[j] = h * max(1.0, abs(theta[j]))
        _, Sp = row_scores(theta + e, X, Z, y)
        _, Sm = row_scores(theta - e, X, Z, y)
        H[j] = -(w @ (Sp - Sm)) / (2 * e[j])
    return 0.5 * (H + H.T)


def replicate_newton(theta, X, Z, y, design: engine.Design, steps: int = 3):
    """Replicate estimates by Newton / chord iterations started at the full-sample optimum.

    For replicate weights w_r the first Newton step is theta + H_r^{-1} g_r with g_r = sum w_r S_i(theta) and
    H_r = -sum w_r dS_i/dtheta; later steps re-evaluate the scores at the updated estimate and reuse H_r (chord).
    The per-row derivative of the score is a central difference of the analytic scores, so H_r for all replicates
    costs 2p score evaluations plus p matrix products.
    """
    X = np.asarray(X, float)
    Z = None if Z is None else np.asarray(Z, float)
    y = np.asarray(y, float)
    p = len(theta)
    R = design.reps.astype(np.float64)  # (n, G)
    G = R.shape[1]
    Hr = np.empty((G, p, p))
    for j in range(p):
        e = np.zeros(p)
        h = 1e-5 * max(1.0, abs(theta[j]))
        e[j] = h
        _, Sp = row_scores(theta + e, X, Z, y)
        _, Sm = row_scores(theta - e, X, Z, y)
        Hr[:, :, j] = -(R.T @ ((Sp - Sm) / (2 * h)))  # (G, p): column j of H_r
    Hr = 0.5 * (Hr + Hr.transpose(0, 2, 1))
    Hinv = np.linalg.inv(Hr)
    _, S0 = row_scores(theta, X, Z, y)
    B = np.empty((G, p))
    g = R.T @ S0  # (G, p)
    B[:] = theta + np.einsum("gij,gj->gi", Hinv, g)
    for _ in range(steps - 1):
        for r in range(G):
            _, Sr = row_scores(B[r], X, Z, y)
            B[r] = B[r] + Hinv[r] @ (R[:, r] @ Sr)
    return B


def fit_regimes(Xdf: pd.DataFrame, Zdf: pd.DataFrame | None, y, design: engine.Design | None,
                replicates: bool = True, weight_scale: str = "sample", regimes=("naive", "weighted", "design"),
                newton_steps: int = 3):
    """Fit under the three regimes; returns a long table (part, term, b_*, se_*, p_*)."""
    from math import erf, sqrt

    X = Xdf.to_numpy(float)
    Z = None if Zdf is None else Zdf.to_numpy(float)
    y = np.asarray(y, float)
    n = len(y)
    names = [("count", c) for c in Xdf.columns]
    if Z is not None:
        names += [("inflate", c) for c in Zdf.columns]
    names += [("alpha", "log_alpha")]
    out = pd.DataFrame(names, columns=["part", "term"])

    def pval(z):
        return np.array([1 - erf(abs(v) / sqrt(2)) for v in z])

    th0, r0 = fit(X, Z, y)
    if "naive" in regimes:
        H = info_matrix(th0, X, Z, y, np.ones(n))
        se = np.sqrt(np.diag(np.linalg.inv(H)))
        out["b_naive"], out["se_naive"], out["p_naive"] = th0, se, pval(th0 / se)
        out.attrs["naive_converged"] = bool(r0.success)
        out.attrs["ll_naive"] = float(-r0.fun)
    if design is not None:
        w = design.w * (n / design.w.sum() if weight_scale == "sample" else 1.0)
        thw, rw = fit(X, Z, y, w, start=th0)
        if "weighted" in regimes:
            H = info_matrix(thw, X, Z, y, w)
            se_m = np.sqrt(np.diag(np.linalg.inv(H)))
            _, S = row_scores(thw, X, Z, y)
            sc = S * w[:, None]
            G = int(design.cluster.max()) + 1
            C = np.zeros((G, S.shape[1]))
            np.add.at(C, design.cluster, sc)
            meat = C.T @ C * (G / (G - 1))
            Hi = np.linalg.inv(H)
            se_r = np.sqrt(np.diag(Hi @ meat @ Hi))
            out["b_weighted"], out["se_weighted_model"], out["se_weighted_robust"] = thw, se_m, se_r
            out["p_weighted"] = pval(thw / se_r)
        if "design" in regimes and replicates:
            sc = n / design.w.sum()
            scaled = engine.Design(w=design.w * sc, reps=(design.reps * np.float32(sc)).astype(np.float32),
                                   factor=design.factor, df=design.df, cluster=design.cluster)
            full = engine.Design(w=scaled.w, reps=scaled.w[:, None].astype(np.float32), factor=1.0, df=1.0, cluster=design.cluster)
            thf = replicate_newton(thw, X, Z, y, full, steps=newton_steps + 2)[0]
            B = replicate_newton(thf, X, Z, y, scaled, steps=newton_steps)
            se_d = np.sqrt(design.factor * np.sum((B - thf) ** 2, axis=0))
            out["b_design"], out["se_design"], out["p_design"] = thf, se_d, pval(thf / se_d)
    return out
