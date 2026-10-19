"""Pilot step 2: add a conditional VAE and a privacy/novelty metric (DCR) to the fidelity benchmark.

Same splits and z-score as ``run_pilot.py``. Writes ``deep_results.csv`` (z per target) and
``privacy.csv`` (DCR per model and split).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_pilot as rp  # noqa: E402  (sets PYNHTS_CACHE_DIR, imports pynhts)
from deep import ConditionalVAE, dcr  # noqa: E402
from diary import build_diaries, person_covariates, person_stats  # noqa: E402
from models import MarkovChain, WeightedResampler  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", type=int, default=5)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--dcr-n", type=int, default=2000)
    ap.add_argument("--out", default=str(rp.ROOT / "paper" / "pilot"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    d = rp.pynhts.load(2017)
    svy = d.survey("person", ["R_AGE_IMP", "WORKER", "HHVEHCNT", "TRAVDAY"])
    persons = svy.rows
    trips = d.trips(["TDTRPNUM", "STRTTIME", "ENDTIME", "WHYTO", "WHYFROM"], keys=True)
    diary, _ = build_diaries(persons, trips)
    cov = person_covariates(persons)
    real = person_stats(diary)
    w = persons["WTPERFIN"].to_numpy(dtype=np.float64)
    hh = persons["HOUSEID"].to_numpy()
    uh = np.unique(hh)
    full_moe = {n: rp.mean_est(svy, y, m)[1] * 1.984 for n, y, m in rp.targets(real, cov)}

    zrows, prows = [], []
    t0 = time.time()
    for sp in range(args.splits):
        rng = np.random.default_rng(1000 + sp)  # identical split to run_pilot.py
        test_h = set(rng.choice(uh, size=len(uh) // 2, replace=False))
        te = np.isin(hh, list(test_h))
        tr = ~te
        cov_tr, cov_te = cov[tr].reset_index(drop=True), cov[te].reset_index(drop=True)
        te_idx = np.flatnonzero(te)

        models = [WeightedResampler("none"), WeightedResampler("coarse"), WeightedResampler("fine"),
                  MarkovChain(duration=False), MarkovChain(duration=True),
                  ConditionalVAE(epochs=args.epochs, seed=sp)]
        for m in models:
            m.fit(diary[tr], cov_tr, w[tr])
        print(f"split {sp}: fitted, {time.time() - t0:.0f}s", flush=True)

        # --- fidelity of the CVAE (other models are in pilot_results.csv) -----------------------
        cvae = models[-1]
        stats = [person_stats(cvae.generate(cov_te, np.random.default_rng(sp * 100 + r)))
                 for r in range(args.reps)]
        for name, y, mask in rp.targets(real, cov):
            e_te, se_te = rp.mean_est(svy, y, mask & te)
            _, se_tr = rp.mean_est(svy, y, mask & tr)
            ests = []
            for st in stats:
                ysyn = np.full(len(persons), np.nan)
                ysyn[te_idx] = st[name.split("|")[0]].to_numpy()
                ests.append(rp.mean_est(svy, ysyn, mask & te)[0])
            est = float(np.mean(ests))
            zrows.append(dict(split=sp, target=name, model="cvae", est=est, test=e_te,
                              se_test=se_te, se_train=se_tr, z=(est - e_te) / np.hypot(se_te, se_tr),
                              err_moe=(est - e_te) / full_moe[name]))

        # --- privacy: distance to the closest training record ---------------------------------
        sub = np.random.default_rng(sp).choice(len(cov_te), size=args.dcr_n, replace=False)
        cov_sub = cov_te.iloc[sub].reset_index(drop=True)
        ref = diary[tr]
        entries = {"real_test (reference)": diary[te][sub]}
        for m in models:
            entries[m.name] = m.generate(cov_sub, np.random.default_rng(777 + sp))
        for name, q in entries.items():
            dist = dcr(q, ref)
            trav = (q == 6).any(axis=1)  # days with at least one trip (all-home days are trivially shared)
            prows.append(dict(split=sp, model=name, n=len(dist), n_travellers=int(trav.sum()),
                              dcr_median=float(np.median(dist)),
                              exact_copy_share=float((dist == 0).mean()),
                              dcr_median_travellers=float(np.median(dist[trav])),
                              dcr_p05_travellers=float(np.quantile(dist[trav], 0.05)),
                              exact_copy_share_travellers=float((dist[trav] == 0).mean())))
        print(f"split {sp}: done, {time.time() - t0:.0f}s", flush=True)
        pd.DataFrame(zrows).to_csv(out / "deep_results.csv", index=False)
        pd.DataFrame(prows).to_csv(out / "privacy.csv", index=False)


if __name__ == "__main__":
    main()
