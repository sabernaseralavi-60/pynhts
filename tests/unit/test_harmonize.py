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
WAVES = {"purpose": (2017, 2022), "fuel": (2001, 2009, 2017),
         "race_person": (2017, 2022), "hispanic_person": (2017, 2022)}


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
    primary = harmonize.variable_of(concept, wave)
    for variable in [primary, *info["also"]]:
        col = _codebook(concept, wave, variable)
        real = {c.code for c in col.codes
                if c.code not in col.missing_codes and c.code != col.skip_code
                and not (not c.label and ("-" in c.code[1:] or ":" in c.code))}
        # the crosswalk may list codes by their canonical form; compare without zero padding
        canon_listed = {_canon(x) for x in listed}
        missing = {c for c in real if c not in listed and _canon(c) not in canon_listed}
        assert not missing, (concept, wave, variable, sorted(missing))
    book = {c.code for c in _codebook(concept, wave, primary).codes}
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


# ---- race and Hispanic origin (0.8.0) ---------------------------------------------------------
def _py(series: pd.Series) -> list:
    """Values as a plain list with None for NA (pd.NA compares unequal to everything)."""
    return [None if pd.isna(v) else v for v in series]


def _tagged(frame: pd.DataFrame, wave: int) -> pd.DataFrame:
    frame.attrs["pynhts"] = {"wave": wave}
    return frame


def test_race_column_is_named_differently_in_2001_and_the_crosswalk_knows_it():
    assert harmonize.variable_of("race_household", 2001) == "HHR_RACE"
    assert harmonize.variable_of("race_household", 2009) == "HH_RACE"
    assert harmonize.variable_of("hispanic_household", 2001) == "HHR_HISP"
    assert harmonize.variable_of("mode", 2001) == "TRPTRANS"
    cw = harmonize.crosswalk("race_household")
    assert set(cw.loc[cw["wave"] == 2001, "variable"]) == {"HHR_RACE"}
    assert set(cw.loc[cw["wave"] != 2001, "variable"]) == {"HH_RACE"}
    assert harmonize.concept_info("race_household")["variable_by_wave"] == {2001: "HHR_RACE"}


def test_single_race_groups_are_comparable_from_2009_on_but_2001_breaks_three():
    for a, b in [(2009, 2017), (2017, 2022), (2009, 2022)]:
        rep = harmonize.category_report("race_household", a, b).set_index("category")
        for cat in ("black", "asian", "aian", "nhpi"):
            assert rep.loc[cat, "comparable"], (a, b, cat)
    # 2009 offered a Hispanic race answer, so its White is not 2017's White (review of 0.8.0)
    for b in (2017, 2022):
        rep = harmonize.category_report("race_household", 2009, b).set_index("category")
        assert not rep.loc["white", "comparable"] and "Hispanic" in rep.loc["white", "issue"], b
    assert harmonize.category_report("race_household", 2017, 2022).set_index("category").loc[
        "white", "comparable"]
    # 2001 files 'White & Hispanic', 'African American & Hispanic' and 'American Indian & Hispanic'
    # under the race part (approximate), so only Asian and Pacific Islander are clean
    for b in (2009, 2017, 2022):
        rep = harmonize.category_report("race_household", 2001, b).set_index("category")
        assert rep.loc[["asian", "nhpi"], "comparable"].all()
        for cat in ("white", "black", "aian"):
            assert not rep.loc[cat, "comparable"] and "Hispanic" in rep.loc[cat, "issue"], (b, cat)
    rep = harmonize.category_report("race_household", 2017, 2022).set_index("category")
    assert rep.loc["other", "comparable"] and rep.loc["multiple", "comparable"]
    for a in (2001, 2009):
        rep = harmonize.category_report("race_household", a, 2017).set_index("category")
        assert not rep.loc["other", "comparable"] and "Hispanic" in rep.loc["other", "issue"]
    # 2009 'Multiracial' equals 2017; the 2001 combination codes do not (13, 14, 16 are mixes)
    assert harmonize.category_report("race_household", 2009, 2017).set_index(
        "category").loc["multiple", "comparable"]
    assert not harmonize.category_report("race_household", 2001, 2017).set_index(
        "category").loc["multiple", "comparable"]


