"""Shared helpers for the data-feasibility audit of the papers in ``some papers/``.

Each paper gets a script ``pNN_*.py`` that (1) builds the analysis dataset with pynhts only,
(2) compares the quantities the paper publishes about that dataset (sample sizes, descriptive
tables) with what pynhts returns, (3) writes ``docs/paper_data_audit/results/pNN.csv``.
Nothing is tuned to hit a published number: a gap is reported as a gap.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "docs" / "paper_data_audit" / "results"


def setup() -> None:
    """Point pynhts at the local cache and import the working-tree package."""
    sys.path.insert(0, str(ROOT / "src"))
    os.environ.setdefault("PYNHTS_CACHE_DIR", str(ROOT / "local_data" / "cache"))
    RESULTS.mkdir(parents=True, exist_ok=True)


def _decimals(x: float | int | str) -> int:
    d = Decimal(str(x))  # keeps trailing zeros: 5.0 means one printed decimal
    return max(0, -d.as_tuple().exponent)  # type: ignore[operator]


def grade(published: float, ours: float) -> str:
    """EXACT: equal at the printed precision. CLOSE <= 2 %, ACCEPTABLE <= 5 %, else GAP."""
    if published is None or ours is None or ours != ours:
        return "NOT_COMPUTED"
    dec = _decimals(published)
    if round(float(ours), dec) == round(float(published), dec):
        return "EXACT"
    if published == 0:
        return "GAP"
    rel = abs(ours - published) / abs(published)
    if rel <= 0.02:
        return "CLOSE"
    if rel <= 0.05:
        return "ACCEPTABLE"
    return "GAP"


@dataclass
class Audit:
    paper: str
    rows: list[dict] = field(default_factory=list)
    t0: float = field(default_factory=time.time)

    def check(self, item: str, published: float, ours: float, note: str = "") -> str:
        st = grade(published, ours)
        self.rows.append(
            {"item": item, "published": published, "pynhts": None if ours != ours else round(float(ours), 4),
             "status": st, "note": note}
        )
        return st

    def info(self, item: str, ours, note: str = "") -> None:
        """A computed quantity the paper does not publish a number for (kept for the record)."""
        self.rows.append({"item": item, "published": None, "pynhts": ours, "status": "INFO", "note": note})

    def save(self) -> "pd.DataFrame":  # noqa: F821
        import pandas as pd

        df = pd.DataFrame(self.rows)
        df.to_csv(RESULTS / f"{self.paper}.csv", index=False)
        counts = df["status"].value_counts().to_dict()
        print(f"\n=== {self.paper}: {counts}; {time.time() - self.t0:.1f} s ===")
        with pd.option_context("display.width", 220, "display.max_colwidth", 70, "display.max_rows", 500):
            print(df.to_string(index=False))
        return df


def wlogit(X, y, w, add_const=True, iters=50, tol=1e-10):
    """Weighted logistic regression by IRLS (numpy only; no scipy/statsmodels needed).

    Weights act as frequency weights scaled to the sample size (like Stata ``pweight`` after
    normalisation), which reproduces point estimates; standard errors are not computed here.
    """
    import numpy as np

    X = np.asarray(X, float)
    if add_const:
        X = np.column_stack([np.ones(len(X)), X])
    y = np.asarray(y, float)
    w = np.asarray(w, float)
    w = w * len(w) / w.sum()
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        eta = X @ b
        mu = 1.0 / (1.0 + np.exp(-eta))
        W = w * mu * (1 - mu)
        z = eta + (y - mu) / np.clip(mu * (1 - mu), 1e-12, None)
        XtW = X.T * W
        b_new = np.linalg.solve(XtW @ X, XtW @ z)
        if np.max(np.abs(b_new - b)) < tol:
            b = b_new
            break
        b = b_new
    return b
