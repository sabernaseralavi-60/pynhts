"""pynhts.models against R's survey package on NHTS 2017 (golden: tests/golden/models_2017_r.csv, tools/validate_models_r.R)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import pynhts
from pynhts import models

pytestmark = pytest.mark.data
GOLDEN = pd.read_csv(Path(__file__).resolve().parents[1] / "golden" / "models_2017_r.csv")


@pytest.fixture(scope="module")
def adults():
    d = pynhts.load(2017, replicates=True)
    p = d.persons(
        ["R_AGE", "R_SEX", "WORKER", "DRIVER", "CNTTDTR"], missing="keep", skip="keep", weight=False
    )
    age = pd.to_numeric(p["R_AGE"], errors="coerce")
    trips = pd.to_numeric(p["CNTTDTR"], errors="coerce")
    ok = (
        (age >= 18)
        & (trips >= 0)
        & p["R_SEX"].isin(["01", "02"])
        & p["WORKER"].isin(["01", "02"])
        & p["DRIVER"].isin(["01", "02"])
    )
    p, age, trips = (
        p[ok].reset_index(drop=True),
        age[ok].reset_index(drop=True),
        trips[ok].reset_index(drop=True),
    )
    X = pd.DataFrame(
        {
            "age": age,
            "female": (p["R_SEX"] == "02").astype(float),
            "worker": (p["WORKER"] == "01").astype(float),
            "driver": (p["DRIVER"] == "01").astype(float),
        }
    )
    return d, p, X, trips


@pytest.mark.parametrize("family", ["binomial", "poisson", "gaussian"])
def test_design_fit_equals_r_svyglm(adults, family):
    d, p, X, trips = adults
    y = (trips > 0).astype(float) if family == "binomial" else trips
    res = models.fit(d, p, y, X, family=family, level="person", regime="design")
    ref = GOLDEN[GOLDEN["family"] == family].set_index("term")
    assert res.n == int(ref["n"].iloc[0])
    t = res.table().set_index("term")
    for term in ref.index:
        assert t.loc[term, "estimate"] == pytest.approx(
            ref.loc[term, "estimate"], rel=1e-5, abs=1e-7
        )
        assert t.loc[term, "se"] == pytest.approx(ref.loc[term, "se"], rel=2e-3)


GOLDEN22 = pd.read_csv(Path(__file__).resolve().parents[1] / "golden" / "models_2022_r.csv")


@pytest.mark.parametrize("family", ["binomial", "poisson"])
def test_taylor_design_fit_equals_r_svyglm_2022(family):
    """2022 has no replicate weights: the design is strata x households, linearised (tools/validate_models_taylor_r.R)."""
    d = pynhts.load(2022)
    p = d.persons(
        ["R_AGE", "R_SEX", "WORKER", "DRIVER", "PTUSED"], missing="keep", skip="keep", weight=False
    )
    age = pd.to_numeric(p["R_AGE"], errors="coerce")
    pt = pd.to_numeric(p["PTUSED"], errors="coerce")
    ok = (
        (age >= 18)
        & p["R_SEX"].isin(["01", "02"])
        & p["WORKER"].isin(["01", "02"])
        & p["DRIVER"].isin(["01", "02"])
        & (pt >= 0)
    )
    p, age, pt = (
        p[ok].reset_index(drop=True),
        age[ok].reset_index(drop=True),
        pt[ok].reset_index(drop=True),
    )
    X = pd.DataFrame(
        {
            "age": age,
            "female": (p["R_SEX"] == "02").astype(float),
            "worker": (p["WORKER"] == "01").astype(float),
        }
    )
    if family == "binomial":
        y = (p["DRIVER"] == "01").astype(float)
    else:
        X["driver"] = (p["DRIVER"] == "01").astype(float)
        y = pt
    res = models.fit(d, p, y, X, family=family, level="person", regime="design")
    ref = GOLDEN22[GOLDEN22["family"] == family].set_index("term")
    assert res.n == int(ref["n"].iloc[0])
    t = res.table().set_index("term")
    for term in ref.index:
        assert t.loc[term, "estimate"] == pytest.approx(
            ref.loc[term, "estimate"], rel=1e-5, abs=1e-7
        )
        assert t.loc[term, "se"] == pytest.approx(ref.loc[term, "se"], rel=5e-3)
