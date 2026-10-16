"""Reproducibility recipes: replicate published NHTS tables and report every gap.

>>> import pynhts
>>> from pynhts import recipes
>>> table = recipes.run("stt2017", pynhts.load(2017))        # doctest: +SKIP
>>> print(recipes.to_markdown(table))                        # doctest: +SKIP
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from pynhts.recipes.base import RecipeSpec, Target, classify, comparison_frame, load_spec
from pynhts.recipes.stt2017 import COMPUTE, Context

if TYPE_CHECKING:
    from pynhts.core.data import NHTSData

RECIPES = {"stt2017": COMPUTE}


def available() -> list[str]:
    """Names of the packaged recipes."""
    return sorted(RECIPES)


def run(name: str, data: NHTSData) -> pd.DataFrame:
    """Reproduce every target of recipe ``name`` and compare with the published figures.

    Returns:
        One row per target with the published and estimated value, the published and
        estimated margin of error, the relative MOE difference, the resulting ``status`` and the
        ``expected`` status recorded with the target.
    """
    if name not in RECIPES:
        raise ValueError(f"unknown recipe {name!r}; available: {available()}")
    spec = load_spec(name)
    ctx = Context(data)
    results: dict[str, tuple[float, float]] = {}
    for t in spec.targets:
        est, moe = RECIPES[name][t.compute](ctx)
        results[t.id] = (est / t.scale, moe / t.scale)
    return comparison_frame(spec, results)


def to_markdown(table: pd.DataFrame) -> str:
    """Render a comparison table as GitHub-flavoured Markdown."""
    head = "| Table | Quantity | Published | MOE pub. | Estimate | MOE | MOE diff | Status |\n"
    head += "|---|---|---:|---:|---:|---:|---:|---|\n"
    lines = []
    for r in table.to_dict("records"):
        pub, est, moe = float(r["published"]), float(r["estimate"]), float(r["moe"])
        dec = 0 if abs(pub) >= 1000 else 2
        pm = "" if pd.isna(r["published_moe"]) else f"{float(r['published_moe']):,.{dec}f}"
        rel = "" if pd.isna(r["moe_rel_diff"]) else f"{float(r['moe_rel_diff']):+.1%}"
        lines.append(
            f"| {r['table']} | {r['label']} | {pub:,.{dec}f} | {pm} | {est:,.{dec}f} "
            f"| {moe:,.{dec}f} | {rel} | {r['status']} |"
        )
    return head + "\n".join(lines) + "\n"


__all__ = [
    "RECIPES", "Context", "RecipeSpec", "Target", "available", "classify",
    "comparison_frame", "load_spec", "run", "to_markdown",
]
