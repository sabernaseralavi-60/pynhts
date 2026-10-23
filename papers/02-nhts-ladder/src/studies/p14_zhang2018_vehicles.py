"""P14 Zhang & Zhang (2018): ZINB of 30-day ridesharing count on household vehicles, 35 states + DC, NHTS 2017.

Published: Table 2A, unweighted Stata zinb with the same covariates in the count and the inflation part.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "tools" / "paper_audit"))
import countmodels as cm  # noqa: E402
import engine  # noqa: E402

engine.setup()
from zhang_common import COMMON, EXCLUDED_15, p, raw  # noqa: E402

import pynhts  # noqa: E402

PUB_COUNT = {"const": 0.572, "veh": -0.082, "female": -0.100, "age": -0.010, "edu": -0.032, "white": 0.014,
             "worker": 0.009, "driver": -0.445, "inc": 0.059, "rent": 0.234, "lndens": 0.138, "rail": 0.109,
             "urban": -0.358, "pt": 0.012, "spring": 0.131, "summer": -0.090, "winter": 0.004}
PUB_INFL = {"const": 6.071, "veh": 0.207, "female": 0.109, "age": 0.040, "edu": -0.464, "white": -0.160,
            "worker": -0.368, "driver": -0.342, "inc": -0.242, "rent": -0.610, "lndens": -0.264, "rail": -0.307,
            "urban": -0.238, "pt": -0.059, "spring": 0.072, "summer": 0.114, "winter": -0.080}
TERMS = ["veh", "female", "age", "edu", "white", "worker", "driver", "inc", "rent", "lndens", "rail", "urban", "pt",
         "spring", "summer", "winter"]


def build():
    ok = p[~p["state"].isin(EXCLUDED_15)]
    ok = ok[ok["ride"].notna()]
    cc = ok.dropna(subset=["veh", "age", "female", "edu", "inc", "white", "worker", "driver", "lndens", "rent", "pt"])
    ids = raw.loc[cc.index, ["HOUSEID", "PERSONID"]].reset_index(drop=True)
    return cc.reset_index(drop=True), ids


def run(replicates=True) -> pd.DataFrame:
    d = pynhts.load(2017, replicates=True)
    cc, ids = build()
    des = engine.design_for(d, ids, "person")
    X = cc[TERMS].copy()
    X.insert(0, "const", 1.0)
    res = cm.fit_regimes(X, X, cc["ride"].to_numpy(), des, replicates=replicates)
    res["published"] = [PUB_COUNT.get(t) if part == "count" else PUB_INFL.get(t) if part == "inflate" else None
                        for part, t in zip(res["part"], res["term"])]
    res.attrs["n"] = len(cc)
    return res


if __name__ == "__main__":
    with engine.Timer() as t:
        r = run()
    r.to_csv(engine.RESULTS / "tables" / "p14_models.csv", index=False)
    print(f"{t.dt:.0f} s; n = {r.attrs['n']}; ll naive = {r.attrs.get('ll_naive')}")
    with pd.option_context("display.width", 250, "display.max_rows", 100):
        print(r.round(3).to_string())
