"""Command line interface: ``pynhts fetch | register | info | validate``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pynhts import __version__


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pynhts", description="NHTS microdata toolkit")
    p.add_argument("--version", action="version", version=f"pynhts {__version__}")
    p.add_argument("--cache", help="cache directory (default: $PYNHTS_CACHE_DIR or user cache)")
    sub = p.add_subparsers(dest="command", required=True)

    f = sub.add_parser("fetch", help="download, verify and convert the NHTS data to Parquet")
    f.add_argument("--wave", type=int, default=2017)
    f.add_argument("--replicates", action="store_true", help="also fetch the 98 replicate weights")
    f.add_argument("--offline", action="store_true", help="never use the network")

    r = sub.add_parser("register", help="adopt NHTS CSV files you already have (hash-checked)")
    r.add_argument("path", type=Path, help="folder holding hhpub.csv, perpub.csv, ...")
    r.add_argument("--wave", type=int, default=2017)
    r.add_argument("--link", action="store_true", help="hard-link instead of copying")

    i = sub.add_parser("info", help="show the cache location and what it contains")
    i.add_argument("--wave", type=int, default=2017)

    v = sub.add_parser("validate", help="reproduce a published table and compare")
    v.add_argument("recipe", nargs="?", default="stt2017")
    v.add_argument("--markdown", action="store_true", help="print the table as Markdown")
    return p


def _info(wave: int, cache: str | None) -> int:
    from pynhts.io import load_registry, parquet_dir, raw_dir

    reg = load_registry(wave)
    raw, pq = raw_dir(wave, cache), parquet_dir(wave, cache)
    print(f"NHTS {wave}\n  raw CSV : {raw}\n  Parquet : {pq}")
    for m in reg.members.values():
        state = "present" if (raw / m.name).is_file() else "absent"
        print(f"  {m.name:<12} {state:<8} {m.size / 1e6:>8.1f} MB")
    for stem in ("household", "person", "trip", "vehicle", "repw_household", "repw_person",
                 "repw_trip"):
        f = pq / f"{stem}.parquet"
        print(f"  {f.name:<24} {'built' if f.is_file() else 'not built'}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point; returns the process exit code."""
    args = _build_parser().parse_args(argv)
    cache: str | None = args.cache
    if args.command == "info":
        return _info(args.wave, cache)
    if args.command == "register":
        from pynhts.io import register_local

        adopted = register_local(args.path, args.wave, cache=cache, link=args.link)
        for name, path in adopted.items():
            print(f"registered {name} -> {path}")
        return 0
    if args.command == "fetch":
        from pynhts.io import convert

        groups = ("core", "replicates") if args.replicates else ("core",)
        for name, res in convert(args.wave, groups, cache=cache, offline=args.offline).items():
            print(f"{name:<24} {res.rows:>9,} rows  {'up to date' if res.skipped else 'built'}")
        return 0
    if args.command == "validate":
        import pynhts
        from pynhts import recipes

        wave = recipes.load_spec(args.recipe).wave
        data = pynhts.load(wave, cache=cache, replicates=True)
        table = recipes.run(args.recipe, data)
        if args.markdown:
            print(recipes.to_markdown(table))
        else:
            cols = ["id", "published", "estimate", "published_moe", "moe", "status"]
            print(table[cols].to_string(index=False, float_format=lambda x: f"{x:,.4f}"))
        wrong = table[table["status"] != table["expected"]]
        counts = table["status"].value_counts().to_dict()
        print(f"\n{counts}; unexpected results: {len(wrong)}")
        return 1 if len(wrong) else 0
    return 2  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
