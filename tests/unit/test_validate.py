"""pynhts.validate: weighted AUC against brute force, SMOTE balance and the leakage audit on a planted-leak example."""

from __future__ import annotations

import numpy as np
import pytest

from pynhts import validate
from pynhts.core.flags import PynhtsWarning


def _auc_bruteforce(y, s, w):
    pos, neg = np.flatnonzero(y == 1), np.flatnonzero(y == 0)
    num = den = 0.0
    for i in pos:
        for j in neg:
            ww = w[i] * w[j]
            den += ww
            num += ww * (1.0 if s[i] > s[j] else 0.5 if s[i] == s[j] else 0.0)
    return num / den


def test_weighted_auc_matches_pairwise_definition_with_ties():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 120)
    s = np.round(rng.normal(size=120) + 0.8 * y, 1)  # ties on purpose
    w = rng.uniform(0.5, 3.0, 120)
    assert validate.weighted_auc(y, s, w) == pytest.approx(_auc_bruteforce(y, s, w))
    assert validate.weighted_auc(y, s) == pytest.approx(_auc_bruteforce(y, s, np.ones(120)))


def test_smote_balances_classes_and_stays_between_neighbours():
    rng = np.random.default_rng(1)
    X = np.vstack([rng.normal(0, 1, (300, 3)), rng.normal(4, 0.5, (30, 3))])
    y = np.r_[np.zeros(300, int), np.ones(30, int)]
    Xb, yb = validate.smote(X, y, seed=3)
    assert yb.sum() == 300 and (yb == 0).sum() == 300
    new = Xb[len(X) :]
    assert new.min() >= X[y == 1].min() - 1e-9 and new.max() <= X[y == 1].max() + 1e-9


def test_group_split_keeps_groups_together():
    groups = np.repeat(np.arange(100), 3)
    tr, te = validate.group_split(groups, test_size=0.3, seed=2)
    assert not (set(groups[tr]) & set(groups[te])) and len(tr) + len(te) == 300


def test_audit_detects_the_leak_with_a_nearest_neighbour_model():
    """With pure noise features a 1-nearest-neighbour rule memorises: resampling first lets copies reach the test rows."""

    class OneNN:
        def fit(self, X, y):
            self.X, self.y = X, y
            return self

        def predict_proba(self, X):
            d = ((X[:, None, :] - self.X[None, :, :]) ** 2).sum(-1)
            p1 = self.y[d.argmin(1)].astype(float)
            return np.column_stack([1 - p1, p1])

    rng = np.random.default_rng(5)
    n = 500
    X = rng.normal(size=(n, 4))
    y = (rng.random(n) < 0.1).astype(int)  # no signal at all
    groups = np.arange(n) // 2
    with pytest.warns(PynhtsWarning):
        rep = validate.audit_classifier(OneNN, X, y, groups, seeds=(0, 1))
    assert rep.inflation_auc > 0.1
    assert abs(rep.table.loc["grouped", "auc"] - 0.5) < 0.12
