"""P06 / P17 again with every model tuned alike (nested): does the leakage gap survive proper tuning?

Protocol (identical for the five classifiers): random search with the same budget (10 trials); inner validation = 3
folds inside the training rows, grouped by household in the grouped pipelines and by row in the row pipelines, SMOTE
only inside the inner training folds of the pipelines that resample after the split; score = ROC-AUC. The selected
configuration is refitted on all training rows and scored on the held-out rows. Two master seeds (stability repeat).
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold, KFold, train_test_split
from sklearn.naive_bayes import GaussianNB
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine  # noqa: E402
import mlkit  # noqa: E402
from p06_p17_jia import FEATURES, build  # noqa: E402

import pynhts  # noqa: E402

engine.setup()
warnings.filterwarnings("ignore")
TRIALS = 10


def lu(rng, lo, hi):
    return float(np.exp(rng.uniform(np.log(lo), np.log(hi))))


SPACES = {  # name -> (sampler, builder); every model has 1-4 searched hyper-parameters, same trial budget
    "LR": (lambda r: {"C": lu(r, 1e-3, 1e2), "penalty_l1": bool(r.integers(0, 2))},
           lambda h: make_pipeline(StandardScaler(), LogisticRegression(C=h["C"], l1_ratio=1.0 if h["penalty_l1"] else 0.0,
                                                                         solver="saga", max_iter=300))),
    "NB": (lambda r: {"vs": lu(r, 1e-11, 1e-3)}, lambda h: GaussianNB(var_smoothing=h["vs"])),
    "DT": (lambda r: {"depth": int(r.choice([3, 5, 8, 12, 20])), "leaf": int(r.choice([1, 5, 20, 50])),
                      "crit": str(r.choice(["gini", "entropy"]))},
           lambda h: DecisionTreeClassifier(max_depth=h["depth"], min_samples_leaf=h["leaf"], criterion=h["crit"], random_state=0)),
    "RF": (lambda r: {"n": int(r.choice([50, 100, 200])), "depth": int(r.choice([5, 10, 20, 40])),
                      "leaf": int(r.choice([1, 2, 5, 20])), "mf": float(r.choice([0.3, 0.5, 1.0]))},
           lambda h: RandomForestClassifier(n_estimators=h["n"], max_depth=h["depth"], min_samples_leaf=h["leaf"],
                                            max_features=h["mf"], n_jobs=6, random_state=0)),
    "SVM": (lambda r: {"C": lu(r, 0.1, 100), "gamma": lu(r, 1e-3, 1.0)},
            lambda h: make_pipeline(StandardScaler(), SVC(C=h["C"], gamma=h["gamma"]))),
}


class Sub:
    """Subsample the training rows for the costly SVM (same cap in tuning and in the final fit)."""

    def __init__(self, m, cap, seed):
        self.m, self.cap, self.seed = m, cap, seed

    def fit(self, X, y):
        idx = np.random.default_rng(self.seed).choice(len(y), min(self.cap, len(y)), replace=False)
        self.m.fit(X[idx], y[idx])
        return self

    def decision_function(self, X):
        return self.m.decision_function(X)


def make(name, h, seed):
    m = SPACES[name][1](h)
    return Sub(m, 12000, seed) if name == "SVM" else m


def score(m, X):
    return m.predict_proba(X)[:, 1] if hasattr(m, "predict_proba") else m.decision_function(X)


def tune(name, X, y, groups, grouped_inner, resample_inner, seed):
    rng = np.random.default_rng(1000 + seed)
    best, best_h = -1.0, None
    sampler = SPACES[name][0]
    for _ in range(TRIALS):
        h = sampler(rng)
        aucs = []
        splitter = GroupKFold(3) if grouped_inner else KFold(3, shuffle=True, random_state=seed)
        for tr, va in splitter.split(X, y, groups):
            Xt, yt = X[tr], y[tr]
            if resample_inner:
                Xt, yt = mlkit._smote(Xt, yt, seed)
            m = make(name, h, seed).fit(Xt, yt)
            aucs.append(roc_auc_score(y[va], score(m, X[va])))
        if np.mean(aucs) > best:
            best, best_h = float(np.mean(aucs)), h
    return best_h, best


def outer(name, X, y, groups, w, pipeline, seed):
    if pipeline == "resample_then_split":
        Xr, yr = mlkit._smote(X, y, seed)
        Xtr, Xte, ytr, yte = train_test_split(Xr, yr, test_size=0.3, random_state=seed, stratify=yr)
        gtr, wte, grouped, res_inner = np.arange(len(ytr)), None, False, False
    elif pipeline == "split_then_resample":
        Xtr, Xte, ytr, yte, _, _ = train_test_split(X, y, w, test_size=0.3, random_state=seed, stratify=y)
        gtr, wte, grouped, res_inner = np.arange(len(ytr)), None, False, True
        Xfit, yfit = mlkit._smote(Xtr, ytr, seed)
    else:
        from pynhts.validate import group_split

        tr, te = group_split(groups, test_size=0.3, seed=seed)
        Xtr, ytr, Xte, yte, gtr, wte = X[tr], y[tr], X[te], y[te], groups[tr], w[te]
        grouped, res_inner = True, pipeline == "grouped"
        if pipeline == "grouped":
            Xfit, yfit = mlkit._smote(Xtr, ytr, seed)
    if pipeline == "resample_then_split":
        Xfit, yfit = Xtr, ytr
    elif pipeline == "grouped_weighted":
        Xfit, yfit = Xtr, ytr
    h, inner = tune(name, Xtr, ytr, gtr, grouped, res_inner, seed)
    m = make(name, h, seed).fit(Xfit, yfit)
    sc = score(m, Xte)
    out = {"auc": roc_auc_score(yte, sc), "inner_auc": inner, "hparams": str(h)}
    if pipeline == "grouped_weighted":
        out["auc_w"] = roc_auc_score(yte, sc, sample_weight=wte)
    return out


def run(label, seeds=(0, 1)):
    d = pynhts.load(2017)
    k = build(d)
    X, y = k[FEATURES].to_numpy(float), k[label].to_numpy()
    g, w = k["HOUSEID"].to_numpy(), k["WTHHFIN"].to_numpy()
    rows = []
    for pipe in mlkit.CLASS_SCHEMES:
        for name in SPACES:
            for s in seeds:
                r = outer(name, X, y, g, w, pipe, s)
                rows.append({"label": label, "scheme": pipe, "model": name, "seed": s, **r})
                print(label, pipe, name, s, round(r["auc"], 3), flush=True)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    r = pd.concat([run("AFV"), run("EV")], ignore_index=True)
    r.to_csv(engine.RESULTS / "tables" / "p06_p17_tuned.csv", index=False)
    print(r.groupby(["label", "scheme", "model"])["auc"].mean().round(3).to_string())
