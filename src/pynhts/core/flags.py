"""Per-wave column flags that the codebooks do not state: top-codes, national-only items."""

from __future__ import annotations

from functools import cache
from importlib import resources
from typing import Any

import yaml


class PynhtsWarning(UserWarning):
    """A result is technically valid but easy to misread (top-coded or sample-restricted column)."""


@cache
def _flags() -> dict[str, Any]:
    ref = resources.files("pynhts") / "_schema" / "column_flags.yaml"
    raw: dict[str, Any] = yaml.safe_load(ref.read_text(encoding="utf-8"))
    return raw


def topcode(wave: int, column: str) -> dict[str, Any] | None:
    """Top- or bottom-code of ``column`` in ``wave``, or ``None``.

    The entry has ``kind``, ``code``, ``boundary``, ``meaning`` and ``source``.
    """
    entry = _flags()["topcodes"].get(wave, {}).get(column)
    return dict(entry) if entry else None


def topcoded_columns(wave: int) -> dict[str, dict[str, Any]]:
    """All top-coded columns of ``wave``."""
    return {k: dict(v) for k, v in _flags()["topcodes"].get(wave, {}).items()}


def national_only(wave: int, column: str, table: str | None = None) -> bool:
    """True if ``column`` (or the whole ``table``) exists only for the national sample."""
    entry = _flags().get("national_only", {}).get(wave)
    if not entry:
        return False
    return column in entry["columns"] or (table is not None and table in entry["tables"])


def national_only_columns(wave: int) -> list[str]:
    """Columns that exist only for the national sample of ``wave`` (empty if none)."""
    entry = _flags().get("national_only", {}).get(wave)
    return list(entry["columns"]) if entry else []


def cautions(wave: int, table: str, columns: list[str]) -> dict[str, str]:
    """Warning text per requested column that is easy to misread in ``wave``."""
    out: dict[str, str] = {}
    for col in columns:
        tc = topcode(wave, col)
        note = ""
        if national_only(wave, col, table):
            note = (
                f" {col} also exists only for the national-sample households of NHTS {wave} "
                "(-1 for the add-on areas); the full-sample weight leaves their records out."
            )
        if tc:
            if tc["kind"] == "cap":
                out[col] = (
                    f"{col} is capped in NHTS {wave}: {tc['code']:g} stands for '{tc['meaning']}', "
                    "so means and totals are biased downward for the capped records." + note
                )
                continue
            where = "above" if tc["kind"] == "top" else "below"
            out[col] = (
                f"{col} is {'top' if tc['kind'] == 'top' else 'bottom'}-coded in NHTS {wave}: the "
                f"value {tc['code']:g} stands for '{tc['meaning']}' (every value {where} "
                f"{tc['boundary']:g}), so means and totals are biased; use bands or treat it as "
                "censored." + note
            )
        elif national_only(wave, col, table):
            out[col] = (
                f"{col} exists only for the national-sample households of NHTS {wave} (-1 for the "
                "add-on areas). The full-sample weight leaves their records out of the total; the "
                "national weights (WTHHNTL, WTPRNTL, ...) are not offered by pynhts."
            )
    return out
