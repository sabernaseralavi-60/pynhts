"""P13 / P15 Zhang & Zhang (2018): ZINB of 30-day bikesharing (nine states) and ridesharing (all states) on public-transit use.

Published headline (abstracts): one more public-transit use per month is associated with a 4.0 % higher probability and a
1.4 % higher frequency of bikesharing (P13), and a 5.7 % higher probability and 1.2 % higher frequency of ridesharing
(P15). The full covariate set is the one of P14 (same authors, same file) without the vehicle-ownership levels.
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
from zhang_common import COMMON, NINE, p, raw  # noqa: E402

import pynhts  # noqa: E402

TERMS = ["pt", "female", "age", "edu", "white", "worker", "driver", "inc", "veh", "lndens", "rail", "urban", "spring", "summer", "winter"]
# The printed headline effects (percentages in the abstracts) cannot be mapped onto the coefficients of a zero-inflated model
# without a model-specific conversion, so no printed target is graded here: these two models are re-estimated for their design
# effects only, with the specification of P14 (review of 2026-10-23, item 9).
PUB: dict = {"P13": {}, "P15": {}}


def build(paper):
    if paper == "P13":
        s = p[p["state"].isin(NINE) & p["bike"].notna()]
        y = "bike"
    else:
        s = p[p["ride"].notna()]
        y = "ride"
    cc = s.dropna(subset=["pt", "female", "age", "edu", "white", "inc", "veh", "lndens", "worker", "driver"])
    ids = raw.loc[cc.index, ["HOUSEID", "PERSONID"]].reset_index(drop=True)
    return cc.reset_index(drop=True), ids, y


def run(papers=("P13", "P15"), replicates=True) -> pd.DataFrame:
    d = pynhts.load(2017, replicates=True)
    out = []
    for paper in papers:
        cc, ids, y = build(paper)
        des = engine.design_for(d, ids, "person")
        X = cc[TERMS].copy()
        X.insert(0, "const", 1.0)
        res = cm.fit_regimes(X, X, cc[y].to_numpy(float), des, replicates=replicates)
        res.insert(0, "paper", paper)
        res["published"] = [PUB[paper].get(part) if t == "pt" else None for part, t in zip(res["part"], res["term"])]
        res["n"] = len(cc)
        out.append(res)
    return pd.concat(out, ignore_index=True)


if __name__ == "__main__":
    r = run()
    r.to_csv(engine.RESULTS / "tables" / "p13_p15_models.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_rows", 200):
        print(r[r["term"] == "pt"].round(4).to_string())
