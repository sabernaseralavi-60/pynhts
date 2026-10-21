"""Typed access to the codebook-derived column schema of an NHTS wave."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from typing import Any

import yaml

TABLES = ("household", "person", "trip", "vehicle")
# 2001 (long trips) and 2022 (one row per person) add a long-distance-travel file, a child of
# the person table.
ALL_TABLES = (*TABLES, "longdist")
KEYS = {
    "household": ("HOUSEID",),
    "person": ("HOUSEID", "PERSONID"),
    "trip": ("HOUSEID", "PERSONID", "TDTRPNUM"),
    "vehicle": ("HOUSEID", "VEHID"),
    "longdist": ("HOUSEID", "PERSONID"),
}
# Keys that differ from KEYS in a wave: the 2022 trip file is keyed by TRIPID (no TDTRPNUM);
# the 2001 long-distance file has one row per long trip (TPTRPNUM), not one per person.
WAVE_KEYS: dict[int, dict[str, tuple[str, ...]]] = {
    2022: {"trip": ("HOUSEID", "PERSONID", "TRIPID")},
    2001: {"longdist": ("HOUSEID", "PERSONID", "TPTRPNUM")},
}


def table_key(table: str, wave: int = 2017) -> tuple[str, ...]:
    """Primary-key columns of ``table`` in ``wave``."""
    return WAVE_KEYS.get(wave, {}).get(table, KEYS[table])


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
    codebook_sha256: str = ""

    @property
    def key(self) -> tuple[str, ...]:
        """Primary-key columns of this table."""
        return table_key(self.table, self.wave)

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
def _missing_overrides() -> dict[int, dict[str, dict[str, str]]]:
    ref = resources.files("pynhts") / "_schema" / "missing_overrides.yaml"
    raw: dict[int, dict[str, dict[str, str]]] = yaml.safe_load(ref.read_text(encoding="utf-8"))
    return raw


@cache
def load_schema(table: str, wave: int = 2017) -> TableSchema:
    """Load the schema of ``table`` (household, person, trip or vehicle).

    Raises:
        ValueError: unknown table or unsupported wave.
    """
    if table not in ALL_TABLES:
        raise ValueError(f"unknown table {table!r}; expected one of {ALL_TABLES}")
    ref = resources.files("pynhts") / "_schema" / str(wave) / f"{table}.yaml"
    if not ref.is_file():
        raise ValueError(f"no schema for table {table!r} in NHTS wave {wave}")
    raw: dict[str, Any] = yaml.safe_load(ref.read_text(encoding="utf-8"))
    extra = _missing_overrides().get(int(raw["wave"]), {})
    cols = {
        name: Column(
            name=name,
            label=c["label"],
            dtype=c["dtype"],
            length=c["length"],
            owner=c["owner"],
            missing_codes={**c["missing_codes"],
                           **{str(k): v for k, v in extra.get(name, {}).items()}},
            skip_code=c["skip_code"],
            range=c["range"],
            codes=tuple(Code(**k) for k in c["codes"]),
        )
        for name, c in raw["columns"].items()
    }
    return TableSchema(
        wave=int(raw["wave"]),
        table=table,
        csv=raw["csv"],
        columns=cols,
        codebook_sha256=str(raw["codebook"]["sha256"]),
    )


def wave_tables(wave: int) -> tuple[str, ...]:
    """Tables that exist in ``wave`` (the four core tables, plus ``longdist`` in 2001 and 2022)."""
    root = resources.files("pynhts") / "_schema" / str(wave)
    return tuple(t for t in ALL_TABLES if (root / f"{t}.yaml").is_file())
