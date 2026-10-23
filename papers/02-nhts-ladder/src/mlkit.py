"""Evaluation pipelines for the machine-learning studies: how much of a published score survives a sound design?

Classification (imbalanced outcomes, e.g. alternative-fuel adoption) is scored under four pipelines that differ only in
how the data are split and where the resampling happens:

* ``resample_then_split`` - SMOTE on the whole file, then a random row split (resampled copies can sit in test);
* ``split_then_resample`` - random row split, SMOTE on the training part only;
* ``grouped``            - split by household (all rows of a household on one side), SMOTE on training only;
* ``grouped_weighted``   - like ``grouped`` but no resampling; scores are survey-weighted.

Regression targets use ``random`` / ``grouped`` / ``group_holdout`` (whole states out) splits.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, average_precision_score, mean_squared_error, r2_score, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit, train_test_split

CLASS_SCHEMES = ("resample_then_split", "split_then_resample", "grouped", "grouped_weighted")


def _smote(X, y, seed, k=5):
    """SMOTE (Chawla et al. 2002): synthetic minority points on segments to k nearest minority neighbours, to balance."""
    from sklearn.neighbors import NearestNeighbors

    rng = np.random.default_rng(seed)
    Xm = X[y == 1]
    n_new = int((y == 0).sum() - len(Xm))
    if n_new <= 0 or len(Xm) < 2:
        return X, y
    k = int(min(k, len(Xm) - 1))
    nn = NearestNeighbors(n_neighbors=k + 1).fit(Xm)
    nbr = nn.kneighbors(Xm, return_distance=False)[:, 1:]
    base = rng.integers(0, len(Xm), n_new)
    other = nbr[base, rng.integers(0, k, n_new)]
    delta = rng.random((n_new, 1))
    Xn = Xm[base] + delta * (Xm[other] - Xm[base])
    return np.vstack([X, Xn]), np.concatenate([y, np.ones(n_new, dtype=y.dtype)])


def classify(make_model, X, y, groups, w, scheme: str, seed: int, test_size: float = 0.3) -> dict:
    X = np.asarray(X, float)
    y = np.asarray(y).astype(int)
    w = np.asarray(w, float)
    if scheme == "resample_then_split":
        Xr, yr = _smote(X, y, seed)
        Xtr, Xte, ytr, yte = train_test_split(Xr, yr, test_size=test_size, random_state=seed, stratify=yr)
        wte = None
    elif scheme == "split_then_resample":
        Xtr, Xte, ytr, yte, _, wte = train_test_split(X, y, w, test_size=test_size, random_state=seed, stratify=y)
        Xtr, ytr = _smote(Xtr, ytr, seed)
        wte = None
    else:
        from pynhts.validate import group_split

        tr, te = group_split(groups, test_size=test_size, seed=seed)
        Xtr, Xte, ytr, yte, wte = X[tr], X[te], y[tr], y[te], w[te]
        if scheme == "grouped":
            Xtr, ytr = _smote(Xtr, ytr, seed)
            wte = None
    m = make_model()
    m.fit(Xtr, ytr)
    score = m.predict_proba(Xte)[:, 1] if hasattr(m, "predict_proba") else m.decision_function(Xte)
    pred = (score > 0.5) if hasattr(m, "predict_proba") else (score > 0)
    out = {"auc": roc_auc_score(yte, score), "acc": accuracy_score(yte, pred),
           "ap": average_precision_score(yte, score),
           "tpr": float(pred[yte == 1].mean()) if (yte == 1).any() else np.nan,
           "tnr": float((~pred[yte == 0]).mean()), "n_test": len(yte), "pos_test": int(yte.sum())}
    if scheme == "grouped_weighted":
        out["auc_w"] = roc_auc_score(yte, score, sample_weight=wte)
        out["ap_w"] = average_precision_score(yte, score, sample_weight=wte)
        out["acc_w"] = float(np.average(pred == yte, weights=wte))
    return out


def regress(make_model, X, y, groups, w, scheme: str, seed: int, test_size: float = 0.2) -> dict:
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    w = np.asarray(w, float)
    if scheme == "random":
        idx = np.arange(len(y))
        tr, te = train_test_split(idx, test_size=test_size, random_state=seed)
    else:  # grouped (households) or group_holdout (states): both split on `groups`
        gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
        tr, te = next(gss.split(X, y, groups))
    m = make_model()
    m.fit(X[tr], y[tr])
    p = m.predict(X[te])
    return {"r2": r2_score(y[te], p), "rmse": float(np.sqrt(mean_squared_error(y[te], p))),
            "r2_w": r2_score(y[te], p, sample_weight=w[te]), "n_test": len(te),
            "r2_train": r2_score(y[tr], m.predict(X[tr]))}


def repeat(fn, seeds, **kw) -> pd.DataFrame:
    rows = [{**fn(seed=s, **kw), "seed": s} for s in seeds]
    return pd.DataFrame(rows)
