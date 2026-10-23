"""pynhts.models on a synthetic survey: point estimates, jackknife variance and regime plumbing, no NHTS files needed."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pynhts import models
from pynhts.stats import Survey


class _FakeData:
    """Just enough of NHTSData: ``survey_rows`` returns a jackknife Survey over person-day style units."""

    def __init__(self, n_units: int, g: int, seed: int = 0) -> None:
        rng = np.random.default_rng(seed)
        self.w = rng.uniform(0.5, 3.0, n_units) * 100
        drop = rng.integers(0, g, n_units)
        self.reps = np.array([np.where(drop == r, 0.0, self.w * g / (g - 1.0)) for r in range(g)]).T
        self.g = g

    def survey_rows(self, rows: pd.DataFrame, level: str) -> Survey:
        unit = np.arange(len(rows))
        return Survey(
            rows, unit, self.w, self.reps, level=0.95, df=self.g, factor=(self.g - 1.0) / self.g
        )


def _make(n=1500, seed=1):
    rng = np.random.default_rng(seed)
    rows = pd.DataFrame({"HOUSEID": np.arange(n) // 2, "PERSONID": np.arange(n) % 2})
    x1, x2 = rng.normal(size=n), rng.integers(0, 2, n).astype(float)
    p = 1 / (1 + np.exp(-(0.2 + 0.8 * x1 - 0.5 * x2)))
    y_bin = (rng.random(n) < p).astype(float)
    y_cnt = rng.poisson(np.exp(0.1 + 0.3 * x1 + 0.2 * x2)).astype(float)
    return rows, pd.DataFrame({"x1": x1, "x2": x2}), y_bin, y_cnt


def test_weighted_logit_point_estimate_equals_independent_solution():
    rows, X, y, _ = _make()
    data = _FakeData(len(rows), 20)
    res = models.fit(data, rows, y, X, family="binomial", regime="design")
    # independent Newton solution of the weighted score equations
    A = np.column_stack([np.ones(len(y)), X.to_numpy()])
    w = data.w * len(y) / data.w.sum()
    b = np.zeros(3)
    for _ in range(40):
        mu = 1 / (1 + np.exp(-A @ b))
        b += np.linalg.solve((A.T * (w * mu * (1 - mu))) @ A, A.T @ (w * (y - mu)))
    assert np.allclose(res.params, b, atol=1e-7)


def test_design_standard_error_is_the_jackknife_of_exact_refits():
    rows, X, y, _ = _make()
    data = _FakeData(len(rows), 20)
    res = models.fit(data, rows, y, X, family="binomial", regime="design")
    A = np.column_stack([np.ones(len(y)), X.to_numpy()])
    sc = len(y) / data.w.sum()

    def solve(w):
        b = np.zeros(3)
        for _ in range(60):
            mu = 1 / (1 + np.exp(-A @ b))
            b += np.linalg.solve((A.T * (w * mu * (1 - mu))) @ A, A.T @ (w * (y - mu)))
        return b

    full = solve(data.w * sc)
    reps = np.array([solve(data.reps[:, r] * sc) for r in range(data.g)])
    se = np.sqrt((data.g - 1.0) / data.g * np.sum((reps - full) ** 2, axis=0))
    assert np.allclose(res.se, se, rtol=2e-4)


def test_regimes_and_table_and_compare():
    rows, X, y, yc = _make()
    data = _FakeData(len(rows), 20)
    naive = models.fit(data, rows, yc, X, family="poisson", regime="naive")
    weighted = models.fit(data, rows, yc, X, family="poisson", regime="weighted")
    design = models.fit(data, rows, yc, X, family="poisson", regime="design")
    assert naive.terms == ["const", "x1", "x2"] and naive.design.startswith("unweighted")
    assert weighted.n == design.n == len(y)
    assert np.allclose(
        weighted.params, design.params, atol=1e-7
    )  # same weighted estimator, different variance
    t = design.table(exp=True)
    assert {"estimate", "se", "p", "lower", "upper"} <= set(t.columns)
    assert t.attrs["pynhts"]["regime"] == "design"
    cmp = models.compare_regimes(data, rows, y, X, family="binomial")
    assert {"se_ratio", "se_clustered", "se_ratio_clustering", "sign_flip", "sig_change"} <= set(
        cmp.columns
    )
    assert np.allclose(
        cmp["b_clustered"], cmp["b_naive"], atol=1e-8
    )  # same unweighted estimate, different variance


def test_clustered_regime_matches_a_brute_force_sandwich():
    rows, X, y, _ = _make(600)
    rows = rows.assign(HOUSEID=np.arange(len(rows)) // 5)  # clusters of five
    res = models.fit(_FakeData(len(rows), 10), rows, y, X, family="binomial", regime="clustered")
    A = np.column_stack([np.ones(len(y)), X.to_numpy()])
    b = res.params
    mu = 1 / (1 + np.exp(-A @ b))
    bread = np.linalg.inv((A.T * (mu * (1 - mu))) @ A)
    sc = A * (y - mu)[:, None]
    tot = np.array([sc[rows["HOUSEID"].to_numpy() == g].sum(0) for g in np.unique(rows["HOUSEID"])])
    g = len(tot)
    cov = bread @ (tot.T @ tot * g / (g - 1)) @ bread
    assert np.allclose(res.se, np.sqrt(np.diag(cov)), rtol=1e-6)


def test_refuses_missing_values_instead_of_dropping():
    rows, X, y, _ = _make(200)
    y = y.copy()
    y[3] = np.nan
    with pytest.raises(ValueError, match="missing"):
        models.fit(_FakeData(len(rows), 10), rows, y, X, family="binomial", regime="design")


def test_negative_binomial_replicates_match_exact_refits():
    pytest.importorskip("scipy")
    rng = np.random.default_rng(4)
    n = 2500
    rows = pd.DataFrame({"HOUSEID": np.arange(n), "PERSONID": 0})
    X = pd.DataFrame({"x": rng.normal(size=n)})
    mu = np.exp(0.2 + 0.4 * X["x"].to_numpy())
    y = rng.negative_binomial(2.0, 2.0 / (2.0 + mu)).astype(float)
    data = _FakeData(n, 12, seed=2)
    res = models.fit(data, rows, y, X, family="nb", regime="design")
    sc = n / data.w.sum()
    full = models._nb_fit(np.column_stack([np.ones(n), X["x"]]), y, data.w * sc)
    reps = np.array(
        [
            models._nb_fit(
                np.column_stack([np.ones(n), X["x"]]), y, data.reps[:, r] * sc, start=full
            )
            for r in range(data.g)
        ]
    )
    se = np.sqrt((data.g - 1.0) / data.g * np.sum((reps - full) ** 2, axis=0))
    assert np.allclose(res.params, full, atol=1e-5)
    assert np.allclose(res.se, se, rtol=0.03)


def test_weighted_without_clustering_equals_clusters_of_one():
    rows, X, y, _ = _make(500)
    data = _FakeData(len(rows), 10)
    solo = rows.assign(HOUSEID=np.arange(len(rows)))  # every observation its own household
    a = models.fit(data, solo, y, X, family="binomial", regime="weighted")
    b = models.fit(data, rows, y, X, family="binomial", regime="weighted", cluster="none")
    assert np.allclose(a.se, b.se, rtol=1e-9)
