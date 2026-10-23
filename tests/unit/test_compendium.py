"""pynhts.compendium: shipped corpus, search filters, tags on planted texts, BibTeX, advisor and the case-study bridge."""

from __future__ import annotations

import pandas as pd
import pytest

from pynhts import compendium as comp


def test_corpus_schema_and_unique_ids():
    df = comp.load()
    assert len(df) > 4000 and df["cid"].is_unique
    for col in ("title", "authors", "pub_year", "editions", "domain", "model_families", "mentions_weights", "mentions_variance_design",
                "mentions_resampling", "linked_audit_id", "repro_level", "doi", "url"):
        assert col in df.columns
    assert "abstract" not in df.columns and "terms" not in df.columns  # the shipped table holds no abstract text
    assert set(df["domain"]).issuperset({"Travel behavior", "Energy consumption", "Bicycle and pedestrian studies"})


def test_counts_in_audit_summary_agree_with_the_table():
    a = comp.audit_summary()
    df = comp.load()
    assert a.numbers["n_unique"] == len(df)
    assert a.numbers["n_records"] == a.numbers["n_pdf_records"] + a.numbers["n_csv_records"]
    assert a.numbers["n_duplicates_removed"] == a.numbers["n_records"] - a.numbers["n_unique"]
    assert a.numbers["mod_weights_n"] <= a.numbers["mod_n"]
    assert a.numbers["audit_max_abs_diff"] <= 3  # parsed entries vs the independent count of every PDF edition
    assert set(a.extraction["edition"]) >= {"2006-2011", "2012", "2016", "2022", "2025"}
    assert "Compendium" in str(a)


def test_search_filters_combine():
    all_ev = comp.search("electric vehicle")
    assert len(all_ev) > 100
    both = comp.search("electric vehicle", wave=2017)
    assert 0 < len(both) < len(all_ev)
    assert both["nhts_waves_mentioned"].str.contains("2017").all()
    zinb = comp.search(model="ZINB")
    assert len(zinb) > 0 and zinb["model_families"].str.contains("Count").all()
    ml = comp.search(ml=True, years=(2023, None))
    assert len(ml) > 0 and (ml["pub_year"] >= 2023).all() and ml["model_families"].str.contains("Machine learning").all()
    assert comp.search(weights=True, variance=True)["mentions_weights"].all()
    assert len(comp.search("zzzzqqq")) == 0
    assert len(comp.search("older adults chaining", match="any")) >= len(comp.search("older adults chaining"))
    with pytest.raises(ValueError):
        comp.search(model="no-such-family")
    with pytest.raises(ValueError):
        comp.search("x", match="some")


def test_search_limit_and_edition():
    assert len(comp.search("bikeshare", limit=5)) == 5
    ed = comp.search(edition=2012)
    assert len(ed) > 100 and ed["editions"].str.contains("2012").all()


def test_get_and_unknown_id():
    cid = comp.search("bikeshare", limit=1)["cid"].iloc[0]
    assert comp.get(cid)["cid"] == cid
    with pytest.raises(KeyError):
        comp.get("Cdeadbeef")


def test_tags_on_planted_texts():
    t = comp.tag("Mode choice with machine learning",
                 "We oversample with SMOTE and a random forest reaches an accuracy of 0.937 on the 2017 NHTS and 2009 NHTS.")
    assert t.is_ml and t.mentions_resampling and t.mentions_imbalance_or_leakage_risk
    assert t.accuracy_claim_pct == pytest.approx(93.7)
    assert t.nhts_waves_mentioned == ["2009", "2017"]
    w = comp.tag("", "Survey weights were applied and jackknife replicate weights gave the standard errors.")
    assert w.mentions_weights and w.mentions_variance_design and "jackknife" in w.variance_terms
    # things that look like weights but are not survey weights
    for text in ("geographically weighted regression of crashes", "propensity score weighting method", "vehicle weight and fuel economy",
                 "population-weighted density", "weighted F-scores of the classifier"):
        assert not comp.tag("", text).mentions_weights, text
    # a descriptive survey-design remark is not a variance estimator
    assert not comp.tag("", "survey design, recruitment and data cleaning").mentions_variance_design
    zinb = comp.tag("", "Zero-inflated negative binomial regression of ride-hailing use")
    assert zinb.model_families[:1] == ["Count (Poisson/NB/ZINB)"] and zinb.study_type == "regression_inference"
    assert comp.tag("", "NextGen Passenger Origin-Destination data").nhts_waves_mentioned == ["NextGen OD"]
    assert comp.tag("", "traffic counts at an intersection").study_type == "descriptive_or_other"


def test_bibtex_is_well_formed_and_keys_unique():
    r = comp.search("bikeshare", limit=4)
    bib = comp.to_bibtex(r)
    assert bib.count("@") >= 4 and bib.count("{") == bib.count("}")
    keys = [ln.split("{", 1)[1].rstrip(",") for ln in bib.splitlines() if ln.startswith("@")]
    assert len(keys) == len(set(keys)) == 4
    assert "NHTS Compendium of Uses" in bib
    assert comp.to_bibtex([]) == ""
    assert comp.to_bibtex(r["cid"].iloc[0]).startswith("@")


def test_register_bridge_to_the_ladder():
    reg = comp.register()
    assert len(reg) == 22 and {"P01", "P24"} <= set(reg["audit_id"])
    found = comp.register(only_found=True)
    assert 0 < len(found) <= 22 and found["cid"].str.startswith("C").all()
    df = comp.load()
    linked = df[df["linked_audit_id"] != ""]
    assert set(linked["linked_audit_id"]) == set(found["audit_id"])
    assert set(linked["repro_level"]) <= {"L0", "L1", "L2", "L3"}
    assert comp.search(audited=True).shape[0] == len(linked)


def test_advise_topic_mode_and_empty():
    a = comp.advise("EV adoption")
    assert a.topic == "EV / alternative fuel adoption" and a.n_studies > 100
    text = str(a)
    assert "Weights and variance" in text and "Leakage" in text and "concepts.find" in text
    assert any("median" in p for p in a.pitfalls)
    ml = comp.advise("classification")
    assert ml.family == "Machine learning" and any("Leakage" in p for p in ml.pitfalls)
    none = comp.advise("zzzqqq")
    assert none.n_studies == 0 and "No study" in str(none)
    assert comp.advise("bikeshare", wave=2017).n_studies <= comp.advise("bikeshare").n_studies
    assert "age" in comp.advise("older adults").concepts_to_read


def test_topic_and_family_lists():
    assert "older adults" in comp.topics() and "Machine learning" in comp.model_families()
    assert comp.domains()[0] == "Energy consumption"
    assert isinstance(comp.advise("bikeshare").register, pd.DataFrame)
