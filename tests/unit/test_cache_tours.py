"""Derived-tour cache: identical results, speed-up path, invalidation, force_rebuild."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pynhts.core.data import NHTSData
from pynhts.tours import TourConfig


@pytest.fixture
def d(tmp_path: Path) -> NHTSData:
    pq_dir = tmp_path / "2017" / "parquet"
    pq_dir.mkdir(parents=True)
    why_from = ["01", "03", "01", "01"]
    why_to = ["03", "01", "11", "01"]
    trips = pa.table({
        "HOUSEID": ["H1", "H1", "H2", "H2"], "PERSONID": ["01"] * 4,
        "TDTRPNUM": ["01", "02", "01", "02"], "WHYFROM": why_from, "WHYTO": why_to,
        "TRPTRANS": ["03", "03", "11", "11"], "STRTTIME": ["0800", "1700", "0900", "1000"],
        "ENDTIME": ["0830", "1730", "0930", "1030"],
        "WTTRDFIN": [1.0, 1.0, 2.0, 2.0],
    })
    pq.write_table(trips, pq_dir / "trip.parquet")
    for name, key in (("household", "HOUSEID"), ("person", "HOUSEID"), ("vehicle", "HOUSEID")):
        pq.write_table(pa.table({key: ["H1"]}), pq_dir / f"{name}.parquet")
    return NHTSData(2017, pq_dir)


def test_second_call_reads_the_cache_and_matches(d):
    first = d.tours()
    files = sorted(p.name for p in (d.directory.parent / "derived").iterdir())
    assert len(files) == 2 and files[0].startswith("tour_trips_") and files[1].startswith("tours_")
    second = d.tours()
    pd.testing.assert_frame_equal(first.tours, second.tours)
    pd.testing.assert_frame_equal(first.trips, second.trips)
    assert second.config == TourConfig()


def test_cache_is_used_not_recomputed(d, monkeypatch):
    d.tours()
    import pynhts.tours as tours_mod

    def boom(*a, **k):
        raise AssertionError("tours were recomputed")

    monkeypatch.setattr(tours_mod, "build_tours", boom)
    assert len(d.tours().tours) == 2


def test_force_rebuild_recomputes(d, monkeypatch):
    d.tours()
    import pynhts.tours as tours_mod

    calls = []
    real = tours_mod.build_tours
    monkeypatch.setattr(tours_mod, "build_tours", lambda *a, **k: calls.append(1) or real(*a, **k))
    d.tours(force_rebuild=True)
    assert calls == [1]


def test_different_config_or_columns_use_different_files(d):
    d.tours()
    d.tours(TourConfig.mcnally_rafiq())
    d.tours(columns=["TRPTRANS", "ENDTIME"])  # already in the default set: same file
    d.tours(columns=["WTTRDFIN"])
    d.tours(columns=["WTTRDFIN", "TRPTRANS"])  # same set, same file
    assert len(list((d.directory.parent / "derived").glob("tours_*.parquet"))) == 3


def test_changed_source_invalidates(d):
    d.tours()
    path = d.directory / "trip.parquet"
    t = pq.read_table(path)
    pq.write_table(t.slice(0, 2), path)  # shrink the source file
    assert len(d.tours().tours) == 1


def test_corrupt_cache_is_rebuilt(d):
    d.tours()
    for p in (d.directory.parent / "derived").glob("tours_*.parquet"):
        p.write_bytes(b"not parquet")
    assert len(d.tours().tours) == 2
