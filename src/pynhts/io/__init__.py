"""Data ingestion: verified download, local registration, caching."""

from pynhts.io.fetcher import (
    NHTSIntegrityError,
    cache_dir,
    fetch,
    raw_dir,
    register_local,
    sha256_file,
)
from pynhts.io.registry import Registry, load_registry

__all__ = [
    "NHTSIntegrityError",
    "Registry",
    "cache_dir",
    "fetch",
    "load_registry",
    "raw_dir",
    "register_local",
    "sha256_file",
]
