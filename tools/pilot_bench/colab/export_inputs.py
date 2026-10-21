
import hashlib, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, "/content/pb")
import pynhts
from diary import build_diaries, person_covariates
from schedule import diary_to_schedule

SPLIT = int(os.environ.get("SPLIT", "0"))  # seed 1000 + split, same as common.split in the local pipeline
# sha256 of (train pids, test pids, train_schedules.csv bytes) from the local export_caveat.py output
EXPECTED = {
    0: ("501683a613223f4ab2ddc3efdac75fae408f984d8d00bc67b11474c4c797bd19",
        "b138f71999e2d1e9e26f732d138e31dcc0f266a013ce5efc52f417b78aab4dad",
        "48657ae395595359c2d47c8af9dd4a58658dd9dc6c491fc0b4c715e6f8f0d906"),
    1: ("caf6c8fbe56f9b3345b03398302d9d11e6c0052e675831814fdcf5fc0c810ed2",
        "66e4c05c5f46c052a8d7306b086bba695f34b35e867aef5c8e2018c2f1b34917",
        "c7d8a9d9de774255de042492998a8c2389d6caeb625bd330eecd65ae27613707"),
    2: ("ec76e2d698b5536188d8c3e216de0e96591b003cf8d6fc1417a5a993bf8079ce",
        "d5fd27efc8a0cf8c4e1b4a1dc4aff835db0f9ada11b019bfc391c3fac33a4044",
        "43653e365d727fdb999f5557c1f773cb4d722ee4c3074d38496e61acf28d0247"),
    3: ("0a125b87d944ad96cb2bfc211e7464471c8c35d9adb3ec6270946567dede92ef",
        "3820f5fcada52e76d0d51d878ea6a0fc357ad6dd28b2369fbd971ca95a327154",
        "0fb20e3a93933fd30a3c937e0ac9fc8a60c92352f4acf9b341de5a88c3fff88d"),
    4: ("229a7e25d7fe19a99959977bad5107093997d3edc470d29b28a1d68d459fc1d1",
        "0a0312f0755b511c9bc2479c1abc40546f69eb2d6384e130526dbbecd42d98dd",
        "c78b5ae5a7a7b61062579c54ffbbe1c8f86d9c7e947cb2eeaa95e0096239237a"),
}
d = pynhts.load(2017)
persons = d.persons(["R_AGE_IMP", "WORKER", "HHVEHCNT", "TRAVDAY"])
trips = d.trips(["TDTRPNUM", "STRTTIME", "ENDTIME", "WHYTO", "WHYFROM"], keys=True)
diary, rep = build_diaries(persons, trips); print(rep)
cov = person_covariates(persons)
hh = persons["HOUSEID"].to_numpy(); uh = np.unique(hh)
rng = np.random.default_rng(1000 + SPLIT)
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
os.makedirs(out, exist_ok=True)
sched[sched.pid.isin(tr_pids)].to_csv(out + "/train_schedules.csv", index=False)
attrs(np.isin(np.arange(len(tr)), tr_pids)).to_csv(out + "/train_attributes.csv", index=False)
attrs(te).to_csv(out + "/test_attributes.csv", index=False)
h = lambda p: hashlib.sha256(",".join(map(str, pd.read_csv(p)["pid"])).encode()).hexdigest()
got = (h(out + "/train_attributes.csv"), h(out + "/test_attributes.csv"),
       hashlib.sha256(open(out + "/train_schedules.csv", "rb").read()).hexdigest())
print("split", SPLIT, "hashes:", got)
if SPLIT in EXPECTED:
    ok = tuple(a == b for a, b in zip(got, EXPECTED[SPLIT]))
    print("matches local export (train pids, test pids, train schedules):", ok)
    assert all(ok[:2]), "household split differs from the local one: stop and tell Claude"
    if not ok[2]:
        print("WARNING: schedule bytes differ from local (formatting?); pids match, continuing")
else:
    print("no local hashes registered for this split: cannot verify against the laptop")
