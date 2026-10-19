"""One-split check: does decoding the CVAE by per-slot mode instead of independent sampling fix it?"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_pilot as rp
from deep import ConditionalVAE, dcr
from diary import build_diaries, person_covariates, person_stats

d = rp.pynhts.load(2017)
svy = d.survey("person", ["R_AGE_IMP", "WORKER", "HHVEHCNT", "TRAVDAY"]); persons = svy.rows
trips = d.trips(["TDTRPNUM", "STRTTIME", "ENDTIME", "WHYTO", "WHYFROM"], keys=True)
diary, _ = build_diaries(persons, trips); cov = person_covariates(persons); real = person_stats(diary)
w = persons["WTPERFIN"].to_numpy(float); hh = persons["HOUSEID"].to_numpy(); uh = np.unique(hh)
rng = np.random.default_rng(1000); te = np.isin(hh, list(set(rng.choice(uh, len(uh)//2, replace=False)))); tr = ~te
cte = cov[te].reset_index(drop=True); te_idx = np.flatnonzero(te)
m = ConditionalVAE(epochs=12, seed=0).fit(diary[tr], cov[tr].reset_index(drop=True), w[tr])
rows = []
for mode in ["sample", "mode"]:
    m.decode = mode
    gen = m.generate(cte, np.random.default_rng(5)); st = person_stats(gen)
    z = []
    for name, y, mask in rp.targets(real, cov):
        e, se = rp.mean_est(svy, y, mask & te); _, se2 = rp.mean_est(svy, y, mask & tr)
        ys = np.full(len(persons), np.nan); ys[te_idx] = st[name.split("|")[0]].to_numpy()
        z.append((rp.mean_est(svy, ys, mask & te)[0] - e) / np.hypot(se, se2))
    z = np.array(z); sub = np.random.default_rng(0).choice(len(cte), 2000, replace=False)
    q = gen[sub]; dist = dcr(q, diary[tr]); trav = (q == 6).any(1)
    print(mode, "mean_z2", round((z**2).mean(), 1), "median|z|", round(np.median(abs(z)), 2),
          "within", round((abs(z) < 1.96).mean(), 2), "dcr_trav", round(float(np.median(dist[trav])), 3),
          "exact_trav", round(float((dist[trav] == 0).mean()), 3), "mean trips", round(st.trips.mean(), 2))
