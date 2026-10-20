"""Derived-data cache: expensive results are computed once and stored as Parquet.

Files live in ``<cache root>/<wave>/derived/``. The file name carries a hash of everything the
result depends on (the parameters *and* the size/mtime of the source Parquet files), so changing
a parameter, or re-converting the raw data, never returns a stale result.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa

CACHE_VERSION = 1


def arrow_to_pandas(table: pa.Table) -> pd.DataFrame:
    """Arrow table to DataFrame with Arrow-backed strings.

    Python-object strings needed ~3x the memory on the 0.9M-row trip table. Every read of the NHTS
    tables goes through here (derived frames use :func:`arrow_strings`).
    """
    # pandas metadata (written by DataFrame.to_parquet) would restore the stored Python-string dtype
    plain = table.replace_schema_metadata(None)
    arrow_str = pd.StringDtype("pyarrow")
    mapper = {pa.string(): arrow_str, pa.large_string(): arrow_str}.get
    df: pd.DataFrame = plain.to_pandas(types_mapper=mapper)
    return df


def arrow_strings(df: pd.DataFrame) -> pd.DataFrame:
    """Give every ``string`` column Arrow storage (``object`` columns are left as they are).

    pandas restores ``string`` columns read from Parquet with Python storage; applying this to the
    fresh and the cached result alike keeps the two identical.
    """
    arrow_str = pd.StringDtype("pyarrow")
    cols = [c for c in df.columns if isinstance(df[c].dtype, pd.StringDtype)]
    return df.astype(dict.fromkeys(cols, arrow_str)) if cols else df


def _plain(value: Any) -> Any:
    """Turn parameters into JSON-stable data (sets become sorted lists)."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {k: _plain(v) for k, v in dataclasses.asdict(value).items()}
    if isinstance(value, (set, frozenset)):
        return sorted(_plain(v) for v in value)
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in sorted(value.items())}
    return value


def fingerprint(params: Any, sources: Iterable[Path] = ()) -> str:
    """Short hash of ``params`` and of the identity (name, size, mtime) of ``sources``."""
    stamp = [
        (p.name, p.stat().st_size, p.stat().st_mtime_ns) for p in sorted(sources) if p.exists()
    ]
    blob = json.dumps(
        {"v": CACHE_VERSION, "params": _plain(params), "sources": stamp}, sort_keys=True
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def derived_dir(parquet_directory: Path) -> Path:
    """``<wave>/derived`` next to the wave's ``parquet`` directory."""
    return parquet_directory.parent / "derived"


def cached_frames(
    directory: Path,
    names: Sequence[str],
    key: str,
    build: Callable[[], dict[str, pd.DataFrame]],
    *,
    force_rebuild: bool = False,
) -> dict[str, pd.DataFrame]:
    """Return the DataFrames ``names`` from ``<name>_<key>.parquet``; build and store if absent.

    A missing or unreadable cache falls back to ``build``. Files are written to a temporary
    name and renamed, so an interrupted run never leaves a half-written cache, and a
    read-only cache directory only costs the speed-up.
    """
    paths = {n: directory / f"{n}_{key}.parquet" for n in names}
    if not force_rebuild and all(p.exists() for p in paths.values()):
        try:
            return {n: arrow_strings(pd.read_parquet(p)) for n, p in paths.items()}
        except (OSError, ValueError):
            pass
    frames = {n: arrow_strings(f) for n, f in build().items()}
    try:
        directory.mkdir(parents=True, exist_ok=True)
        for name, target in paths.items():
            tmp = target.with_suffix(f".{os.getpid()}.tmp")
            frames[name].to_parquet(tmp, index=False)
            tmp.replace(target)
    except OSError:
        pass
    return frames
