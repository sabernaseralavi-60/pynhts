"""Write the schedule tables needed to calibrate caveat/acteval distances (split `sp`)."""
import os, sys, glob
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from cart import CARTSynthesizer
from models import WeightedResampler
from schedule import diary_to_schedule

sp = int(sys.argv[1]) if len(sys.argv) > 1 else 0
out = common.ROOT / "local_data" / "acteval" / f"split{sp}"; out.mkdir(parents=True, exist_ok=True)
b = common.load(); tr, te = b.split(sp)
cov_tr, cov_te = b.cov[tr].reset_index(drop=True), b.cov[te].reset_index(drop=True)
pids_tr, pids_te = np.flatnonzero(tr), np.flatnonzero(te)
sched = diary_to_schedule(b.diary)
sched[sched.pid.isin(pids_te)].to_csv(out / "real_test.csv", index=False)
sched[sched.pid.isin(pids_tr)].to_csv(out / "real_train.csv", index=False)
pd.DataFrame({"pid": pids_te, "w": b.w[te]}).to_csv(out / "w_test.csv", index=False)
pd.DataFrame({"pid": pids_tr, "w": b.w[tr]}).to_csv(out / "w_train.csv", index=False)
m = WeightedResampler("fine").fit(b.diary[tr], cov_tr, b.w[tr])
diary_to_schedule(m.generate(cov_te, np.random.default_rng(sp)), pids_te).to_csv(out / "resample_fine.csv", index=False)
CARTSynthesizer().fit(sched, cov_tr, b.w[tr], pids_tr).generate(cov_te, np.random.default_rng(sp), pids_te).to_csv(out / "cart.csv", index=False)
for tag, run in (("caveat_light", "nhts_split0"), ("caveat", "nhts_split0_paper"), ("caveat_full", "nhts_split0_full")):
    files = sorted(glob.glob(str(common.ROOT / "local_data" / "caveat_run" / "logs" / run / "**" / "synthetic_schedules.csv"), recursive=True))
    if not files:
        continue
    cv = pd.read_csv(files[-1]); assert cv.pid.max() == len(pids_te) - 1  # caveat renumbers 0..n-1 in test_attributes order
    cv["pid"] = pids_te[cv["pid"].to_numpy()]; cv.to_csv(out / f"{tag}.csv", index=False)
    print("caveat", tag, files[-1])
print("exported to", out)
