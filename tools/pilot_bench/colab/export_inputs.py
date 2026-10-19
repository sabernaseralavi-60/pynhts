
import hashlib, sys
import numpy as np, pandas as pd
sys.path.insert(0, "/content/pb")
import pynhts
from diary import build_diaries, person_covariates
from schedule import diary_to_schedule

d = pynhts.load(2017)
persons = d.persons(["R_AGE_IMP", "WORKER", "HHVEHCNT", "TRAVDAY"])
trips = d.trips(["TDTRPNUM", "STRTTIME", "ENDTIME", "WHYTO", "WHYFROM"], keys=True)
diary, rep = build_diaries(persons, trips); print(rep)
cov = person_covariates(persons)
hh = persons["HOUSEID"].to_numpy(); uh = np.unique(hh)
rng = np.random.default_rng(1000)  # split 0, same as the local pipeline
te = np.isin(hh, list(set(rng.choice(uh, size=len(uh) // 2, replace=False)))); tr = ~te
sched = diary_to_schedule(diary)
n = sched.groupby("pid").size(); keep = n.index[n <= 16]
def attrs(mask):
    c = cov[mask]
    return pd.DataFrame({"pid": np.flatnonzero(mask), "age": c["age"].astype(str).to_numpy(),
        "worker": c["worker"].astype(str).to_numpy(), "veh": c["veh"].astype(str).to_numpy(),
        "weekend": c["weekend"].astype(str).to_numpy()})
tr_pids = np.intersect1d(np.flatnonzero(tr), keep)
out = "/content/caveat_run"
import os; os.makedirs(out, exist_ok=True)
sched[sched.pid.isin(tr_pids)].to_csv(out + "/train_schedules.csv", index=False)
attrs(np.isin(np.arange(len(tr)), tr_pids)).to_csv(out + "/train_attributes.csv", index=False)
attrs(te).to_csv(out + "/test_attributes.csv", index=False)
h = lambda p: hashlib.sha256(",".join(map(str, pd.read_csv(p)["pid"])).encode()).hexdigest()
ok = (h(out + "/train_attributes.csv") == "501683a613223f4ab2ddc3efdac75fae408f984d8d00bc67b11474c4c797bd19", h(out + "/test_attributes.csv") == "b138f71999e2d1e9e26f732d138e31dcc0f266a013ce5efc52f417b78aab4dad",
      hashlib.sha256(open(out + "/train_schedules.csv", "rb").read()).hexdigest() == "48657ae395595359c2d47c8af9dd4a58658dd9dc6c491fc0b4c715e6f8f0d906")
print("matches local export (train pids, test pids, train schedules):", ok)
assert all(ok[:2]), "household split differs from the local one: stop and tell Claude"
if not ok[2]:
    print("WARNING: schedule bytes differ from local (formatting?); pids match, continuing")
