"""Relational aggregation with diagnostics: trips -> persons -> households, vehicles -> households.

The loader joins *parent* columns onto child rows safely. This module does the opposite and more
error-prone direction: collapsing child rows onto a parent (a person-day of trips, a household of
persons) without row multiplication and with every judgement call explicit.

>>> from pynhts import aggregate as A   # doctest: +SKIP
>>> pd_ = A.aggregate(data, "trip", "person", {
...     "n_trips": A.Agg.n(),
...     "walk_trips": A.Agg.n(A.Where("TRPTRANS", "==", "01")),
...     "miles": A.Agg.sum("TRPMILES"),
... })                                                     # doctest: +SKIP
>>> print(pd_.attrs["pynhts_aggregate"])                   # doctest: +SKIP

What the function guarantees (and reports):

* one result row per target row, in the target's file order (a many-to-many join is impossible);
* the target key is unique, and a source row whose parent is missing raises (``orphans="report"``
  only reports it);
* the missing-value policy is chosen, not implied: ``missing="propagate"`` makes a sum or a mean NaN
  when any contributing value is missing (a person whose trip distance is unknown has no known
  daily distance); ``missing="skip"`` ignores them, as FHWA's tables do for miles. Either way the
  number of missing inputs is in the report;
* a parent without child rows gets 0 for counts, sums and indicators (``empty="auto"``) because the
  survey records the day of every person, so "no trips" is a real zero; means, shares, minima
  and the like stay NaN. ``empty="nan"`` refuses that inference;
* the result carries the *target* table's weight column and ``attrs["pynhts"]``; a weight of
  another table is never attached, and household values are never repeated onto child rows.

Daily quantities summed over the survey day are **observed survey-day** quantities, not annual
ones; the trip weight (365 x the person weight) annualises totals, not person-level values.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

import pandas as pd

from pynhts.core.data import _ANCESTORS
from pynhts.core.flags import PynhtsWarning
from pynhts.core.validity import valid
from pynhts.io.fetcher import NHTSIntegrityError

if TYPE_CHECKING:
    from pynhts.core.data import NHTSData

MissingPolicy = Literal["propagate", "skip"]
EmptyPolicy = Literal["auto", "nan"]
OrphanPolicy = Literal["raise", "report"]

_COUNT_LIKE = {"n", "count", "sum", "nunique", "any"}
_NUMERIC = {"sum", "mean", "median", "min", "max", "std", "quantile"}
FUNCS = (
    "n",
    "count",
    "sum",
    "mean",
    "median",
    "min",
    "max",
    "std",
    "quantile",
    "nunique",
    "any",
    "share",
    "first",
    "last",
)


# ---- conditions ---------------------------------------------------------------------------
class Cond:
    """A row condition on the source frame; combine with ``&`` and ``|``."""

    @property
    def columns(self) -> tuple[str, ...]:
        """Source columns the condition reads."""
        raise NotImplementedError

    def mask(self, frame: pd.DataFrame) -> pd.Series:
        """Boolean Series over ``frame`` (NA counts as False)."""
        raise NotImplementedError

    def __and__(self, other: Cond) -> Cond:
        return _Combo("&", self, other)

    def __or__(self, other: Cond) -> Cond:
        return _Combo("|", self, other)

    def __invert__(self) -> Cond:
        return _Not(self)


_OPS = ("==", "!=", "in", "not in", ">=", ">", "<=", "<", "between", "valid", "notna", "isna")


@dataclass(frozen=True)
class Where(Cond):
    """``column op value`` on the source rows.

    ``op`` is one of ``== != in "not in" >= > <= < between valid notna isna``. Coded (string)
    columns are compared as strings, so write ``Where("TRPTRANS", "in", ("03", "04"))``; ``between``
    is inclusive; ``valid`` is the real-answer test of :func:`pynhts.valid`.
    """

    column: str
    op: str
    value: Any = None

    def __post_init__(self) -> None:
        if self.op not in _OPS:
            raise ValueError(f"op must be one of {_OPS}")

    @property
    def columns(self) -> tuple[str, ...]:
        """The one column read."""
        return (self.column,)

    def mask(self, frame: pd.DataFrame) -> pd.Series:
        """Evaluate the condition; NA never satisfies it."""
        s = frame[self.column]
        op = self.op
        if op == "valid":
            return valid(s)
        if op == "notna":
            return s.notna()
        if op == "isna":
            return s.isna()
        if pd.api.types.is_numeric_dtype(s) and op in {">=", ">", "<=", "<", "between"}:
            x: pd.Series = pd.to_numeric(s, errors="coerce")
        elif pd.api.types.is_numeric_dtype(s):
            x = s
        else:
            x = s.astype("string")
        v = self.value
        if x.dtype == "string" and op in {"==", "!=", "in", "not in"}:
            v = [str(i) for i in v] if op in {"in", "not in"} else str(v)
        if op == "==":
            out = x == v
        elif op == "!=":
            out = (x != v) & x.notna()
        elif op == "in":
            out = x.isin(list(v))
        elif op == "not in":
            out = ~x.isin(list(v)) & x.notna()
        elif op == ">=":
            out = x >= v
        elif op == ">":
            out = x > v
        elif op == "<=":
            out = x <= v
        elif op == "<":
            out = x < v
        else:  # between
            lo, hi = v
            out = (x >= lo) & (x <= hi)
        return out.fillna(False).astype(bool)

    def __str__(self) -> str:
        return (
            f"{self.column} {self.op} {self.value!r}"
            if self.value is not None
            else f"{self.column} {self.op}"
        )


@dataclass(frozen=True)
class _Combo(Cond):
    op: str
    left: Cond
    right: Cond

    @property
    def columns(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys([*self.left.columns, *self.right.columns]))

    def mask(self, frame: pd.DataFrame) -> pd.Series:
        a, b = self.left.mask(frame), self.right.mask(frame)
        return (a & b) if self.op == "&" else (a | b)

    def __str__(self) -> str:
        return f"({self.left} {self.op} {self.right})"


@dataclass(frozen=True)
class _Not(Cond):
    inner: Cond

    @property
    def columns(self) -> tuple[str, ...]:
        return self.inner.columns

    def mask(self, frame: pd.DataFrame) -> pd.Series:
        return ~self.inner.mask(frame)

    def __str__(self) -> str:
        return f"not {self.inner}"


@dataclass(frozen=True)
class Custom(Cond):
    """An arbitrary condition: ``fn(frame) -> bool Series``; list the columns it reads in ``needs``."""

    fn: Callable[[pd.DataFrame], pd.Series]
    needs: tuple[str, ...] = ()

    @property
    def columns(self) -> tuple[str, ...]:
        """The declared columns."""
        return self.needs

    def mask(self, frame: pd.DataFrame) -> pd.Series:
        """Evaluate ``fn``."""
        return self.fn(frame).fillna(False).astype(bool)

    def __str__(self) -> str:
        return f"custom({getattr(self.fn, '__name__', 'fn')})"


# ---- aggregation specs --------------------------------------------------------------------
@dataclass(frozen=True)
class Agg:
    """One output column: ``func`` over ``column`` of the source rows that satisfy ``where``.

    Build with the constructors (``Agg.n``, ``Agg.sum`` ...). ``share`` is the number of rows
    satisfying ``where`` divided by the number satisfying ``over`` (all rows when ``over`` is None).
    """

    func: str
    column: str | None = None
    where: Cond | None = None
    over: Cond | None = None
    q: float | None = None

    def __post_init__(self) -> None:
        if self.func not in FUNCS:
            raise ValueError(f"func must be one of {FUNCS}")
        if self.func in _NUMERIC | {"nunique", "first", "last"} and self.column is None:
            raise ValueError(f"{self.func!r} needs a column")
        if self.func == "quantile" and (self.q is None or not 0 <= self.q <= 1):
            raise ValueError("quantile needs q in [0, 1]")

    @property
    def needs(self) -> tuple[str, ...]:
        """Source columns this spec reads."""
        cols = [self.column] if self.column else []
        for c in (self.where, self.over):
            if c is not None:
                cols.extend(c.columns)
        return tuple(dict.fromkeys(cols))

    @classmethod
    def n(cls, where: Cond | None = None) -> Agg:
        """Number of source rows (satisfying ``where``)."""
        return cls("n", None, where)

    @classmethod
    def count(cls, column: str, where: Cond | None = None) -> Agg:
        """Number of rows with a real answer in ``column``."""
        return cls("count", column, where)

    @classmethod
    def sum(cls, column: str, where: Cond | None = None) -> Agg:
        """Sum of ``column``."""
        return cls("sum", column, where)

    @classmethod
    def mean(cls, column: str, where: Cond | None = None) -> Agg:
        """Mean of ``column``."""
        return cls("mean", column, where)

    @classmethod
    def median(cls, column: str, where: Cond | None = None) -> Agg:
        """Median of ``column``."""
        return cls("median", column, where)

    @classmethod
    def min(cls, column: str, where: Cond | None = None) -> Agg:
        """Minimum of ``column``."""
        return cls("min", column, where)

    @classmethod
    def max(cls, column: str, where: Cond | None = None) -> Agg:
        """Maximum of ``column``."""
        return cls("max", column, where)

    @classmethod
    def std(cls, column: str, where: Cond | None = None) -> Agg:
        """Sample standard deviation of ``column`` (NaN with fewer than two rows)."""
        return cls("std", column, where)

    @classmethod
    def quantile(cls, column: str, q: float, where: Cond | None = None) -> Agg:
        """The ``q`` quantile of ``column``."""
        return cls("quantile", column, where, q=q)

    @classmethod
    def nunique(cls, column: str, where: Cond | None = None) -> Agg:
        """Number of distinct real answers in ``column``."""
        return cls("nunique", column, where)

    @classmethod
    def any(cls, where: Cond | None = None, column: str | None = None) -> Agg:
        """True when at least one row satisfies ``where`` (and has an answer in ``column``)."""
        return cls("any", column, where)

    @classmethod
    def share(cls, where: Cond, over: Cond | None = None) -> Agg:
        """Rows satisfying ``where`` divided by rows satisfying ``over`` (NaN when none)."""
        return cls("share", None, where, over)

    @classmethod
    def first(cls, column: str, where: Cond | None = None) -> Agg:
        """Value of ``column`` in the first matching row (source key order)."""
        return cls("first", column, where)

    @classmethod
    def last(cls, column: str, where: Cond | None = None) -> Agg:
        """Value of ``column`` in the last matching row (source key order)."""
        return cls("last", column, where)

    def describe(self) -> str:
        """One line for lineage tables."""
        parts = [self.func + (f"({self.column})" if self.column else "()")]
        if self.q is not None:
            parts.append(f"q={self.q}")
        if self.where is not None:
            parts.append(f"where {self.where}")
        if self.over is not None:
            parts.append(f"over {self.over}")
        return " ".join(parts)


@dataclass
class AggregateReport:
    """What :func:`aggregate` did; stored in ``result.attrs["pynhts_aggregate"]``."""

    source: str
    target: str
    keys: tuple[str, ...]
    wave: int
    n_source_rows: int = 0
    n_target_rows: int = 0
    n_targets_with_source: int = 0
    n_orphan_source_rows: int = 0
    missing_policy: str = "propagate"
    empty_policy: str = "auto"
    weight: str = ""
    specs: dict[str, dict[str, Any]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def n_targets_without_source(self) -> int:
        """Target rows that have no source row at all."""
        return self.n_target_rows - self.n_targets_with_source

    def to_frame(self) -> pd.DataFrame:
        """One row per output column: definition, missing inputs, groups affected."""
        return pd.DataFrame.from_dict(self.specs, orient="index").rename_axis("output")

    def __str__(self) -> str:
        lines = [
            f"aggregate {self.source} -> {self.target} (NHTS {self.wave}), keys {list(self.keys)}",
            f"  source rows {self.n_source_rows:,}; target rows {self.n_target_rows:,} "
            f"({self.n_targets_with_source:,} with source rows, {self.n_targets_without_source:,} without)",
            f"  orphan source rows {self.n_orphan_source_rows:,}; missing policy {self.missing_policy!r}; "
            f"empty policy {self.empty_policy!r}; weight {self.weight}",
        ]
        lines += [f"  WARNING {w}" for w in self.warnings]
        return "\n".join(lines)


# ---- the engine ----------------------------------------------------------------------------
def aggregate(
    data: NHTSData,
    source: str | pd.DataFrame,
    target: str,
    specs: Mapping[str, Agg],
    *,
    base_columns: Sequence[str] = (),
    missing: MissingPolicy = "propagate",
    empty: EmptyPolicy = "auto",
    orphans: OrphanPolicy = "raise",
    weights: str = "all",
) -> pd.DataFrame:
    """Collapse ``source`` rows onto the rows of ``target`` and return one row per target row.

    Args:
        data: An opened wave.
        source: A child table name (``"trip"``, ``"person"``, ``"vehicle"``) or a DataFrame that
            carries the target's key columns (e.g. trips with your own derived columns).
        target: An ancestor table of ``source``: ``"person"`` or ``"household"`` for trips,
            ``"household"`` for persons and vehicles.
        specs: ``{output name: Agg}``.
        base_columns: Columns of the target table to carry in the result (keys and the
            target's weight are always included).
        missing: ``"propagate"`` (default) or ``"skip"`` for sum, mean and the other numeric
            functions; see the module docstring.
        empty: ``"auto"`` (default: 0 for counts, sums and indicators of targets without source
            rows) or ``"nan"``.
        orphans: ``"raise"`` (default) or ``"report"`` source rows whose target row is absent.
        weights: Weight set of the target (see :meth:`pynhts.NHTSData.weight_column`).

    Returns:
        The target rows with the output columns appended, with ``attrs["pynhts"]`` and
        ``attrs["pynhts_aggregate"]`` (an :class:`AggregateReport`).

    Raises:
        ValueError: ``target`` is not an ancestor of ``source``, or an unknown name is used.
        NHTSIntegrityError: the target key is not unique, or orphan source rows exist.
    """
    if missing not in ("propagate", "skip"):
        raise ValueError("missing must be 'propagate' or 'skip'")
    if empty not in ("auto", "nan"):
        raise ValueError("empty must be 'auto' or 'nan'")
    if not specs:
        raise ValueError("specs is empty")
    keys = tuple(data.key(target))
    needs = list(dict.fromkeys(c for s in specs.values() for c in s.needs))
    if isinstance(source, str):
        label = source
        if target not in _ANCESTORS[data._check_table(source)]:
            raise ValueError(
                f"target {target!r} is not an ancestor of {source!r}; choose one of "
                f"{_ANCESTORS[source] or 'none (this table has no parent)'}"
            )
        order = list(data.key(source))
        src = data.table(source, needs, weight=False, missing="nan", skip="keep")
        src = _in_key_order(src, order)
    else:
        label = "<frame>"
        src = source.reset_index(drop=True)
        miss_keys = [k for k in keys if k not in src.columns]
        if miss_keys:
            raise ValueError(f"source frame lacks the target key columns {miss_keys}")
        absent = [c for c in needs if c not in src.columns]
        if absent:
            raise KeyError(f"source frame lacks columns {absent}")
    base = data.table(target, list(base_columns), weights=weights)
    if base.duplicated(list(keys)).any():
        raise NHTSIntegrityError(f"target {target} key {list(keys)} is not unique")
    rep = AggregateReport(
        source=label,
        target=target,
        keys=keys,
        wave=data.wave,
        n_source_rows=len(src),
        n_target_rows=len(base),
        missing_policy=missing,
        empty_policy=empty,
        weight=str(base.attrs["pynhts"]["weight"]),
    )

    # referential integrity: every source row must name a target row
    idx = base[list(keys)].drop_duplicates()
    probe = src[list(keys)].merge(idx, on=list(keys), how="left", indicator=True)
    n_orphan = int((probe["_merge"] != "both").sum())
    rep.n_orphan_source_rows = n_orphan
    if n_orphan:
        msg = f"{n_orphan:,} {label} rows have no {target} row"
        if orphans == "raise":
            raise NHTSIntegrityError(msg)
        rep.warnings.append(msg)
        src = src[(probe["_merge"] == "both").to_numpy()].reset_index(drop=True)

    cols: dict[str, pd.Series] = {}
    for name, spec in specs.items():
        if name in base.columns:
            raise ValueError(f"output name {name!r} collides with a column of {target}")
        cols[name], info = _one(src, keys, spec, missing, empty)
        info["definition"] = spec.describe()
        rep.specs[name] = info
        numeric = spec.func in _NUMERIC
        if numeric and info["rows_with_missing_input"] and missing == "skip":
            rep.warnings.append(
                f"{name}: {info['rows_with_missing_input']:,} rows with a missing value were skipped "
                f"in {info['groups_affected']:,} {target} rows"
            )
        if numeric and info["rows_with_missing_input"] and missing == "propagate":
            rep.warnings.append(
                f"{name}: {info['groups_affected']:,} {target} rows are NaN because a contributing "
                "value is missing (use missing='skip' to ignore such rows)"
            )
    has = src[list(keys)].drop_duplicates().assign(_has=True)
    rep.n_targets_with_source = int(len(has))
    out = base.merge(
        pd.DataFrame(cols).reset_index(), on=list(keys), how="left", validate="one_to_one"
    )
    out = out.merge(has, on=list(keys), how="left", validate="one_to_one")
    if len(out) != len(base):  # pragma: no cover - guarded by validate=
        raise NHTSIntegrityError("aggregation changed the number of target rows")
    no_source = out.pop("_has").isna()
    for name, spec in specs.items():
        out[name] = _fill_empty(out[name], no_source, spec, empty)
        if spec.func in ("n", "count", "nunique") and out[name].notna().all():
            out[name] = out[name].astype("int64")
    out.attrs["pynhts"] = {
        **base.attrs["pynhts"],
        "unit": f"{target} rows with {label} aggregates "
        "(observed survey-day values, not annualised)",
    }
    out.attrs["pynhts_aggregate"] = rep
    for w in rep.warnings:
        warnings.warn(w, PynhtsWarning, stacklevel=2)
    return out


def _in_key_order(src: pd.DataFrame, order: list[str]) -> pd.DataFrame:
    """Sort by the key, the last key (trip number) numerically when it is digits ("2" before "10")."""
    last = pd.to_numeric(src[order[-1]], errors="coerce")
    if last.notna().all():
        return (
            src.assign(_o=last)
            .sort_values([*order[:-1], "_o"], kind="stable")
            .drop(columns="_o")
            .reset_index(drop=True)
        )
    return src.sort_values(order, kind="stable").reset_index(drop=True)


def _fill_empty(col: pd.Series, no_source: pd.Series, spec: Agg, empty: EmptyPolicy) -> pd.Series:
    """A target with no source row at all is a true zero for counts, sums and indicators.

    A target that has source rows but an unknown value (all missing, or propagated) stays NaN.
    """
    if empty == "auto" and spec.func in _COUNT_LIKE:
        if spec.func == "any":
            return col.mask(no_source, False).astype("boolean")
        return col.mask(no_source, 0)
    return col


def _one(
    src: pd.DataFrame, keys: tuple[str, ...], spec: Agg, missing: MissingPolicy, empty: EmptyPolicy
) -> tuple[pd.Series, dict[str, Any]]:
    """Aggregate one spec; returns the result indexed by the keys and a diagnostics dict."""
    k = list(keys)
    m = spec.where.mask(src) if spec.where is not None else pd.Series(True, index=src.index)
    info: dict[str, Any] = {
        "func": spec.func,
        "column": spec.column,
        "rows_with_missing_input": 0,
        "groups_affected": 0,
    }
    kdf = src[k]
    f = spec.func
    if f == "n":
        return m.groupby([kdf[c] for c in k], sort=False).sum().astype("int64"), info
    if f == "share":
        den = spec.over.mask(src) if spec.over is not None else pd.Series(True, index=src.index)
        num = (m & den).groupby([kdf[c] for c in k], sort=False).sum()
        dn = den.groupby([kdf[c] for c in k], sort=False).sum()
        return (num / dn.where(dn > 0)).astype("float64"), info
    if f == "any" and spec.column is None:
        return m.groupby([kdf[c] for c in k], sort=False).any().astype("boolean"), info
    assert spec.column is not None
    col = src[spec.column]
    ok = valid(col) if not pd.api.types.is_numeric_dtype(col) else col.notna()
    miss = m & ~ok
    info["rows_with_missing_input"] = int(miss.sum())

    def grp(s: pd.Series) -> Any:
        return s.groupby([kdf[c] for c in k], sort=False)

    n_m = grp(m).sum()
    n_ok = grp(m & ok).sum()
    n_miss = grp(miss).sum()
    info["groups_affected"] = int((n_miss > 0).sum())
    if f == "count":
        return n_ok.astype("int64"), info
    if f == "any":
        return (n_ok > 0).astype("boolean"), info
    if f == "nunique":
        return grp(col.where(m & ok)).nunique().astype("int64"), info
    if f in ("first", "last"):
        return getattr(grp(col.where(m & ok)), f)(), info
    x = pd.to_numeric(col, errors="coerce").where(m & ok)
    g = grp(x)
    if f == "sum":
        res = g.sum(min_count=1)
        res = res.where(n_m > 0, 0.0) if empty == "auto" else res
    elif f == "mean":
        res = g.mean()
    elif f == "median":
        res = g.median()
    elif f == "min":
        res = g.min()
    elif f == "max":
        res = g.max()
    elif f == "std":
        res = g.std()
    else:
        res = g.quantile(float(spec.q))  # type: ignore[arg-type]
    if missing == "propagate":
        res = res.where(n_miss == 0)
    return res.astype("float64"), info
