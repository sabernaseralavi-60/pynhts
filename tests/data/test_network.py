"""Live download from the ORNL server. Manual only: pytest -m network -o addopts=-ra

Downloads the ~81 MB ReplicatesCSV.zip into a temporary cache and extracts only hhwgt.csv.
"""

from __future__ import annotations

import pytest

from pynhts.io import fetch, load_registry, sha256_file

pytestmark = pytest.mark.network


def test_live_download_is_verified_against_pinned_hash(tmp_path):
    out = fetch(2017, ("replicates",), cache=tmp_path, names=("hhwgt.csv",))
    reg = load_registry(2017)
    assert set(out) == {"hhwgt.csv"}
    assert sha256_file(out["hhwgt.csv"]) == reg.members["hhwgt.csv"].sha256
    assert not (tmp_path / "2017" / "raw" / "_downloads").exists()  # archive cleaned up
