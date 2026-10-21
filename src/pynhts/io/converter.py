"""Deterministic, idempotent conversion of the raw NHTS CSV files to typed Parquet.

Design notes:

* Column types come from the codebook schema, never from inference: coded columns stay
  strings so leading zeros survive (``"01"``), numeric columns are float64.
* Original survey codes (-9, -8, -7, -88, -77, -1) are **kept** in the Parquet files; masking
  to NaN is a load-time choice.
* Replicate weights go to their own files. The replicate columns are stored as float32
  (relative error ~6e-8, irrelevant next to sampling variance); the full-sample weight in those
  files stays float64. Readers must cast to float64 before squaring deviations.
* Conversion streams in 64 MiB blocks, so peak memory stays well below the CSV size.
* Output bytes depend only on inputs, converter version and pyarrow version: no timestamps.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from pynhts.core.schema import TableSchema, load_schema
from pynhts.io.fetcher import cache_dir, clean_downloads, fetch, sha256_file
from pynhts.io.registry import ReplicateJob, load_registry

CONVERTER_VERSION = "1"
N_REPLICATES = 98  # 2017; other waves declare their own count in the registry
_BLOCK = 1 << 26
_COMPRESSION = "zstd"

@dataclass(frozen=True)
class Converted:
    """Result of converting one output file."""

    path: Path
    rows: int
    sha256: str
    skipped: bool


def parquet_dir(wave: int = 2017, cache: str | os.PathLike[str] | None = None) -> Path:
    """Directory that holds the Parquet files of ``wave``."""
    return cache_dir(cache) / str(wave) / "parquet"


def replicate_columns(prefix: str, n: int = N_REPLICATES, pad: int = 0) -> list[str]:
    """Names ``<prefix>1`` ... ``<prefix>n`` of the replicate weight columns (2017: n = 98).

    ``pad`` zero-pads the number to that many digits (``FPTPWT01`` for ``pad=2``).
    """
    return [f"{prefix}{i:0{pad}d}" for i in range(1, n + 1)]


def _open_csv(
    path: Path, column_types: dict[str, pa.DataType], null_values: tuple[str, ...] = ("",),
    *, quoted_nulls: bool = False,
) -> pacsv.CSVStreamingReader:
    return pacsv.open_csv(
        path,
        read_options=pacsv.ReadOptions(block_size=_BLOCK),
        convert_options=pacsv.ConvertOptions(
            column_types=column_types,
            null_values=list(null_values),
            strings_can_be_null=False,
            quoted_strings_can_be_null=quoted_nulls,
        ),
    )


def _atomic_writer(final: Path, schema: pa.Schema) -> tuple[pq.ParquetWriter, Path]:
    final.parent.mkdir(parents=True, exist_ok=True)
    tmp = final.with_name(final.name + ".part")
    return pq.ParquetWriter(tmp, schema, compression=_COMPRESSION), tmp


def _read_manifest(directory: Path) -> dict[str, dict[str, Any]]:
    path = directory / "manifest.json"
    if path.is_file():
        data: dict[str, dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
        return data
    return {}


def _write_manifest(directory: Path, manifest: dict[str, dict[str, Any]]) -> None:
    tmp = directory / "manifest.json.part"
    tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, directory / "manifest.json")


def _up_to_date(
    manifest: dict[str, dict[str, Any]], out: Path, inputs: dict[str, str], codebook: str
) -> bool:
    rec = manifest.get(out.name)
    return bool(
        rec
        and out.is_file()
        and rec.get("inputs") == inputs
        and rec.get("converter_version") == CONVERTER_VERSION
        and rec.get("codebook_sha256") == codebook
        and rec.get("size") == out.stat().st_size
    )


def _finish(
    tmp: Path, final: Path, rows: int, expected: int | None, inputs: dict[str, str],
    codebook: str, manifest: dict[str, dict[str, Any]],
) -> Converted:
    if expected is not None and rows != expected:
        tmp.unlink(missing_ok=True)
        raise ValueError(f"{final.name}: wrote {rows} rows, registry expects {expected}")
    os.replace(tmp, final)
    digest = sha256_file(final)
    manifest[final.name] = {
        "inputs": inputs,
        "converter_version": CONVERTER_VERSION,
        "codebook_sha256": codebook,
        "rows": rows,
        "size": final.stat().st_size,
        "sha256": digest,
    }
    return Converted(final, rows, digest, skipped=False)


def _convert_core(
    csv: Path, schema: TableSchema, out: Path, expected: int | None, inputs: dict[str, str],
    codebook: str, manifest: dict[str, dict[str, Any]],
) -> Converted:
    types = {
        n: pa.string() if c.is_string else pa.float64() for n, c in schema.columns.items()
    }
    reader = _open_csv(csv, types)
    if set(reader.schema.names) != set(schema.columns):
        raise ValueError(f"{csv.name}: header does not match the {schema.table} schema")
    writer, tmp = _atomic_writer(out, reader.schema)
    rows = 0
    try:
        with writer:
            for batch in reader:
                writer.write_batch(batch)
                rows += batch.num_rows
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return _finish(tmp, out, rows, expected, inputs, codebook, manifest)


def _convert_replicates(
    csv: Path, jobs: list[ReplicateJob], n_rep: int, directory: Path,
    inputs: dict[str, str], codebook: str, manifest: dict[str, dict[str, Any]],
    todo: set[str],
    expected: int | None,
) -> dict[str, Converted]:
    # key columns are coded strings (leading zeros); the file may call them something else (ID9)
    all_keys = {k for j in jobs for k in j.keys} | {f for j in jobs for f in j.rename}
    header = pacsv.open_csv(csv, read_options=pacsv.ReadOptions(block_size=_BLOCK)).schema.names
    types: dict[str, pa.DataType] = {
        n: pa.string() if n in all_keys else pa.float64() for n in header
    }
    # the 2001 replicate files write a SAS missing value, a quoted ".", where a weight is undefined
    reader = _open_csv(csv, types, null_values=("", "."), quoted_nulls=True)
    writers: dict[str, tuple[pq.ParquetWriter, Path, list[str]]] = {}
    for job in jobs:
        if job.out not in todo:
            continue
        # file column -> table column: only the key names can differ (2001: ID9 -> HOUSEID)
        file_keys = [next((f for f, t in job.rename.items() if t == k), k) for k in job.keys]
        cols = [*file_keys, job.weight, *replicate_columns(job.prefix, n_rep, job.pad)]
        missing = [c for c in cols if c not in header]
        if missing:
            raise ValueError(f"{csv.name}: missing columns {missing[:3]}...")
        names = [*job.keys, *cols[len(job.keys):]]
        fields = [
            pa.field(
                n, pa.string() if n in job.keys else pa.float32() if n != job.weight
                else pa.float64()
            )
            for n in names
        ]
        w, tmp = _atomic_writer(directory / job.out, pa.schema(fields))
        writers[job.out] = (w, tmp, cols)
    rows = 0
    try:
        for batch in reader:
            rows += batch.num_rows
            for w, _, cols in writers.values():
                target = w.schema
                arrays = [
                    batch.column(c).cast(target.field(i).type, safe=False)
                    for i, c in enumerate(cols)
                ]
                w.write_batch(pa.RecordBatch.from_arrays(arrays, schema=target))
    except BaseException:
        for w, tmp, _ in writers.values():
            w.close()
            tmp.unlink(missing_ok=True)
        raise
    out: dict[str, Converted] = {}
    for fname, (w, tmp, _) in writers.items():
        w.close()
        out[fname] = _finish(tmp, directory / fname, rows, expected, inputs, codebook, manifest)
    return out


def convert(
    wave: int = 2017,
    groups: tuple[str, ...] = ("core",),
    *,
    cache: str | os.PathLike[str] | None = None,
    force: bool = False,
    offline: bool = False,
) -> dict[str, Converted]:
    """Fetch (if needed) and convert the raw files of ``groups`` to Parquet.

    Idempotent: an output whose recorded inputs, converter version, codebook hash and size all
    still match is skipped, and then the raw CSV files are not needed (or fetched) at all.
    ``force=True`` rebuilds everything. Conversion of a file is atomic
    (written to ``*.part`` and renamed), so an interrupted run never leaves a half-written file.

    Args:
        wave: Survey year.
        groups: ``"core"`` and/or ``"replicates"``.
        cache: Cache root override.
        force: Rebuild even if up to date.
        offline: Do not download; raise if a raw file is missing.

    Returns:
        Mapping from Parquet file name to a :class:`Converted` record.

    Raises:
        ValueError: a CSV header does not match the schema, or a row count differs from the
            registry.
    """
    reg = load_registry(wave)

    def raw(csv_name: str) -> Path:
        """Verified raw file, fetched only now (so up-to-date outputs need no raw CSVs)."""
        group = reg.members[csv_name].group
        # keep the archive until the whole conversion is done: several members share one zip
        return fetch(wave, (group,), cache=cache, offline=offline, names=(csv_name,),
                     keep_archives=True)[csv_name]

    directory = parquet_dir(wave, cache)
    directory.mkdir(parents=True, exist_ok=True)
    manifest = _read_manifest(directory)
    results: dict[str, Converted] = {}

    try:
        if "core" in groups:
            for table, member in reg.tables.items():
                csv_name = member.name
                schema = load_schema(table, wave)
                out = directory / f"{table}.parquet"
                codebook = schema.codebook_sha256
                inputs = {csv_name: reg.members[csv_name].sha256}
                if not force and _up_to_date(manifest, out, inputs, codebook):
                    rec = manifest[out.name]
                    results[out.name] = Converted(
                        out, int(str(rec["rows"])), str(rec["sha256"]), True
                    )
                    continue
                results[out.name] = _convert_core(
                    raw(csv_name), schema, out, reg.members[csv_name].rows, inputs, codebook,
                    manifest,
                )
                _write_manifest(directory, manifest)

        if "replicates" in groups and "replicates" not in reg.groups:
            raise ValueError(
                f"NHTS {wave} has no replicate weights (standard errors use Taylor series); "
                "request groups=('core',)"
            )
        if "replicates" in groups:
            codebook = load_schema("household", wave).codebook_sha256
            by_csv: dict[str, list[ReplicateJob]] = {}
            for job in reg.replicate_jobs.values():
                by_csv.setdefault(job.csv, []).append(job)
            for csv_name, jobs in by_csv.items():
                inputs = {csv_name: reg.members[csv_name].sha256}
                todo = set()
                for job in jobs:
                    out = directory / job.out
                    if not force and _up_to_date(manifest, out, inputs, codebook):
                        rec = manifest[job.out]
                        results[job.out] = Converted(
                            out, int(str(rec["rows"])), str(rec["sha256"]), True
                        )
                    else:
                        todo.add(job.out)
                if todo:
                    results.update(
                        _convert_replicates(
                            raw(csv_name), jobs, reg.n_replicates, directory, inputs, codebook,
                            manifest, todo, reg.members[csv_name].rows,
                        )
                    )
                    _write_manifest(directory, manifest)
    finally:
        clean_downloads(wave, cache)
    return results
