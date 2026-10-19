"""How far do unweighted (sample) statistics sit from the survey-weighted (population) ones?

Effect size of the "evaluation frame" problem: a generator trained or scored without survey weights
reproduces the sample, not the population. Output: paper/pilot/sample_vs_population.csv
"""
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

b = common.load()
r, w = b.real, b.w
rows = []
for c in ["trips", "any_trip", "trips_3plus", "min_home", "min_work", "min_school", "min_maint", "min_leisure", "work_at_10"]:
    y = r[c].to_numpy()
    est, se = b.mean_est(y, np.ones(len(r), bool))  # weighted mean with JKn SE
    unw = float(np.nanmean(y))
    rows.append(dict(stat=c, unweighted=unw, weighted=est, se_weighted=se,
                     diff_pct=100 * (unw - est) / est if est else np.nan, diff_in_se=(unw - est) / se))
out = pd.DataFrame(rows)
dst = common.ROOT / "paper" / "pilot" / "sample_vs_population.csv"
out.round(4).to_csv(dst, index=False)
print(out.round(3).to_string(index=False))
