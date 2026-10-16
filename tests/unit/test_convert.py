"""Unit tests for pynhts.io.convert with tiny synthetic CSVs."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pynhts.core.schema import Column, TableSchema
from pynhts.io import converter as cv
from pynhts.io.registry import Archive, Member, Registry

HH_CSV = '"HOUSEID","TRAVDAY","HHSIZE"\n"30000007","01",2\n"30000008","-9",-9\n"30000009","07",-8\n'


def _col(name: str, dtype: str) -> Column:
    return Column(name, name, dtype, None, "household", {}, None, None)


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _rep_csv(prefix: str, keys: list[str], rows: int) -> str:
    cols = [*keys, prefix, *[f"{prefix}{i}" for i in range(1, 99)]]
    lines = [",".join(f'"{c}"' for c in cols)]
    for r in range(rows):
        key_vals = [f'"{30000000 + r}"'] + ['"01"'] * (len(keys) - 1)
        lines.append(",".join(key_vals + [f"{100.5 + r + i / 7:.10f}" for i in range(99)]))
    return "\n".join(lines) + "\n"


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "hhpub.csv").write_text(HH_CSV)
    (raw / "hhwgt.csv").write_text(_rep_csv("WTHHFIN", ["HOUSEID"], 3))
    perwgt = _rep_csv("WTPERFIN", ["HOUSEID", "PERSONID"], 2).splitlines()
    trd = _rep_csv("WTTRDFIN", ["HOUSEID", "PERSONID"], 2).splitlines()
    # perwgt.csv has WTPERFIN block and WTTRDFIN block side by side; keys only once
    merged = [perwgt[0] + "," + ",".join(trd[0].split(",")[2:])]
    for a, b in zip(perwgt[1:], trd[1:], strict=True):
        merged.append(a + "," + ",".join(b.split(",")[2:]))
    (raw / "perwgt.csv").write_text("\n".join(merged) + "\n")

    def member(name: str, group: str, rows: int | None) -> Member:
        b = (raw / name).read_bytes()
        return Member(name, "x.zip", group, _sha(b), len(b), rows)

    reg = Registry(
        2017, "fake",
        {"x.zip": Archive("x.zip", "u", "0" * 64, 1)},
        {
            "hhpub.csv": member("hhpub.csv", "core", 3),
            "hhwgt.csv": member("hhwgt.csv", "replicates", 3),
            "perwgt.csv": member("perwgt.csv", "replicates", 2),
        },
        {},
    )
    schema = TableSchema(
        2017, "household", "hhpub.csv",
        {"HOUSEID": _col("HOUSEID", "string"), "TRAVDAY": _col("TRAVDAY", "string"),
         "HHSIZE": _col("HHSIZE", "float64")},
        codebook_sha256="cb1",
    )
    monkeypatch.setattr(cv, "load_registry", lambda wave: reg)
    monkeypatch.setattr(cv, "load_schema", lambda table, wave=2017: schema)
    monkeypatch.setattr(cv, "CORE_TABLES", {"hhpub.csv": "household"})
    fetch_calls: list[tuple] = []

    def fake_fetch(wave, groups, cache=None, offline=False):
        fetch_calls.append(groups)
        return {m.name: raw / m.name for m in reg.members_in(groups)}

    monkeypatch.setattr(cv, "fetch", fake_fetch)
    return {"cache": tmp_path / "cache", "reg": reg, "raw": raw, "schema": schema,
            "monkeypatch": monkeypatch, "fetch_calls": fetch_calls}


def test_core_keeps_leading_zeros_codes_and_types(env):
    res = cv.convert(2017, ("core",), cache=env["cache"])
    t = pq.read_table(res["household.parquet"].path)
    assert t.schema.field("TRAVDAY").type == pa.string()
    assert t.schema.field("HHSIZE").type == pa.float64()
    assert t.column("TRAVDAY").to_pylist() == ["01", "-9", "07"]  # zeros and codes kept
    assert t.column("HHSIZE").to_pylist() == [2.0, -9.0, -8.0]  # codes not masked at rest
    assert t.column("HOUSEID").to_pylist()[0] == "30000007"


def test_idempotent_and_deterministic(env):
    first = cv.convert(2017, ("core",), cache=env["cache"])["household.parquet"]
    second = cv.convert(2017, ("core",), cache=env["cache"])["household.parquet"]
    assert not first.skipped and second.skipped and first.sha256 == second.sha256
    forced = cv.convert(2017, ("core",), cache=env["cache"], force=True)["household.parquet"]
    assert not forced.skipped and forced.sha256 == first.sha256  # byte-identical rebuild


def test_rebuilds_when_input_hash_or_codebook_changes(env):
    cv.convert(2017, ("core",), cache=env["cache"])
    env["monkeypatch"].setattr(
        cv, "load_schema", lambda table, wave=2017: TableSchema(
            2017, "household", "hhpub.csv", env["schema"].columns, codebook_sha256="cb2")
    )
    again = cv.convert(2017, ("core",), cache=env["cache"])["household.parquet"]
    assert not again.skipped


def test_row_count_mismatch_raises_and_leaves_no_partial_file(env):
    reg = env["reg"]
    bad = Member("hhpub.csv", "x.zip", "core", reg.members["hhpub.csv"].sha256,
                 reg.members["hhpub.csv"].size, 99)
    env["monkeypatch"].setattr(
        cv, "load_registry", lambda wave: Registry(2017, "f", reg.archives,
                                                   {**reg.members, "hhpub.csv": bad}, {}))
    with pytest.raises(ValueError, match="expects 99"):
        cv.convert(2017, ("core",), cache=env["cache"])
    assert not list(cv.parquet_dir(2017, env["cache"]).glob("*.part"))
    assert not (cv.parquet_dir(2017, env["cache"]) / "household.parquet").exists()


def test_header_mismatch_raises(env):
    env["monkeypatch"].setattr(
        cv, "load_schema", lambda table, wave=2017: TableSchema(
            2017, "household", "hhpub.csv", {"HOUSEID": _col("HOUSEID", "string")})
    )
    with pytest.raises(ValueError, match="does not match"):
        cv.convert(2017, ("core",), cache=env["cache"])


def test_replicates_split_into_three_files_with_float32(env):
    res = cv.convert(2017, ("replicates",), cache=env["cache"])
    assert set(res) == {"repw_household.parquet", "repw_person.parquet", "repw_trip.parquet"}
    hh = pq.read_table(res["repw_household.parquet"].path)
    assert hh.num_rows == 3 and hh.num_columns == 1 + 1 + 98
    assert hh.schema.field("WTHHFIN").type == pa.float64()
    assert hh.schema.field("WTHHFIN1").type == pa.float32()
    assert hh.schema.field("WTHHFIN98").type == pa.float32()
    assert hh.schema.field("HOUSEID").type == pa.string()
    trip = pq.read_table(res["repw_trip.parquet"].path)
    assert trip.column_names[:3] == ["HOUSEID", "PERSONID", "WTTRDFIN"]
    assert trip.column("PERSONID").to_pylist() == ["01", "01"]
    per = pq.read_table(res["repw_person.parquet"].path)
    assert "WTTRDFIN" not in per.column_names and "WTPERFIN98" in per.column_names


def test_replicates_float32_error_is_negligible(env):
    res = cv.convert(2017, ("replicates",), cache=env["cache"])
    hh = pq.read_table(res["repw_household.parquet"].path).to_pandas()
    src = [float(x) for x in (env["raw"] / "hhwgt.csv").read_text().splitlines()[1].split(",")[2:]]
    got = hh.iloc[0][[f"WTHHFIN{i}" for i in range(1, 99)]].astype("float64").to_numpy()
    assert max(abs(g - s) / s for g, s in zip(got, src, strict=True)) < 1e-6


def test_replicates_idempotent(env):
    cv.convert(2017, ("replicates",), cache=env["cache"])
    again = cv.convert(2017, ("replicates",), cache=env["cache"])
    assert all(c.skipped for c in again.values())
