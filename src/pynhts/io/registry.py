"""Load the bundled, hash-pinned file registry for an NHTS wave."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from typing import Any

import yaml


@dataclass(frozen=True)
class Archive:
    """A downloadable zip archive."""

    name: str
    url: str
    sha256: str
    size: int


@dataclass(frozen=True)
class Member:
    """A data file stored inside an archive."""

    name: str
    archive: str
    group: str
    sha256: str
    size: int
    rows: int | None
    table: str = ""


@dataclass(frozen=True)
class Registry:
    """Hash-pinned description of all files of one survey wave."""

    wave: int
    citation: str
    archives: dict[str, Archive]
    members: dict[str, Member]
    documentation: dict[str, dict[str, Any]]
    variance: dict[str, Any] = field(default_factory=dict)

    def members_in(self, groups: tuple[str, ...]) -> list[Member]:
        """Return the members that belong to any of ``groups``."""
        return [m for m in self.members.values() if m.group in groups]

    @property
    def tables(self) -> dict[str, Member]:
        """Core CSV member of each table (``household``, ``person``, ...) of this wave."""
        return {m.table: m for m in self.members.values() if m.group == "core" and m.table}

    @property
    def variance_method(self) -> str:
        """``"jkn"`` (replicate weights) or ``"taylor"`` (strata + clusters)."""
        return str(self.variance.get("method", "jkn"))

    @property
    def groups(self) -> tuple[str, ...]:
        """Member groups this wave offers (``core``, and ``replicates`` when it has them)."""
        return tuple(dict.fromkeys(m.group for m in self.members.values()))


@cache
def load_registry(wave: int) -> Registry:
    """Read ``_registry/<wave>.yaml``.

    Raises:
        ValueError: if the wave is not supported yet.
    """
    ref = resources.files("pynhts") / "_registry" / f"{wave}.yaml"
    if not ref.is_file():
        raise ValueError(f"NHTS wave {wave} is not supported; available: {supported_waves()}")
    raw = yaml.safe_load(ref.read_text(encoding="utf-8"))
    archives = {k: Archive(name=k, **v) for k, v in raw["archives"].items()}
    members = {
        k: Member(name=k, rows=v.pop("rows", None), **v) for k, v in raw["members"].items()
    }
    return Registry(
        wave=int(raw["wave"]),
        citation=str(raw["citation"]).strip(),
        archives=archives,
        members=members,
        documentation=raw.get("documentation", {}),
        variance=dict(raw.get("variance", {})),
    )


def supported_waves() -> list[int]:
    """Survey years that have a bundled registry (and schema)."""
    root = resources.files("pynhts") / "_registry"
    return sorted(int(p.name.removesuffix(".yaml")) for p in root.iterdir()
                  if p.name.endswith(".yaml"))
