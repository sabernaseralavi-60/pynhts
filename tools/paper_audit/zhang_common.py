"""Shared sample preparation for P13-P15 (Zhang & Zhang 2018, three papers on the 2017 NHTS person file)."""

from __future__ import annotations

import numpy as np
import pandas as pd

import common

common.setup()
import pynhts  # noqa: E402

NINE = {"CA", "TX", "NY", "NC", "GA", "SC", "IA", "FL", "IL"}
EXCLUDED_15 = {"WV", "MS", "WY", "SD", "AR", "KS", "ND", "MT", "ID", "DE", "ME", "AL", "UT", "VT", "OR"}

d = pynhts.load(2017)
cols = ["R_SEX", "R_AGE", "EDUC", "R_RACE", "WORKER", "DRIVER", "HHFAMINC", "HHVEHCNT", "HBPPOPDN", "RAIL", "URBAN",
        "URBRUR", "TDAYDATE", "HOMEOWN", "HHSTATE", "RIDESHARE", "PTUSED", "BIKESHARE"]
raw = d.persons(cols, missing="keep", skip="keep", weight=False)


def num(s: pd.Series) -> pd.Series:
    """Numeric with every negative code (skip and non-answers) as NaN."""
    x = pd.to_numeric(s, errors="coerce")
    return x.where(x >= 0)


p = pd.DataFrame({
    "state": raw["HHSTATE"],
    "bike": num(raw["BIKESHARE"]), "ride": num(raw["RIDESHARE"]), "pt": num(raw["PTUSED"]),
    "female": (raw["R_SEX"] == "02").where(raw["R_SEX"].isin(["01", "02"])).astype(float),
    "age": num(raw["R_AGE"]),
    "edu": num(raw["EDUC"]),
    "white": (raw["R_RACE"] == "01").where(raw["R_RACE"].isin(["01", "02", "03", "04", "05", "06", "97"])).astype(float),
    "worker": (raw["WORKER"] == "01").where(raw["WORKER"].isin(["01", "02"])).astype(float),
    "driver": (raw["DRIVER"] == "01").where(raw["DRIVER"].isin(["01", "02"])).astype(float),
    "inc": num(raw["HHFAMINC"]),
    "veh": num(raw["HHVEHCNT"]),
    "lndens": np.log(num(raw["HBPPOPDN"])),
    "rail": (raw["RAIL"] == "01").astype(float),
    "urban": (raw["URBRUR"] == "01").astype(float),
    "urban_area": (raw["URBAN"] == "01").astype(float),
    # "Home is rental (Yes = 1)": the printed mean 0.212 is reproduced only when "some other arrangement" (97) counts as
    # not owned (HOMEOWN 02 alone gives 0.205); convention recovered by testing against the printed mean
    "rent": (raw["HOMEOWN"] != "01").where(raw["HOMEOWN"].isin(["01", "02", "97"])).astype(float),
})
month = raw["TDAYDATE"].str[-2:].astype(int)
p["spring"] = month.isin([3, 4, 5]).astype(float)
p["summer"] = month.isin([6, 7, 8]).astype(float)
p["fall"] = month.isin([9, 10, 11]).astype(float)
p["winter"] = month.isin([12, 1, 2]).astype(float)

COMMON = ["female", "age", "edu", "white", "worker", "driver", "inc", "veh", "lndens"]


def table(a: common.Audit, s: pd.DataFrame, spec: dict, tag: str) -> None:
    """spec: column -> (mean, sd, min, max) as printed. Unweighted, like the paper's Stata table."""
    for col, (m, sd, lo, hi) in spec.items():
        x = s[col]
        a.check(f"{tag} mean {col}", m, float(x.mean()))
        a.check(f"{tag} sd {col}", sd, float(x.std(ddof=1)))
        a.check(f"{tag} min {col}", lo, float(x.min()))
        a.check(f"{tag} max {col}", hi, float(x.max()))


def distribution(a: common.Audit, y: pd.Series, spec: list[tuple[str, int, int, float]]) -> None:
    pos = y[y > 0]
    for lab, lo, hi, pub in spec:
        a.check(f"share of users with {lab} uses, %", pub, float(pos.between(lo, hi).mean() * 100))


