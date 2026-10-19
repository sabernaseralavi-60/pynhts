"""Activity-schedule representation (no travel state) shared by every model in the sprint.

A schedule is a table ``pid, act, start, end`` (minutes since 04:00, 0..1440): a sequence of
activities where the time spent travelling to an activity belongs to that activity, the format
`caveat` (UCL) uses. Every model's output is brought to this form before it is scored, so models
that can and cannot produce a travel state are compared on the same footing.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from diary import N_SLOTS, SLOT_MIN, STATES

ACTS = ["home", "work", "school", "maint", "leisure", "other"]  # STATES without "travel"
T = 6


def diary_to_schedule(diary: np.ndarray, pids: np.ndarray | None = None) -> pd.DataFrame:
    """Convert a ``(n, 288)`` diary matrix to a schedule table (a new activity starts at each
    departure; travel time is absorbed into the destination activity)."""
    n = len(diary)
    pids = np.arange(n) if pids is None else np.asarray(pids)
    travel = diary == T
    # destination state for each slot: next non-travel state; fall back to the last one seen
    nxt = np.full(n, 255, dtype=np.uint8)
    dest = np.empty_like(diary)
    for t in range(N_SLOTS - 1, -1, -1):
        nxt = np.where(travel[:, t], nxt, diary[:, t])
        dest[:, t] = nxt
    prv = np.zeros(n, dtype=np.uint8)
    for t in range(N_SLOTS):
        prv = np.where(travel[:, t], prv, diary[:, t])
        dest[:, t] = np.where(dest[:, t] == 255, prv, dest[:, t])
    begin = np.zeros_like(travel)
    begin[:, 0] = True
    begin[:, 1:] = travel[:, 1:] & ~travel[:, :-1]
    rows, cols = np.nonzero(begin)  # row-major => sorted by row then column
    nxt_col = np.append(cols[1:], N_SLOTS)
    last = np.append(rows[1:] != rows[:-1], True)
    end_col = np.where(last, N_SLOTS, nxt_col)
    act = dest[rows, cols]
    out = pd.DataFrame({"pid": pids[rows], "act": np.array(ACTS, dtype=object)[act],
                        "start": cols * SLOT_MIN, "end": end_col * SLOT_MIN})
    return out


def schedule_stats(sched: pd.DataFrame, pids: np.ndarray) -> pd.DataFrame:
    """Person-level outcomes of a schedule table, one row per ``pids`` entry (in that order)."""
    s = sched.sort_values(["pid", "start"], kind="stable").reset_index(drop=True)
    s["dur"] = s["end"] - s["start"]
    g = s.groupby("pid")
    n_acts = g.size().reindex(pids).fillna(0).to_numpy()
    out = pd.DataFrame(index=np.arange(len(pids)))
    trips = np.maximum(n_acts - 1, 0)
    out["any_trip"] = (trips > 0).astype(float)
    out["trips"] = trips
    out["trips_3plus"] = (trips >= 3).astype(float)
    mins = s.pivot_table(index="pid", columns="act", values="dur", aggfunc="sum",
                         fill_value=0).reindex(pids).fillna(0)
    for a in ACTS:
        out[f"min_{a}"] = mins[a].to_numpy() if a in mins else 0.0
    out["has_work"] = (out["min_work"] > 0).astype(float)
    first = g.head(1).set_index("pid").reindex(pids)
    out["first_departure_min"] = np.where(trips > 0, first["end"].to_numpy(), np.nan)
    last = g.tail(1).set_index("pid").reindex(pids)
    out["ends_at_home"] = (last["act"].to_numpy() == "home").astype(float)
    for name, t in (("work_at_10", 360), ("home_at_23", 1140)):
        hit = s[(s["start"] <= t) & (s["end"] > t)]
        at = hit.drop_duplicates("pid").set_index("pid")["act"].reindex(pids)
        out[name] = (at.to_numpy() == ("work" if name.startswith("work") else "home")).astype(float)
    w = s[s["act"] == "work"].drop_duplicates("pid").set_index("pid")["start"].reindex(pids)
    out["work_start_min"] = w.to_numpy(dtype=float)
    return out
