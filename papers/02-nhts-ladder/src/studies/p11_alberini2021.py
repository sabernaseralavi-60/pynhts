"""P11 Alberini et al. (2021): elasticity of vehicle miles with respect to fuel cost per mile, NHTS 2017.

Published: Table 8, OLS of ln(annual miles) on ln(price per mile), household controls and make / MSA category /
density / state fixed effects, with robust standard errors; vehicles of households with a main driver, top and bottom 1 %
of each mileage measure dropped (Panel A), then vehicles under 1,000 miles dropped (Panel B). Only the two NHTS-supplied
measures (ANNMILES, BESTMILE) are rebuilt; the paper's own constructions (MILESDRIVEN, TRIPANNMILES) are outside this run.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import engine  # noqa: E402

engine.setup()
import pynhts  # noqa: E402

PUB = {("A", "ANNMILES"): -0.5102, ("A", "BESTMILE"): -0.2279, ("B", "ANNMILES"): -0.2746, ("B", "BESTMILE"): -0.1932}
PUB_N = {("A", "ANNMILES"): 135073, ("A", "BESTMILE"): 180970, ("B", "ANNMILES"): 122397, ("B", "BESTMILE"): 175577}


def build(d):
    v = d.vehicles(["MAKE", "GSCOST", "FEGEMPG", "ANNMILES", "BESTMILE", "VEHTYPE", "HHSTATE", "PERSONID"],
                   missing="nan", skip="auto")
    h = d.households(["HHFAMINC", "HHSIZE", "NUMADLT", "YOUNGCHILD", "WRKCOUNT", "DRVRCNT", "HHVEHCNT", "MSACAT", "HBPPOPDN"],
                     missing="nan", skip="auto", weight=False)
    s = v[v["VEHTYPE"].isin(["01", "02", "03"]) & ~v["HHSTATE"].isin(["AK", "HI"])].merge(h, on="HOUSEID", how="left")
    s = s[s["PERSONID"].notna() & s["GSCOST"].notna() & s["FEGEMPG"].gt(0) & s["MAKE"].notna() & s["MSACAT"].notna()]
    s["lppm"] = np.log(pd.to_numeric(s["GSCOST"]) / pd.to_numeric(s["FEGEMPG"]))
    inc = pd.to_numeric(s["HHFAMINC"], errors="coerce")
    s = s[inc.between(1, 11)].copy()
    s["lincome"] = np.log(inc.map({1: 5, 2: 12.5, 3: 20, 4: 30, 5: 42.5, 6: 62.5, 7: 87.5, 8: 112.5, 9: 137.5, 10: 175, 11: 250}))
    return s.reset_index(drop=True)


def design_matrix(s):
    X = pd.DataFrame({"const": 1.0, "lppm": s["lppm"], "lincome": s["lincome"]})
    for c in ("HHSIZE", "NUMADLT", "YOUNGCHILD", "WRKCOUNT", "DRVRCNT", "HHVEHCNT"):
        X[c] = pd.to_numeric(s[c])
    X = X.join(pd.get_dummies(s["MAKE"], prefix="make", drop_first=True, dtype=float))
    X = X.join(pd.get_dummies(s["MSACAT"], prefix="msa", drop_first=True, dtype=float))
    X = X.join(pd.get_dummies(pd.to_numeric(s["HBPPOPDN"]).clip(upper=30000).pipe(
        lambda x: pd.cut(x, [-1, 99, 499, 999, 1999, 3999, 9999, 40000], labels=False)), prefix="dens", drop_first=True, dtype=float))
    X = X.join(pd.get_dummies(s["HHSTATE"], prefix="st", drop_first=True, dtype=float))
    return X


def run(replicates=True) -> pd.DataFrame:
    d = pynhts.load(2017, replicates=True)
    s = build(d)
    out = []
    for panel in ("A", "B"):
        for y in ("ANNMILES", "BESTMILE"):
            m = s[y].notna() & s[y].gt(0)
            lo, hi = s.loc[m, y].quantile([0.01, 0.99])
            m &= s[y].between(lo, hi)
            if panel == "B":
                m &= s[y] >= 1000
            sub = s[m].reset_index(drop=True)
            X = design_matrix(sub)
            des = engine.design_for(d, sub[["HOUSEID"]], "household")
            res = engine.fit_regimes(X, np.log(sub[y].to_numpy(float)), des, "gaussian", replicates=replicates)
            res = res[res["term"].isin(["lppm", "lincome"])].copy()
            res.insert(0, "model", f"{panel}_{y}")
            res["published"] = np.where(res["term"] == "lppm", PUB[(panel, y)], np.nan)
            res["n"] = len(sub)
            res["n_published"] = PUB_N[(panel, y)]
            out.append(res)
    return pd.concat(out, ignore_index=True)


if __name__ == "__main__":
    with engine.Timer() as t:
        r = run()
    r.to_csv(engine.RESULTS / "tables" / "p11_models.csv", index=False)
    print(f"{t.dt:.0f} s")
    with pd.option_context("display.width", 250, "display.max_rows", 100):
        print(r.round(4).to_string())
