"""Variable dictionary of a wave, built from the codebook-derived schema (no data needed).

>>> import pynhts
>>> pynhts.dictionary(2022).query("variable == 'TRPTRANS'")      # doctest: +SKIP
>>> pynhts.describe("HHSIZE", 2017)                                # doctest: +SKIP
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from pynhts.core.schema import load_schema, wave_tables


def dictionary(wave: int = 2017) -> pd.DataFrame:
    """One row per variable of ``wave``: where it lives, its type and its coded values.

    A variable that parent tables copy into child files (household income in the trip file, for
    instance) has one row, under the table that owns it, with every table that carries a copy in
    ``tables``. Names that mean different things in different tables (``PERSONID`` in the
    vehicle file) get one row per meaning.

    Columns: ``variable``, ``owner``, ``label``, ``dtype``, ``length``, ``n_codes``,
    ``missing_codes``, ``skip_code``, ``range``, ``tables``.
    """
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for table in wave_tables(wave):
        for name, col in load_schema(table, wave).columns.items():
            key = (name, col.owner)
            if key not in seen:
                seen[key] = {
                    "variable": name, "owner": col.owner, "label": col.label,
                    "dtype": col.dtype, "length": col.length, "n_codes": len(col.codes),
                    "missing_codes": ",".join(col.missing_codes), "skip_code": col.skip_code,
                    "range": col.range, "tables": [],
                }
            seen[key]["tables"].append(table)
    frame = pd.DataFrame(list(seen.values()))
    frame["tables"] = frame["tables"].map(lambda t: ",".join(t))
    result: pd.DataFrame = frame.sort_values(["variable", "owner"], ignore_index=True)
    return result


def describe(variable: str, wave: int = 2017) -> dict[str, Any]:
    """Everything the codebook says about ``variable`` (the first meaning if the name is shared).

    Returns a dictionary with the dictionary-row fields plus ``codes``: a list of
    ``{"code", "label", "n", "weighted"}`` with the unweighted and weighted frequency of each
    code in the public file; ``topcode`` (what a top- or bottom-coded value stands for, or
    ``None``), ``national_only`` (2001 columns that exist only for the national sample) and
    ``concepts`` (names of the entries of :mod:`pynhts.concepts` that use the variable).

    Raises:
        KeyError: ``variable`` is not in the wave.
    """
    from pynhts import concepts
    from pynhts.core import flags

    for table in wave_tables(wave):
        col = load_schema(table, wave).columns.get(variable)
        if col is not None and col.owner == table:
            return {
                "topcode": flags.topcode(wave, variable),
                "national_only": flags.national_only(wave, variable, table),
                "concepts": [c["concept"] for c in concepts.find(variable, wave)],
                "variable": variable, "owner": table, "label": col.label, "dtype": col.dtype,
                "length": col.length, "missing_codes": dict(col.missing_codes),
                "skip_code": col.skip_code, "range": col.range,
                "codes": [
                    {"code": c.code, "label": c.label, "n": c.n, "weighted": c.weighted}
                    for c in col.codes
                ],
            }
    raise KeyError(f"{variable!r} is not a variable of NHTS {wave}")
