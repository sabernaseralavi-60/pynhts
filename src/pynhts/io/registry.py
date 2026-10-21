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
    zip_path: str = ""

    @property
    def path_in_archive(self) -> str:
        """Name of the member inside its zip archive (2009 keeps its CSVs in ``Ascii/``)."""
        return self.zip_path or self.name


@dataclass(frozen=True)
class ReplicateJob:
    """One set of replicate weights read from a replicate CSV file.

    ``weight`` is the full-sample weight column of the replicate file and ``prefix`` the stem of
    the replicate columns (``prefix1`` ... ``prefixR``, zero-padded to ``pad`` digits when the file
    does so: the 2001 long-distance file has ``FPTPWT01``). ``fill_from`` gives units without a
    weight ``factor`` times the weights of another level (2009: persons without trips have no
    travel-day weight; it is exactly 365 times their person weight). ``rename`` maps key
    columns of the replicate file to the key names of the data tables (2001 calls the household
    id ``ID9``).
    """

    level: str
    csv: str
    weight: str
    prefix: str
    keys: tuple[str, ...]
    out: str
    rename: dict[str, str] = field(default_factory=dict)
    pad: int = 0
    fill_from: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Registry:
    """Hash-pinned description of all files of one survey wave."""

    wave: int
    citation: str
    archives: dict[str, Archive]
    members: dict[str, Member]
    documentation: dict[str, dict[str, Any]]
    variance: dict[str, Any] = field(default_factory=dict)

    @property
    def design_description(self) -> str:
        """One sentence on how standard errors are obtained in this wave (for table footnotes)."""
        return str(self.variance.get("description", "")).strip()

    @property
    def n_replicates(self) -> int:
        """Number of replicate weights (98 in 2017, 100 in 2009, 99 in 2001)."""
        return int(self.variance.get("replicates", 98))

    @property
    def jackknife_factor(self) -> float:
        """Multiplier of the summed squared deviations: 6/7 (2017), 99/100 (2009), 98/99 (2001)."""
        return float(self.variance.get("factor", 6 / 7))

    def convention(self, name: str) -> tuple[float, float]:
        """Variance multiplier and t degrees of freedom: ``"fhwa"`` or ``"design"``.

        ``fhwa`` is what the User's Guide and the published tables use (99/100 and 100 df in
        2009, 98/99 and 99 df in 2001, 6/7 and 98 df in 2017); ``design`` the textbook convention
        of the replicate method (2009 JK2: multiplier 1 and 99 df; 2001 JK1: 98 df; 2017: 84 df,
        replicates minus strata).
        """
        if name == "fhwa":
            return self.jackknife_factor, self.degrees_of_freedom
        if name == "design":
            d = self.variance.get("design")
            if not d:
                raise ValueError(f"NHTS {self.wave} has no 'design' convention (Taylor series)")
            return float(d["factor"]), float(d["df"])
        raise ValueError("convention must be 'fhwa' or 'design'")

    @property
    def degrees_of_freedom(self) -> float:
        """Degrees of freedom of the t multiplier for margins of error."""
        return float(self.variance.get("df", self.n_replicates))

    @property
    def replicate_jobs(self) -> dict[str, ReplicateJob]:
        """Replicate-weight sets of this wave by level (household, person, trip, longdist)."""
        jobs: dict[str, ReplicateJob] = {}
        for csv, entries in dict(self.variance.get("replicate_files", {})).items():
            for e in entries:
                jobs[e["level"]] = ReplicateJob(
                    level=e["level"], csv=csv, weight=e["weight"],
                    prefix=e.get("prefix", e["weight"]), keys=tuple(e["keys"]),
                    out=e["out"], rename=dict(e.get("rename", {})), pad=int(e.get("pad", 0)),
                    fill_from=dict(e.get("fill_from", {})),
                )
        return jobs

    def weight_for(self, table: str, default: str) -> str:
        """Full-sample weight column of ``table`` (``default`` unless the wave overrides it)."""
        override: dict[str, str] = self.variance.get("default_weights", {})
        return override.get(table, default)

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
