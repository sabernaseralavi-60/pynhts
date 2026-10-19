"""Survey-design-aware two-sample test (weighted pMSE / AUC with JKn SE) and membership-inference
style novelty metric for synthetic activity schedules."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

from diary import N_SLOTS, SLOT_MIN
from schedule import ACTS, schedule_stats


def schedule_to_slots(sched: pd.DataFrame, pids: np.ndarray, chunk: int = 20000) -> np.ndarray:
    """``(len(pids), 288)`` uint8 matrix: activity code (index in ACTS) at every 5-minute slot."""
    s = sched.sort_values(["pid", "start"], kind="stable")
    code = s["act"].map({a: i for i, a in enumerate(ACTS)}).to_numpy(dtype=np.uint8)
    pos = pd.Series(np.arange(len(pids)), index=pids).reindex(s["pid"]).to_numpy()
    start = (s["start"].to_numpy() // SLOT_MIN).astype(np.int64)
    key = pos.astype(np.int64) * (N_SLOTS + 1) + start
    out = np.zeros((len(pids), N_SLOTS), dtype=np.uint8)
    slot_ix = np.arange(N_SLOTS)
    for i in range(0, len(pids), chunk):
        hi = min(i + chunk, len(pids))
        q = (np.arange(i, hi)[:, None] * (N_SLOTS + 1) + slot_ix[None, :]).ravel()
        j = np.clip(np.searchsorted(key, q, side="right") - 1, 0, len(key) - 1)
        out[i:hi] = code[j].reshape(hi - i, N_SLOTS)
    return out


def features(sched: pd.DataFrame, pids: np.ndarray, cov: pd.DataFrame) -> pd.DataFrame:
    """Hourly activity shares + schedule summaries + covariates (the covariates are shared by the
    real and synthetic copy of a person, so the test is about the *conditional* distribution)."""
    slots = schedule_to_slots(sched, pids)
    per_hour = 60 // SLOT_MIN
    cols = {}
    for k, a in enumerate(ACTS):
        occupied = (slots == k).reshape(len(pids), 24, per_hour).mean(axis=2)
        for h in range(24):
            cols[f"{a}_h{h:02d}"] = occupied[:, h]
    stats = schedule_stats(sched, pids)
    out = pd.concat([pd.DataFrame(cols), stats.reset_index(drop=True),
                     cov.reset_index(drop=True)], axis=1)
    return out


def weighted_pmse(p: np.ndarray, y: np.ndarray, w: np.ndarray) -> float:
    return float(np.sum(w * (p - 0.5) ** 2) / np.sum(w))


def _class_norm(w_r, w_s):
    return w_r / np.sum(w_r), w_s / np.sum(w_s)


def c2st(real_feat: pd.DataFrame, syn_feat: pd.DataFrame, w_real, w_syn, g_real, g_syn,
         rep_real: np.ndarray, rep_syn: np.ndarray, *, folds: int = 3, seed: int = 0) -> dict:
    """Weighted classifier two-sample test with a JKn standard error.

    Each class is weighted by its persons' survey weights, normalised so that both classes carry
    equal total weight (so 0.5 is the right reference probability). ``g_*`` are household ids
    (a household is never split across folds); ``rep_*`` are ``(n, 98)`` replicate weights, used
    to re-compute the weighted pMSE and AUC under every replicate for the JKn variance.
    """
    X = pd.concat([real_feat, syn_feat], ignore_index=True)
    y = np.r_[np.zeros(len(real_feat)), np.ones(len(syn_feat))]
    wr, ws = _class_norm(np.asarray(w_real, float), np.asarray(w_syn, float))
    ww = np.r_[wr, ws] * len(y) / 2
    g = np.r_[g_real, g_syn]
    oof = np.zeros(len(y))
    for tr, te in GroupKFold(n_splits=folds).split(X, y, g):
        clf = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31,
                                             early_stopping=True, validation_fraction=0.1,
                                             random_state=seed)
        clf.fit(X.iloc[tr], y[tr], sample_weight=ww[tr])
        oof[te] = clf.predict_proba(X.iloc[te])[:, 1]
    pm, auc = weighted_pmse(oof, y, ww), roc_auc_score(y, oof, sample_weight=ww)
    pm_r, auc_r = [], []
    for r in range(rep_real.shape[1]):
        a, c = _class_norm(rep_real[:, r], rep_syn[:, r])
        wrr = np.r_[a, c] * len(y) / 2
        pm_r.append(weighted_pmse(oof, y, wrr))
        auc_r.append(roc_auc_score(y, oof, sample_weight=wrr))
    jk = 6 / 7
    return dict(pmse=pm, pmse_se=float(np.sqrt(jk * np.sum((np.array(pm_r) - pm) ** 2))),
                auc=auc, auc_se=float(np.sqrt(jk * np.sum((np.array(auc_r) - auc) ** 2))))


def mia_advantage(syn_slots: np.ndarray, train_slots: np.ndarray, holdout_slots: np.ndarray,
                  mask: np.ndarray | None = None) -> dict:
    """Distance-based membership inference: is a synthetic day closer to the training set than to an
    equally large real holdout? ``advantage`` = P(closer to train) + 0.5 P(tie) - 0.5 (0 = no leakage,
    +0.5 = every synthetic day has a closer training record). Distance = share of differing slots."""
    from deep import dcr  # lazy: needs torch

    q = syn_slots if mask is None else syn_slots[mask]
    d_tr, d_ho = dcr(q, train_slots), dcr(q, holdout_slots)
    adv = float(np.mean(d_tr < d_ho) + 0.5 * np.mean(d_tr == d_ho) - 0.5)
    return dict(mia_advantage=adv, dcr_train=float(np.median(d_tr)), dcr_holdout=float(np.median(d_ho)),
                exact_copy_train=float(np.mean(d_tr == 0)), exact_copy_holdout=float(np.mean(d_ho == 0)),
                n=len(q))
