"""P14 - Zhang & Zhang (2018), Sustainability 10:2720: household vehicle ownership and ridesharing (35 states + DC), 2017 NHTS.

Sample and helpers: zhang_common.py. Unweighted statistics, as in the paper (Stata).
"""

from __future__ import annotations

import pandas as pd  # noqa: F401

import common
from zhang_common import COMMON, EXCLUDED_15, NINE, distribution, p, table  # noqa: F401

# =================================================== P14  vehicle ownership and ridesharing (35 states + DC)
a = common.Audit("p14_zhang2018_vehicle_rideshare")
ok_states = p[~p["state"].isin(EXCLUDED_15)]
answered = ok_states[ok_states["ride"].notna()]
a.check("answered the ridesharing question (35 states + DC)", 228002, len(answered))
cc = answered.dropna(subset=["veh", "age", "female", "edu", "inc", "white", "worker", "driver", "lndens", "rent", "pt"])
a.check("complete cases, ZINB sample", 219026, len(cc), "complete case on the Table 1 covariates; the paper's own arithmetic is consistent (228,002 - 8,976)")
a.check("zero counts", 202209, int((cc["ride"] == 0).sum()))
a.check("non-zero counts", 16817, int((cc["ride"] > 0).sum()))
distribution(a, cc["ride"], [("1", 1, 1, 28.32), ("2", 2, 2, 25.15), ("1-5", 1, 5, 81.19), ("6-20", 6, 20, 17.61), ("21-99", 21, 99, 1.21)])
for k, lab in ((0, "Vehicle 0"), (1, "Vehicle 1"), (2, "Vehicle 2")):
    cc = cc.assign(**{f"v{k}": (cc["veh"] == k).astype(float)})
cc = cc.assign(v3=(cc["veh"] >= 3).astype(float))
table(a, cc, {
    "ride": (0.309, 1.757, 0, 99), "veh": (2.232, 1.231, 0, 12), "v0": (0.033, 0.180, 0, 1), "v1": (0.229, 0.420, 0, 1),
    "v2": (0.415, 0.493, 0, 1), "v3": (0.322, 0.467, 0, 1), "female": (0.531, 0.499, 0, 1), "age": (53.025, 18.245, 16, 92),
    "edu": (3.332, 1.185, 1, 5), "white": (0.822, 0.383, 0, 1), "worker": (0.549, 0.498, 0, 1), "driver": (0.919, 0.272, 0, 1),
    "inc": (6.315, 2.593, 1, 11), "rent": (0.212, 0.409, 0, 1), "lndens": (7.172, 1.752, 3.9, 10.3), "rail": (0.161, 0.368, 0, 1),
    "urban": (0.770, 0.421, 0, 1), "pt": (0.895, 4.345, 0, 240), "spring": (0.205, 0.403, 0, 1), "summer": (0.259, 0.438, 0, 1),
    "fall": (0.266, 0.442, 0, 1), "winter": (0.270, 0.444, 0, 1)}, "T1")
a.save()

