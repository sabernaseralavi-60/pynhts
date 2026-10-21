"""Guards against silent misreading (review of 0.4.0): tags, permuted codes, flags, warnings."""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

from pynhts import harmonize
from pynhts.core import flags
from pynhts.core.schema import load_schema, wave_tables
from pynhts.stats import Survey, SurveyMeta, ratio_across


def test_apply_checks_the_wave_tag_and_refuses_a_mismatch():
    codes = pd.Series(["01", "02"], dtype="string")
    codes.attrs["pynhts"] = {"wave": 2017}
    assert harmonize.apply(codes, "mode").tolist() == ["walk", "bike"]  # wave from the tag
    assert harmonize.apply(codes, "mode", wave=2017).tolist() == ["walk", "bike"]
    with pytest.raises(ValueError, match="come from NHTS 2017"):
        harmonize.apply(codes, "mode", wave=2009)
    with pytest.raises(ValueError, match="wave is required"):
        harmonize.apply(pd.Series(["01"], dtype="string"), "mode")


def test_apply_column_reads_the_wave_from_the_frame():
    frame = pd.DataFrame({"TRPTRANS": pd.Series(["01", "08"], dtype="string")})
    frame.attrs["pynhts"] = {"wave": 2009}
    assert harmonize.apply_column(frame, "TRPTRANS", "mode").tolist() == ["car", "golf_cart"]
    with pytest.raises(ValueError, match="wave is required"):
        harmonize.apply_column(pd.DataFrame({"TRPTRANS": ["01"]}), "TRPTRANS", "mode")


def test_a_permuted_code_system_is_not_called_relabelled():
    # URBAN: 2001 1 = urban cluster, 2 = urban area; 2009 01 = urban area, 02 = urban cluster
    c = harmonize.compare_waves(2001, 2009).set_index("variable")
    assert c.loc["URBAN", "status"] == "codes_permuted"
    assert set(c.loc["URBAN", "conflicting_codes"].split(",")) == {"1", "2"}
    # the 2017 -> 2022 relationship codes are permuted too (07 = self in 2022)
    c2 = harmonize.compare_waves(2017, 2022).set_index("variable")
    assert c2.loc["R_RELAT", "status"] == "codes_permuted"


def test_flags_match_the_schemas():
    for wave in (2001, 2009, 2017, 2022):
        for col, tc in flags.topcoded_columns(wave).items():
            tables = [t for t in wave_tables(wave) if col in load_schema(t, wave).columns]
            assert tables, (wave, col)
            assert tc["kind"] in ("top", "bottom") and tc["source"] in ("codebook", "data")
    assert flags.topcode(2009, "R_AGE")["code"] == 92
    assert flags.topcode(2001, "R_AGE")["code"] == 88  # 85 or older, not 88
    assert flags.topcode(2022, "TRPMILES") is None
    assert flags.national_only(2001, "BESTMILE") and not flags.national_only(2009, "BESTMILE")
    assert flags.national_only(2001, "TPTRPNUM", table="longdist")
    for col in flags.national_only_columns(2001):
        assert any(col in load_schema(t, 2001).columns for t in wave_tables(2001)), col


def test_cautions_name_the_problem_and_the_meaning():
    text = flags.cautions(2001, "person", ["R_AGE", "TRPMILES"])
    assert list(text) == ["R_AGE"] and "85 or older" in text["R_AGE"]
    assert "national-sample" in flags.cautions(2001, "vehicle", ["BESTMILE"])["BESTMILE"]


def _survey(system: str = "main", cautions: dict[str, str] | None = None) -> Survey:
    rng = np.random.default_rng(1)
    w = rng.uniform(10, 20, 30)
    reps = w[:, None] * rng.uniform(0.9, 1.1, (30, 99))
    rows = pd.DataFrame({"y": rng.normal(5, 1, 30), "R_AGE": rng.integers(5, 88, 30)})
    meta = SurveyMeta(wave=2001, table="person", weight="WTPERFIN", design="jackknife test",
                      unit="persons", cautions=cautions or {}, replicate_system=system)
    return Survey(rows, np.arange(30), w, reps, df=99, factor=98 / 99, meta=meta)


def test_results_carry_wave_design_and_unit():
    res = _survey().total("y")
    assert res.attrs["pynhts"] == {"wave": 2001, "table": "person", "weight": "WTPERFIN",
                                   "design": "jackknife test", "unit": "persons"}
    assert _survey().mean("y").attrs["pynhts"]["unit"] == "persons"


def test_top_coded_column_warns_when_analysed():
    s = _survey(cautions=flags.cautions(2001, "person", ["R_AGE"]))
    with pytest.warns(flags.PynhtsWarning, match="85 or older"):
        s.mean("R_AGE")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        s.mean("y")  # an ordinary column does not warn


def test_ratio_across_refuses_different_replicate_systems_and_waves():
    a, b = _survey("main"), _survey("national-longdist")
    with pytest.raises(ValueError, match="different systems"):
        ratio_across(a, "y", b, "y")
    other = _survey("main")
    other.meta = SurveyMeta(wave=2009, table="household", replicate_system="main")
    with pytest.raises(ValueError, match="cannot form a ratio"):
        ratio_across(a, "y", other, "y")
    assert ratio_across(a, "y", _survey("main"), "y").attrs["pynhts"]["unit"] == "ratio"
