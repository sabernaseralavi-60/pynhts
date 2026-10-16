"""Design-based estimates (totals, means, proportions, ratios) with JKn standard errors.

A :class:`Survey` ties a table of rows (households, persons, trips or vehicles) to the 98
replicate weights of the unit that carries the weight:

* household and vehicle rows -> household replicate weights (``WTHHFIN1..98``)
* person rows               -> person replicate weights (``WTPERFIN1..98``)
* trip rows                 -> person-day replicate weights (``WTTRDFIN1..98``)

All rows of one unit share one weight, so any weighted sum over rows equals
``sum_units W_u * (sum of the row values inside unit u)``. Estimates therefore run on the unit
matrix (at most 264 234 x 98) and never need a rows x 98 matrix, even for 923 572 trips.

Missing values: a row whose analysis variable is NA is dropped from numerator *and* denominator
(complete-case within the domain), like ``na.rm=TRUE`` in R's survey package. Use
``data.table(..., missing="nan")`` (the default) so that survey codes -9/-8/-7 are NA.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray

from pynhts.stats.distributions import t_ppf
from pynhts.stats.jackknife import DEFAULT_DF, JKN_FACTOR, jackknife_variance

Kind = Literal["total", "mean", "ratio"]
VarSpec = str | ArrayLike | pd.Series


class Survey:
    """Rows plus replicate weights, with JKn estimators. Build it with ``data.survey(...)``."""

    def __init__(
        self,
        rows: pd.DataFrame,
        unit_index: NDArray[np.int64],
        unit_weights: NDArray[np.float64],
        replicates: NDArray[np.float64],
        *,
        level: float = 0.95,
        df: float = DEFAULT_DF,
        factor: float = JKN_FACTOR,
    ) -> None:
        """Create a survey; prefer :meth:`pynhts.NHTSData.survey`.

        Args:
            rows: Row-level data (one row per household, person, trip or vehicle).
            unit_index: For each row, the position of its unit in ``unit_weights``/``replicates``.
            unit_weights: Full-sample weight of each unit, shape ``(n_units,)``.
            replicates: Replicate weights of each unit, shape ``(n_units, 98)``.
            level: Confidence level of the margin of error and interval.
            df: Degrees of freedom of the t multiplier (98 = number of replicates, as FHWA).
            factor: JKn factor ``(n_h - 1) / n_h``.
        """
        if len(unit_index) != len(rows):
            raise ValueError("unit_index must have one entry per row")
        self.rows = rows.reset_index(drop=True)
        self._unit = np.asarray(unit_index, dtype=np.int64)
        self._w = np.asarray(unit_weights, dtype=np.float64)
        self._r = np.asarray(replicates, dtype=np.float64)
        self.level, self.df, self.factor = level, df, factor
        self._tcrit = t_ppf(0.5 + level / 2.0, df)

    @property
    def n_units(self) -> int:
        """Number of weight-carrying units (households or persons or person-days)."""
        return len(self._w)

    # -- public estimators ---------------------------------------------------------------
    def total(
        self, y: VarSpec | None = None, *, domain: ArrayLike | None = None,
        by: str | Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """Weighted total of ``y`` (``None`` counts rows, i.e. a population count)."""
        valid, yv = self._values(y, domain)
        return self._run("total", yv, None, valid, by)

    def mean(
        self, y: VarSpec, *, domain: ArrayLike | None = None,
        by: str | Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """Weighted mean of ``y`` over rows with a non-NA value (ratio of two totals)."""
        valid, yv = self._values(y, domain)
        return self._run("mean", yv, None, valid, by)

    def proportion(
        self, condition: ArrayLike, *, domain: ArrayLike | None = None,
        by: str | Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """Weighted share of rows for which the boolean ``condition`` is true.

        Rows where ``condition`` is NA are excluded from numerator and denominator.
        """
        cond = pd.Series(condition).reset_index(drop=True)
        if len(cond) != len(self.rows):
            raise ValueError("condition must have one entry per row")
        valid, yv = self._values(cond.astype("Float64"), domain)
        return self._run("mean", yv, None, valid, by)

    def ratio(
        self, numerator: VarSpec, denominator: VarSpec, *, domain: ArrayLike | None = None,
        by: str | Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """Ratio of the weighted totals of two variables (complete cases only)."""
        v1, y1 = self._values(numerator, domain)
        v2, y2 = self._values(denominator, domain)
        return self._run("ratio", y1, y2, v1 & v2, by)

    def total_replicates(
        self, y: VarSpec | None = None, *, domain: ArrayLike | None = None
    ) -> tuple[float, NDArray[np.float64]]:
        """Full-sample total and its 98 replicate totals (for combining surveys)."""
        valid, yv = self._values(y, domain)
        codes = np.where(valid, 0, -1).astype(np.int64)
        a = self._unit_matrix(yv * valid, codes, 1)
        return float((self._w @ a)[0]), (self._r.T @ a)[:, 0]

    # -- internals -----------------------------------------------------------------------
    def _values(
        self, spec: VarSpec | None, domain: ArrayLike | None
    ) -> tuple[NDArray[np.bool_], NDArray[np.float64]]:
        n = len(self.rows)
        valid = np.ones(n, dtype=bool)
        if domain is not None:
            dom = pd.Series(domain).reset_index(drop=True)
            if len(dom) != n:
                raise ValueError("domain must have one entry per row")
            valid &= dom.fillna(False).astype(bool).to_numpy()
        if spec is None:
            return valid, np.ones(n)
        s = self.rows[spec] if isinstance(spec, str) else pd.Series(spec).reset_index(drop=True)
        if len(s) != n:
            raise ValueError("variable must have one entry per row")
        arr = pd.to_numeric(s, errors="raise").astype("Float64").to_numpy(
            dtype=np.float64, na_value=np.nan
        )
        ok = ~np.isnan(arr)
        return valid & ok, np.where(ok, arr, 0.0)

    def _groups(
        self, by: str | Sequence[str] | None
    ) -> tuple[NDArray[np.int64], int, pd.DataFrame | None]:
        if by is None:
            return np.zeros(len(self.rows), dtype=np.int64), 1, None
        cols = [by] if isinstance(by, str) else list(by)
        grouped = self.rows.groupby(cols, sort=True, dropna=True, observed=True)
        raw = np.asarray(grouped.ngroup().to_numpy(), dtype=np.float64)
        codes: NDArray[np.int64] = np.where(np.isnan(raw), -1, raw).astype(np.int64)
        labels: pd.DataFrame = grouped.size().reset_index()[cols]
        return codes, len(labels), labels

    def _unit_matrix(
        self, values: NDArray[np.float64], codes: NDArray[np.int64], k: int
    ) -> NDArray[np.float64]:
        """Sum row values into a ``(n_units, k)`` matrix (rows with code -1 are dropped)."""
        keep = codes >= 0
        flat = codes[keep] * self.n_units + self._unit[keep]
        counts = np.bincount(flat, weights=values[keep], minlength=k * self.n_units)
        mat: NDArray[np.float64] = np.asarray(counts, dtype=np.float64).reshape(
            k, self.n_units).T
        return mat

    def _run(
        self, kind: Kind, num: NDArray[np.float64], den: NDArray[np.float64] | None,
        valid: NDArray[np.bool_], by: str | Sequence[str] | None,
    ) -> pd.DataFrame:
        codes, k, labels = self._groups(by)
        codes = np.where(valid, codes, -1)
        a = self._unit_matrix(num * valid, codes, k)
        a_full, a_rep = self._w @ a, self._r.T @ a
        if kind == "total":
            full, reps = a_full, a_rep
        else:
            d = self._unit_matrix((den if den is not None else np.ones_like(num)) * valid,
                                  codes, k)
            d_full, d_rep = self._w @ d, self._r.T @ d
            with np.errstate(divide="ignore", invalid="ignore"):
                full, reps = a_full / d_full, a_rep / d_rep
        se = np.sqrt(jackknife_variance(full, reps, self.factor))
        moe = self._tcrit * se
        n = np.bincount(codes[codes >= 0], minlength=k)
        with np.errstate(divide="ignore", invalid="ignore"):
            cv = np.where(full != 0, se / np.abs(full), np.nan)
        out = pd.DataFrame({
            "estimate": full, "se": se, "moe": moe,
            "ci_low": full - moe, "ci_high": full + moe, "cv": cv, "n": n,
        })
        if labels is not None:
            out = pd.concat([labels.reset_index(drop=True), out], axis=1)
        result: pd.DataFrame = out
        return result


def ratio_across(
    numerator: Survey, num_var: VarSpec | None, denominator: Survey,
    den_var: VarSpec | None = None, *, num_domain: ArrayLike | None = None,
    den_domain: ArrayLike | None = None,
) -> pd.DataFrame:
    """Ratio of a total in one survey to a total in another (e.g. person trips / households).

    Both surveys share the same 98 replicate indices, so the replicate ratios are formed
    index by index. This is how FHWA's per-household rates are built: person-weighted trips
    divided by household-weighted households.
    """
    n_full, n_rep = numerator.total_replicates(num_var, domain=num_domain)
    d_full, d_rep = denominator.total_replicates(den_var, domain=den_domain)
    full = n_full / d_full
    reps = n_rep / d_rep
    se = float(np.sqrt(jackknife_variance(full, reps, numerator.factor)))
    moe = numerator._tcrit * se
    result: pd.DataFrame = pd.DataFrame({
        "estimate": [full], "se": [se], "moe": [moe], "ci_low": [full - moe],
        "ci_high": [full + moe], "cv": [se / abs(full) if full else np.nan],
        "n": [len(numerator.rows)],
    })
    return result
