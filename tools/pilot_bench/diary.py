"""Discretised person-day diaries from NHTS trips (pilot).

A diary is a ``(n_persons, 288)`` uint8 matrix of 5-minute slots covering the NHTS travel day
(04:00 to 04:00). States: 0 home, 1 work, 2 school/care, 3 maintenance (errands, escort,
health), 4 leisure (meals, social, recreation, religious, volunteer), 5 other, 6 travelling.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

N_SLOTS = 288
SLOT_MIN = 5
DAY_START_MIN = 240  # 04:00
STATES = ["home", "work", "school", "maint", "leisure", "other", "travel"]
H, W, S, M, L, O, T = range(7)

_WHY = {
    "01": H, "02": H, "03": W, "04": W, "08": S, "09": S, "10": S,
    "06": M, "11": M, "12": M, "14": M, "18": M,
    "13": L, "15": L, "16": L, "17": L, "19": L, "05": L,
    "07": O, "97": O,
}


def _slot(hhmm: pd.Series) -> np.ndarray:
    """Slot index of an ``hhmm`` string; times before 04:00 belong to the next calendar day."""
    v = pd.to_numeric(hhmm, errors="coerce").to_numpy(dtype=np.float64)
    minutes = (v // 100) * 60 + (v % 100)
    minutes = np.where(minutes < DAY_START_MIN, minutes + 1440, minutes)
    return np.asarray((minutes - DAY_START_MIN) // SLOT_MIN)


def person_covariates(persons: pd.DataFrame) -> pd.DataFrame:
    """Conditioning variables used by every model (age band, worker, vehicles, weekend)."""
    age = persons["R_AGE_IMP"].to_numpy(dtype=np.float64)
    band = np.digitize(age, [5, 18, 25, 45, 65])  # 0:<5 1:5-17 2:18-24 3:25-44 4:45-64 5:65+
    worker = (persons["WORKER"] == "01").fillna(False).to_numpy().astype(int)
    veh = np.minimum(persons["HHVEHCNT"].to_numpy(dtype=np.float64), 2).astype(int)
    weekend = persons["TRAVDAY"].isin(["01", "07"]).to_numpy().astype(int)
    return pd.DataFrame({"age": band, "worker": worker, "veh": veh, "weekend": weekend},
                        index=persons.index)


def build_diaries(persons: pd.DataFrame, trips: pd.DataFrame) -> tuple[np.ndarray, dict[str, int]]:
    """Diary matrix for ``persons`` (row order preserved) from their ``trips``.

    Returns the matrix and a small report (trips used / skipped).
    """
    n = len(persons)
    diary = np.zeros((n, N_SLOTS), dtype=np.uint8)
    key = pd.MultiIndex.from_frame(persons[["HOUSEID", "PERSONID"]])
    t = trips.copy()
    t["_p"] = key.get_indexer(pd.MultiIndex.from_frame(t[["HOUSEID", "PERSONID"]]))
    t["_n"] = pd.to_numeric(t["TDTRPNUM"])
    t["_s"], t["_e"] = _slot(t["STRTTIME"]), _slot(t["ENDTIME"])
    wrap = t["_e"] < t["_s"]
    t.loc[wrap, "_e"] = t.loc[wrap, "_e"] + 1440 // SLOT_MIN
    bad = (t["_p"] < 0) | t["_s"].isna() | t["_e"].isna()
    report = {"trips": len(t), "skipped": int(bad.sum())}
    t = t[~bad].sort_values(["_p", "_n"], kind="stable")
    p = t["_p"].to_numpy()
    s = np.clip(t["_s"].to_numpy(dtype=np.int64), 0, N_SLOTS - 1)
    e = np.clip(t["_e"].to_numpy(dtype=np.int64), 0, N_SLOTS - 1)
    to = t["WHYTO"].map(_WHY).fillna(O).to_numpy(dtype=np.uint8)
    fr = t["WHYFROM"].map(_WHY).fillna(H).to_numpy(dtype=np.uint8)
    nxt = np.append(s[1:], N_SLOTS)
    nxt = np.where(np.append(p[1:] == p[:-1], False), nxt, N_SLOTS)
    first = np.append(True, p[1:] != p[:-1])
    for i in range(len(p)):
        row = diary[p[i]]
        if first[i]:
            row[: s[i]] = fr[i]
        row[s[i]: e[i] + 1] = T
        if e[i] + 1 < nxt[i]:
            row[e[i] + 1: nxt[i]] = to[i]
    return diary, report


def person_stats(diary: np.ndarray) -> pd.DataFrame:
    """Per-person outcomes whose weighted means are the benchmark targets."""
    trav = diary == T
    starts = trav[:, 1:] & ~trav[:, :-1]
    trips = starts.sum(axis=1) + trav[:, 0]
    minutes = {f"min_{name}": (diary == k).sum(axis=1) * SLOT_MIN for k, name in enumerate(STATES)}
    first_dep = np.where(trav.any(axis=1), trav.argmax(axis=1) * SLOT_MIN, np.nan)
    at = lambda hhmm: (hhmm - DAY_START_MIN) // SLOT_MIN  # noqa: E731
    out = pd.DataFrame({
        "any_trip": (trips > 0).astype(float),
        "trips": trips.astype(float),
        "trips_3plus": (trips >= 3).astype(float),
        **{k: v.astype(float) for k, v in minutes.items()},
        "has_work": (diary == W).any(axis=1).astype(float),
        "first_departure_min": first_dep,
        "work_at_10": (diary[:, at(600)] == W).astype(float),
        "travel_at_08": (diary[:, at(480)] == T).astype(float),
        "travel_at_17": (diary[:, at(1020)] == T).astype(float),
        "home_at_23": (diary[:, at(1380)] == H).astype(float),
    })
    return out
