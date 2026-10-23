"""Leakage-aware evaluation of machine-learning models on NHTS rows.

NHTS rows are not independent (persons and trips of one household share everything that matters) and the usual
imbalanced-class fix, SMOTE, invents rows from neighbours. Two common orderings therefore inflate scores:

* oversampling **before** the split (synthetic copies of a test row sit in the training set);
* splitting **rows** instead of **households**.

:func:`audit_classifier` scores one model under four pipelines that differ only in those two choices and returns the
inflation of the headline score, so a reported AUC can be read against what a sound design would give.

Only NumPy is needed here. The estimator is any object with scikit-learn's ``fit`` and ``predict_proba`` (or
``decision_function``); a factory (a function returning a fresh estimator) is passed so that every fit starts clean.

>>> from sklearn.ensemble import RandomForestClassifier                       # doctest: +SKIP
>>> rep = validate.audit_classifier(lambda: RandomForestClassifier(200), X, y, groups=household_ids)   # doctest: +SKIP
>>> rep.table, rep.inflation_auc                                              # doctest: +SKIP
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from pynhts.core.flags import PynhtsWarning

Floats = NDArray[np.float64]
__all__ = ["PIPELINES", "AuditReport", "audit_classifier", "group_split", "smote", "weighted_auc"]

PIPELINES = ("resample_then_split", "split_then_resample", "grouped", "grouped_weighted")


def group_split(
    groups: Any, *, test_size: float = 0.3, seed: int = 0
) -> tuple[NDArray[np.intp], NDArray[np.intp]]:
    """Row indices of a train/test split that keeps every group (household) on one side."""
    g = np.asarray(pd.factorize(np.asarray(groups))[0], dtype=np.int64)
    rng = np.random.default_rng(seed)
    ids = np.arange(int(np.max(g)) + 1)
    test_ids = rng.choice(ids, int(round(len(ids) * test_size)), replace=False)
    mask = np.isin(g, test_ids)
    return np.flatnonzero(~mask), np.flatnonzero(mask)


def smote(X: Any, y: Any, *, seed: int = 0, k: int = 5) -> tuple[Floats, NDArray[np.int_]]:
    """SMOTE (Chawla et al. 2002) for a binary 0/1 outcome: balance the classes with interpolated minority rows.

    Apply it to the **training** part only; see :func:`audit_classifier`.
    """
    Xa, ya = np.asarray(X, dtype=np.float64), np.asarray(y).astype(int)
    xm = Xa[ya == 1]
    n_new = int((ya == 0).sum() - len(xm))
    if n_new <= 0 or len(xm) < 2:
        return Xa, ya
    k = int(min(k, len(xm) - 1))
    sq = (xm**2).sum(axis=1)
    nbr = np.empty((len(xm), k), dtype=np.intp)
    for s in range(0, len(xm), 2048):
        blk = xm[s : s + 2048]
        d2 = (blk**2).sum(axis=1)[:, None] - 2.0 * blk @ xm.T + sq[None, :]
        np.fill_diagonal(d2[:, s : s + len(blk)], np.inf)
        nbr[s : s + len(blk)] = np.argpartition(d2, k, axis=1)[:, :k]
    rng = np.random.default_rng(seed)
    base = rng.integers(0, len(xm), n_new)
    other = nbr[base, rng.integers(0, k, n_new)]
    xn = xm[base] + rng.random((n_new, 1)) * (xm[other] - xm[base])
    return np.vstack([Xa, xn]), np.concatenate([ya, np.ones(n_new, dtype=int)])


def weighted_auc(y: Any, score: Any, weight: Any = None) -> float:
    """Area under the ROC curve (probability that a positive outranks a negative), optionally survey-weighted."""
    yv, sv = np.asarray(y).astype(int), np.asarray(score, dtype=np.float64)
    w = np.ones(len(yv)) if weight is None else np.asarray(weight, dtype=np.float64)
    order = np.argsort(sv, kind="mergesort")
    yv, sv, w = yv[order], sv[order], w[order]
    # tie-aware: group equal scores
    uniq, start = np.unique(sv, return_index=True)
    wp = np.add.reduceat(w * (yv == 1), start)
    wn = np.add.reduceat(w * (yv == 0), start)
    cum_neg = np.cumsum(wn) - wn
    num = float(np.sum(wp * (cum_neg + 0.5 * wn)))
    den = float(wp.sum() * wn.sum())
    return num / den if den > 0 else float("nan")


@dataclass
class AuditReport:
    """Scores of one model under the four pipelines and the inflation of the leaky one."""

    table: pd.DataFrame
    inflation_auc: float
    note: str

    def __str__(self) -> str:
        return f"{self.note}\n{self.table.round(3).to_string()}"


def _score(model: Any, X: Floats) -> Floats:
    if hasattr(model, "predict_proba"):
        return np.asarray(model.predict_proba(X))[:, 1]
    return np.asarray(model.decision_function(X))


def audit_classifier(
    make_model: Callable[[], Any],
    X: Any,
    y: Any,
    groups: Any,
    weights: Any = None,
    *,
    seeds: tuple[int, ...] = (0, 1, 2),
    test_size: float = 0.3,
    warn_above: float = 0.05,
) -> AuditReport:
    """Score one classifier under the four pipelines and report how much the leaky ones inflate AUC.

    Pipelines: ``resample_then_split`` (SMOTE on everything, random row split), ``split_then_resample`` (random row split,
    SMOTE on training rows), ``grouped`` (split by ``groups``, SMOTE on training rows) and ``grouped_weighted``
    (split by ``groups``, no resampling, survey-weighted AUC). ``inflation_auc`` is ``resample_then_split`` minus
    ``grouped``; a :class:`PynhtsWarning` is raised when it exceeds ``warn_above``.
    """
    Xa, ya = np.asarray(X, dtype=np.float64), np.asarray(y).astype(int)
    wa = np.ones(len(ya)) if weights is None else np.asarray(weights, dtype=np.float64)
    ga = np.asarray(groups)
    if len(np.unique(ya)) != 2 or not set(np.unique(ya)) <= {0, 1}:
        raise ValueError("y must be binary 0/1")
    rows = []
    for pipe in PIPELINES:
        for s in seeds:
            rng = np.random.default_rng(s)
            if pipe == "resample_then_split":
                Xr, yr = smote(Xa, ya, seed=s)
                perm = rng.permutation(len(yr))
                cut = int(len(yr) * (1 - test_size))
                tr, te = perm[:cut], perm[cut:]
                Xtr, ytr, Xte, yte, wte = Xr[tr], yr[tr], Xr[te], yr[te], None
            else:
                if pipe == "split_then_resample":
                    perm = rng.permutation(len(ya))
                    cut = int(len(ya) * (1 - test_size))
                    tr, te = perm[:cut], perm[cut:]
                else:
                    tr, te = group_split(ga, test_size=test_size, seed=s)
                Xtr, ytr, Xte, yte = Xa[tr], ya[tr], Xa[te], ya[te]
                wte = wa[te] if pipe == "grouped_weighted" else None
                if pipe != "grouped_weighted":
                    Xtr, ytr = smote(Xtr, ytr, seed=s)
            model = make_model()
            model.fit(Xtr, ytr)
            sc = _score(model, Xte)
            rows.append(
                {"pipeline": pipe, "seed": s, "auc": weighted_auc(yte, sc, wte), "n_test": len(yte)}
            )
    tab = (
        pd.DataFrame(rows)
        .groupby("pipeline", sort=False)
        .agg(auc=("auc", "mean"), auc_sd=("auc", "std"), n_test=("n_test", "mean"))
        .reindex(PIPELINES)
    )
    auc = tab["auc"].to_numpy(dtype=np.float64)  # in PIPELINES order
    leaky, grouped = float(auc[0]), float(auc[2])
    infl = leaky - grouped
    note = (
        f"AUC inflation from resampling before the split and splitting rows: {infl:+.3f} "
        f"({leaky:.3f} versus {grouped:.3f} by household)"
    )
    if infl > warn_above:
        warnings.warn(
            note + "; report the grouped, train-only-resampled score", PynhtsWarning, stacklevel=2
        )
    return AuditReport(tab, infl, note)
