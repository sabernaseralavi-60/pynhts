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
  has its own switch (``skip``): by default it becomes NA in numeric columns only.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from numpy.typing import NDArray

from pynhts.core.cache import arrow_to_pandas, cached_frames, derived_dir, fingerprint
from pynhts.core.flags import cautions as column_cautions
from pynhts.core.schema import (
    Column,
    TableSchema,
    load_schema,
    table_key,
    wave_tables,
)
from pynhts.io.converter import convert, parquet_dir, replicate_columns
from pynhts.io.fetcher import NHTSIntegrityError
from pynhts.io.registry import load_registry
from pynhts.stats.survey import Survey, SurveyMeta, TaylorSurvey

if TYPE_CHECKING:
    from pynhts.tours import TourConfig, TourResult

MissingMode = Literal["nan", "keep"]
SkipMode = Literal["auto", "keep", "nan"]

DEFAULT_WEIGHT = {
    "household": "WTHHFIN",
    "person": "WTPERFIN",
    "trip": "WTTRDFIN",
    "vehicle": "WTHHFIN",
    "longdist": "WTPERFIN",
}
# child table -> tables whose columns can be joined on (nearest first)
_ANCESTORS = {
    "household": (),
    "person": ("household",),
    "trip": ("person", "household"),
    "vehicle": ("household",),
    "longdist": ("person", "household"),
}
_REPLICATE_LEVEL = {
    "household": "household",
    "vehicle": "household",
    "person": "person",
    "trip": "trip",
    "longdist": "longdist",
}


