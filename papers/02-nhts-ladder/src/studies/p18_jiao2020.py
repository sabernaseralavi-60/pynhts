"""P18 Jiao, Bischak & Hyden (2020): negative binomial models of daily person trips on shared-mobility use, NHTS 2017.

Published: Table 3, R glm.nb, unweighted, separate models for weekdays (N = 143,099) and weekends (N = 37,506).
Ordinal predictors (education, health, income) enter as numbers; the paper does not state how DRIVER and the
child dummy were coded, so the coding below is the one that reproduces the printed signs (see docs).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import countmodels as cm  # noqa: E402
import engine  # noqa: E402

engine.setup()
import pynhts  # noqa: E402

PUB = {  # term -> (weekday, weekend)
    "R_AGE": (0.002, 0.001), "EDUC": (0.046, 0.034), "WRK_HOME": (0.048, 0.006), "CARSHARE": (-0.003, 0.001),
    "BIKESHARE": (0.001, 0.000), "RIDESHARE": (0.004, 0.005), "TIMETOWK": (-0.001, 0.000), "HEALTH": (-0.027, -0.031),
    "HBPPOPDN": (0.000, 0.000), "WORKER": (0.039, 0.035), "URBRUR": (0.030, 0.047), "HHFAMINC": (-0.002, 0.001),
    "DRIVER": (0.202, 0.155), "MALE": (-0.035, -0.022), "FULL_TIME": (-0.101, 0.040), "CHILDERN": (0.077, -0.002)}


def build(d):
    cols = ["R_AGE", "R_SEX", "EDUC", "WRK_HOME", "CARSHARE", "BIKESHARE", "RIDESHARE", "TIMETOWK", "HEALTH", "HBPPOPDN",
            "WORKER", "URBRUR", "HHFAMINC", "DRIVER", "WKFTPT", "LIF_CYC", "CNTTDTR", "TRAVDAY"]
    p = d.persons(cols, missing="keep", skip="keep", weight=False)
    n = lambda c: pd.to_numeric(p[c], errors="coerce")  # noqa: E731
    age, trips = n("R_AGE"), n("CNTTDTR")
    ok = (age >= 18) & (trips > 0)
    for c in ("HHFAMINC", "HEALTH", "WRK_HOME", "TIMETOWK", "WKFTPT", "EDUC", "CARSHARE", "BIKESHARE", "RIDESHARE",
              "HBPPOPDN", "R_SEX"):
        x = n(c)
        ok &= ~((x < 0) & (x != -1))
    s = p[ok].copy().reset_index(drop=True)
    num = lambda c: pd.to_numeric(s[c], errors="coerce")  # noqa: E731
    tw = num("TIMETOWK").where(num("TIMETOWK") >= 0, 0)
    X = pd.DataFrame({
        "const": 1.0, "R_AGE": num("R_AGE"), "EDUC": num("EDUC"), "WRK_HOME": (s["WRK_HOME"] == "01").astype(float),
        "CARSHARE": num("CARSHARE"), "BIKESHARE": num("BIKESHARE"), "RIDESHARE": num("RIDESHARE"), "TIMETOWK": tw,
        "HEALTH": num("HEALTH"), "HBPPOPDN": num("HBPPOPDN"), "WORKER": (s["WORKER"] == "01").astype(float),
        "URBRUR": (s["URBRUR"] == "01").astype(float), "HHFAMINC": num("HHFAMINC"),
        "DRIVER": (s["DRIVER"] == "01").astype(float), "MALE": (s["R_SEX"] == "01").astype(float),
        "FULL_TIME": (s["WKFTPT"] == "01").astype(float), "CHILDERN": num("LIF_CYC").between(3, 8).astype(float)})
    s["wkday"] = s["TRAVDAY"].isin(["02", "03", "04", "05", "06"])
    return s, X


def run(replicates=True) -> pd.DataFrame:
    d = pynhts.load(2017, replicates=True)
    s, X = build(d)
    out = []
    for name, mask in (("weekday", s["wkday"]), ("weekend", ~s["wkday"])):
        sub = s[mask].reset_index(drop=True)
        Xs = X[mask.to_numpy()].reset_index(drop=True)
        des = engine.design_for(d, sub[["HOUSEID", "PERSONID"]], "person")
        res = cm.fit_regimes(Xs, None, sub["CNTTDTR"].to_numpy(float), des, replicates=replicates)
        res.insert(0, "model", name)
        k = 0 if name == "weekday" else 1
        res["published"] = [PUB.get(t, (None, None))[k] if part == "count" else None for part, t in zip(res["part"], res["term"])]
        res["n"] = len(sub)
        out.append(res)
    return pd.concat(out, ignore_index=True)


if __name__ == "__main__":
    with engine.Timer() as t:
        r = run()
    r.to_csv(engine.RESULTS / "tables" / "p18_models.csv", index=False)
    print(f"{t.dt:.0f} s")
    with pd.option_context("display.width", 250, "display.max_rows", 100):
        print(r[["model", "term", "published", "b_naive", "b_weighted", "b_design", "se_naive", "se_design", "p_naive", "p_design", "n"]].round(4).to_string())
