"""Sprint step 2: CART baseline and resampling baselines scored at schedule level."""
import sys, time
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from cart import CARTSynthesizer
from models import WeightedResampler
from schedule import diary_to_schedule, schedule_stats

splits = int(sys.argv[1]) if len(sys.argv) > 1 else 5
reps = 3
out = common.ROOT / "paper" / "pilot"; out.mkdir(parents=True, exist_ok=True)
b = common.load(); sched_all = diary_to_schedule(b.diary); res = []; t0 = time.time()
for sp in range(splits):
    tr, te = b.split(sp)
    cov_tr, cov_te = b.cov[tr].reset_index(drop=True), b.cov[te].reset_index(drop=True)
    pids_tr, pids_te = np.flatnonzero(tr), np.flatnonzero(te)
    cart = CARTSynthesizer().fit(sched_all, cov_tr, b.w[tr], pids_tr)
    syn = []
    for r in range(reps):
        s = cart.generate(cov_te, np.random.default_rng(sp * 100 + r), pids_te)
        syn.append(schedule_stats(s, pids_te))
    res.append(b.score(syn, tr, te, "cart", sp))
    for lvl in ("fine", "none"):
        m = WeightedResampler(lvl).fit(b.diary[tr], cov_tr, b.w[tr])
        syn = []
        for r in range(reps):
            g = m.generate(cov_te, np.random.default_rng(sp * 100 + r))
            syn.append(schedule_stats(diary_to_schedule(g, pids_te), pids_te))
        res.append(b.score(syn, tr, te, f"resample_{lvl}", sp))
    # noise floor: train half as "model"
    ref = b.real.iloc[0:0]
    print(f"split {sp} done {time.time()-t0:.0f}s", flush=True)
    pd.concat(res).to_csv(out / "schedule_results.csv", index=False)
r = pd.concat(res)
print(r.assign(z2=r.z**2, w=r.z.abs() < 1.96).groupby("model").agg(mean_z2=("z2", "mean"), within=("w", "mean")).round(2))
