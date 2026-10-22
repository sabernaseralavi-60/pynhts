"""P16 - Sabouri, Brewer & Ewing (2020), Landscape and Urban Planning 198: 103797.

Ride-sourcing and household vehicle ownership with the 2017 NHTS, multilevel Poisson and ML. The analysis sample is the
households whose home CENSUS TRACT is known (115,755 of 129,696), a geocode that is not in the public file, and the
D-variables (activity density, intersection density, transit stops, Uber launch year) are external. Part A checks what
the public file can say: the file sizes quoted in the text, and the household means of Table 1 on the households that
have a trip record (the probable base of the paper's sample, see the gasoline-price row).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import common

common.setup()
import pynhts  # noqa: E402

a = common.Audit("p16_sabouri2020")
d = pynhts.load(2017)
trips = d.trips(["GASPRICE", "TRPMILES"], missing="keep", skip="keep", weight=False)
a.check("trips in the pooled data", 923572, len(trips))
cols = ["HHSIZE", "WRKCOUNT", "DRVRCNT", "HHVEHCNT", "HHFAMINC", "HOMEOWN", "HH_RACE", "TAXI"]
hh = d.households(cols, missing="keep", skip="keep", weight=False)
a.check("households", 129696, len(hh))

gas = pd.to_numeric(trips["GASPRICE"]).groupby(trips["HOUSEID"]).mean().rename("gas")
hh = hh.join(gas, on="HOUSEID")
p = d.persons(["RIDESHARE"], missing="keep", skip="keep", weight=False)
r = pd.to_numeric(p["RIDESHARE"]).where(lambda s: s >= 0)
hh = hh.join(r.groupby(p["HOUSEID"]).mean().rename("rideshare"), on="HOUSEID")

MID = {1: 5, 2: 12.5, 3: 20, 4: 30, 5: 42.5, 6: 62.5, 7: 87.5, 8: 112.5, 9: 137.5, 10: 175, 11: 250}
inc = pd.to_numeric(hh["HHFAMINC"]).map(MID)
hh["lnincome"] = np.log(inc / 10)
hh["veh"] = pd.to_numeric(hh["HHVEHCNT"])
hh["hhsize"] = pd.to_numeric(hh["HHSIZE"])
hh["employed"] = pd.to_numeric(hh["WRKCOUNT"])
hh["drivers"] = pd.to_numeric(hh["DRVRCNT"])

T1 = {  # variable: (N, mean, sd) as printed
    "veh": (115755, 2.021, 1.173), "hhsize": (115755, 2.184, 1.181), "employed": (115755, 1.050, 0.899),
    "lnincome": (112210, 1.686, 0.554), "drivers": (115755, 1.719, 0.761), "gas": (115755, 240.238, 22.867),
    "rideshare": (115755, 0.351, 1.685),
}
for scope, base in (("all households", hh), ("households with a trip record", hh[hh["gas"].notna()])):
    a.info(f"[{scope}] n", len(base), "paper's sample: 115,755 households with a known home census tract")
    for v, (n, m, sd) in T1.items():
        a.check(f"[{scope}] mean {v}", m, float(base[v].mean()), "")
        a.check(f"[{scope}] sd {v}", sd, float(base[v].std(ddof=1)))
a.info("households with a trip record (gas price known)", int(hh["gas"].notna().sum()),
       "the gas price exists only for households with trips and the paper has it for all 115,755 households, so its sample is a subset "
       "of these 117,222; on this base the means of vehicles, size, workers and drivers agree with Table 1 within 0.2 %")
a.info("share of households that report taxi/rideshare use (TAXI 01-04)",
       float(hh["TAXI"].isin(["01", "02", "03", "04"]).mean()), "TAXI answered: 104,219 in the paper; not an NHTS count here")
a.rows.append({"item": "D variables (activity density, job-pop balance, transit stops, intersection density, Uber years)",
               "published": None, "pynhts": None, "status": "NOT_COMPUTABLE",
               "note": "need the home census tract (restricted file) and ACS/LEHD/Intermodal/Uber external data"})
a.save()
