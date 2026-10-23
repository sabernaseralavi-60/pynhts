"""The ZINB engine: analytic scores equal finite differences, and the optimum equals statsmodels."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import countmodels as cm  # noqa: E402


def _data(n=4000, seed=1):
    rng = np.random.default_rng(seed)
    X = np.column_stack([np.ones(n), rng.normal(size=n), rng.integers(0, 2, n)])
    Z = np.column_stack([np.ones(n), rng.normal(size=n)])
    mu = np.exp(0.3 + 0.4 * X[:, 1] - 0.3 * X[:, 2])
    pi = 1 / (1 + np.exp(-(-0.5 + 0.8 * Z[:, 1])))
    r = 2.0
    y = rng.negative_binomial(r, r / (r + mu))
    y = np.where(rng.random(n) < pi, 0, y)
    return X, Z, y.astype(float)


@pytest.mark.parametrize("inflated", [True, False])
def test_scores_match_finite_differences(inflated):
    X, Z, y = _data()
    Zm = Z if inflated else None
    p = X.shape[1] + (Z.shape[1] if inflated else 0) + 1
    theta = np.linspace(-0.3, 0.3, p)
    ll, S = cm.row_scores(theta, X, Zm, y)
    num = np.empty(p)
    for j in range(p):
        e = np.zeros(p)
        e[j] = 1e-6
        num[j] = (cm.row_scores(theta + e, X, Zm, y)[0].sum() - cm.row_scores(theta - e, X, Zm, y)[0].sum()) / 2e-6
    assert np.allclose(S.sum(0), num, rtol=1e-4, atol=1e-4)


def test_matches_statsmodels():
    sm = pytest.importorskip("statsmodels.discrete.count_model")
    X, Z, y = _data()
    th, _ = cm.fit(X, Z, y)
    m = sm.ZeroInflatedNegativeBinomialP(y, X, exog_infl=Z, inflation="logit", p=2)
    r = m.fit(method="bfgs", maxiter=2000, disp=0)
    # statsmodels order: inflate, count, alpha
    kz, kx = Z.shape[1], X.shape[1]
    sm_count = np.asarray(r.params)[kz:kz + kx]
    sm_infl = np.asarray(r.params)[:kz]
    assert np.allclose(th[:kx], sm_count, atol=2e-3)
    assert np.allclose(th[kx:kx + kz], sm_infl, atol=5e-3)
    assert np.isclose(np.exp(th[-1]), np.asarray(r.params)[-1], rtol=2e-2)


@pytest.mark.parametrize("inflated", [True, False])
def test_newton_replicates_match_refits(inflated):
    import engine

    X, Z, y = _data(n=6000, seed=3)
    Zm = Z if inflated else None
    rng = np.random.default_rng(5)
    G = 8
    reps = np.where(rng.random((len(y), G)) < 0.15, 0.0, 1.0 / 0.85).astype(np.float32)
    des = engine.Design(w=np.ones(len(y)), reps=reps, factor=1.0, df=G, cluster=np.arange(len(y)))
    th, _ = cm.fit(X, Zm, y)
    B = cm.replicate_newton(th, X, Zm, y, des, steps=4)
    for r in range(G):
        ex, _ = cm.fit(X, Zm, y, reps[:, r].astype(float), start=th, ftol=1e-13)
        assert np.allclose(B[r], ex, atol=3e-3), (r, np.max(np.abs(B[r] - ex)))