def test_same_race_code_means_the_same_in_2009_2017_2022_but_2001_hispanic_codes_move():
    s = pd.Series(["01", "06", "07", "97"], dtype="string")
    assert _py(harmonize.apply(s, "race_household", 2017)) == ["white", "multiple", None, "other"]
    assert _py(harmonize.apply(s, "race_household", 2022)) == ["white", "multiple", None, "other"]
    # 06 is 'Hispanic/Mexican' in 2001 and 'Multiracial' in 2009; 07 is 'White & African American'
    # in 2001 and 'Hispanic/Mexican' in 2009
    assert _py(harmonize.apply(s, "race_household", 2001)) == ["white", "other", "multiple", None]
    assert _py(harmonize.apply(s, "race_household", 2009)) == [
        "white", "multiple", "other", "other"]
    # non-answers are not categories
    na = pd.Series(["-7", "-8", "-9", "-1"], dtype="string")
    assert harmonize.apply(na, "race_household", 2009).isna().all()


def test_race_ethnicity_combines_race_and_hispanic_origin_in_every_wave():
    f01 = _tagged(pd.DataFrame({
        "HHR_RACE": ["01", "01", "06", "10", "02", "13", "-7", "03", "06"],
        "HHR_HISP": ["2", "1", "1", None, "2", "2", "2", None, "2"]}), 2001)
    # white non-Hispanic; white Hispanic (the question wins over the race code); Hispanic race code
    # and Hispanic yes; Hispanic race code, question unanswered; black non-Hispanic; unknown
    # combination, non-Hispanic; unknown race; Asian with unknown origin (cannot be placed);
    # Hispanic race code but the question says no (the question wins)
    assert _py(harmonize.race_ethnicity(f01)) == [
        "nh_white", "hispanic", "hispanic", "hispanic", "nh_black", "nh_multiple", None, None,
        "nh_other"]
    f09 = _tagged(pd.DataFrame({"HH_RACE": ["07", "01", "97"],
                                "HH_HISP": ["02", "01", None]}), 2009)
    assert _py(harmonize.race_ethnicity(f09)) == ["nh_other", "hispanic", None]
    f17 = _tagged(pd.DataFrame({"HH_RACE": ["01", "06", "97", "05"],
                                "HH_HISP": ["02", "02", "01", "02"]}), 2017)
    assert harmonize.race_ethnicity(f17).tolist() == [
        "nh_white", "nh_multiple", "hispanic", "nh_nhpi"]
    p22 = _tagged(pd.DataFrame({"R_RACE": ["02", "01"], "R_HISP": ["02", "01"]}), 2022)
    assert harmonize.race_ethnicity(p22, level="person").tolist() == ["nh_black", "hispanic"]


def test_race_ethnicity_refuses_what_it_cannot_do():
    f = _tagged(pd.DataFrame({"HH_RACE": ["01"], "HH_HISP": ["01"]}), 2009)
    with pytest.raises(ValueError, match="do not exist in NHTS 2009"):
        harmonize.race_ethnicity(f, level="person")
    with pytest.raises(KeyError, match="HH_HISP"):
        harmonize.race_ethnicity(_tagged(pd.DataFrame({"HH_RACE": ["01"]}), 2009))
    with pytest.raises(ValueError, match="wave is required"):
        harmonize.race_ethnicity(pd.DataFrame({"HH_RACE": ["01"], "HH_HISP": ["01"]}))
    with pytest.raises(ValueError, match="level"):
        harmonize.race_ethnicity(f, level="trip")


