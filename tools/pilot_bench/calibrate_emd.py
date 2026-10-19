"""Step 4: put caveat/acteval distances on the sampling-noise scale (run inside the caveat venv).

Distances of each model to the held-out real test half are compared with the distance between two
*real* samples of the same size (train half vs test half): the floor that any model, however good,
cannot go below. Both the unweighted frame (what acteval/caveat report) and a survey-weighted frame
(persons re-drawn with probability proportional to their survey weight, same draw for real and
synthetic copies) are computed.
"""
import sys, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
import acteval

sp = int(sys.argv[1]) if len(sys.argv) > 1 else 0
draws = int(sys.argv[2]) if len(sys.argv) > 2 else 3
root = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("D:/ReproducibleResearch_R_Projects/NHTS/02_tools")
d = root / "local_data" / "acteval" / f"split{sp}"
names = ["resample_fine", "cart"] + [k for k in ("caveat_light", "caveat", "caveat_full") if (d / f"{k}.csv").exists()]
tab = {k: pd.read_csv(d / f"{k}.csv") for k in ["real_test", "real_train"] + names}
wt, wr = pd.read_csv(d / "w_test.csv"), pd.read_csv(d / "w_train.csv")

def redraw(df, pids_all, src):
    """New table whose person j is a copy of person src[j] (new pid j)."""
    df = df[df.pid.isin(pids_all)].sort_values(["pid", "start"], kind="stable")
    pid_arr = df.pid.to_numpy()
    u, first, size = np.unique(pid_arr, return_index=True, return_counts=True)
    lookup = pd.Series(np.arange(len(u)), index=u)
    k = lookup.reindex(src).to_numpy()
    lens = size[k]
    rows = np.repeat(first[k], lens) + (np.arange(lens.sum()) - np.repeat(np.cumsum(lens) - lens, lens))
    out = df.iloc[rows][["act", "start", "end"]].copy()
    out.insert(0, "pid", np.repeat(np.arange(len(src)), lens))
    return out.reset_index(drop=True)

def run(real, models):
    ev = acteval.Evaluator(real)
    res = ev.compare(models)
    return res

def tidy(res, tag, draw):
    df = res.domains.combined.distances if hasattr(res, "domains") else res.distances
    df = df.copy(); df["frame"] = tag; df["draw"] = draw
    return df

rows = []
pids_te = wt.pid.to_numpy(); pids_tr = wr.pid.to_numpy()
# unweighted frame
models = {k: tab[k] for k in names + ["real_train"]}
r = run(tab["real_test"], models); rows.append(tidy(r, "unweighted", 0))
# weighted frame
for j in range(draws):
    rng = np.random.default_rng(900 + j)
    idx = rng.choice(len(pids_te), size=len(pids_te), p=wt.w / wt.w.sum())
    src_te = pids_te[idx]
    real = redraw(tab["real_test"], pids_te, src_te)
    models = {k: redraw(tab[k], pids_te, src_te) for k in names}
    src_tr = pids_tr[rng.choice(len(pids_tr), size=len(pids_te), p=wr.w / wr.w.sum())]
    models["real_train"] = redraw(tab["real_train"], pids_tr, src_tr)
    r = run(real, models); rows.append(tidy(r, "weighted", j))
    print("draw", j, "done", flush=True)
out = pd.concat(rows)
dst = root / "paper" / "pilot" / f"emd_calibration_split{sp}.csv"
out.to_csv(dst)
print(out.head(20).to_string()); print("saved", dst)
