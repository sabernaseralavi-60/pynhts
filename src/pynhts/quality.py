"""Data-quality report for one wave: keys, referential integrity, weights and top-coded values.

>>> from pynhts import quality                      # doctest: +SKIP
>>> rep = quality.report(pynhts.load(2017))         # doctest: +SKIP
>>> print(rep)                                      # doctest: +SKIP

The report reads only keys, weights and the few top-coded columns, so it is fast. It checks what a
join or a weighted estimate silently depends on: unique keys, every child row has a parent, weights
are positive and finite, and how many values sit on a top code (where a mean is not a mean).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from pynhts.core.data import _ANCESTORS
from pynhts.core.flags import topcoded_columns

if TYPE_CHECKING:
    from pynhts.core.data import NHTSData


@dataclass
class QualityReport:
    """Result of :func:`report`: one table per aspect."""

    wave: int
    tables: pd.DataFrame
    topcodes: pd.DataFrame

    @property
    def ok(self) -> bool:
        """True when keys are unique, no orphans exist and all weights are positive and finite."""
        t = self.tables
        return bool(
            (t["duplicate_keys"] == 0).all()
            and (t["orphan_rows"] == 0).all()
            and (t["bad_weights"] == 0).all()
        )

    def __str__(self) -> str:
        return (
            f"NHTS {self.wave} data quality: {'OK' if self.ok else 'PROBLEMS'}\n"
            f"{self.tables.to_string()}\n\ntop-coded columns:\n{self.topcodes.to_string()}"
        )


def report(data: NHTSData) -> QualityReport:
    """Integrity and quality summary of every table of ``data``."""
    rows = []
    keysets: dict[str, pd.DataFrame] = {}
    for t in data.tables:
        df = data.table(t, [], missing="keep", skip="keep")
        wcol = data.weight_column(t)
        keys = list(data.key(t))
        keysets[t] = df[keys]
        w = pd.to_numeric(df[wcol], errors="coerce")
        parent = next((a for a in _ANCESTORS[t] if a in keysets), None)
        orphans = 0
        if parent is not None:
            pk = list(data.key(parent))
            m = df[pk].merge(
                keysets[parent][pk].drop_duplicates(), on=pk, how="left", indicator=True
            )
            orphans = int((m["_merge"] != "both").sum())
        rows.append(
            {
                "table": t,
                "rows": len(df),
                "key": "+".join(keys),
                "duplicate_keys": int(df.duplicated(keys).sum()),
                "parent": parent or "-",
                "orphan_rows": orphans,
                "weight": wcol,
                "weight_na": int(w.isna().sum()),
                "bad_weights": int((~(w > 0) & w.notna()).sum()),
                "weight_min": float(np.nanmin(w)) if len(w) else np.nan,
                "weight_max": float(np.nanmax(w)) if len(w) else np.nan,
                "weight_total": float(w.sum()),
            }
        )
    tops = []
    for col, spec in topcoded_columns(data.wave).items():
        owner = next(
            (
                t
                for t in data.tables
                if col in data.schema(t).columns and data.schema(t).columns[col].owner == t
            ),
            None,
        )
        if owner is None or col not in pq.read_schema(data.directory / f"{owner}.parquet").names:
            continue
        s = pd.to_numeric(
            data.table(owner, [col], missing="keep", skip="keep", weight=False, keys=False)[col],
            errors="coerce",
        )
        valid = s.notna() & (s >= 0)
        tops.append(
            {
                "column": col,
                "table": owner,
                "code": spec["code"],
                "kind": spec["kind"],
                "meaning": spec["meaning"],
                "n_valid": int(valid.sum()),
                "n_at_code": int((s == spec["code"]).sum()),
                "share_at_code_pct": round(
                    100.0 * float((s == spec["code"]).sum()) / max(int(valid.sum()), 1), 3
                ),
            }
        )
    return QualityReport(
        wave=data.wave,
        tables=pd.DataFrame(rows).set_index("table"),
        topcodes=pd.DataFrame(tops).set_index("column") if tops else pd.DataFrame(),
    )
