"""The same Yang et al. (2011) person-day outcomes as p01_yang2011.py, with the 0.7.0 API (about 12 lines).

p01 needed a hand-written trip groupby, a merge and fill-ins; here aggregate() does it with a diagnostics report.
Run: python tools/paper_audit/example_new_api.py   (all 65+ persons of the file, not the paper's 130,222-person analysis sample:
about 0.30 active trips/day and 15 % with an active trip; p01 applies the paper's exclusions and gets 0.3104 and 15.5 %)
"""

from __future__ import annotations

import warnings

import common

common.setup()
import pynhts  # noqa: E402
from pynhts import aggregate as A  # noqa: E402
from pynhts import eda  # noqa: E402

warnings.simplefilter("ignore")
d = pynhts.load(2001)
p = A.aggregate(
    d, "trip", "person",
    {"n_trips": A.Agg.n(), "n_active": A.Agg.n(A.Where("TRPTRANS", "in", ("25", "26")))},
    base_columns=["R_AGE", "HBHUR", "HHINCTTL", "R_SEX", "HHR_RACE"],
)
elderly = p[p["R_AGE"] >= 65]
w = elderly["WTPERFIN"]
mean_active = eda.weighted_mean_sd(elderly["n_active"], w)[0]
pat = eda.weighted_mean_sd((elderly["n_active"] > 0).astype(float), w)[0] * 100
print(f"65+: {len(elderly):,} persons, {mean_active:.4f} active trips/day, {pat:.1f} % with an active trip")
print(p.attrs["pynhts_aggregate"])
