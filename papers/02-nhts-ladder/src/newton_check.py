"""Check of the Newton/chord replicate variance against exact refits on one real model (P18 weekend negative binomial).

Writes results/tables/newton_check.csv with the Newton and the exact jackknife standard error of every coefficient.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "studies"))
import countmodels as cm  # noqa: E402
import engine  # noqa: E402

engine.setup()
import p18_jiao2020 as P  # noqa: E402

import pynhts  # noqa: E402


def main() -> None:
    d = pynhts.load(2017, replicates=True)
    s, X = P.build(d)
    m = ~s["wkday"].to_numpy()
    sub = s[m].reset_index(drop=True)
    Xs = X[m].reset_index(drop=True)
    des = engine.design_for(d, sub[["HOUSEID", "PERSONID"]], "person")
    y = sub["CNTTDTR"].to_numpy(float)
    res = cm.fit_regimes(Xs, None, y, des, replicates=True)
    sc = len(y) / des.w.sum()
    Xa = Xs.to_numpy(float)
    full = res["b_design"].to_numpy()
    reps = np.empty((des.n_reps, len(full)))
    for r in range(des.n_reps):
        reps[r], _ = cm.fit(Xa, None, y, des.reps[:, r].astype(float) * sc, start=full, ftol=1e-13)
    se_exact = np.sqrt(des.factor * np.sum((reps - full) ** 2, axis=0))
    out = pd.DataFrame({"term": res["term"], "se_newton": res["se_design"].to_numpy(), "se_exact": se_exact})
    out["rel_diff"] = out["se_newton"] / out["se_exact"] - 1
    out.to_csv(engine.RESULTS / "tables" / "newton_check.csv", index=False)
    print(out.round(5).to_string())
    print("max relative difference:", float(out["rel_diff"].abs().max()))


if __name__ == "__main__":
    main()