class NHTSData:
    """Access to one NHTS wave stored as Parquet. Create it with :func:`pynhts.load`."""

    def __init__(self, wave: int, directory: Path) -> None:
        """Wrap the Parquet files in ``directory``; use :func:`pynhts.load` instead."""
        self.wave = wave
        self.directory = directory
        self.tables: tuple[str, ...] = wave_tables(wave)
        self._registry = load_registry(wave)
        self._schemas: dict[str, TableSchema] = {t: load_schema(t, wave) for t in self.tables}
        self._owner_spec: dict[str, Column] = {}
        self._taylor_cache: tuple[pd.Index, NDArray[Any]] | None = None
        for t in self.tables:
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

    @property
    def variance_method(self) -> str:
        """``"jkn"`` (replicate weights: 2001, 2009, 2017) or ``"taylor"`` (2022)."""
        return self._registry.variance_method

    @property
    def _weight_rtol(self) -> float:
        """Relative tolerance when comparing a row's weight with the replicate file's."""
        return float(self._registry.variance.get("weight_rtol", 1e-12))

    def key(self, table: str) -> tuple[str, ...]:
        """Primary-key columns of ``table`` in this wave."""
        return table_key(self._check_table(table), self.wave)

    def weight_column(self, table: str, weights: str = "all") -> str:
        """Full-sample weight of ``table``.

        ``weights`` selects the day-type weight set in waves that have several (2022):
        ``"all"`` (seven days, the default), ``"weekday"`` (``...5D``) or ``"weekend"``
        (``...2D``). Waves with a single weight set accept only ``"all"``.
        """
        base = self._registry.weight_for(table, DEFAULT_WEIGHT[self._check_table(table)])
        sets: dict[str, str] = self._registry.variance.get("weight_sets", {"all": ""})
        if weights not in sets:
            raise ValueError(f"weights must be one of {tuple(sets)} for NHTS {self.wave}")
        return base + sets[weights]

    def labels(self, column: str, table: str | None = None) -> dict[str, str]:
        """Mapping ``code -> label`` for a coded column, from the codebook.

        ``table`` is needed only for names that mean different things in different tables
        (``PERSONID`` and ``VEHID`` in the vehicle file).
        """
        spec = self._schemas[table].columns[column] if table else self._owner_spec[column]
        return {c.code: c.label for c in spec.codes}

    def _check_table(self, table: str) -> str:
        if table not in self.tables:
            raise ValueError(
                f"unknown table {table!r} in NHTS {self.wave}; expected one of {self.tables}"
            )
        return table

    # -- loading -------------------------------------------------------------------------
    def table(
        self,
        table: str,
        columns: Sequence[str] | None = None,
        *,
        missing: MissingMode = "nan",
        skip: SkipMode = "auto",
        weight: bool = True,
        keys: bool = True,
        weights: str = "all",
    ) -> pd.DataFrame:
        """Load ``table`` as a DataFrame with only the requested columns.

        Args:
            table: ``"household"``, ``"person"``, ``"trip"`` or ``"vehicle"``.
            columns: Columns to load. May include columns owned by a parent table (e.g.
                ``HHFAMINC`` on ``"trip"``); they are joined in with validation. ``None``
                loads every column of the table itself.
            missing: ``"nan"`` masks the codebook's missing codes (-9 not ascertained, -8/-88
                don't know, -7/-77 refused) to NA, per column; ``"keep"`` leaves all codes.
            skip: What to do with the appropriate-skip code ``-1`` (the question did not apply).
                ``"auto"`` (default) turns it into NA in numeric columns, where it is never a
                quantity (a mean of ``VMT_MILE`` that includes the -1 rows is about 45 % too
                low), and keeps it as a code in coded columns, where it is an answer category
                ("not applicable"); it has no effect with ``missing="keep"``. ``"nan"`` masks
                it everywhere, ``"keep"`` nowhere.
            weight: Also load the table's full-sample weight.
            keys: Also load the table's key columns.
            weights: Weight set (``"all"``, ``"weekday"``, ``"weekend"``); see
                :meth:`weight_column`.

        Returns:
            DataFrame in the order keys, requested columns, weight; rows in file order.

        Raises:
            KeyError: a requested column does not exist or is not reachable from ``table``.
            NHTSIntegrityError: an orphan child row or a non-unique parent key was found.
        """
        self._check_table(table)
        wcol = self.weight_column(table, weights)
        if missing not in ("nan", "keep"):
            raise ValueError("missing must be 'nan' or 'keep'")
        if skip not in ("auto", "keep", "nan"):
            raise ValueError("skip must be 'auto', 'keep' or 'nan'")
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
        source = {c: table for c in [*self.key(table), *base_cols, wcol]}
        source.update({c: anc for anc, cols in pulled.items() for c in cols})

        lead = list(self.key(table)) if keys else []
        w = [wcol] if weight else []
        read = list(dict.fromkeys([*lead, *base_cols, *w]))
        if any(anc_cols for anc_cols in pulled.values()):
            # join keys must be present even when the caller did not ask for keys
            read = list(dict.fromkeys([*self.key(table), *read]))
        df = arrow_to_pandas(pq.read_table(self.directory / f"{table}.parquet", columns=read))
        n_rows = len(df)

        for anc, cols in pulled.items():
            on = list(self.key(anc))
            parent = arrow_to_pandas(
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
        masked = self._mask(df, missing, skip, source)
        masked.attrs["pynhts"] = {"wave": self.wave, "table": table, "weight": wcol}
        return masked

    def households(
        self,
        columns: Sequence[str] | None = None,
        *,
        missing: MissingMode = "nan",
        skip: SkipMode = "auto",
        weight: bool = True,
        keys: bool = True,
        weights: str = "all",
    ) -> pd.DataFrame:
        """Shortcut for ``table("household", ...)``; see :meth:`table`."""
        return self.table(
            "household", columns, missing=missing, skip=skip, weight=weight, keys=keys,
            weights=weights,
        )

    def persons(
        self,
        columns: Sequence[str] | None = None,
        *,
        missing: MissingMode = "nan",
        skip: SkipMode = "auto",
        weight: bool = True,
        keys: bool = True,
        weights: str = "all",
    ) -> pd.DataFrame:
        """Shortcut for ``table("person", ...)``; see :meth:`table`."""
        return self.table(
            "person", columns, missing=missing, skip=skip, weight=weight, keys=keys,
            weights=weights,
        )

    def trips(
        self,
        columns: Sequence[str] | None = None,
        *,
        missing: MissingMode = "nan",
        skip: SkipMode = "auto",
        weight: bool = True,
        keys: bool = True,
        weights: str = "all",
    ) -> pd.DataFrame:
        """Shortcut for ``table("trip", ...)``; see :meth:`table`."""
        return self.table(
            "trip", columns, missing=missing, skip=skip, weight=weight, keys=keys,
            weights=weights,
        )

    def vehicles(
        self,
        columns: Sequence[str] | None = None,
        *,
        missing: MissingMode = "nan",
        skip: SkipMode = "auto",
        weight: bool = True,
        keys: bool = True,
        weights: str = "all",
    ) -> pd.DataFrame:
        """Shortcut for ``table("vehicle", ...)``; see :meth:`table`."""
        return self.table(
            "vehicle", columns, missing=missing, skip=skip, weight=weight, keys=keys,
            weights=weights,
        )

    def longdist(
        self,
        columns: Sequence[str] | None = None,
        *,
        missing: MissingMode = "nan",
        skip: SkipMode = "auto",
        weight: bool = True,
        keys: bool = True,
        weights: str = "all",
    ) -> pd.DataFrame:
        """Shortcut for ``table("longdist", ...)`` (NHTS 2001 and 2022); see :meth:`table`."""
        return self.table(
            "longdist", columns, missing=missing, skip=skip, weight=weight, keys=keys,
            weights=weights,
        )

    def survey(
        self,
        table: str,
        columns: Sequence[str] | None = None,
        *,
        missing: MissingMode = "nan",
        skip: SkipMode = "auto",
        level: float = 0.95,
        weights: str = "all",
        clusters: Literal["all", "observed"] = "all",
        convention: Literal["fhwa", "design"] = "fhwa",
    ) -> Survey | TaylorSurvey:
        """Rows of ``table`` bound to the weights and the wave's variance design.

        NHTS 2017 (``variance_method == "jkn"``): household and vehicle rows use the household
        replicates, person rows the person replicates and trip rows the person-day
        (``WTTRDFIN``) replicates; the result is a :class:`pynhts.stats.Survey` with JKn
        standard errors. NHTS 2022 (``"taylor"``, no replicate weights): every row carries its own
        weight and belongs to its household (cluster) and ``STRATUMID`` (stratum); the result is a
        :class:`pynhts.stats.TaylorSurvey`. Both offer ``total``, ``mean``, ``proportion`` and
        ``ratio`` with standard errors, margins of error and confidence intervals.

        Args:
            table: Table whose rows are analysed.
            columns: Columns to load (see :meth:`table`).
            missing: Missing-code handling (see :meth:`table`).
            skip: Appropriate-skip handling (see :meth:`table`).
            level: Confidence level.
            weights: Weight set: ``"all"`` (default), ``"weekday"`` or ``"weekend"`` (2022 only).
            convention: Jackknife waves only. ``"fhwa"`` (default) uses the variance multiplier and
                degrees of freedom of the User's Guide and the published tables; ``"design"`` the
                textbook convention of the replicate method (2009: multiplier 1, 99 df, as R's
                ``svrepdesign(type="JK2")``; 2001: 98 df; 2017: 84 df). Standard errors differ by
                about 0.5 % in 2009 (multiplier 1 instead of 0.99) and not at all in 2001 and
                2017; the degrees of freedom change the t multiplier in the fourth digit (2017:
                1.989 on 84 df against 1.984 on 98).
            clusters: 2022 only. ``"all"`` (default) keeps every sampled household in the design,
                also those without a row in ``table`` (no trip on the travel day, no vehicle);
                they contribute zeros, which is the design-correct variance. ``"observed"``
                keeps only households that have a row, which is what software gives when you
                feed it the trip or vehicle file alone (smaller standard errors; use it only to
                compare with such output).

        Raises:
            NHTSIntegrityError: a row has no weight unit, or its weight differs from the
                replicate file's full-sample weight.
        """
        rows = self.table(table, columns, missing=missing, skip=skip, weight=True, keys=True,
                          weights=weights)
        meta = self._meta(table, self.weight_column(table, weights), list(rows.columns),
                          convention)
        if self.variance_method == "taylor":
            return self._bind_taylor(rows, self._check_table(table), level, weights,
                                     clusters=clusters, meta=meta)
        if weights != "all":
            raise ValueError(f"NHTS {self.wave} has only the 'all' weight set")
        return self._bind(rows, _REPLICATE_LEVEL[self._check_table(table)],
                          self.weight_column(table), level, meta=meta, convention=convention)

    def survey_rows(
        self, rows: pd.DataFrame, level: str, *, level_conf: float = 0.95, weights: str = "all",
        convention: Literal["fhwa", "design"] = "fhwa",
    ) -> Survey | TaylorSurvey:
        """Bind your own rows to the weights and variance design, e.g. tours (``level="trip"``).

        In 2017 ``level="trip"`` means the person-day replicate weight (keys ``HOUSEID`` and
        ``PERSONID``). In 2022 the levels are the weight-carrying tables (``"household"``,
        ``"person"``, ``"trip"`` keyed by ``TRIPID``, ``"vehicle"``, ``"longdist"``); rows must
        carry the keys of that table, and each row takes the weight of the table row it names.

        ``rows`` must carry the keys of the weight unit: ``HOUSEID`` for ``"household"``,
        ``HOUSEID`` and ``PERSONID`` for ``"person"`` and for ``"trip"`` (person-day). All rows
        sharing a key share the unit's weight, so tour-level or stop-level tables get correct
        jackknife standard errors without new variance code.

        Raises:
            NHTSIntegrityError: a row has no replicate-weight unit.
        """
        meta = self._meta(level, self.weight_column(level, weights), list(rows.columns),
                          convention)
        if self.variance_method == "taylor":
            return self._bind_taylor(rows, self._check_table(level), level_conf, weights,
                                     rows_are_table=False, meta=meta)
        levels = self._registry.replicate_jobs
        if level not in levels:
            raise ValueError(f"level must be one of {tuple(levels)}")
        return self._bind(rows, level, None, level_conf, meta=meta, convention=convention)

    def _meta(
        self, table: str, weight: str, columns: list[str], convention: str = "fhwa"
    ) -> SurveyMeta:
        """Wave, design, unit and cautions that travel with a survey object and its results."""
        unit = {
            "household": "households",
            "person": "persons",
            "vehicle": "household vehicles",
            "trip": "annual person trips (travel-day weight = 365 x person weight)"
            if self.wave != 2022 else "annual person trips (trip weights include the methods "
            "adjustment)",
            "longdist": "annual long-distance person trips, national sample (weight = national "
            "person weight x 365/28)" if self.wave == 2001
            else "persons (one row per person, not per trip)",
        }[table]
        cautions = column_cautions(self.wave, table, columns)
        system = "national-longdist" if (self.wave == 2001 and table == "longdist") else "main"
        design = self._registry.design_description
        if convention != "fhwa" and self.variance_method != "taylor":
            factor, df = self._registry.convention(convention)
            design += (f"; variance multiplier {factor:.6g} and {df:g} degrees of freedom (the "
                       "textbook replicate-design convention, not the published-table one)")
        return SurveyMeta(
            wave=self.wave, table=table, weight=weight, design=design,
            unit=unit, cautions=cautions, replicate_system=system,
        )

    def _bind(
        self, rows: pd.DataFrame, level_name: str, weight_col: str | None, level: float,
        meta: SurveyMeta | None = None, convention: str = "fhwa",
    ) -> Survey:
        keys = list(self.key("household" if level_name == "household" else "person"))
        job = self._registry.replicate_jobs[level_name]
        absent = [k for k in keys if k not in rows.columns]
        if absent:
            raise KeyError(f"rows lack the key columns {absent}")
        rep = self.replicate_weights(level_name)
        wcol = job.weight
        index = pd.MultiIndex.from_frame(rep[keys]) if len(keys) > 1 else pd.Index(rep[keys[0]])
        wanted = pd.MultiIndex.from_frame(rows[keys]) if len(keys) > 1 else pd.Index(rows[keys[0]])
        unit = index.get_indexer(wanted)
        if (unit < 0).any():
            raise NHTSIntegrityError("rows without a replicate-weight unit")
        raw_w = rep[wcol].to_numpy(dtype=np.float64)
        raw_reps = rep[
            replicate_columns(job.prefix, self._registry.n_replicates, job.pad)
        ].to_numpy(dtype=np.float64)
        # A unit without weights (2009: 45,967 persons without a travel-day weight; 2001: persons
        # outside the long-distance sample) has no rows to weigh. Zero its weights so that
        # 0 * NaN cannot poison the matrix products; a *referenced* unit must be complete.
        absent = np.isnan(raw_w) | np.isnan(raw_reps).any(axis=1)
        if absent[unit].any():
            raise NHTSIntegrityError(
                f"{int(absent[unit].sum())} rows belong to a unit with a missing weight"
            )
        unit_w = np.asarray(np.where(absent, 0.0, raw_w), dtype=np.float64)
        reps = np.asarray(np.where(absent[:, None], 0.0, raw_reps), dtype=np.float64)
        if weight_col is not None and not np.allclose(
            rows[weight_col].to_numpy(dtype=np.float64), unit_w[unit], rtol=self._weight_rtol,
            atol=0
        ):
            raise NHTSIntegrityError("row weights differ from the replicate file's weights")
        factor, df = self._registry.convention(convention)
        return Survey(rows, unit.astype(np.int64), unit_w, reps, level=level, df=df,
                      factor=factor, meta=meta)

    def _taylor_design(self) -> tuple[pd.Index, NDArray[Any]]:
        """Household ids and the stratum label of each household (the clusters)."""
        if self._taylor_cache is None:
            col = str(self._registry.variance["strata"])
            hh = arrow_to_pandas(
                pq.read_table(self.directory / "household.parquet", columns=["HOUSEID", col])
            )
            if hh[col].isna().any():
                raise NHTSIntegrityError(f"{col} has missing values")
            self._taylor_cache = (pd.Index(hh["HOUSEID"]), hh[col].to_numpy())
        return self._taylor_cache

    def _bind_taylor(
        self, rows: pd.DataFrame, table: str, level: float, weights: str,
        *, rows_are_table: bool = True, clusters: Literal["all", "observed"] = "all",
        meta: SurveyMeta | None = None,
    ) -> TaylorSurvey:
        """Bind rows to the weight-carrying ``table`` of a Taylor-series wave.

        Every row of ``table`` is a unit with its own weight; its cluster is the household.
        ``rows`` (the table itself, or your own rows keyed like it) are mapped to those units.
        """
        key = list(self.key(table))
        absent = [k for k in key if k not in rows.columns]
        if absent:
            raise KeyError(f"rows lack the key columns {absent}")
        wcol = self.weight_column(table, weights)
        units = arrow_to_pandas(
            pq.read_table(self.directory / f"{table}.parquet", columns=[*key, wcol])
        )
        if units.duplicated(key).any():
            raise NHTSIntegrityError(f"{table} keys {key} are not unique")
        index = pd.MultiIndex.from_frame(units[key]) if len(key) > 1 else pd.Index(units[key[0]])
        wanted = pd.MultiIndex.from_frame(rows[key]) if len(key) > 1 else pd.Index(rows[key[0]])
        unit = index.get_indexer(wanted)
        if (unit < 0).any():
            raise NHTSIntegrityError(f"rows without a {table} weight unit")
        unit_w = units[wcol].to_numpy(dtype=np.float64)
        if rows_are_table and wcol in rows.columns and not np.allclose(
            rows[wcol].to_numpy(dtype=np.float64), unit_w[unit], rtol=1e-12, atol=0
        ):
            raise NHTSIntegrityError("row weights differ from the table's weights")
        hh_ids, hh_stratum = self._taylor_design()
        cluster: NDArray[np.int64] = np.asarray(
            hh_ids.get_indexer(pd.Index(units["HOUSEID"])), dtype=np.int64
        )
        if (cluster < 0).any():
            raise NHTSIntegrityError(f"{table} rows without a household row")
        if clusters == "observed":
            present, inverse = np.unique(cluster, return_inverse=True)
            cluster = np.asarray(inverse, dtype=np.int64).ravel()
            hh_stratum = hh_stratum[present]
        elif clusters != "all":
            raise ValueError("clusters must be 'all' or 'observed'")
        return TaylorSurvey(rows, unit.astype(np.int64), unit_w, cluster.astype(np.int64),
                            hh_stratum, level=level, meta=meta)

    def tours(
        self,
        config: TourConfig | None = None,
        columns: Sequence[str] = (),
        *,
        force_rebuild: bool = False,
    ) -> TourResult:
        """Tours of every person-day (see :func:`pynhts.tours.build_tours`), cached as Parquet.

        Validated for NHTS 2017 only: other waves need an explicit ``config`` (see Raises).

        The first call forms the tours and stores them in ``<cache>/<wave>/derived/``; later
        calls with the same ``config``, ``columns`` and source data read that file (about a
        hundred times faster). The file name carries a hash of the parameters and of the source
        Parquet files, so a changed parameter or a re-converted wave never returns stale tours.

        Args:
            config: Tour parameters (default :class:`~pynhts.tours.TourConfig`).
            columns: Extra trip columns to carry on ``TourResult.trips``. ``WHYFROM``, ``WHYTO``,
                ``TRPTRANS``, ``STRTTIME`` and ``ENDTIME`` are always included.
            force_rebuild: Ignore and overwrite the cached file.

        Returns:
            The :class:`~pynhts.tours.TourResult` (``.tours`` and ``.trips`` are DataFrames). Trip
            purposes are loaded with ``missing="keep"``, as tour formation needs.
        """
        from pynhts.tours import TourConfig, TourResult, build_tours

        if config is None and self.wave != 2017:
            raise ValueError(
                f"the default tour rules use NHTS 2017 purpose codes (home 01/02, work 03); in "
                f"NHTS {self.wave} work and home trips have other WHYTO codes and the result "
                "would contain no home-based-work tours. Pass a TourConfig written for this wave "
                "(none is validated yet)."
            )
        cfg = config or TourConfig()
        cols = sorted({"WHYFROM", "WHYTO", "TRPTRANS", "STRTTIME", "ENDTIME", *columns})
        key = fingerprint(
            {"wave": self.wave, "config": cfg, "columns": cols},
            [self.directory / "trip.parquet"],
        )

        def build() -> dict[str, pd.DataFrame]:
            trips = self.trips(cols, weight=False, missing="keep")
            res = build_tours(trips, cfg)
            return {"tours": res.tours, "tour_trips": res.trips}

        frames = cached_frames(
            derived_dir(self.directory), ("tours", "tour_trips"), key, build,
            force_rebuild=force_rebuild,
        )
        return TourResult(frames["tour_trips"], frames["tours"], cfg)

    def decode_labels(
        self, frame: pd.DataFrame, columns: Sequence[str] | None = None, *, table: str
    ) -> pd.DataFrame:
        """Return a copy of ``frame`` with coded columns replaced by codebook labels.

        Args:
            frame: A DataFrame obtained from ``table`` (``table`` selects the codebook, which
                matters for names that differ by table such as ``PERSONID`` in vehicles).
            columns: Columns to decode; default every coded string column of ``frame``.
            table: ``"household"``, ``"person"``, ``"trip"`` or ``"vehicle"``.

        Codes without a label (including masked NA) are left unchanged. Numeric columns and
        range-valued columns (age, miles, ...) have no labels and are skipped.
        """
        cols_schema = self.schema(table).columns
        todo = list(columns) if columns is not None else list(frame.columns)
        out = frame.copy()
        for name in todo:
            spec = cols_schema.get(name)
            if spec is None or not spec.is_string or name not in out.columns:
                continue
            mapping = {c.code: c.label for c in spec.codes if c.label}
            if mapping:
                out[name] = out[name].map(mapping).fillna(out[name])
        result: pd.DataFrame = out
        return result

    def replicate_weights(self, level: str, *, dtype: str = "float64") -> pd.DataFrame:
        """Full-sample weight plus the jackknife replicates for ``level`` (98, 100 or 99 by wave).

        ``level`` is ``"household"``, ``"person"`` or ``"trip"``. The trip level is keyed by
        person-day (``HOUSEID``, ``PERSONID``): join it to trips on those two keys.
        Replicates are stored as float32 and returned as float64 by default, which is the
        precision required before squaring deviations.
        """
        if self.variance_method != "jkn":
            raise ValueError(
                f"NHTS {self.wave} has no replicate weights; its standard errors use "
                "Taylor-series linearisation (see NHTSData.survey)"
            )
        levels = self._registry.replicate_jobs
        if level not in levels:
            raise ValueError(f"level must be one of {tuple(levels)}")
        job = levels[level]
        path = self.directory / job.out
        if not path.is_file():
            raise FileNotFoundError(
                f"{path} missing; run pynhts.io.convert(groups=('replicates',)) "
                "or load(..., replicates=True)"
            )
        df = arrow_to_pandas(pq.read_table(path))
        cols = replicate_columns(job.prefix, self._registry.n_replicates, job.pad)
        converted: pd.DataFrame = df.astype({c: dtype for c in cols})
        if job.fill_from:
            self._fill_missing_weights(converted, job, cols, levels)
        return converted

    def _fill_missing_weights(
        self, frame: pd.DataFrame, job: Any, cols: list[str], levels: dict[str, Any]
    ) -> None:
        """Give units without weights ``factor`` x the weights of ``fill_from['level']``."""
        src_job = levels[str(job.fill_from["level"])]
        factor = float(job.fill_from["factor"])
        src = self.replicate_weights(src_job.level, dtype="float64").set_index(list(job.keys))
        src_cols = [src_job.weight, *replicate_columns(
            src_job.prefix, self._registry.n_replicates, src_job.pad)]
        dst_cols = [job.weight, *cols]
        missing = frame[job.weight].isna().to_numpy()
        if not missing.any():
            return
        index = pd.MultiIndex.from_frame(frame.loc[missing, list(job.keys)])
        values = src.reindex(index)[src_cols].to_numpy(dtype=np.float64) * factor
        if np.isnan(values).any():
            raise NHTSIntegrityError("units without weights have no weights to borrow either")
        frame.loc[missing, dst_cols] = values

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
            if spec.skip_code is not None and (
                skip == "nan" or (skip == "auto" and missing == "nan" and not spec.is_string)
            ):
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
        wave: Survey year (2001, 2009, 2017 or 2022).
        cache: Cache root override (default: ``$PYNHTS_CACHE_DIR`` or the user cache dir).
        offline: Never download; raise if the data are not already cached.
        replicates: Also make sure the jackknife replicate weights are available (waves
            without replicate weights, i.e. 2022, ignore this flag).

    Returns:
        An :class:`NHTSData` handle. Nothing large is read until you ask for a table.
    """
    has_replicates = "replicates" in load_registry(wave).groups
    groups: tuple[str, ...] = ("core", "replicates") if replicates and has_replicates else ("core",)
    convert(wave, groups, cache=cache, offline=offline)
    return NHTSData(wave, parquet_dir(wave, cache))

