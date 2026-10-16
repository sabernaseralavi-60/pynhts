"""Typed access to the codebook-derived column schema of an NHTS wave."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from typing import Any

import yaml

TABLES = ("household", "person", "trip", "vehicle")
KEYS = {
    "household": ("HOUSEID",),
    "person": ("HOUSEID", "PERSONID"),
    "trip": ("HOUSEID", "PERSONID", "TDTRPNUM"),
    "vehicle": ("HOUSEID", "VEHID"),
}


@dataclass(frozen=True)
class Code:
    """One ``code=label`` line of the codebook, with its unweighted/weighted frequency."""

    code: str
    label: str
    n: int | None
    weighted: float | None


@dataclass(frozen=True)
class Column:
    """Schema of one CSV column."""

    name: str
    label: str
    dtype: str
    length: int | None
    owner: str
    missing_codes: dict[str, str]
    skip_code: str | None
    range: str | None
    codes: tuple[Code, ...] = field(default_factory=tuple)

    @property
    def is_string(self) -> bool:
        """True for coded (character) columns whose values keep leading zeros."""
        return self.dtype == "string"


@dataclass(frozen=True)
class TableSchema:
    """Schema of one NHTS table."""

    wave: int
    table: str
    csv: str
    columns: dict[str, Column]

    @property
    def key(self) -> tuple[str, ...]:
        """Primary-key columns of this table."""
        return KEYS[self.table]

    def dtypes(self) -> dict[str, str]:
        """Mapping suitable for ``pandas.read_csv(dtype=...)``."""
        return {n: c.dtype for n, c in self.columns.items()}

    def owned(self) -> list[str]:
        """Columns that originate in this table (not copies from a parent table)."""
        return [n for n, c in self.columns.items() if c.owner == self.table]

    def inherited(self) -> list[str]:
        """Columns that are copies of columns owned by another table."""
        return [n for n, c in self.columns.items() if c.owner != self.table]


@cache
def load_schema(table: str, wave: int = 2017) -> TableSchema:
    """Load the schema of ``table`` (household, person, trip or vehicle).

    Raises:
        ValueError: unknown table or unsupported wave.
    """
    if table not in TABLES:
        raise ValueError(f"unknown table {table!r}; expected one of {TABLES}")
    ref = resources.files("pynhts") / "_schema" / str(wave) / f"{table}.yaml"
    if not ref.is_file():
        raise ValueError(f"no schema for NHTS wave {wave}")
    raw: dict[str, Any] = yaml.safe_load(ref.read_text(encoding="utf-8"))
    cols = {
        name: Column(
            name=name,
            label=c["label"],
            dtype=c["dtype"],
            length=c["length"],
            owner=c["owner"],
            missing_codes=dict(c["missing_codes"]),
            skip_code=c["skip_code"],
            range=c["range"],
            codes=tuple(Code(**k) for k in c["codes"]),
        )
        for name, c in raw["columns"].items()
    }
    return TableSchema(wave=int(raw["wave"]), table=table, csv=raw["csv"], columns=cols)
