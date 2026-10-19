"""Baseline generators of person-day diaries (pilot).

Every model is fitted on a weighted training set and then asked for one diary per *test* person,
conditional on that person's covariates (age band, worker, vehicles, weekend).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from diary import N_SLOTS, SLOT_MIN  # noqa: F401

N_STATES = 7
SLOTS_PER_HOUR = 60 // SLOT_MIN
CELL_COLS = {"coarse": ["age", "worker", "weekend"], "fine": ["age", "worker", "weekend", "veh"]}
_BUCKET_EDGES = np.array([2, 4, 7, 13, 37])  # run length (slots) -> 6 buckets


def _cell_ids(cov: pd.DataFrame, cols: list[str]) -> np.ndarray:
    ids = np.zeros(len(cov), dtype=np.int64)
    for c in cols:
        ids = ids * (int(cov[c].max()) + 2) + cov[c].to_numpy(dtype=np.int64)
    return ids


class WeightedResampler:
    """Draw a training person's whole day with probability proportional to the survey weight.

    ``level="none"`` ignores covariates; ``"coarse"``/``"fine"`` draw within the covariate cell
    (backing off to the coarse cell and then to everyone when a cell has < ``min_cell`` people).
    """

    def __init__(self, level: str = "fine", min_cell: int = 30) -> None:
        self.level, self.min_cell = level, min_cell
        self.name = f"resample_{level}"

    def fit(self, diary: np.ndarray, cov: pd.DataFrame, w: np.ndarray) -> WeightedResampler:
        self._diary, self._w = diary, w
        self._cov_cols = CELL_COLS.get(self.level, [])
        self._groups = {}
        levels = [self.level, "coarse"] if self.level == "fine" else [self.level]
        for lv in levels:
            if lv == "none":
                continue
            ids = _cell_ids(cov, CELL_COLS[lv])
            for cid in np.unique(ids):
                idx = np.flatnonzero(ids == cid)
                self._groups[(lv, cid)] = (idx, np.cumsum(w[idx]) / w[idx].sum())
        self._all = (np.arange(len(w)), np.cumsum(w) / w.sum())
        self._train_cov = cov
        return self

    def _draw(self, group: tuple[np.ndarray, np.ndarray], k: int, rng: np.random.Generator):
        idx, cdf = group
        return idx[np.minimum(np.searchsorted(cdf, rng.random(k)), len(idx) - 1)]

    def generate(self, cov: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
        n = len(cov)
        pick = np.empty(n, dtype=np.int64)
        if self.level == "none":
            pick[:] = self._draw(self._all, n, rng)
            return self._diary[pick]
        done = np.zeros(n, dtype=bool)
        for lv in (["fine", "coarse"] if self.level == "fine" else ["coarse"]):
            ids = _cell_ids(cov, CELL_COLS[lv])
            for cid in np.unique(ids[~done]):
                grp = self._groups.get((lv, cid))
                if grp is None or len(grp[0]) < self.min_cell:
                    continue
                sel = np.flatnonzero((ids == cid) & ~done)
                pick[sel] = self._draw(grp, len(sel), rng)
                done[sel] = True
        if (~done).any():
            pick[~done] = self._draw(self._all, int((~done).sum()), rng)
        return self._diary[pick]


class MarkovChain:
    """Time-inhomogeneous Markov chain of 5-minute states, conditional on a covariate cell.

    The transition law depends on (cell, hour of day, context). ``duration=False`` uses the
    current state as context (first-order Markov); ``duration=True`` adds how long the person has
    been in the state (6 run-length buckets), i.e. an approximate semi-Markov chain.
    Sparse cells are shrunk towards the pooled law with ``shrink`` pseudo-observations.
    """

    def __init__(self, duration: bool = False, shrink: float = 20.0) -> None:
        self.duration, self.shrink = duration, shrink
        self.name = "markov_dur" if duration else "markov1"
        self.n_ctx = N_STATES * (6 if duration else 1)

    def _ctx(self, state: np.ndarray, run: np.ndarray) -> np.ndarray:
        if not self.duration:
            return state.astype(np.int64)
        bucket = np.searchsorted(_BUCKET_EDGES, run, side="right")
        return state.astype(np.int64) * 6 + bucket

    def fit(self, diary: np.ndarray, cov: pd.DataFrame, w: np.ndarray) -> MarkovChain:
        cols = CELL_COLS["coarse"]
        ids = _cell_ids(cov, cols)
        self._cells = {c: i for i, c in enumerate(np.unique(ids))}
        cell = np.array([self._cells[c] for c in ids])
        wn = w / w.mean()
        nc = len(self._cells)
        counts = np.zeros((nc, 24, self.n_ctx, N_STATES))
        state = diary[:, 0]
        run = np.ones(len(diary), dtype=np.int64)
        init = np.zeros((nc, N_STATES))
        np.add.at(init, (cell, state), wn)
        self._init = init / init.sum(axis=1, keepdims=True)
        for t in range(N_SLOTS - 1):
            hour = (t // SLOTS_PER_HOUR) % 24
            ctx = self._ctx(state, run)
            nxt = diary[:, t + 1]
            np.add.at(counts[:, hour], (cell, ctx, nxt), wn)
            run = np.where(nxt == state, run + 1, 1)
            state = nxt
        pooled = counts.sum(axis=0)  # (24, ctx, S)
        stay = np.zeros((24, self.n_ctx, N_STATES))
        for ctx in range(self.n_ctx):
            stay[:, ctx, ctx // (self.n_ctx // N_STATES)] = 1.0
        tot_p = pooled.sum(axis=-1, keepdims=True)
        pooled_p = np.where(tot_p > 0, pooled / np.maximum(tot_p, 1e-12), stay)
        tot = counts.sum(axis=-1, keepdims=True)
        self._p = (counts + self.shrink * pooled_p[None]) / (tot + self.shrink)
        self._cdf = np.cumsum(self._p, axis=-1)
        return self

    def generate(self, cov: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
        n = len(cov)
        ids = _cell_ids(cov, CELL_COLS["coarse"])
        cell = np.array([self._cells.get(c, 0) for c in ids])
        out = np.empty((n, N_SLOTS), dtype=np.uint8)
        icdf = np.cumsum(self._init, axis=1)[cell]
        state = np.minimum((rng.random(n)[:, None] > icdf).sum(axis=1), N_STATES - 1)
        out[:, 0] = state
        run = np.ones(n, dtype=np.int64)
        for t in range(N_SLOTS - 1):
            hour = (t // SLOTS_PER_HOUR) % 24
            ctx = self._ctx(state, run)
            cdf = self._cdf[cell, hour, ctx]
            nxt = np.minimum((rng.random(n)[:, None] > cdf).sum(axis=1), N_STATES - 1)
            run = np.where(nxt == state, run + 1, 1)
            state = nxt
            out[:, t + 1] = state
        return out
