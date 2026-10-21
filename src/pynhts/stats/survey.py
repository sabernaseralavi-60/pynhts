"""Design-based estimates (totals, means, proportions, ratios) with survey-correct errors.

Two variance designs share one estimator interface:

* :class:`Survey` (NHTS 2001, 2009, 2017): jackknife variance from the replicate weights (99,
  100 and 98 of them; the multiplier and degrees of freedom come from the wave's registry);
* :class:`TaylorSurvey` (NHTS 2022, which ships no replicate weights): Taylor-series
  linearisation with the stratum variable and households as primary sampling units, the
  method the 2022 User's Guide prescribes.

A :class:`Survey` ties a table of rows (households, persons, trips or vehicles) to the
replicate weights of the unit that carries the weight (2017 names):

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

import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray

from pynhts.core.flags import PynhtsWarning
from pynhts.stats.distributions import t_ppf
from pynhts.stats.jackknife import DEFAULT_DF, JKN_FACTOR, jackknife_variance
from pynhts.stats.taylor import taylor_variance

Kind = Literal["total", "mean", "ratio"]
VarSpec = str | ArrayLike | pd.Series


@dataclass(frozen=True)
class SurveyMeta:
    """What a survey object is, so that results can say it and guards can read it.

    Attributes:
        wave: Survey year.
        table: Table whose rows are analysed.
        weight: Full-sample weight column.
        design: One sentence on the variance method (used for table footnotes).
        unit: What a weighted total of rows counts ("annual person trips", "households", ...).
        cautions: Column -> warning text, issued when an estimator is asked about that column.
        replicate_system: Name of the replicate-weight system; surveys can be combined by
            :func:`ratio_across` only if their systems agree (the 2001 long-distance replicates
            belong to the national sample and are a different system).
    """

    wave: int | None = None
    table: str | None = None
    weight: str | None = None
    design: str = ""
    unit: str = ""
    cautions: Mapping[str, str] = field(default_factory=dict)
    replicate_system: str = ""

    def stamp(self) -> dict[str, Any]:
        """The entries copied to ``DataFrame.attrs["pynhts"]`` of every result."""
        return {"wave": self.wave, "table": self.table, "weight": self.weight,
                "design": self.design, "unit": self.unit}


class _SurveyBase:
    """Rows bound to weight-carrying units; estimators differ only in how variance is formed."""

    def __init__(
        self,
        rows: pd.DataFrame,
        unit_index: NDArray[np.int64],
        unit_weights: NDArray[np.float64],
        *,
        level: float,
        df: float,
        meta: SurveyMeta | None = None,
    ) -> None:
        if len(unit_index) != len(rows):
            raise ValueError("unit_index must have one entry per row")
        self.rows = rows.reset_index(drop=True)
        self._unit = np.asarray(unit_index, dtype=np.int64)
        self._w = np.asarray(unit_weights, dtype=np.float64)
        self.level, self.df = level, df
        self.meta = meta or SurveyMeta()
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
        return self._stamp(self._run("total", yv, None, valid, by))

    def mean(
        self, y: VarSpec, *, domain: ArrayLike | None = None,
        by: str | Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """Weighted mean of ``y`` over rows with a non-NA value (ratio of two totals)."""
        valid, yv = self._values(y, domain)
        return self._stamp(self._run("mean", yv, None, valid, by))

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
        return self._stamp(self._run("mean", yv, None, valid, by))

    def ratio(
        self, numerator: VarSpec, denominator: VarSpec, *, domain: ArrayLike | None = None,
        by: str | Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """Ratio of the weighted totals of two variables (complete cases only)."""
        v1, y1 = self._values(numerator, domain)
        v2, y2 = self._values(denominator, domain)
        return self._stamp(self._run("ratio", y1, y2, v1 & v2, by))

    # -- internals
    def _stamp(self, frame: pd.DataFrame) -> pd.DataFrame:
        frame.attrs["pynhts"] = self.meta.stamp()
        return frame

    def _warn(self, spec: object) -> None:
        if isinstance(spec, str) and spec in self.meta.cautions:
            warnings.warn(self.meta.cautions[spec], PynhtsWarning, stacklevel=4)
    def _values(
        self, spec: VarSpec | None, domain: ArrayLike | None
    ) -> tuple[NDArray[np.bool_], NDArray[np.float64]]:
        n = len(self.rows)
        self._warn(spec)
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
        raise NotImplementedError  # pragma: no cover

    @staticmethod
    def _table(
        full: NDArray[np.float64], se: NDArray[np.float64], tcrit: float | NDArray[np.float64],
        codes: NDArray[np.int64], k: int, labels: pd.DataFrame | None,
        df: NDArray[np.float64] | None = None,
    ) -> pd.DataFrame:
        moe = tcrit * se
        n = np.bincount(codes[codes >= 0], minlength=k)
        with np.errstate(divide="ignore", invalid="ignore"):
            cv = np.where(full != 0, se / np.abs(full), np.nan)
        out = pd.DataFrame({
            "estimate": full, "se": se, "moe": moe,
            "ci_low": full - moe, "ci_high": full + moe, "cv": cv, "n": n,
        })
        if df is not None:
            out["df"] = df
        if labels is not None:
            out = pd.concat([labels.reset_index(drop=True), out], axis=1)
        result: pd.DataFrame = out
        return result


class Survey(_SurveyBase):
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
        meta: SurveyMeta | None = None,
    ) -> None:
        """Create a survey; prefer :meth:`pynhts.NHTSData.survey`.

        Args:
            rows: Row-level data (one row per household, person, trip or vehicle).
            unit_index: For each row, the position of its unit in ``unit_weights``/``replicates``.
            unit_weights: Full-sample weight of each unit, shape ``(n_units,)``.
            replicates: Replicate weights of each unit, shape ``(n_units, n_replicates)``.
            level: Confidence level of the margin of error and interval.
            df: Degrees of freedom of the t multiplier (the number of replicates, as FHWA).
            factor: Multiplier of the summed squared deviations (6/7 in 2017, 99/100 in 2009,
                98/99 in 2001).
            meta: What the survey is (wave, table, unit, cautions); see :class:`SurveyMeta`.
        """
        super().__init__(rows, unit_index, unit_weights, level=level, df=df, meta=meta)
        self._r = np.asarray(replicates, dtype=np.float64)
        self.factor = factor

    def total_replicates(
        self, y: VarSpec | None = None, *, domain: ArrayLike | None = None
    ) -> tuple[float, NDArray[np.float64]]:
        """Full-sample total and its replicate totals (for combining surveys)."""
        valid, yv = self._values(y, domain)
        codes = np.where(valid, 0, -1).astype(np.int64)
        a = self._unit_matrix(yv * valid, codes, 1)
        return float((self._w @ a)[0]), (self._r.T @ a)[:, 0]

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
        se = np.sqrt(jackknife_variance(full, reps, self.factor, self._r.shape[1]))
        return self._table(full, se, self._tcrit, codes, k, labels)


class TaylorSurvey(_SurveyBase):
    """Rows bound to weights, strata and clusters, with Taylor-series standard errors.

    Build it with ``data.survey(...)`` on a wave without replicate weights (NHTS 2022).
    """

    def __init__(
        self,
        rows: pd.DataFrame,
        unit_index: NDArray[np.int64],
        unit_weights: NDArray[np.float64],
        unit_cluster: NDArray[np.int64],
        cluster_stratum: NDArray[np.int64],
        *,
        level: float = 0.95,
        meta: SurveyMeta | None = None,
    ) -> None:
        """Create a survey; prefer :meth:`pynhts.NHTSData.survey`.

        Args:
            rows: Row-level data (one row per household, person, trip or vehicle).
            unit_index: For each row, the position of its unit in ``unit_weights``.
            unit_weights: Weight of each unit, shape ``(n_units,)`` (zeros are allowed: such
                units stay in the design, which is what domain estimation needs).
            unit_cluster: Cluster (household) index of each unit, ``0..n_clusters-1``.
            cluster_stratum: Stratum label of each cluster, shape ``(n_clusters,)``.
            level: Confidence level of the margin of error and interval.
            meta: What the survey is (wave, table, unit, cautions); see :class:`SurveyMeta`.
        """
        strata, stratum = np.unique(np.asarray(cluster_stratum), return_inverse=True)
        self._cluster = np.asarray(unit_cluster, dtype=np.int64)
        self._stratum = np.asarray(stratum, dtype=np.int64).ravel()
        if len(self._cluster) != len(unit_weights):
            raise ValueError("unit_cluster must have one entry per unit")
        if (np.bincount(self._stratum) < 2).any():
            raise ValueError("every stratum needs at least two clusters")
        self.n_clusters = len(self._stratum)
        self.n_strata = len(strata)
        # Degrees of freedom as in R's survey::degf: clusters that carry weight, minus the strata
        # they fall in. Zero-weight clusters stay in the variance (they are part of the design)
        # but not in the df, e.g. households with no weekday weight when weekday weights are used.
        live = np.bincount(self._cluster, weights=np.asarray(unit_weights) > 0,
                           minlength=self.n_clusters) > 0
        df = float(live.sum() - len(np.unique(self._stratum[live])))
        super().__init__(rows, unit_index, unit_weights, level=level, df=df, meta=meta)

    def _cluster_sums(self, values: NDArray[np.float64]) -> NDArray[np.float64]:
        """Weighted values summed over the units of each cluster, shape ``(n_clusters, k)``."""
        cols = [
            np.bincount(self._cluster, weights=self._w * values[:, j], minlength=self.n_clusters)
            for j in range(values.shape[1])
        ]
        return np.stack(cols, axis=1)

    def cluster_totals(
        self, y: VarSpec | None = None, *, domain: ArrayLike | None = None
    ) -> NDArray[np.float64]:
        """Weighted total of ``y`` in every cluster (basis of cross-survey ratios)."""
        valid, yv = self._values(y, domain)
        codes = np.where(valid, 0, -1).astype(np.int64)
        a = self._unit_matrix(yv * valid, codes, 1)
        z: NDArray[np.float64] = self._cluster_sums(a)[:, 0]
        return z

    def _run(
        self, kind: Kind, num: NDArray[np.float64], den: NDArray[np.float64] | None,
        valid: NDArray[np.bool_], by: str | Sequence[str] | None,
    ) -> pd.DataFrame:
        codes, k, labels = self._groups(by)
        codes = np.where(valid, codes, -1)
        za = self._cluster_sums(self._unit_matrix(num * valid, codes, k))
        total_a = za.sum(axis=0)
        if kind == "total":
            full, z = total_a, za
        else:
            d = den if den is not None else np.ones_like(num)
            zd = self._cluster_sums(self._unit_matrix(d * valid, codes, k))
            total_d = zd.sum(axis=0)
            with np.errstate(divide="ignore", invalid="ignore"):
                full = total_a / total_d
                z = (za - full * zd) / total_d
        se = np.sqrt(taylor_variance(np.nan_to_num(z), self._stratum))
        se = np.where(np.isfinite(full), se, np.nan)
        df = self._domain_df(codes, k)
        tcrit = np.array([t_ppf(0.5 + self.level / 2.0, d) if d > 0 else np.nan for d in df])
        return self._table(full, se, tcrit, codes, k, labels, df)

    def _domain_df(self, codes: NDArray[np.int64], k: int) -> NDArray[np.float64]:
        """Degrees of freedom per group: clusters with weighted rows in it minus their strata.

        Same rule as ``survey::degf`` on a subpopulation design, so margins of error of a domain
        estimate use fewer degrees of freedom than the whole-sample ones.
        """
        out = np.empty(k)
        keep = codes >= 0
        for j in range(k):
            rows = keep & (codes == j)
            live = rows & (self._w[self._unit] > 0)
            present = np.unique(self._cluster[self._unit[live]])
            out[j] = len(present) - len(np.unique(self._stratum[present]))
        return out


def ratio_across(
    numerator: _SurveyBase, num_var: VarSpec | None, denominator: _SurveyBase,
    den_var: VarSpec | None = None, *, num_domain: ArrayLike | None = None,
    den_domain: ArrayLike | None = None,
) -> pd.DataFrame:
    """Ratio of a total in one survey to a total in another (e.g. person trips / households).

    Both surveys share the same replicate indices, so the replicate ratios are formed
    index by index. This is how FHWA's per-household rates are built: person-weighted trips
    divided by household-weighted households.
    """
    if isinstance(numerator, TaylorSurvey) or isinstance(denominator, TaylorSurvey):
        return _ratio_across_taylor(numerator, num_var, denominator, den_var, num_domain,
                                    den_domain)
    if not isinstance(numerator, Survey) or not isinstance(denominator, Survey):
        raise TypeError("both surveys must use the same variance design")
    a, b = numerator.meta, denominator.meta
    if a.wave is not None and b.wave is not None and a.wave != b.wave:
        raise ValueError(f"surveys of NHTS {a.wave} and {b.wave} cannot form a ratio")
    if a.replicate_system and b.replicate_system and a.replicate_system != b.replicate_system:
        raise ValueError(
            f"the replicate weights of {a.table!r} ({a.replicate_system}) and {b.table!r} "
            f"({b.replicate_system}) are different systems: replicate r does not delete the same "
            "units, so a ratio across them has no valid variance"
        )
    n_full, n_rep = numerator.total_replicates(num_var, domain=num_domain)
    d_full, d_rep = denominator.total_replicates(den_var, domain=den_domain)
    full = n_full / d_full
    reps = n_rep / d_rep
    se = float(np.sqrt(jackknife_variance(full, reps, numerator.factor, n_rep.shape[0])))
    moe = numerator._tcrit * se
    result: pd.DataFrame = pd.DataFrame({
        "estimate": [full], "se": [se], "moe": [moe], "ci_low": [full - moe],
        "ci_high": [full + moe], "cv": [se / abs(full) if full else np.nan],
        "n": [len(numerator.rows)],
    })
    result.attrs["pynhts"] = {**numerator.meta.stamp(), "unit": "ratio"}
    return result


def _ratio_across_taylor(
    numerator: _SurveyBase, num_var: VarSpec | None, denominator: _SurveyBase,
    den_var: VarSpec | None, num_domain: ArrayLike | None, den_domain: ArrayLike | None,
) -> pd.DataFrame:
    if not isinstance(numerator, TaylorSurvey) or not isinstance(denominator, TaylorSurvey):
        raise TypeError("both surveys must use the same variance design")
    if not np.array_equal(numerator._stratum, denominator._stratum):
        raise ValueError("the two surveys do not share one cluster/stratum design")
    zn = numerator.cluster_totals(num_var, domain=num_domain)
    zd = denominator.cluster_totals(den_var, domain=den_domain)
    full = float(zn.sum() / zd.sum())
    z = (zn - full * zd) / zd.sum()
    se = float(np.sqrt(taylor_variance(z, numerator._stratum)[0]))
    moe = numerator._tcrit * se
    result: pd.DataFrame = pd.DataFrame({
        "estimate": [full], "se": [se], "moe": [moe], "ci_low": [full - moe],
        "ci_high": [full + moe], "cv": [se / abs(full) if full else np.nan],
        "n": [len(numerator.rows)],
    })
    result.attrs["pynhts"] = {**numerator.meta.stamp(), "unit": "ratio"}
    return result
