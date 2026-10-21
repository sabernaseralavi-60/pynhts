"""Concept dictionary: what a variable means in each wave and whether waves can be compared.

>>> from pynhts import concepts
>>> concepts.table()[["concept", "comparability", "harmonize"]]          # doctest: +SKIP
>>> concepts.get("age")["pitfalls"]                                       # doctest: +SKIP
>>> concepts.find("VEHAGE", 2009)                                         # doctest: +SKIP

Each entry names the variable of every wave, who is asked, the unit, a comparability grade
(``C`` comparable, ``H`` comparable after the named harmonization, ``N`` do not compare) and the
pitfalls that were seen in the data. The same facts are available as JSON (:func:`to_json`) for
agents and other tools.
"""

from __future__ import annotations

import copy
import json
from functools import cache
from importlib import resources
from typing import Any

import pandas as pd
import yaml

from pynhts.core.flags import national_only, topcode

WAVES = (2001, 2009, 2017, 2022)
GRADES = {"C": "comparable as is", "H": "comparable after harmonization", "N": "do not compare"}


@cache
def _load() -> dict[str, dict[str, Any]]:
    ref = resources.files("pynhts") / "concepts.yaml"
    raw: dict[str, Any] = yaml.safe_load(ref.read_text(encoding="utf-8"))
    concepts: dict[str, dict[str, Any]] = raw["concepts"]
    return concepts


def names() -> list[str]:
    """Names of all concepts."""
    return list(_load())


def get(name: str) -> dict[str, Any]:
    """The full entry of a concept (a copy).

    Raises:
        KeyError: unknown concept.
    """
    data = _load()
    if name not in data:
        raise KeyError(f"unknown concept {name!r}; available: {names()}")
    return copy.deepcopy({"concept": name, **data[name]})


def table() -> pd.DataFrame:
    """One row per concept: variable of each wave, grade, harmonization, number of pitfalls."""
    rows = []
    for name, c in _load().items():
        row: dict[str, Any] = {"concept": name, "title": c["title"], "table": c["table"]}
        for w in WAVES:
            row[str(w)] = c["variables"].get(w)
        row.update(comparability=c["comparability"], harmonize=c["harmonize"],
                   n_pitfalls=len(c["pitfalls"]))
        rows.append(row)
    frame: pd.DataFrame = pd.DataFrame(rows)
    return frame


def find(variable: str, wave: int) -> list[dict[str, Any]]:
    """Concepts whose variable (or imputed version) in ``wave`` is ``variable``.

    The result also carries ``topcode`` and ``national_only`` flags of the column, so one call
    tells a human or an agent what to watch for before using the column.
    """
    out = []
    for name, c in _load().items():
        used = {c["variables"].get(wave), (c.get("imputed") or {}).get(wave)}
        if variable in used:
            entry = get(name)
            entry["topcode"] = topcode(wave, variable)
            entry["national_only"] = national_only(wave, variable)
            out.append(entry)
    return out


def to_json(indent: int | None = 2) -> str:
    """The whole dictionary as JSON (for tools and AI agents)."""
    payload = {"waves": list(WAVES), "grades": GRADES,
               "concepts": [get(n) for n in names()]}
    return json.dumps(payload, indent=indent, ensure_ascii=False)
