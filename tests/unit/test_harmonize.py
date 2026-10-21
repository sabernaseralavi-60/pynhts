"""The 2017 <-> 2022 crosswalks against the two codebooks (schemas), no microdata needed."""

from __future__ import annotations

import pandas as pd
import pytest

from pynhts import harmonize
from pynhts.core.schema import load_schema

# listed by the User Guide's Table 13 but absent from the public file (the codebook lists only
# observed codes)
UNOBSERVED = {("mode", 2022, "22")}
# the detailed purpose crosswalk covers 2017 and 2022 (2001 and 2009 have a different WHYTO
# scheme, aligned through the summary purpose WHYTRP1S and the 1990-scheme purpose WHYTRP90);
# 2022 has no FUELTYPE
ALL = (2001, 2009, 2017, 2022)
WAVES = {"purpose": (2017, 2022), "fuel": (2001, 2009, 2017)}


def _codebook(concept: str, wave: int, variable: str):
    info = harmonize.concept_info(concept)
    return load_schema(info["table"], wave).columns[variable]


CASES = [(c, w) for c in harmonize.concepts() for w in WAVES.get(c, ALL)]


def _canon(code: str) -> str:
    return str(int(code)) if code.isdigit() else code


@pytest.mark.parametrize(("concept", "wave"), CASES)
def test_every_observed_code_has_a_category_and_every_crosswalk_code_exists(concept, wave):
    cw = harmonize.crosswalk(concept)
    assert not cw.duplicated(["wave", "code"]).any()
    info = harmonize.concept_info(concept)
    listed = set(cw.loc[cw["wave"] == wave, "code"])
    for variable in [info["variable"], *info["also"]]:
        col = _codebook(concept, wave, variable)
        real = {c.code for c in col.codes
                if c.code not in col.missing_codes and c.code != col.skip_code
                and not (not c.label and ("-" in c.code[1:] or ":" in c.code))}
        # the crosswalk may list codes by their canonical form; compare without zero padding
        canon_listed = {_canon(x) for x in listed}
        missing = {c for c in real if c not in listed and _canon(c) not in canon_listed}
        assert not missing, (concept, wave, variable, sorted(missing))
    book = {c.code for c in _codebook(concept, wave, info["variable"]).codes}
    extra = {c for c in listed if c not in book and (concept, wave, c) not in UNOBSERVED}
    assert not extra, extra


@pytest.mark.parametrize("concept", harmonize.concepts())
def test_label_hints_match_the_codebook_wording(concept):
    cw = harmonize.crosswalk(concept)
    for r in cw.itertuples():
        col = _codebook(concept, int(r.wave), str(r.variable))
        book = {c.code: c.label for c in col.codes}
        if r.code not in book:
            continue
        label = book[r.code].lower().replace("  ", " ").replace('"', "'")
        assert label.startswith(str(r.hint).lower()), (
            r.wave, r.code, r.hint, book[r.code])


def test_status_vocabulary_and_comparability():
    for concept in harmonize.concepts():
        cw = harmonize.crosswalk(concept)
        assert set(cw["status"]) <= set(harmonize.STATUSES)
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
    assert "other_truck" not in mode.index  # exists only in the 2001 and 2009 rows


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
        harmonize.apply(s, "nonsense", 2017)
    with pytest.raises(ValueError, match="no crosswalk rows"):
        harmonize.apply(s, "mode", 1995)


def test_old_waves_use_other_codes_for_the_same_modes():
    # the same raw code means different things in every wave: 08 is a commercial airplane (2001),
    # a golf cart (2009) and a motorcycle (2017); 22 is a taxi (2001), a bicycle (2009) and a
    # ferry (2022)
    s = pd.Series(["01", "08", "22", "23"], dtype="string")
    assert harmonize.apply(s, "mode", 2001).tolist() == [
        "car", "air", "taxi_rideshare", "taxi_rideshare"]
    assert harmonize.apply(s, "mode", 2009).tolist() == ["car", "golf_cart", "bike", "walk"]
    assert harmonize.apply(s, "mode", 2017).tolist()[:2] == ["walk", "motorcycle"]
    rep = harmonize.category_report("mode", 2001, 2009).set_index("category")
    assert rep.loc["walk", "comparable"] and rep.loc["bike", "comparable"]
    assert not rep.loc["bus", "comparable"] and rep.loc["golf_cart", "issue"] == "only in 2009"


def test_whytrp1s_has_three_code_systems_but_shared_categories():
    one = pd.Series(["01", "10"], dtype="string")
    # the same raw codes: 2001 01 = to work, 10 = serve passenger; later 01 = home, 10 = work
    assert harmonize.apply(one, "purpose_summary", 2001).tolist() == ["work", "transport_someone"]
    assert harmonize.apply(one, "purpose_summary", 2009).tolist() == ["home", "work"]
    assert harmonize.apply(one, "purpose_summary", 2017).tolist() == ["home", "work"]
    rep = harmonize.category_report("purpose_summary", 2009, 2017).set_index("category")
    assert rep.loc["work", "comparable"] and not rep.loc["shopping_errands", "comparable"]


def test_purpose_codes_18_and_19_follow_the_codebook_not_the_guide_table():
    book = {c.code: c.label for c in _codebook("purpose", 2022, "WHYTO").codes}
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
