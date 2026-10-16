"""The :class:`NHTSData` loader: lazy column selection and ownership-aware, validated merges.

Rules the loader enforces so that analyses cannot silently go wrong:

* Columns are read lazily from Parquet; only what you ask for is loaded.
* A requested column that the base table does not carry is taken from the table that **owns**
  it (e.g. household income onto trips) with a validated many-to-one left join: parent keys are
  unique, no base row is dropped or duplicated, and an orphan child raises an error.
* Columns that are copies of parent columns (e.g. ``HHSIZE`` inside the trip file) are read
  from the base table itself, so there are never ``_x/_y`` duplicates.
* Missing-value codes are masked per column from the codebook (``missing="nan"``) or kept
  untouched (``missing="keep"``). The appropriate-skip code ``-1`` is a different thing and
  has its own switch (``skip``).
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from pynhts.core.schema import KEYS, TABLES, Column, TableSchema, load_schema
from pynhts.io.converter import convert, parquet_dir, replicate_columns
from pynhts.io.fetcher import NHTSIntegrityError

MissingMode = Literal["nan", "keep"]
SkipMode = Literal["keep", "nan"]

DEFAULT_WEIGHT = {
    "household": "WTHHFIN",
    "person": "WTPERFIN",
    "trip": "WTTRDFIN",
    "vehicle": "WTHHFIN",
}
# child table -> tables whose columns can be joined on (nearest first)
_ANCESTORS = {
    "household": (),
    "person": ("household",),
    "trip": ("person", "household"),
    "vehicle": ("household",),
}
_REPLICATE_FILE = {
    "household": ("repw_household.parquet", "WTHHFIN"),
    "person": ("repw_person.parquet", "WTPERFIN"),
    "trip": ("repw_trip.parquet", "WTTRDFIN"),
}


def _to_pandas(table: pa.Table) -> pd.DataFrame:
    df: pd.DataFrame = table.to_pandas(types_mapper={pa.string(): pd.StringDtype()}.get)
    return df


class NHTSData:
    """Access to one NHTS wave stored as Parquet. Create it with :func:`pynhts.load`."""

    def __init__(self, wave: int, directory: Path) -> None:
        """Wrap the Parquet files in ``directory``; use :func:`pynhts.load` instead."""
        self.wave = wave
        self.directory = directory
        self._schemas: dict[str, TableSchema] = {t: load_schema(t, wave) for t in TABLES}
        self._owner_spec: dict[str, Column] = {}
        for t in TABLES:
            for name, col in self._schemas[t].columns.items():
                if col.owner == t:
                    self._owner_spec.setdefault(name, col)

    # -- introspection -------------------------------------------------------------------
    def schema(self, table: str) -> TableSchema:
        """Schema of ``table`` (household, person, trip or vehicle)."""
        return self._schemas[self._check_table(table)]

    def columns(self, table: str, *, include_parents: bool = True) -> list[str]:
        """Names that can be requested for ``table`` (its own plus parent-owned columns)."""
        own = list(self.schema(table).columns)
        if not include_parents:
            return own
        extra = [
            n
            for anc in _ANCESTORS[table]
            for n, c in self._schemas[anc].columns.items()
            if c.owner == anc and n not in own
        ]
        return own + sorted(set(extra) - set(own))

    def weight_column(self, table: str) -> str:
        """Default full-sample weight of ``table``."""
        return DEFAULT_WEIGHT[self._check_table(table)]

    def labels(self, column: str, table: str | None = None) -> dict[str, str]:
        """Mapping ``code -> label`` for a coded column, from the codebook.

        ``table`` is needed only for names that mean different things in different tables
        (``PERSONID`` and ``VEHID`` in the vehicle file).
        """
        spec = self._schemas[table].columns[column] if table else self._owner_spec[column]
        return {c.code: c.label for c in spec.codes}

    @staticmethod
    def _check_table(table: str) -> str:
        if table not in TABLES:
            raise ValueError(f"unknown table {table!r}; expected one of {TABLES}")
        return table

    # -- loading -------------------------------------------------------------------------
    def table(
        self,
        table: str,
        columns: Sequence[str] | None = None,
        *,
        missing: MissingMode = "nan",
        skip: SkipMode = "keep",
        weight: bool = True,
        keys: bool = True,
    ) -> pd.DataFrame:
        """Load ``table`` as a DataFrame with only the requested columns.

        Args:
            table: ``"household"``, ``"person"``, ``"trip"`` or ``"vehicle"``.
            columns: Columns to load. May include columns owned by a parent table (e.g.
                ``HHFAMINC`` on ``"trip"``); they are joined in with validation. ``None``
                loads every column of the table itself.
            missing: ``"nan"`` masks the codebook's missing codes (-9 not ascertained, -8/-88
                don't know, -7/-77 refused) to NA, per column; ``"keep"`` leaves all codes.
            skip: What to do with the appropriate-skip code ``-1``: ``"keep"`` (default; it is
                not a missing value but it is also not a real number, so numeric columns that
                contain it need care) or ``"nan"``.
            weight: Also load the table's default full-sample weight.
            keys: Also load the table's key columns.

        Returns:
            DataFrame in the order keys, requested columns, weight; rows in file order.

        Raises:
            KeyError: a requested column does not exist or is not reachable from ``table``.
            NHTSIntegrityError: an orphan child row or a non-unique parent key was found.
        """
        self._check_table(table)
        if missing not in ("nan", "keep"):
            raise ValueError("missing must be 'nan' or 'keep'")
        if skip not in ("keep", "nan"):
            raise ValueError("skip must be 'keep' or 'nan'")
        own = self.schema(table)
        want = list(own.columns) if columns is None else list(dict.fromkeys(columns))
        base_cols = [c for c in want if c in own.columns]
        pulled: dict[str, list[str]] = {}
        for c in want:
            if c in own.columns:
                continue
            anc = self._find_ancestor(table, c)
            pulled.setdefault(anc, []).append(c)
        # the schema that describes each loaded column: the table it is read from
        source = {c: table for c in [*KEYS[table], *base_cols, DEFAULT_WEIGHT[table]]}
        source.update({c: anc for anc, cols in pulled.items() for c in cols})

        lead = list(KEYS[table]) if keys else []
        w = [self.weight_column(table)] if weight else []
        read = list(dict.fromkeys([*lead, *base_cols, *w]))
        if any(anc_cols for anc_cols in pulled.values()):
            # join keys must be present even when the caller did not ask for keys
            read = list(dict.fromkeys([*KEYS[table], *read]))
        df = _to_pandas(pq.read_table(self.directory / f"{table}.parquet", columns=read))
        n_rows = len(df)

        for anc, cols in pulled.items():
            on = list(KEYS[anc])
            parent = _to_pandas(
                pq.read_table(self.directory / f"{anc}.parquet", columns=[*on, *cols])
            )
            if parent.duplicated(on).any():
                raise NHTSIntegrityError(f"{anc} keys {on} are not unique")
            df = df.merge(parent, on=on, how="left", validate="many_to_one", indicator="_m")
            if (df["_m"] != "both").any():
                raise NHTSIntegrityError(f"{table} rows without a parent {anc} row")
            df = df.drop(columns="_m")
            if len(df) != n_rows:
                raise NHTSIntegrityError(f"join with {anc} changed the row count")

        df = df[list(dict.fromkeys([*lead, *want, *w]))]
        return self._mask(df, missing, skip, source)

    def households(
        self,
        columns: Sequence[str] | None = None,
        *,
        missing: MissingMode = "nan",
        skip: SkipMode = "keep",
        weight: bool = True,
        keys: bool = True,
    ) -> pd.DataFrame:
        """Shortcut for ``table("household", ...)``; see :meth:`table`."""
        return self.table(
            "household", columns, missing=missing, skip=skip, weight=weight, keys=keys
        )

    def persons(
        self,
        columns: Sequence[str] | None = None,
        *,
        missing: MissingMode = "nan",
        skip: SkipMode = "keep",
        weight: bool = True,
        keys: bool = True,
    ) -> pd.DataFrame:
        """Shortcut for ``table("person", ...)``; see :meth:`table`."""
        return self.table(
            "person", columns, missing=missing, skip=skip, weight=weight, keys=keys
        )

    def trips(
        self,
        columns: Sequence[str] | None = None,
        *,
        missing: MissingMode = "nan",
        skip: SkipMode = "keep",
        weight: bool = True,
        keys: bool = True,
    ) -> pd.DataFrame:
        """Shortcut for ``table("trip", ...)``; see :meth:`table`."""
        return self.table(
            "trip", columns, missing=missing, skip=skip, weight=weight, keys=keys
        )

    def vehicles(
        self,
        columns: Sequence[str] | None = None,
        *,
        missing: MissingMode = "nan",
        skip: SkipMode = "keep",
        weight: bool = True,
        keys: bool = True,
    ) -> pd.DataFrame:
        """Shortcut for ``table("vehicle", ...)``; see :meth:`table`."""
        return self.table(
            "vehicle", columns, missing=missing, skip=skip, weight=weight, keys=keys
        )

    def replicate_weights(self, level: str, *, dtype: str = "float64") -> pd.DataFrame:
        """Full-sample weight plus the 98 jackknife replicates for ``level``.

        ``level`` is ``"household"``, ``"person"`` or ``"trip"``. The trip level is keyed by
        person-day (``HOUSEID``, ``PERSONID``): join it to trips on those two keys.
        Replicates are stored as float32 and returned as float64 by default, which is the
        precision required before squaring deviations.
        """
        if level not in _REPLICATE_FILE:
            raise ValueError(f"level must be one of {tuple(_REPLICATE_FILE)}")
        fname, wcol = _REPLICATE_FILE[level]
        path = self.directory / fname
        if not path.is_file():
            raise FileNotFoundError(
                f"{path} missing; run pynhts.io.convert(groups=('replicates',)) "
                "or load(..., replicates=True)"
            )
        df = _to_pandas(pq.read_table(path))
        rep = replicate_columns(wcol)
        df[rep] = df[rep].astype(dtype)
        return df

    # -- internals -----------------------------------------------------------------------
    def _find_ancestor(self, table: str, column: str) -> str:
        if column not in self._owner_spec:
            raise KeyError(f"unknown NHTS column {column!r}")
        for anc in _ANCESTORS[table]:
            spec = self._schemas[anc].columns.get(column)
            if spec is not None and spec.owner == anc:
                return anc
        raise KeyError(
            f"column {column!r} is owned by the {self._owner_spec[column].owner} table and "
            f"cannot be joined onto {table}; reachable parent tables: "
            f"{_ANCESTORS[table] or 'none'}"
        )

    def _mask(
        self, df: pd.DataFrame, missing: MissingMode, skip: SkipMode, source: dict[str, str]
    ) -> pd.DataFrame:
        for name in df.columns:
            spec = self._schemas[source[name]].columns[name]
            codes: set[str] = set(spec.missing_codes) if missing == "nan" else set()
            if skip == "nan" and spec.skip_code is not None:
                codes.add(spec.skip_code)
            if not codes:
                continue
            col = df[name]
            if spec.is_string:
                df[name] = col.mask(col.isin(codes))
            else:
                df[name] = col.mask(col.isin([float(c) for c in codes]))
        return df


def load(
    wave: int = 2017,
    *,
    cache: str | os.PathLike[str] | None = None,
    offline: bool = False,
    replicates: bool = False,
) -> NHTSData:
    """Open an NHTS wave, downloading and converting it on first use.

    Args:
        wave: Survey year (only 2017 in Phase 1).
        cache: Cache root override (default: ``$PYNHTS_CACHE_DIR`` or the user cache dir).
        offline: Never download; raise if the data are not already cached.
        replicates: Also make sure the 98 jackknife replicate weights are available.

    Returns:
        An :class:`NHTSData` handle. Nothing large is read until you ask for a table.
    """
    groups: tuple[str, ...] = ("core", "replicates") if replicates else ("core",)
    convert(wave, groups, cache=cache, offline=offline)
    return NHTSData(wave, parquet_dir(wave, cache))

