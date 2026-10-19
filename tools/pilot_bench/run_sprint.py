"""Sprint driver: score models at schedule level (z table, survey-design C2ST, MIA) for one split.

usage: python run_sprint.py SPLIT model [model ...]      models: resample_fine resample_none cart
       markov_dur caveat (caveat reads local_data/caveat_run/logs/**/synthetic_schedules.csv)
"""
import os, sys, time, glob
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from cart import CARTSynthesizer
from evalkit import c2st, features, mia_advantage, schedule_to_slots
from models import MarkovChain, WeightedResampler
from schedule import diary_to_schedule, schedule_stats

sp = int(sys.argv[1]); names = sys.argv[2:]
out = common.ROOT / "paper" / "pilot"; out.mkdir(parents=True, exist_ok=True)
t0 = time.time()
b = common.load(); tr, te = b.split(sp)
cov_tr, cov_te = b.cov[tr].reset_index(drop=True), b.cov[te].reset_index(drop=True)
pids_tr, pids_te = np.flatnonzero(tr), np.flatnonzero(te)
sched_all = diary_to_schedule(b.diary)
real_te = sched_all[sched_all.pid.isin(pids_te)]
real_te_feat = features(real_te, pids_te, cov_te)
tr_slots = schedule_to_slots(sched_all[sched_all.pid.isin(pids_tr)], pids_tr)
te_slots = schedule_to_slots(real_te, pids_te)
rep_te = b.svy._r[b.svy._unit[te]]  # (n_test, 98) replicate weights of the test persons
w_te, hh_te = b.w[te], b.hh[te]
rng_sub = np.random.default_rng(sp)
trav_te = (real_te.groupby("pid").size().reindex(pids_te).to_numpy() > 1)

def generate(name):
    if name.startswith("resample"):
        m = WeightedResampler(name.split("_")[1]).fit(b.diary[tr], cov_tr, b.w[tr])
        return diary_to_schedule(m.generate(cov_te, np.random.default_rng(sp)), pids_te)
    if name == "markov_dur":
        m = MarkovChain(duration=True).fit(b.diary[tr], cov_tr, b.w[tr])
        return diary_to_schedule(m.generate(cov_te, np.random.default_rng(sp)), pids_te)
    if name == "cart":
        m = CARTSynthesizer().fit(sched_all, cov_tr, b.w[tr], pids_tr)
        return m.generate(cov_te, np.random.default_rng(sp), pids_te)
    if name in ("caveat", "caveat_light", "caveat_full"):
        os.environ["CAVEAT_RUN"] = {"caveat": "nhts_split0_paper", "caveat_light": "nhts_split0", "caveat_full": "nhts_split0_full"}[name]
        f = sorted(glob.glob(str(common.ROOT / "local_data" / "caveat_run" / "logs" / os.environ.get("CAVEAT_RUN", "nhts_split0_paper") / "**" / "synthetic_schedules.csv"), recursive=True))[-1]
        s = pd.read_csv(f); print("caveat file", f, len(s))
        assert s.pid.max() == len(pids_te) - 1  # caveat renumbers persons 0..n-1 in test_attributes order
        s["pid"] = pids_te[s["pid"].to_numpy()]; return s
    raise SystemExit(f"unknown model {name}")

def upsert(path, df):
    old = pd.read_csv(path) if path.exists() else pd.DataFrame()
    if len(old):
        old = old[~((old.split == sp) & old.model.isin(df.model.unique()))]
    pd.concat([old, df]).to_csv(path, index=False)

def null_runs(k=5):
    rows = []
    uh = np.unique(hh_te)
    for j in range(k):
        rg = np.random.default_rng(5000 + 10 * sp + j)
        half = np.isin(hh_te, rg.choice(uh, size=len(uh) // 2, replace=False))
        c = c2st(real_te_feat[half].reset_index(drop=True), real_te_feat[~half].reset_index(drop=True),
                 w_te[half], w_te[~half], hh_te[half], hh_te[~half], rep_te[half], rep_te[~half])
        c.update(model="null_real_vs_real", split=sp, run=j); rows.append(c)
        print("null", j, "pMSE=%.5f AUC=%.3f" % (c["pmse"], c["auc"]), flush=True)
    return pd.DataFrame(rows)

if "null" in names:
    pd.concat([pd.read_csv(out / "sprint_null.csv").query("split != @sp") if (out / "sprint_null.csv").exists() else pd.DataFrame(), null_runs()]).to_csv(out / "sprint_null.csv", index=False)
    names = [n for n in names if n != "null"]

for name in names:
    s = generate(name)
    s = s[s.pid.isin(pids_te)]
    # z-scores (3 independent draws are not available for caveat -> one draw for all, for parity)
    z = b.score(schedule_stats(s, pids_te), tr, te, name, sp)
    upsert(out / "sprint_z.csv", z)
    feat = features(s, pids_te, cov_te)
    c = c2st(real_te_feat, feat, w_te, w_te, hh_te, hh_te, rep_te, rep_te); c.update(model=name, split=sp)
    sl = schedule_to_slots(s, pids_te)
    idx = rng_sub.choice(np.flatnonzero(trav_te), size=3000, replace=False)
    m = mia_advantage(sl[idx], tr_slots, te_slots); m.update(model=name, split=sp)
    upsert(out / "sprint_c2st.csv", pd.DataFrame([c])); upsert(out / "sprint_mia.csv", pd.DataFrame([m]))
    print(name, "z2=%.2f" % (z.z**2).mean(), "within=%.2f" % (z.z.abs() < 1.96).mean(),
          "pMSE=%.4f+-%.4f AUC=%.3f+-%.3f" % (c["pmse"], c["pmse_se"], c["auc"], c["auc_se"]),
          "MIA adv=%.3f" % m["mia_advantage"], "%.0fs" % (time.time() - t0), flush=True)
