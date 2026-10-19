"""Pilot: do synthetic-diary generators reproduce a held-out half of NHTS 2017 within sampling error?

Protocol (see docs/pilot_bench_notes.md): split households 50/50 at random; fit on the train half;
generate one diary per test person given the test person's covariates; compare weighted means of
person-level outcomes with the held-out half. The error is expressed as
    z = (theta_model - theta_test) / sqrt(se_test^2 + se_train^2),
where the SEs are JKn standard errors of the two half-sample domain estimates, so z ~ N(0, 1) for
a perfect model (checked with the train-vs-test reference). Also reported: error in units of the
full-sample 95% margin of error (the published-table scale).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
os.environ.setdefault("PYNHTS_CACHE_DIR", str(ROOT / "local_data" / "cache"))

import pynhts  # noqa: E402
from diary import build_diaries, person_covariates, person_stats  # noqa: E402
from models import MarkovChain, WeightedResampler  # noqa: E402

SUBGROUPS = {  # outcome -> (label, covariate mask)
    "trips|age65+": ("trips", lambda c: c["age"] == 5),
    "trips|zero_vehicle": ("trips", lambda c: c["veh"] == 0),
    "min_work|workers": ("min_work", lambda c: c["worker"] == 1),
    "travel_at_08|workers": ("travel_at_08", lambda c: c["worker"] == 1),
    "any_trip|weekend": ("any_trip", lambda c: c["weekend"] == 1),
}


def mean_est(survey, y: np.ndarray, domain: np.ndarray) -> tuple[float, float]:
    r = survey.mean(y, domain=domain)
    return float(r["estimate"].iloc[0]), float(r["se"].iloc[0])


def targets(stats: pd.DataFrame, cov: pd.DataFrame):
    """Yield (name, y, mask over persons) for every benchmark target."""
    for col in stats.columns:
        yield col, stats[col].to_numpy(), np.ones(len(stats), dtype=bool)
    for name, (col, fn) in SUBGROUPS.items():
        yield name, stats[col].to_numpy(), fn(cov).to_numpy()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", type=int, default=5)
    ap.add_argument("--reps", type=int, default=3, help="synthetic draws per model and split")
    ap.add_argument("--out", default=str(ROOT / "paper" / "pilot"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    d = pynhts.load(2017)
    cols = ["R_AGE_IMP", "WORKER", "HHVEHCNT", "TRAVDAY"]
    svy = d.survey("person", cols)
    persons = svy.rows
    trips = d.trips(["TDTRPNUM", "STRTTIME", "ENDTIME", "WHYTO", "WHYFROM"], keys=True)
    t0 = time.time()
    diary, rep = build_diaries(persons, trips)
    print(f"diaries {diary.shape}, trips {rep}, {time.time() - t0:.1f}s")
    cov = person_covariates(persons)
    real = person_stats(diary)
    w = persons["WTPERFIN"].to_numpy(dtype=np.float64)
    hh = persons["HOUSEID"].to_numpy()
    uh = np.unique(hh)

    # full-sample reference (published-table scale)
    full = {}
    for name, y, mask in targets(real, cov):
        e, se = mean_est(svy, y, mask)
        full[name] = (e, se * 1.984)  # t(0.975, 98)

    rows = []
    for sp in range(args.splits):
        rng = np.random.default_rng(1000 + sp)
        test_h = set(rng.choice(uh, size=len(uh) // 2, replace=False))
        is_test = np.isin(hh, list(test_h))
        tr, te = ~is_test, is_test
        models = [
            WeightedResampler("none"), WeightedResampler("coarse"), WeightedResampler("fine"),
            MarkovChain(duration=False), MarkovChain(duration=True),
        ]
        for m in models:
            m.fit(diary[tr], cov[tr].reset_index(drop=True), w[tr])
        syn_stats = {m.name: [] for m in models}
        profiles = {}
        for m in models:
            for r in range(args.reps):
                gen = m.generate(cov[te].reset_index(drop=True), np.random.default_rng(sp * 100 + r))
                full_stats = person_stats(gen)
                syn_stats[m.name].append(full_stats)
                if sp == 0 and r == 0:
                    profiles[m.name] = (w[te] / w[te].sum()) @ (gen == 6)
        te_idx = np.flatnonzero(te)
        cov_te = cov[te].reset_index(drop=True)
        for name, y, mask in targets(real, cov):
            e_te, se_te = mean_est(svy, y, mask & te)
            e_tr, se_tr = mean_est(svy, y, mask & tr)
            denom = np.hypot(se_te, se_tr)
            rows.append(dict(split=sp, target=name, model="reference_train", est=e_tr,
                             test=e_te, se_test=se_te, se_train=se_tr, z=(e_tr - e_te) / denom,
                             err_moe=(e_tr - e_te) / full[name][1]))
            for m in models:
                ests = []
                for st in syn_stats[m.name]:
                    # re-use the survey with synthetic outcomes placed on the test rows
                    ysyn = np.full(len(persons), np.nan)
                    base = st[name.split("|")[0]] if "|" in name else st[name]
                    ysyn[te_idx] = base.to_numpy()
                    ests.append(mean_est(svy, ysyn, mask & te)[0])
                est = float(np.mean(ests))
                rows.append(dict(split=sp, target=name, model=m.name, est=est, test=e_te,
                                 se_test=se_te, se_train=se_tr, z=(est - e_te) / denom,
                                 err_moe=(est - e_te) / full[name][1]))
        print(f"split {sp} done, {time.time() - t0:.0f}s")
        if sp == 0:
            test_real = (diary[te] == 6)
            wte = w[te] / w[te].sum()
            prof = pd.DataFrame({"slot": np.arange(288), "test": wte @ test_real})
            for k, v in profiles.items():
                prof[k] = v
            prof.to_csv(out / "travel_profile_split0.csv", index=False)

    res = pd.DataFrame(rows)
    res.to_csv(out / "pilot_results.csv", index=False)
    summ = (res.assign(az=res.z.abs(), within=res.z.abs() < 1.96, chi2=res.z ** 2)
            .groupby("model").agg(median_abs_z=("az", "median"), mean_z2=("chi2", "mean"),
                                  share_within_196=("within", "mean"),
                                  median_abs_err_moe=("err_moe", lambda s: s.abs().median())))
    summ.to_csv(out / "pilot_summary.csv")
    print(summ.round(3).to_string())


if __name__ == "__main__":
    main()
