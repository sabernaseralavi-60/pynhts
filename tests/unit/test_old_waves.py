"""NHTS 2001 and 2009 without microdata: registry, schema, keys, replicate conversion, parsers."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pynhts import harmonize
from pynhts.core.schema import load_schema, table_key, wave_tables
from pynhts.io import converter as cv
from pynhts.io.registry import Archive, Member, Registry, load_registry
from pynhts.stats import jackknife_variance


def test_registry_of_2009_and_2001_describes_their_replicate_designs():
    r09, r01 = load_registry(2009), load_registry(2001)
    assert (r09.n_replicates, r09.jackknife_factor, r09.degrees_of_freedom) == (100, 0.99, 100)
    assert r01.n_replicates == 99
    assert r01.jackknife_factor == pytest.approx(98 / 99)
    assert r01.degrees_of_freedom == 99
    assert set(r09.replicate_jobs) == {"household", "person", "trip"}
    assert set(r01.replicate_jobs) == {"household", "person", "trip", "longdist"}
    # 2001 names the household id ID9 and the replicate stems differ from the full weights
    job = r01.replicate_jobs["household"]
    assert job.rename == {"ID9": "HOUSEID"} and (job.weight, job.prefix) == ("WTHHFIN", "WTHFIN")
    assert r09.replicate_jobs["trip"].weight == "DAYWGT"
    # the 2009 CSV files sit in the archive folder Ascii/
    assert r09.members["HHV2PUB.CSV"].path_in_archive == "Ascii/HHV2PUB.CSV"
    assert r01.members["HHPUB.csv"].path_in_archive == "HHPUB.csv"
    assert r01.weight_for("longdist", "WTPERFIN") == "WTPTPFIN"
    assert r09.weight_for("trip", "WTTRDFIN") == "WTTRDFIN"
    # 2017 keeps its 98 replicates and 6/7
    r17 = load_registry(2017)
    assert (r17.n_replicates, r17.jackknife_factor) == (98, pytest.approx(6 / 7))


def test_tables_and_keys_of_the_old_waves():
    assert wave_tables(2009) == ("household", "person", "trip", "vehicle")
    assert wave_tables(2001) == ("household", "person", "trip", "vehicle", "longdist")
    assert table_key("trip", 2009) == ("HOUSEID", "PERSONID", "TDTRPNUM")
    # 2001 long-distance file: one row per long trip, not per person as in 2022
    assert table_key("longdist", 2001) == ("HOUSEID", "PERSONID", "TPTRPNUM")
    assert table_key("longdist", 2022) == ("HOUSEID", "PERSONID")


def test_schema_of_the_old_waves_keeps_wave_specific_traps():
    # 2009 top-codes age 89+ as 92; 2001 pads yes/no as "1"/"2", 2009 as "01"/"02"
    age = load_schema("person", 2009).columns["R_AGE"]
    assert {c.code: c.label for c in age.codes}["92"] == "89+"
    yes01 = {c.code: c.label for c in load_schema("person", 2001).columns["DRIVER"].codes}
    yes09 = {c.code: c.label for c in load_schema("person", 2009).columns["DRIVER"].codes}
    assert yes01["1"].startswith("Yes") and yes09["01"].startswith("Yes")
    # evidence-based repairs of the printed 2009 codebook (see tools/build_schema_pdf.py)
    ptused = load_schema("person", 2009).columns["PTUSED"]
    assert ptused.missing_codes["99"] == "not_ascertained"
    make = {c.code for c in load_schema("vehicle", 2009).columns["MAKECODE"].codes}
    assert "35" in make and not any("\x16" in c for c in make)


def test_whytrp1s_and_trptrans_are_not_poolable_across_old_waves():
    c = harmonize.compare_waves(2001, 2009).set_index("variable")
    assert c.loc["TRPTRANS", "status"] == "codes_changed"
    assert c.loc["WHYTRP1S", "status"] == "codes_changed"
    # DRIVER differs only by zero padding of the codes ("1" against "01")
    assert c.loc["DRIVER", "status"] == "relabelled" and bool(c.loc["DRIVER", "padding_differs"])


def test_jackknife_variance_for_100_and_99_replicates():
    reps = np.arange(1.0, 101.0)
    v = jackknife_variance(50.0, reps, 0.99, n_replicates=100)
    assert v == pytest.approx(0.99 * np.sum((reps - 50.0) ** 2))
    with pytest.raises(ValueError, match="expected 99"):
        jackknife_variance(1.0, np.ones(100), 98 / 99, n_replicates=99)


# -- replicate conversion with renamed keys, a stem different from the weight, 99 replicates ------
def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def test_replicates_with_renamed_key_and_other_prefix(tmp_path: Path, monkeypatch):
    header = ["ID9", "EXPFLLHH", *[f"EXPFHH{i}" for i in range(1, 100)], "WTHHFIN",
              *[f"WTHFIN{i}" for i in range(1, 100)]]
    rows = []
    for r in range(3):
        rows.append([f"01000{r:04d}", "5.0", *[f"{1 + i / 10:.3f}" for i in range(99)],
                     f"{100 + r}.5", *[f"{100 + r + i / 7:.6f}" for i in range(99)]])
    raw = tmp_path / "hh50wt.csv"
    raw.write_text("\n".join([",".join(f'"{h}"' for h in header),
                              *[",".join(r) for r in rows]]) + "\n")
    data = raw.read_bytes()
    reg = Registry(
        2001, "fake", {"x.zip": Archive("x.zip", "u", "0" * 64, 1)},
        {"hh50wt.csv": Member("hh50wt.csv", "x.zip", "replicates", _sha(data), len(data), 3)},
        {},
        {"method": "jkn", "replicates": 99, "factor": 98 / 99,
         "replicate_files": {"hh50wt.csv": [
             {"level": "household", "weight": "WTHHFIN", "prefix": "WTHFIN",
              "keys": ["HOUSEID"], "out": "repw_household.parquet",
              "rename": {"ID9": "HOUSEID"}}]}},
    )
    schema = load_schema("household", 2001)
    monkeypatch.setattr(cv, "load_registry", lambda wave: reg)
    monkeypatch.setattr(cv, "load_schema", lambda table, wave=2017: schema)
    monkeypatch.setattr(cv, "fetch", lambda *a, **k: {"hh50wt.csv": raw})
    res = cv.convert(2001, ("replicates",), cache=tmp_path / "cache")
    t = pq.read_table(res["repw_household.parquet"].path)
    assert t.column_names[:3] == ["HOUSEID", "WTHHFIN", "WTHFIN1"]
    assert t.num_columns == 2 + 99 and t.num_rows == 3
    assert t.schema.field("HOUSEID").type == pa.string()
    assert t.schema.field("WTHHFIN").type == pa.float64()
    assert t.schema.field("WTHFIN99").type == pa.float32()
    assert t.column("HOUSEID").to_pylist()[0] == "010000000"  # leading zero survives


# -- the PDF codebook parsers on tiny synthetic pages ----------------------------------------------
def _tool():
    path = Path(__file__).resolve().parents[2] / "tools" / "build_schema_pdf.py"
    spec = importlib.util.spec_from_file_location("build_schema_pdf", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _line(head: str, code: str, freq: str = "", weighted: str = "") -> str:
    """One layout line: the code column starts at character 67, as in the real PDF text."""
    return f"{head:<67}{code:<42}{freq:>8}  {weighted:>12}".rstrip()


PAGE_2009 = "\n".join([
    "2009 NHTS Person File - Public Use Codebook, Version 2.1",
    "",
    "Name            Label                       Type Length Question Code / Range"
    "                         Frequency    Weighted",
    _line("BORNINUS        Respondent born in U.S.       C      2      M8", "-1 = Appropriate skip",
          "38,183", "44,757,967"),
    _line("", "01 = Yes", "244,524", "204,383,267"),
    _line("", "02 = No, and a long", "25,990", "33,695,567"),
    _line("", "continued label"),
    _line("CARRODE         Number of people              N      8      E18", "1", "92,199",
          "94,957,969"),
    "",
    " " * 67 + "B-15",
]) + "\n"


def test_2009_pdf_parser_reads_codes_and_wrapped_labels():
    tables = _tool().parse(PAGE_2009)
    cols = tables["person"]
    assert list(cols) == ["BORNINUS", "CARRODE"]
    b = cols["BORNINUS"]
    assert (b["type"], b["length"]) == ("C", "2")
    assert [c["code"] for c in b["codes"]] == ["-1", "01", "02"]
    assert b["codes"][2]["label"] == "No, and a long continued label"
    assert b["codes"][0]["n"] == 38183 and b["codes"][1]["weighted"] == 204383267.0
    assert cols["CARRODE"]["codes"][0]["code"] == "1"
