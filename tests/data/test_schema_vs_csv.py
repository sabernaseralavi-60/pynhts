"""The codebook schema must describe the real CSV headers exactly. Run with: pytest -m data"""

from __future__ import annotations

from pathlib import Path

import pytest

from pynhts.core.schema import TABLES, load_schema

SRC = Path(__file__).resolve().parents[2] / "local_data" / "raw_csv_2019copy"
pytestmark = pytest.mark.data


@pytest.mark.parametrize("table", TABLES)
def test_header_matches_schema(table):
    s = load_schema(table)
    path = SRC / s.csv
    if not path.is_file():
        pytest.skip("real CSVs not present")
    with open(path, encoding="utf-8") as f:
        header = [h.strip('"') for h in f.readline().strip().split(",")]
    assert set(header) == set(s.columns)
    assert len(header) == len(s.columns)
