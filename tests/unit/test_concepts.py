"""The concept dictionary must agree with the schemas and the crosswalks (no microdata)."""

from __future__ import annotations

import json

import pytest

from pynhts import concepts, harmonize
from pynhts.core.schema import load_schema, wave_tables

ENTRIES = concepts.names()


@pytest.mark.parametrize("name", ENTRIES)
def test_every_variable_exists_in_its_wave_and_table(name):
    c = concepts.get(name)
    assert c["comparability"] in concepts.GRADES and c["pitfalls"] and c["evidence"]
    assert set(c["variables"]) == set(concepts.WAVES)
    for wave, var in c["variables"].items():
        if var is None:
            continue
        tables = [t for t in wave_tables(wave) if var in load_schema(t, wave).columns]
        assert tables, (name, wave, var)
        if c["table"]:
            assert c["table"] in tables, (name, wave, var, tables)
    for wave, var in (c.get("imputed") or {}).items():
        assert any(var in load_schema(t, wave).columns for t in wave_tables(wave)), (name, var)


def test_named_harmonizations_exist_and_cover_the_concept_variable():
    for name in ENTRIES:
        c = concepts.get(name)
        h = str(c["harmonize"] or "")
        if h.startswith('harmonize.crosswalk("'):
            concept = h.split('"')[1]
            info = harmonize.concept_info(concept)
            for wave, var in c["variables"].items():
                if var is not None and wave in set(harmonize.crosswalk(concept)["wave"]):
                    assert var in (harmonize.variable_of(concept, wave), *info["also"]), (
                        name, wave, var)


def test_grades_are_consistent_with_the_flags():
    # a concept that depends on a national-only or top-coded column must say so
    for name in ENTRIES:
        c = concepts.get(name)
        text = " ".join(c["pitfalls"]).lower()
        for wave, var in c["variables"].items():
            if var is None:
                continue
            if concepts.find(var, wave)[0]["topcode"]:
                assert any(w in text for w in ("top", "bottom", "band", "cap")), (name, wave, var)
            if concepts.find(var, wave)[0]["national_only"]:
                assert "national" in text, (name, wave, var)


def test_find_and_json_export():
    hit = concepts.find("VEHAGE", 2009)[0]
    assert hit["concept"] == "vehicle_age" and hit["topcode"]["code"] == 35
    assert concepts.find("BESTMILE", 2001)[0]["national_only"] is True
    assert concepts.find("NOT_A_VARIABLE", 2001) == []
    payload = json.loads(concepts.to_json())
    assert len(payload["concepts"]) == len(ENTRIES) >= 35
    assert set(payload["grades"]) == {"C", "H", "N"}
    with pytest.raises(KeyError):
        concepts.get("nonsense")
    t = concepts.table()
    assert list(t["concept"]) == ENTRIES and {"2001", "2022"} <= set(t.columns)
