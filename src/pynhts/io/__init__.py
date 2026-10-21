"""Data ingestion: verified download, local registration, caching."""

from pynhts.io.converter import Converted, convert, parquet_dir, replicate_columns
from pynhts.io.fetcher import (
    NHTSIntegrityError,
    cache_dir,
    clean_downloads,
    fetch,
    raw_dir,
    register_local,
    sha256_file,
)
from pynhts.io.registry import Registry, load_registry

__all__ = [
    "Converted",
    "NHTSIntegrityError",
    "Registry",
    "cache_dir",
    "clean_downloads",
    "convert",
    "fetch",
    "load_registry",
    "parquet_dir",
    "raw_dir",
    "register_local",
    "replicate_columns",
    "sha256_file",
]
