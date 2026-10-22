"""P13 - Zhang & Zhang (2018), Sustainability 10:1868: public transit use and bikesharing, nine states, 2017 NHTS.

Sample and helpers: zhang_common.py. Unweighted statistics, as in the paper (Stata).
"""

from __future__ import annotations

import pandas as pd  # noqa: F401

import common
from zhang_common import COMMON, EXCLUDED_15, NINE, distribution, p, table  # noqa: F401

# =================================================== P13  bikesharing (nine states)
a = common.Audit("p13_zhang2018_bikeshare")
nine = p[p["state"].isin(NINE)]
answered = nine[nine["bike"].notna()]
a.check("answered the bikesharing question (nine states)", 20925, len(answered))
cc = answered.dropna(subset=["pt", *COMMON])
a.check("complete cases, ZINB sample", 17824, len(cc), "complete case on public transit use and the model covariates")
a.check("zero counts", 16850, int((cc["bike"] == 0).sum()))
a.check("non-zero counts", 974, int((cc["bike"] > 0).sum()))
a.check("share not using bikesharing, %", 94.54, float((cc["bike"] == 0).mean() * 100))
a.check("mean monthly bikesharing, all", 0.46, float(cc["bike"].mean()))
a.check("mean monthly bikesharing, users", 8.36, float(cc.loc[cc["bike"] > 0, "bike"].mean()))
distribution(a, cc["bike"], [("1", 1, 1, 20.84), ("1-5", 1, 5, 57.08), ("6-10", 6, 10, 19.20), ("11-20", 11, 20, 16.53),
                             ("21-99", 21, 99, 7.19)])
a.info("1-5 uses share vs. sum of printed bands", None, "the paper prints 'no more than five' 57.08 % and 20.84 % once; the bands 6-10, 11-20, 21-99 sum to 42.9 %")
under16 = int((answered["age"] < 16).sum())
a.info("answerers aged under 16 (public file)", under16,
       "the bikesharing question is asked of children too; Table 2 prints Age min 16, so the 17,824 cannot contain them")
a.info("answerers aged 16+ (public file)", int((answered["age"] >= 16).sum()),
       "this is less than the printed 17,824: Table 2 (min age 16, N = 17,824) is not reproducible from 20,925 answerers")
a.info("paper arithmetic: 20,925 - 3,105", 20925 - 3105, "the paper prints 17,824 (4 more)")
a.info("complete cases without education/worker/driver (children kept)",
       len(answered.dropna(subset=["pt", "female", "age", "white", "inc", "veh", "lndens"])),
       "variant: these three are structurally missing for children; neither this nor the strict rule gives 17,824")
table(a, cc, {
    "bike": (0.457, 3.170, 0, 99), "pt": (1.602, 5.656, 0, 190), "female": (0.385, 0.487, 0, 1),
    "age": (48.297, 16.388, 16, 92), "edu": (3.662, 1.171, 1, 5), "white": (0.843, 0.364, 0, 1),
    "worker": (0.655, 0.475, 0, 1), "driver": (0.925, 0.264, 0, 1), "inc": (6.827, 2.694, 1, 11),
    "veh": (2.214, 1.236, 0, 12), "lndens": (7.499, 1.685, 3.91, 10.31), "rail": (0.166, 0.372, 0, 1),
    "urban": (0.828, 0.378, 0, 1), "spring": (0.179, 0.383, 0, 1), "summer": (0.396, 0.489, 0, 1),
    "fall": (0.210, 0.407, 0, 1), "winter": (0.216, 0.411, 0, 1)}, "T2")
a.info("public file max of public transit use (30-day count)", float(p["pt"].max()), "paper prints max 190 (Table 2), 240 in the two ridesharing papers")
a.info("persons at the public-file cap of 30 (all states)", int((p["pt"] == 30).sum()), "the public PTUSED is top-coded at 30; the papers' maxima (190, 240) come from another file version")
a.save()

