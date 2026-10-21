
import hashlib, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, "/content/pb")
import pynhts
from diary import build_diaries, person_covariates
from schedule import diary_to_schedule

SPLIT = int(os.environ.get("SPLIT", "0"))  # seed 1000 + split, same as common.split in the local pipeline
# sha256 of (train pids, test pids, train_schedules.csv with LF line endings; Windows writes CRLF) from the local export_caveat.py output
EXPECTED = {
    0: ("501683a613223f4ab2ddc3efdac75fae408f984d8d00bc67b11474c4c797bd19",
        "b138f71999e2d1e9e26f732d138e31dcc0f266a013ce5efc52f417b78aab4dad",
        "371fba958e526c69ddf3b4fabfc6899d6cee6ade58540d344d58b5348bb84f88"),
    1: ("caf6c8fbe56f9b3345b03398302d9d11e6c0052e675831814fdcf5fc0c810ed2",
        "66e4c05c5f46c052a8d7306b086bba695f34b35e867aef5c8e2018c2f1b34917",
        "0ea21753dadb45577d5ac1420d93c3abad1a07a6545bfa6401ec53b0daa037dd"),
    2: ("ec76e2d698b5536188d8c3e216de0e96591b003cf8d6fc1417a5a993bf8079ce",
        "d5fd27efc8a0cf8c4e1b4a1dc4aff835db0f9ada11b019bfc391c3fac33a4044",
        "d2968a10684d6439a2a7e39d1e3c5f98bdb9768789834a5d118fe50fcc3f92e0"),
    3: ("0a125b87d944ad96cb2bfc211e7464471c8c35d9adb3ec6270946567dede92ef",
        "3820f5fcada52e76d0d51d878ea6a0fc357ad6dd28b2369fbd971ca95a327154",
        "623e0a61c95787e90f882b23ce283a8f34dfe62bb2b0ddf039cb46e1d60319c6"),
    4: ("229a7e25d7fe19a99959977bad5107093997d3edc470d29b28a1d68d459fc1d1",
        "0a0312f0755b511c9bc2479c1abc40546f69eb2d6384e130526dbbecd42d98dd",
        "fb029b20242c8c512a7342f44ae6317481d691a48c9e31d504ad11e5af3c6fb9"),
}
CRLF, LF = bytes([13, 10]), bytes([10])
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
       hashlib.sha256(open(out + "/train_schedules.csv", "rb").read().replace(CRLF, LF)).hexdigest())
print("split", SPLIT, "hashes:", got)
if SPLIT in EXPECTED:
    ok = tuple(a == b for a, b in zip(got, EXPECTED[SPLIT]))
    print("matches local export (train pids, test pids, train schedules):", ok)
    assert all(ok[:2]), "household split differs from the local one: stop and tell Claude"
    if not ok[2]:
        print("WARNING: schedule bytes differ from local (formatting?); pids match, continuing")
else:
    print("no local hashes registered for this split: cannot verify against the laptop")
