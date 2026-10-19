"""Shared loading, splits and the survey-design z-score for the feasibility sprint."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
os.environ.setdefault("PYNHTS_CACHE_DIR", str(ROOT / "local_data" / "cache"))

import pynhts  # noqa: E402
from diary import build_diaries, person_covariates  # noqa: E402
from schedule import diary_to_schedule, schedule_stats  # noqa: E402

SUBGROUPS = {
    "trips|age65+": ("trips", lambda c: c["age"] == 5),
    "trips|zero_vehicle": ("trips", lambda c: c["veh"] == 0),
    "min_work|workers": ("min_work", lambda c: c["worker"] == 1),
    "work_at_10|workers": ("work_at_10", lambda c: c["worker"] == 1),
    "work_start_min|workers": ("work_start_min", lambda c: c["worker"] == 1),
    "any_trip|weekend": ("any_trip", lambda c: c["weekend"] == 1),
}
T975 = 1.984  # t(0.975, 98)


@dataclass
class Bench:
    svy: object
    persons: pd.DataFrame
    diary: np.ndarray
    cov: pd.DataFrame
    w: np.ndarray
    hh: np.ndarray
    real: pd.DataFrame  # schedule-level outcomes of the real days
    full_moe: dict

    def split(self, sp: int) -> tuple[np.ndarray, np.ndarray]:
        """Same household split as run_pilot.py (seed 1000 + sp). Returns (train, test) masks."""
        uh = np.unique(self.hh)
        rng = np.random.default_rng(1000 + sp)
        te = np.isin(self.hh, list(set(rng.choice(uh, size=len(uh) // 2, replace=False))))
        return ~te, te

    def targets(self, stats: pd.DataFrame):
        for col in stats.columns:
            yield col, stats[col].to_numpy(), np.ones(len(stats), dtype=bool)
        for name, (col, fn) in SUBGROUPS.items():
            yield name, stats[col].to_numpy(), fn(self.cov).to_numpy()

    def mean_est(self, y, domain) -> tuple[float, float]:
        r = self.svy.mean(y, domain=domain)
        return float(r["estimate"].iloc[0]), float(r["se"].iloc[0])

    def score(self, syn: pd.DataFrame | list[pd.DataFrame], tr, te, model: str, split: int):
        """z-score table of synthetic outcomes (rows = test persons in file order)."""
        syn = syn if isinstance(syn, list) else [syn]
        te_idx = np.flatnonzero(te)
        rows = []
        for name, y, mask in self.targets(self.real):
            e_te, se_te = self.mean_est(y, mask & te)
            _, se_tr = self.mean_est(y, mask & tr)
            ests = []
            for st in syn:
                ys = np.full(len(self.persons), np.nan)
                ys[te_idx] = st[SUBGROUPS[name][0] if name in SUBGROUPS else name].to_numpy()
                ests.append(self.mean_est(ys, mask & te)[0])
            est = float(np.mean(ests))
            rows.append(dict(split=split, target=name, model=model, est=est, test=e_te,
                             se_test=se_te, se_train=se_tr,
                             z=(est - e_te) / np.hypot(se_te, se_tr),
                             err_moe=(est - e_te) / self.full_moe[name]))
        return pd.DataFrame(rows)


def load() -> Bench:
    d = pynhts.load(2017)
    svy = d.survey("person", ["R_AGE_IMP", "WORKER", "HHVEHCNT", "TRAVDAY"])
    persons = svy.rows
    trips = d.trips(["TDTRPNUM", "STRTTIME", "ENDTIME", "WHYTO", "WHYFROM"], keys=True)
    diary, _ = build_diaries(persons, trips)
    cov = person_covariates(persons)
    real = schedule_stats(diary_to_schedule(diary), np.arange(len(diary)))
    b = Bench(svy, persons, diary, cov, persons["WTPERFIN"].to_numpy(dtype=np.float64),
              persons["HOUSEID"].to_numpy(), real, {})
    b.full_moe = {n: b.mean_est(y, m)[1] * T975 for n, y, m in b.targets(real)}
    return b
