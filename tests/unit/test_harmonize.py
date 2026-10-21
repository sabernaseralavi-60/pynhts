"""The 2017 <-> 2022 crosswalks against the two codebooks (schemas), no microdata needed."""

from __future__ import annotations

import pandas as pd
import pytest

from pynhts import harmonize
from pynhts.core.schema import load_schema

MISSING = {"-9", "-8", "-7", "-1", "-88", "-77"}
# listed by the User Guide's Table 13 but absent from the public file (the codebook lists only
# observed codes)
UNOBSERVED = {("mode", 2022, "22")}


def _codebook(concept: str, wave: int, variable: str) -> dict[str, str]:
    table = "trip"
    return {c.code: c.label for c in load_schema(table, wave).columns[variable].codes}


@pytest.mark.parametrize("concept", ["purpose", "mode"])
@pytest.mark.parametrize("wave", [2017, 2022])
def test_every_observed_code_has_a_category_and_every_crosswalk_code_exists(concept, wave):
    cw = harmonize.crosswalk(concept)
    assert not cw.duplicated(["wave", "code"]).any()
    variables = {"purpose": ["WHYTO", "WHYFROM"], "mode": ["TRPTRANS"]}[concept]
    listed = set(cw.loc[cw["wave"] == wave, "code"])
    for variable in variables:
        book = _codebook(concept, wave, variable)
        real = {c for c in book if c not in MISSING}
        assert real <= listed, (variable, sorted(real - listed))
    book = _codebook(concept, wave, variables[0])
    extra = {c for c in listed if c not in book and (concept, wave, c) not in UNOBSERVED}
    assert not extra, extra


@pytest.mark.parametrize("concept", ["purpose", "mode"])
def test_label_hints_match_the_codebook_wording(concept):
    cw = harmonize.crosswalk(concept)
    for r in cw.itertuples():
        book = _codebook(concept, int(r.wave), str(r.variable))
        if r.code not in book:
            continue
        assert book[r.code].lower().startswith(str(r.hint).lower()), (r.wave, r.code, r.hint,
                                                                      book[r.code])


def test_status_vocabulary_and_comparability():
    for concept in harmonize.concepts():
        cw = harmonize.crosswalk(concept)
        assert set(cw["status"]) <= {"exact", "merge", "approximate", "only_here"}
        # an approximate or merged row always explains itself
        needs_note = cw[cw["status"].isin(["approximate", "only_here"])]
        by_cat = cw.groupby("category")["note"].apply(lambda s: s.notna().any())
        assert by_cat[needs_note["category"].unique()].all()
    rep = harmonize.category_report("purpose").set_index("category")
    assert rep.loc["work", "comparable"] and not rep.loc["work_related", "comparable"]
    assert not rep.loc["shopping", "comparable"] and "dry cleaning" in rep.loc["shopping", "issue"]
    mode = harmonize.category_report("mode").set_index("category")
    assert mode.loc["walk", "comparable"] and not mode.loc["escooter", "comparable"]
    assert mode.loc["escooter", "issue"] == "only in 2022"


def test_apply_maps_each_wave_with_its_own_codes_and_drops_missing():
    # the same raw code means different things: 02 is a bicycle in 2017 and a van in 2022
    s = pd.Series(["01", "02", "03", "-9", "99", None], dtype="string")
    a17 = harmonize.apply(s, "mode", wave=2017)
    a22 = harmonize.apply(s, "mode", wave=2022)
    assert a17.tolist()[:3] == ["walk", "bike", "car"]
    assert a22.tolist()[:3] == ["car", "van", "suv"]
    assert a17.isna().tolist()[3:] == [True, True, True]  # -9, unlisted 99, NA
    summary = harmonize.apply(pd.Series(["11", "15", "18"], dtype="string"), "mode", 2017,
                              level="summary")
    assert summary.tolist() == ["public_transit", "public_transit", "private_vehicle"]
    with pytest.raises(ValueError, match="no summary level"):
        harmonize.apply(s, "purpose", 2017, level="summary")
    with pytest.raises(ValueError, match="unknown concept"):
        harmonize.apply(s, "income", 2017)
    with pytest.raises(ValueError, match="no crosswalk rows"):
        harmonize.apply(s, "mode", 2009)


def test_purpose_codes_18_and_19_follow_the_codebook_not_the_guide_table():
    book = _codebook("purpose", 2022, "WHYTO")
    assert book["18"].startswith("Rest") and book["19"].startswith("Religious")
    out = harmonize.apply(pd.Series(["18", "19"], dtype="string"), "purpose", 2022)
    assert out.tolist() == ["other", "religious_community"]


def test_compare_waves_flags_what_the_compatibility_document_says():
    c = harmonize.compare_waves(2017, 2022).set_index("variable")
    assert c.loc["TRPTRANS", "status"] == "codes_changed"
    assert c.loc["CENSUS_R", "status"] == "identical"
    # omitted from 2022 for sample-size reasons (2022 Compatibility with Prior Data, page 4)
    for var in ("HHSTATE", "HH_CBSA", "HHRESP", "MODEL"):
        assert c.loc[var, "status"] == "only_2017", var
    assert c.loc["TRIPMODE", "status"] == "only_2022"
    assert {"identical", "relabelled", "codes_changed", "only_2017", "only_2022"} <= set(
        c["status"])
    # the inventory covers exactly the union of the variable names of both waves
    from pynhts import dictionary

    names = set(dictionary(2017)["variable"]) | set(dictionary(2022)["variable"])
    assert set(c.index) == names


def test_dictionary_and_describe():
    import pynhts

    d = pynhts.dictionary(2022)
    assert {"variable", "owner", "label", "dtype", "tables"} <= set(d.columns)
    row = d[(d["variable"] == "HHSIZE") & (d["owner"] == "household")].iloc[0]
    assert row["tables"].startswith("household") and "trip" in row["tables"].split(",")
    # PERSONID in the vehicle file is the main driver, not the person key: two meanings, two rows
    assert (pynhts.dictionary(2017).query("variable == 'PERSONID'")["owner"].nunique()) == 2
    info = pynhts.describe("TRPTRANS", 2022)
    assert info["owner"] == "trip" and {c["code"] for c in info["codes"]} >= {"01", "20"}
    with pytest.raises(KeyError):
        pynhts.describe("NOT_A_VARIABLE", 2017)
