"""P15 - Zhang & Zhang (2018), IJERPH 15:1763: ridesharing and public transit use, 2017 NHTS.

Sample and helpers: zhang_common.py. Unweighted statistics, as in the paper (Stata).
"""

from __future__ import annotations

import pandas as pd  # noqa: F401

import common
from zhang_common import COMMON, EXCLUDED_15, NINE, distribution, p, table  # noqa: F401

# =================================================== P15  ridesharing and public transit (all states)
a = common.Audit("p15_zhang2018_rideshare_transit")
answered = p[p["ride"].notna()]
a.check("answered the ridesharing question", 236089, len(answered))
with_pt = answered[answered["pt"].notna()]
a.check("excluded for missing public transit use", 206, len(answered) - len(with_pt))
cc = with_pt.dropna(subset=["female", "age", "edu", "white", "inc", "veh", "lndens"])
a.check("excluded for missing covariates", 9265, len(with_pt) - len(cc))
a.check("ZINB sample", 226824, len(cc))
a.info("paper arithmetic: 236,089 - 206 - 9,265", 236089 - 206 - 9265,
       "the paper prints 226,824 = 236,089 - 9,265: the 206 are counted twice in the text")
a.check("zero counts", 209794, int((cc["ride"] == 0).sum()))
a.check("non-zero counts", 17030, int((cc["ride"] > 0).sum()))
distribution(a, cc["ride"], [("1", 1, 1, 28.39), ("2", 2, 2, 25.17), ("1-5", 1, 5, 81.27), ("6-10", 6, 10, 13.01),
                             ("11-20", 11, 20, 4.53), ("21-40", 21, 40, 0.97), ("41-99", 41, 99, 0.23)])
cc = cc.dropna(subset=["worker", "driver", "rent"])
table(a, cc, {
    "ride": (0.301, 1.732, 0, 99), "pt": (0.879, 4.297, 0, 240), "female": (0.531, 0.499, 0, 1), "age": (53.022, 18.256, 16, 92),
    "edu": (3.330, 1.185, 1, 5), "white": (0.825, 0.380, 0, 1), "worker": (0.549, 0.498, 0, 1), "driver": (0.920, 0.271, 0, 1),
    "inc": (6.303, 2.588, 1, 11), "veh": (2.240, 1.238, 0, 12), "rent": (0.211, 0.408, 0, 1), "lndens": (7.150, 1.758, 3.9, 10.3),
    "rail": (0.157, 0.364, 0, 1), "urban": (0.766, 0.424, 0, 1), "spring": (0.205, 0.404, 0, 1), "summer": (0.259, 0.438, 0, 1),
    "fall": (0.267, 0.442, 0, 1), "winter": (0.270, 0.444, 0, 1)}, "T1")
a.save()
