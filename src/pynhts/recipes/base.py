"""Recipe machinery: published targets, comparison and status classification."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from typing import Any

import pandas as pd
import yaml

STATUSES = ("reproduced", "estimate_only", "not_reproduced")


@dataclass(frozen=True)
class Target:
    """One published figure to reproduce."""

    id: str
    table: str
    label: str
    scale: float
    decimals: int
    published: float
    moe: float | None
    compute: str
    expected: str
    note: str = ""

    @property
    def estimate_tolerance(self) -> float:
        """Half a unit in the last printed digit."""
        return 0.5 * 10.0**-self.decimals + 1e-9


@dataclass(frozen=True)
class RecipeSpec:
    """A packaged set of targets from one publication."""

    source: str
    title: str
    citation: str
    targets: tuple[Target, ...]


def load_spec(name: str) -> RecipeSpec:
    """Load the packaged target file ``recipes/data/<name>.yaml``."""
    ref = resources.files("pynhts") / "recipes" / "data" / f"{name}.yaml"
    if not ref.is_file():
        raise ValueError(f"unknown recipe {name!r}")
    raw: dict[str, Any] = yaml.safe_load(ref.read_text(encoding="utf-8"))
    targets = tuple(
        Target(
            id=t["id"], table=str(t["table"]), label=t["label"], scale=float(t["scale"]),
            decimals=int(t["decimals"]), published=float(t["published"]),
            moe=None if t["moe"] is None else float(t["moe"]),
            compute=t["compute"], expected=t["expected"], note=str(t.get("note", "")).strip(),
        )
        for t in raw["targets"]
    )
    for t in targets:
        if t.expected not in STATUSES:
            raise ValueError(f"{t.id}: invalid expected status {t.expected!r}")
    return RecipeSpec(raw["source"], raw["title"], raw["citation"], targets)


def classify(target: Target, estimate: float, moe: float) -> str:
    """Return ``reproduced``, ``estimate_only`` or ``not_reproduced`` (rule in the YAML header)."""
    if abs(estimate - target.published) > target.estimate_tolerance:
        return "not_reproduced"
    if target.moe is None:
        return "reproduced"
    tol = max(target.estimate_tolerance, 0.001 * target.moe)
    return "reproduced" if abs(moe - target.moe) <= tol else "estimate_only"


def comparison_frame(spec: RecipeSpec, results: dict[str, tuple[float, float]]) -> pd.DataFrame:
    """Build the comparison table from raw (estimate, moe) results in published units."""
    rows = []
    for t in spec.targets:
        est, moe = results[t.id]
        rows.append({
            "id": t.id, "table": t.table, "label": t.label,
            "published": t.published, "published_moe": t.moe,
            "estimate": est, "moe": moe,
            "estimate_diff": est - t.published,
            "moe_rel_diff": (moe - t.moe) / t.moe if t.moe else float("nan"),
            "status": classify(t, est, moe), "expected": t.expected, "note": t.note,
        })
    frame: pd.DataFrame = pd.DataFrame(rows)
    return frame
