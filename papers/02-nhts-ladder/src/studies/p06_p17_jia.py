"""P06 / P17 Jia (2019, 2020): classifiers of alternative-fuel (AFV) and electric (EV) vehicle adoption, NHTS 2017.

Published (P06): five classifiers on 31,322 new-vehicle owners, SMOTE for the 4.2 % minority; accuracy above 0.9 for
all five and AUC 0.924 (random forest) and 0.908 (decision tree). P17 uses the same sample with an EV label (1.29 %).
The papers do not say whether SMOTE preceded the train/test split; this study scores both orders and a household split.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import engine  # noqa: E402
import mlkit  # noqa: E402

engine.setup()
import pynhts  # noqa: E402

warnings.filterwarnings("ignore")
FEATURES = ["income", "homeown", "HHSIZE", "YOUNGCHILD", "HHVEHCNT", "urban", "popden", "PRICE", "PLACE", "R_AGE",
            "female", "educ", "race", "multijob", "occ", "carshare", "ttw", "ymile"]
PUBLISHED = {"P06": {"auc_rf": 0.924, "auc_dt": 0.908, "acc_min": 0.9}}


class SubsampledSVC:
    """RBF SVM trained on at most ``n`` random rows (full fit is quadratic in the resampled size)."""

    def __init__(self, n=12000, seed=0):
        self.n, self.seed = n, seed

    def fit(self, X, y):
        rng = np.random.default_rng(self.seed)
        idx = rng.choice(len(y), min(self.n, len(y)), replace=False)
        self.m = make_pipeline(StandardScaler(), SVC(kernel="rbf", C=1.0, gamma="scale"))
        self.m.fit(X[idx], y[idx])
        return self

    def decision_function(self, X):
        return self.m.decision_function(X)


MODELS = {
    "LR": lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
    "NB": lambda: GaussianNB(),
    "DT": lambda: DecisionTreeClassifier(criterion="entropy", min_samples_leaf=5, random_state=0),
    "RF": lambda: RandomForestClassifier(n_estimators=200, min_samples_leaf=2, n_jobs=6, random_state=0),
    "SVM": lambda: SubsampledSVC(),
}


def build(d):
    v = d.vehicles(["FUELTYPE", "HFUEL", "VEHAGE", "VEHTYPE", "HHFAMINC", "HHVEHCNT", "PERSONID"], missing="nan", skip="auto")
    pp = d.persons(["R_AGE", "R_SEX", "R_RACE", "EDUC", "OCCAT", "CARSHARE", "TIMETOWK", "YEARMILE", "GT1JBLWK"],
                   missing="nan", skip="keep").drop(columns=["WTPERFIN"], errors="ignore")
    hh = d.households(["HOMEOWN", "YOUNGCHILD", "PRICE", "PLACE", "HBPPOPDN", "URBRUR", "HHSIZE"], missing="nan", skip="keep")
    wt = hh[["HOUSEID", "WTHHFIN"]]
    hh = hh.drop(columns=["WTHHFIN"])
    m = v.drop(columns=["WTHHFIN"], errors="ignore").merge(pp, on=["HOUSEID", "PERSONID"], how="inner").merge(hh, on="HOUSEID", how="left")
    x = m[(m["VEHAGE"] <= 2) & m["FUELTYPE"].isin(["01", "02", "03"])].sort_values(["HOUSEID", "PERSONID", "VEHAGE"])
    x = x.drop_duplicates(["HOUSEID", "PERSONID"])
    for c in ("R_AGE", "HHVEHCNT", "HHSIZE", "YOUNGCHILD", "PRICE", "PLACE"):
        x[c] = pd.to_numeric(x[c])
    req = ["FUELTYPE", "VEHAGE", "R_AGE", "R_SEX", "HHFAMINC", "HHVEHCNT", "VEHTYPE"]
    k = x.dropna(subset=req + ["R_RACE", "EDUC", "PRICE", "PLACE", "HOMEOWN", "URBRUR", "HBPPOPDN"]).copy()
    for c in ("R_RACE", "EDUC", "HOMEOWN", "R_SEX"):
        k = k[~k[c].astype("string").str.startswith("-")]
    inc = pd.to_numeric(k["HHFAMINC"])
    k["income"] = np.select([inc <= 3, inc <= 5, inc == 6, inc == 7], [1, 2, 3, 4], default=5)
    k["homeown"] = (k["HOMEOWN"] == "01").astype(float)
    k["urban"] = (k["URBRUR"] == "01").astype(float)
    k["popden"] = pd.to_numeric(k["HBPPOPDN"]).map({50: 1, 300: 2, 750: 3, 1500: 4, 3000: 5, 7000: 6, 17000: 7, 30000: 8})
    k["female"] = (k["R_SEX"] == "02").astype(float)
    k["educ"] = pd.to_numeric(k["EDUC"])
    k["race"] = pd.to_numeric(k["R_RACE"]).replace({97: 6})
    k["multijob"] = (k["GT1JBLWK"] == "01").astype(float)
    k["occ"] = np.where(k["OCCAT"].isin(["01", "02", "03", "04"]), pd.to_numeric(k["OCCAT"], errors="coerce"), 5)
    k["carshare"] = (pd.to_numeric(k["CARSHARE"]).clip(lower=0) > 0).astype(float)
    k["ttw"] = pd.to_numeric(k["TIMETOWK"]).clip(lower=0).fillna(0)
    k["ymile"] = pd.to_numeric(k["YEARMILE"]).where(lambda s: s >= 0, 0)
    k["AFV"] = (k["FUELTYPE"] == "03").astype(int)
    k["EV"] = k["HFUEL"].isin(["02", "03"]).astype(int)
    k = k.merge(wt, on="HOUSEID", how="left").dropna(subset=FEATURES + ["WTHHFIN"])
    return k.reset_index(drop=True)


def run(label="AFV", seeds=(0, 1, 2), models=("LR", "NB", "DT", "RF", "SVM")) -> pd.DataFrame:
    d = pynhts.load(2017)
    k = build(d)
    X, y = k[FEATURES].to_numpy(float), k[label].to_numpy()
    rows = []
    for scheme in mlkit.CLASS_SCHEMES:
        for name in models:
            for s in seeds:
                r = mlkit.classify(MODELS[name], X, y, k["HOUSEID"].to_numpy(), k["WTHHFIN"].to_numpy(), scheme, s)
                rows.append({"label": label, "scheme": scheme, "model": name, "seed": s, "n": len(k), "pos": int(y.sum()), **r})
                print(label, scheme, name, s, round(r["auc"], 3), round(r["acc"], 3), flush=True)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    out = []
    for lab in ("AFV", "EV"):
        out.append(run(lab))
    r = pd.concat(out, ignore_index=True)
    r.to_csv(engine.RESULTS / "tables" / "p06_p17_models.csv", index=False)
    g = r.groupby(["label", "scheme", "model"])[["auc", "acc", "tpr", "ap"]].mean().round(3)
    print(g.to_string())
