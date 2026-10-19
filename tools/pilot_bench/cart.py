"""Sequential CART synthesis of activity schedules (synthpop-style, survey-weighted donors).

Classical tabular synthesis: variables are synthesised one at a time, each from a decision tree
fitted on the previously synthesised ones; a synthetic value is the value of a donor drawn from
the leaf the case falls in (draw probability proportional to the survey weight). Order:
number of activities -> for position k = 1..n: activity type, then duration (the last activity
takes the remaining time of the 24-hour day).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from schedule import ACTS

COV = ["age", "worker", "veh", "weekend"]
MAX_ACTS = 16


class LeafDonor:
    """Decision tree whose prediction is a weighted random donor from the leaf."""

    def __init__(self, X: np.ndarray, y: np.ndarray, w: np.ndarray, *, categorical: bool,
                 min_leaf: int = 20, max_depth: int = 14, seed: int = 0) -> None:
        tree = (DecisionTreeClassifier if categorical else DecisionTreeRegressor)(
            min_samples_leaf=min_leaf, max_depth=max_depth, random_state=seed)
        tree.fit(X, y, sample_weight=w)
        self.tree = tree
        leaf = tree.apply(X)
        order = np.argsort(leaf, kind="stable")
        self._y = y[order]
        cw = np.cumsum(w[order])
        sl = leaf[order]
        first = np.r_[True, sl[1:] != sl[:-1]]
        starts = np.flatnonzero(first)
        ends = np.r_[starts[1:], len(sl)]
        self._cw = cw
        self._lo = {int(sl[s]): (cw[s - 1] if s > 0 else 0.0, cw[e - 1])
                    for s, e in zip(starts, ends, strict=True)}

    def draw(self, X: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        leaf = self.tree.apply(X)
        lo = np.array([self._lo[int(leaf_id)][0] for leaf_id in leaf])
        hi = np.array([self._lo[int(leaf_id)][1] for leaf_id in leaf])
        target = lo + rng.random(len(leaf)) * (hi - lo)
        idx = np.minimum(np.searchsorted(self._cw, target, side="right"), len(self._y) - 1)
        return self._y[idx]


class CARTSynthesizer:
    name = "cart"

    def __init__(self, min_leaf: int = 20) -> None:
        self.min_leaf = min_leaf

    def fit(self, sched: pd.DataFrame, cov: pd.DataFrame, w: np.ndarray, pids: np.ndarray):
        """``sched``: schedule table of the training persons; ``cov``/``w``/``pids`` aligned."""
        s = sched.sort_values(["pid", "start"], kind="stable")
        s = s[s.pid.isin(pids)]
        n_all = s.groupby("pid").size().reindex(pids).to_numpy()
        ok = n_all <= MAX_ACTS  # like caveat (max_length 16), days with more activities are dropped
        cov, w, pids = cov[ok].reset_index(drop=True), np.asarray(w)[ok], np.asarray(pids)[ok]
        s = s[s.pid.isin(pids)]
        act = s["act"].map({a: i for i, a in enumerate(ACTS)}).to_numpy()
        dur = (s["end"] - s["start"]).to_numpy(dtype=float)
        pos = s.groupby("pid").cumcount().to_numpy()
        n_of = s.groupby("pid").size()
        pid_idx = pd.Series(np.arange(len(pids)), index=pids)
        row = pid_idx.loc[s["pid"]].to_numpy()
        n_acts = n_of.reindex(pids).to_numpy()
        C = cov[COV].to_numpy(dtype=float)
        W = np.asarray(w, dtype=float)
        self.n_model = LeafDonor(C, n_acts, W, categorical=True, min_leaf=self.min_leaf)
        # per-person matrices of the observed sequence
        A = np.full((len(pids), MAX_ACTS), -1)
        D = np.zeros((len(pids), MAX_ACTS))
        A[row, pos] = act
        D[row, pos] = dur
        self.type_models, self.dur_models = {}, {}
        for k in range(MAX_ACTS):
            sel = n_acts > k
            if sel.sum() < 2 * self.min_leaf:
                break
            Xk = self._features(C[sel], n_acts[sel], k, A[sel], D[sel])
            self.type_models[k] = LeafDonor(Xk, A[sel, k], W[sel], categorical=True,
                                            min_leaf=self.min_leaf, seed=k)
            last = n_acts[sel] == k + 1  # last activity duration is the remainder, not modelled
            if (~last).sum() >= 2 * self.min_leaf:
                Xd = np.column_stack([Xk, A[sel, k]])
                self.dur_models[k] = LeafDonor(Xd[~last], D[sel, k][~last], W[sel][~last],
                                               categorical=False, min_leaf=self.min_leaf, seed=k)
        return self

    @staticmethod
    def _features(C, n_acts, k, A, D) -> np.ndarray:
        prev1 = A[:, k - 1] if k >= 1 else np.full(len(C), -1)
        prev2 = A[:, k - 2] if k >= 2 else np.full(len(C), -1)
        start = D[:, :k].sum(axis=1) if k >= 1 else np.zeros(len(C))
        return np.column_stack([C, n_acts, np.full(len(C), k), prev1, prev2, start])

    def generate(self, cov: pd.DataFrame, rng: np.random.Generator, pids: np.ndarray) -> pd.DataFrame:
        n = len(cov)
        C = cov[COV].to_numpy(dtype=float)
        n_acts = np.minimum(np.maximum(self.n_model.draw(C, rng), 1), MAX_ACTS)
        A = np.full((n, MAX_ACTS), -1)
        D = np.zeros((n, MAX_ACTS))
        alive = np.ones(n, dtype=bool)  # still adding activities
        count = np.zeros(n, dtype=int)
        for k in range(MAX_ACTS):
            act_k = alive & (n_acts > k) & (k in self.type_models)
            if not act_k.any():
                break
            idx = np.flatnonzero(act_k)
            Xk = self._features(C[idx], n_acts[idx], k, A[idx], D[idx])
            A[idx, k] = self.type_models[k].draw(Xk, rng)
            count[idx] = k + 1
            is_last = n_acts[idx] == k + 1
            Xd = np.column_stack([Xk, A[idx, k]])
            d = np.zeros(len(idx))
            if k in self.dur_models:
                d[~is_last] = np.maximum(self.dur_models[k].draw(Xd[~is_last], rng), 5.0)
            D[idx, k] = d
            used = D[idx, : k + 1].sum(axis=1)
            over = (~is_last) & (used >= 1440 - 5)  # no room left: this becomes the last activity
            alive[idx[is_last | over]] = False
        # build schedule table; last activity takes the remainder of the day
        m = count
        pid_rep = np.repeat(np.asarray(pids), m)
        pos = np.concatenate([np.arange(c) for c in m])
        r = np.repeat(np.arange(n), m)
        durs = D[r, pos]
        # exclusive cumulative sum within person
        csum = np.cumsum(durs)
        first = np.r_[0, np.cumsum(m)[:-1]]
        cum_before = csum - durs - np.repeat(csum[first] - durs[first], m)
        is_last = pos == (m[r] - 1)
        start = np.minimum(cum_before, 1440 - 5)
        end = np.where(is_last, 1440.0, np.minimum(start + durs, 1440.0))
        start = (np.round(start / 5) * 5).astype(int)
        end = (np.round(end / 5) * 5).astype(int)
        keep = end > start
        out = pd.DataFrame({"pid": pid_rep, "act": np.array(ACTS, dtype=object)[A[r, pos]],
                            "start": start, "end": end})[keep]
        return out