def test_hispanic_race_codes_named_in_the_crosswalk_really_say_hispanic():
    spec = harmonize._spec("race_household")
    for wave, codes in spec["hispanic_codes"].items():
        column = _codebook("race_household", wave, harmonize.variable_of("race_household", wave))
        book = {c.code: c.label for c in column.codes}
        assert codes and all("hispanic" in book[c].lower() for c in codes), (wave, codes)
        # and no other code of the wave names Hispanic origin
        others = [c for c, lab in book.items() if "hispanic" in lab.lower() and c not in codes]
        assert not others, (wave, others)


# ---- medical condition (0.8.0) --------------------------------------------------------------
def test_medical_condition_codes_map_to_yes_no_with_the_padding_of_each_wave():
    assert _py(harmonize.apply(pd.Series(["1", "2", "-1", "-7"], dtype="string"),
                               "medical_condition", 2001)) == ["yes", "no", None, None]
    for wave in (2009, 2017, 2022):
        s = pd.Series(["01", "02", "-1", "-8"], dtype="string")
        assert _py(harmonize.apply(s, "medical_condition", wave)) == ["yes", "no", None, None]


def test_medical_condition_2022_is_marked_not_comparable_but_2001_to_2017_are():
    for a, b in [(2001, 2009), (2009, 2017), (2001, 2017)]:
        rep = harmonize.category_report("medical_condition", a, b).set_index("category")
        assert rep["comparable"].all(), (a, b)
    for a in (2001, 2009, 2017):
        rep = harmonize.category_report("medical_condition", a, 2022).set_index("category")
        assert not rep["comparable"].any() and "do not answer" in rep.loc["yes", "issue"], a


def test_condition_duration_six_bands_collapse_into_three_with_an_honest_boundary():
    old = pd.Series(["1", "2", "3", "4", "5", "6"], dtype="string")
    assert _py(harmonize.apply(old, "condition_duration", 2001)) == [
        "up_to_6_months", "over_6_months", "over_6_months", "over_6_months", "over_6_months",
        "lifelong"]
    assert _py(harmonize.apply(pd.Series(["01", "06"], dtype="string"),
                               "condition_duration", 2009)) == ["up_to_6_months", "lifelong"]
    new = pd.Series(["01", "02", "03", "-1"], dtype="string")
    for wave in (2017, 2022):
        assert _py(harmonize.apply(new, "condition_duration", wave)) == [
            "up_to_6_months", "over_6_months", "lifelong", None]
    # lifelong is the same in all four waves; the 6-month boundary is not (2001/2009 vs 2017/2022)
    rep = harmonize.category_report("condition_duration", 2009, 2017).set_index("category")
    assert rep.loc["lifelong", "comparable"] and not rep.loc["up_to_6_months", "comparable"]
    rep = harmonize.category_report("condition_duration", 2017, 2022).set_index("category")
    assert rep["comparable"].all()
    rep = harmonize.category_report("condition_duration", 2001, 2009).set_index("category")
    assert rep.loc["lifelong", "comparable"] and not rep.loc["over_6_months", "comparable"]


def test_condition_effect_2022_select_all_and_2017_break_are_flagged():
    rep = harmonize.category_report("condition_effect", 2001, 2009).set_index("category")
    assert rep["comparable"].all()
    for a, b in [(2009, 2017), (2017, 2022), (2009, 2022)]:
        rep = harmonize.category_report("condition_effect", a, b).set_index("category")
        assert not rep["comparable"].any(), (a, b)
    s22 = harmonize.apply(pd.Series(["01", "02"], dtype="string"), "condition_effect", 2022)
    assert _py(s22) == ["yes", "no"]
    cw = harmonize.crosswalk("condition_effect")
    assert "select-all" in " ".join(cw.loc[cw["wave"] == 2022, "note"].dropna())
    assert harmonize.concept_info("condition_effect")["also"] == [
        "CONDNIGH", "CONDPUB", "CONDRIDE", "CONDRIVE", "CONDSPEC"]
