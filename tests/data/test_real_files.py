"""Checks against the real NHTS 2017 files. Run with: pytest -m data

Uses ``local_data/raw_csv_2019copy`` (git-ignored) and hard-links into ``local_data/cache``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pynhts.io import fetch, load_registry, register_local

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "local_data" / "raw_csv_2019copy"

pytestmark = pytest.mark.data


@pytest.fixture(scope="module")
def cache() -> Path:
    if not (SRC / "trippub.csv").is_file():
        pytest.skip("real NHTS CSVs not present in local_data/raw_csv_2019copy")
    return ROOT / "local_data" / "cache"


def test_register_local_real_core_files(cache):
    adopted = register_local(SRC, cache=cache, groups=("core",), link=True)
    assert set(adopted) == {"hhpub.csv", "perpub.csv", "trippub.csv", "vehpub.csv"}


def test_offline_fetch_after_registration(cache):
    out = fetch(2017, cache=cache, offline=True)
    reg = load_registry(2017)
    for name, path in out.items():
        assert path.stat().st_size == reg.members[name].size


def test_row_counts_match_registry(cache):
    out = fetch(2017, cache=cache, offline=True)
    reg = load_registry(2017)
    for name, path in out.items():
        with open(path, "rb") as f:
            n = sum(1 for _ in f) - 1
        assert n == reg.members[name].rows, name
