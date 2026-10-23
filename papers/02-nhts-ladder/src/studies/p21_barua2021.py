"""P21 Barua et al. (2021): gradient boosting of household online purchases, NHTS 2009 and 2017.

Published: GBM test R2 0.72 (2009) / 0.71 (2017), RF 0.66/0.65, SVM 0.59/0.56, linear 0.11/0.11 on 16 of 48 candidate
variables. The household file is the unit; the response is the sum of the members' 30-day online purchases.
Here: the same model family on the 16 variables that can be built from the public file, under a random split
(the paper's design) and a split by state (whole states held out), and with survey-weighted R2.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import engine  # noqa: E402
import mlkit  # noqa: E402

engine.setup()
import pynhts  # noqa: E402
from pynhts import aggregate as A  # noqa: E402

warnings.filterwarnings("ignore")
PUB = {2009: {"gbm": 0.72, "rf": 0.66, "svm": 0.59, "lr": 0.11}, 2017: {"gbm": 0.71, "rf": 0.65, "svm": 0.56, "lr": 0.11}}


class SubsampledSVR:
    def __init__(self, n=15000, seed=0):
        self.n, self.seed = n, seed

    def fit(self, X, y):
        idx = np.random.default_rng(self.seed).choice(len(y), min(self.n, len(y)), replace=False)
        self.m = make_pipeline(StandardScaler(), SVR(kernel="rbf", C=10, gamma=0.01))
        self.m.fit(X[idx], y[idx])
        return self

    def predict(self, X):
        return self.m.predict(X)


MODELS = {
    "lr": lambda: LinearRegression(),
    "svm": lambda: SubsampledSVR(),
    "rf": lambda: RandomForestRegressor(n_estimators=200, min_samples_leaf=25, max_features=0.5, n_jobs=6, random_state=0),
    "gbm": lambda: GradientBoostingRegressor(n_estimators=300, max_depth=5, learning_rate=0.05, subsample=0.8, random_state=0),
}


def build(d, wave):
    buy = "PURCHASE" if wave == 2009 else "DELIVER"
    hh = A.aggregate(d, "person", "household", {
        "y": A.Agg.sum(buy), "avg_age": A.Agg.mean("R_AGE"), "n_persons": A.Agg.n(),
        "male": A.Agg.share(A.Where("R_SEX", "==", "01")), "trips_day": A.Agg.sum("CNTTDTR"),
        "bach": A.Agg.share(A.Where("EDUC", "in", ["04", "05"])), "nohs": A.Agg.share(A.Where("EDUC", "==", "01")),
        "adult": A.Agg.share(A.Where("R_AGE", ">=", 18)),
    }, base_columns=["HHFAMINC", "HHSIZE", "HHVEHCNT", "HBPPOPDN", "URBRUR", "HHSTATE", "HOMEOWN"], missing="propagate")
    kept = hh[hh["y"].notna()].copy()
    inc = pd.to_numeric(kept["HHFAMINC"], errors="coerce")
    mids = ({1: 2.5, 2: 7.5, 3: 12.5, 4: 17.5, 5: 22.5, 6: 27.5, 7: 32.5, 8: 37.5, 9: 42.5, 10: 47.5, 11: 52.5, 12: 57.5,
             13: 62.5, 14: 67.5, 15: 72.5, 16: 77.5, 17: 90, 18: 100} if wave == 2009 else
            {1: 5, 2: 12.5, 3: 20, 4: 30, 5: 42.5, 6: 62.5, 7: 87.5, 8: 112.5, 9: 137.5, 10: 175, 11: 250})
    kept["income"] = inc.map(mids)
    kept["hhsize"] = pd.to_numeric(kept["HHSIZE"])
    kept["veh0"] = (pd.to_numeric(kept["HHVEHCNT"]) == 0).astype(float)
    kept["urban"] = (kept["URBRUR"] == "01").astype(float)
    kept["popden"] = pd.to_numeric(kept["HBPPOPDN"])
    kept["own"] = (kept["HOMEOWN"] == "01").astype(float)
    feats = ["avg_age", "male", "hhsize", "income", "adult", "nohs", "bach", "veh0", "trips_day", "urban", "popden", "own"]
    kept = kept.dropna(subset=feats + ["y", "WTHHFIN"])
    return kept.reset_index(drop=True), feats


def run(waves=(2009, 2017), seeds=(0, 1, 2)) -> pd.DataFrame:
    rows = []
    for wave in waves:
        d = pynhts.load(wave)
        k, feats = build(d, wave)
        X, y = k[feats].to_numpy(float), k["y"].to_numpy(float)
        for scheme, groups in (("random", None), ("state_holdout", k["HHSTATE"].to_numpy())):
            for name, mk in MODELS.items():
                for s in seeds:
                    r = mlkit.regress(mk, X, y, groups, k["WTHHFIN"].to_numpy(), scheme, s)
                    rows.append({"wave": wave, "scheme": scheme, "model": name, "seed": s, "n": len(k),
                                 "published_r2": PUB[wave][name], **r})
                    print(wave, scheme, name, s, round(r["r2"], 3), flush=True)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    r = run()
    r.to_csv(engine.RESULTS / "tables" / "p21_models.csv", index=False)
    print(r.groupby(["wave", "scheme", "model"])[["r2", "r2_w", "rmse", "published_r2"]].mean().round(3).to_string())
