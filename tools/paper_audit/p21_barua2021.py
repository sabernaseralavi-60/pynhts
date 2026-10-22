"""P21 - Barua, Zou, Zhou & Liu (2021), household online shopping demand, NHTS 2009 and 2017 (gradient boosting).

Household level: online purchases delivered to home in the last 30 days, summed over members (a household with a
missing member answer is dropped), and household averages of age, sex, size, income and daily trips. Table 3 of the
paper is internally inconsistent (see the rows marked INFO), so only the rows that can be read unambiguously are compared.
Built with pynhts.aggregate (persons -> households), the machine-learning models are out of scope.
"""

from __future__ import annotations

import pandas as pd

import common

common.setup()
import pynhts  # noqa: E402
from pynhts import aggregate as A  # noqa: E402

a = common.Audit("p21_barua2021")
PUB = {  # wave -> printed Table 3 rows (mean, sd) that can be read unambiguously
    2009: {"purchases": (3.4, 6.3, 0, 265), "avg_age": (52.7, 14.2, 18, 92), "male_pct": (44.2, 33.2, 0, 100),
           "hhsize": (2.6, 1.3, 1, 14), "income_k": (64.4, 29.7, 5, 100), "trips_day": (7.4, 4.7, 1, 52)},
    2017: {"purchases": (4.2, 6.4, 0, 198), "avg_age": (57.6, 23.8, 18, 92), "male_pct": (45.2, 34.6, 0, 100),
           "hhsize": (1.7, 0.7, 1, 10), "income_k": (72.7, 53.2, 10, 2000), "trips_day": (7.3, 4.5, 1, 60)},
}
for wave in (2009, 2017):
    d = pynhts.load(wave)
    a.check(f"{wave} persons", {2009: 308901, 2017: 264234}[wave], len(d.persons(["R_AGE"])))
    a.check(f"{wave} households", {2009: 150147, 2017: 129696}[wave], d.households(["HHSIZE"])["HOUSEID"].nunique())
    hh = A.aggregate(d, "person", "household", {
        "purchases": A.Agg.sum("PURCHASE" if wave == 2009 else "DELIVER"), "avg_age": A.Agg.mean("R_AGE"), "n_persons": A.Agg.n(),
        "male": A.Agg.share(A.Where("R_SEX", "==", "01")), "trips_day": A.Agg.sum("CNTTDTR"),
    }, base_columns=["HHFAMINC", "HHSIZE"], missing="propagate")
    a.info(f"{wave} households after aggregation", len(hh), "")
    kept = hh[hh["purchases"].notna()].copy()
    a.info(f"{wave} households with all members' purchase answers", len(kept),
           "the paper drops a household when a member's record is missing; 2009 uses PURCHASE (times purchased via the internet in the past "
           "month, asked of everyone 16+); DELIVER (2009) is a follow-up asked only of buyers")
    kept["male_pct"] = kept["male"] * 100
    kept["hhsize"] = pd.to_numeric(kept["HHSIZE"])
    inc = pd.to_numeric(kept["HHFAMINC"])
    mids = ({1: 2.5, 2: 7.5, 3: 12.5, 4: 17.5, 5: 22.5, 6: 27.5, 7: 32.5, 8: 37.5, 9: 42.5, 10: 47.5, 11: 52.5, 12: 57.5,
             13: 62.5, 14: 67.5, 15: 72.5, 16: 77.5, 17: 90, 18: 100} if wave == 2009 else
            {1: 5, 2: 12.5, 3: 20, 4: 30, 5: 42.5, 6: 62.5, 7: 87.5, 8: 112.5, 9: 137.5, 10: 175, 11: 250})
    kept["income_k"] = inc.map(mids)
    for var, (m, sd, lo, hi) in PUB[wave].items():
        x = pd.to_numeric(kept[var], errors="coerce")
        note = "" if var == "purchases" else "read from Table 3; its columns are misaligned in the paper"
        a.check(f"{wave} mean {var}", m, float(x.mean()), note)
        a.check(f"{wave} sd {var}", sd, float(x.std()))
        a.check(f"{wave} max {var}", hi, float(x.max()))
a.rows += [
    {"item": "Table 3: shopping-trip percentage 149.5-446 (2009), 201-295 (2017)", "published": None, "pynhts": None,
     "status": "INFO", "note": "a percentage cannot exceed 100: the row holds another quantity (probably a count or a mis-shifted column)"},
    {"item": "Table 3: household size mean 1.7 in 2017 (2.6 in 2009)", "published": None, "pynhts": None, "status": "INFO",
     "note": "the 2017 national mean household size is 2.1; 1.7 with max 10 is not the household-size column of the data"},
    {"item": "Table 3: 'Number of vehicles' typed Binary with mean 0.9 / 0.8, and 'Number of trips per day' listed twice", "published": None,
     "pynhts": None, "status": "INFO", "note": "rows are shifted against the labels; values cannot be matched to variables beyond the ones compared above"},
]
a.save()
