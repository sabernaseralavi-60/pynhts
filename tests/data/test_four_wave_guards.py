"""Four-wave invariants behind the guards (review of 0.4.0). Run with: pytest -m data"""

from __future__ import annotations

import warnings

import pandas as pd
import pytest

import pynhts
from pynhts import harmonize
from pynhts.core import flags

pytestmark = pytest.mark.data
WAVES = (2001, 2009, 2017, 2022)


@pytest.fixture(scope="module", params=WAVES)
def data(request) -> pynhts.NHTSData:
    return pynhts.load(request.param, offline=True)


def test_no_negative_value_survives_masking_in_any_numeric_column(data):
    """-3 no contact, -4/-5 did not work ... are non-answers, never quantities."""
    for table in data.tables:
        schema = data.schema(table)
        num = [n for n, c in schema.columns.items()
               if not c.is_string and c.owner == table and not n.startswith(("WT", "EXPF"))]
        df = data.table(table, num, missing="nan", skip="nan", weight=False, keys=False)
        for name in num:
            assert not (df[name] < 0).any(), (data.wave, table, name)


def test_every_labelled_negative_code_is_masked_or_the_skip_code(data):
    for table in data.tables:
        for name, col in data.schema(table).columns.items():
            if col.owner != table:
                continue
            for k in col.codes:
                if k.code.startswith("-") and k.code.lstrip("-").isdigit() and k.label:
                    assert k.code in col.missing_codes or k.code == col.skip_code, (
                        data.wave, table, name, k.code)


def test_topcodes_are_what_the_flags_say(data):
    """The code occurs; nothing lies strictly between the boundary and the code."""
    for col, tc in flags.topcoded_columns(data.wave).items():
        for table in data.tables:
            spec = data.schema(table).columns.get(col)
            if spec is None or spec.owner != table:
                continue
            raw = data.table(table, [col], missing="nan", skip="nan", weight=False, keys=False)[col]
            x = pd.to_numeric(raw, errors="coerce").dropna()
            if x.empty:
                continue  # AGE_P8.. etc. exist but hold nothing
            code, edge = tc["code"], tc["boundary"]
            lo, hi = (edge, code) if tc["kind"] == "top" else (code, edge)
            assert (x == code).any() or x.max() < code, (data.wave, col)
            assert not ((x > lo) & (x < hi)).any(), (data.wave, col)
            if tc["kind"] == "top":
                assert x.max() == code or x.max() <= edge, (data.wave, col)


def test_national_only_columns_are_empty_for_add_on_households():
    d = pynhts.load(2001, offline=True)
    nat = set(d.households(["WTHHNTL"], weight=False).query("WTHHNTL == WTHHNTL")["HOUSEID"])
    for table in d.tables:
        cols = d.schema(table).columns
        columns = [c for c, spec in cols.items()
                   if flags.national_only(2001, c, table) and spec.owner == table]
        if not columns:
            continue
        df = d.table(table, columns, missing="keep", skip="keep", weight=False, keys=True)
        add_on = ~df["HOUSEID"].isin(nat)
        if not add_on.any():  # the long-distance file holds national households only
            continue
        for c in columns:
            s = df[c]
            if pd.api.types.is_numeric_dtype(s):
                empty = ((s == -1) | s.isna()).to_numpy()
            else:
                empty = ((s.astype("string") == "-1") | s.isna()).fillna(True).to_numpy()
            assert empty[add_on.to_numpy()].mean() > 0.95, (table, c)


def test_defaults_do_not_feed_the_skip_code_into_means():
    d = pynhts.load(2009, offline=True, replicates=True)
    vmt = d.survey("trip", ["VMT_MILE"]).mean("VMT_MILE").iloc[0]["estimate"]
    assert vmt == pytest.approx(9.72, abs=0.005)  # 5.36 when -1 was kept
    s = d.survey("person", ["TIMETOWK"])
    assert s.mean("TIMETOWK").iloc[0]["estimate"] == pytest.approx(24.205, abs=0.005)
    assert (s.rows["TIMETOWK"].dropna() >= 0).all()  # -4/-5 are masked


def test_top_coded_age_and_national_only_columns_warn():
    d09 = pynhts.load(2009, offline=True, replicates=True)
    with pytest.warns(flags.PynhtsWarning, match="89 or older"):
        d09.survey("person", ["R_AGE"]).mean("R_AGE")
    d01 = pynhts.load(2001, offline=True, replicates=True)
    with pytest.warns(flags.PynhtsWarning, match="national-sample"):
        d01.survey("vehicle", ["BESTMILE"]).total("BESTMILE")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        d09.survey("person", ["TIMETOWK"]).mean("TIMETOWK")


def test_tours_refuse_other_waves_without_a_config():
    for wave in (2001, 2009, 2022):
        with pytest.raises(ValueError, match="2017 purpose codes"):
            pynhts.load(wave, offline=True).tours()


def test_frames_and_results_carry_the_wave(data):
    trips = data.trips(["TRPTRANS"], weight=False)
    assert trips.attrs["pynhts"]["wave"] == data.wave
    wrong = next(w for w in WAVES if w != data.wave)
    with pytest.raises(ValueError, match="come from NHTS"):
        harmonize.apply(trips["TRPTRANS"], "mode", wave=wrong)
    got = harmonize.apply_column(trips, "TRPTRANS", "mode")
    assert got.notna().mean() > 0.99


def test_summary_mode_matches_the_official_public_transit_flag():
    """The crosswalk's public_transit group equals ORNL's PUBTRANS (TRPPUB in 2001)."""
    for wave, flag, tolerance in ((2009, "PUBTRANS", 0.0), (2017, "PUBTRANS", 0.0),
                                  (2022, "PUBTRANS", 0.0), (2001, "TRPPUB", 0.002)):
        d = pynhts.load(wave, offline=True)
        t = d.trips(["TRPTRANS", flag], weight=False)
        summary = harmonize.apply(t["TRPTRANS"], "mode", wave, level="summary")
        ok = summary.notna() & t[flag].notna()
        yes = t[flag].isin(["01", "1"])
        ours = (summary[ok] == "public_transit")
        disagree = (ours & ~yes[ok]).mean() + (~ours & yes[ok]).mean()
        if wave == 2001:  # TRPPUB also flags taxis, airplanes...: only transit -> yes is required
            assert (ours & ~yes[ok]).sum() / ours.sum() <= tolerance
        else:
            assert disagree <= tolerance, wave


def test_replicate_structure_is_what_the_factors_assume():
    """Delete-one (2001), delete-a-group (2017) and JK2 (2009: half deleted, half doubled)."""
    from pynhts.io import replicate_columns

    for wave in (2001, 2009, 2017):
        d = pynhts.load(wave, offline=True, replicates=True)
        reg = d._registry
        job = reg.replicate_jobs["household"]
        rep = d.replicate_weights("household")
        cols = replicate_columns(job.prefix, reg.n_replicates, job.pad)
        full = rep[job.weight].to_numpy()
        ratio = rep[cols].to_numpy() / full[:, None]
        zero = ratio < 1e-6
        doubled = ratio > 1.5  # the replicate weights are re-calibrated after the doubling
        if wave == 2009:
            assert (zero.sum(axis=1) <= 1).all()
            assert zero.any(axis=1).mean() == pytest.approx(0.5, abs=0.02)
            # the units that are not deleted are doubled exactly once (the other half of the pair)
            assert ((zero | doubled).sum(axis=1) == 1).mean() > 0.9
        elif wave == 2017:
            assert (zero.sum(axis=1) == 1).all()  # every unit is deleted in exactly one replicate
        else:
            assert (zero.sum(axis=1) == 1).mean() > 0.99
            assert zero.mean() == pytest.approx(0.01, rel=0.3)
        # the person replicates delete/double the same units as their household's replicates
        key = (zero | doubled).argmax(axis=1)
        hh_special = pd.Series(key, index=rep["HOUSEID"])
        pj = reg.replicate_jobs["person"]
        person = d.replicate_weights("person").drop_duplicates("HOUSEID")
        pr = person[replicate_columns(pj.prefix, reg.n_replicates, pj.pad)].to_numpy()
        pratio = pr / person[pj.weight].to_numpy()[:, None]
        p_special = pd.Series(((pratio < 1e-6) | (pratio > 1.5)).argmax(axis=1),
                              index=person["HOUSEID"])
        both = pd.concat([hh_special.rename("h"), p_special.rename("p")], axis=1, join="inner")
        assert (both["h"] == both["p"]).mean() > 0.99, wave


def test_2009_day_weights_of_persons_without_trips_are_filled():
    d = pynhts.load(2009, offline=True, replicates=True)
    day = d.replicate_weights("trip")
    assert day["DAYWGT"].notna().all() and day.iloc[:, 2:].notna().all().all()
    person = d.replicate_weights("person")
    merged = day.merge(person, on=["HOUSEID", "PERSONID"])
    assert (merged["DAYWGT"] / merged["WTPERFIN"]).between(364.999, 365.001).all()
    # person-day analyses can now include persons who did not travel
    persons = d.persons(["HOUSEID", "PERSONID"], weight=False)
    s = d.survey_rows(persons.assign(n=1.0), "trip")
    assert s.total("n").iloc[0]["estimate"] == pytest.approx(
        d.persons(["WTPERFIN"], weight=False)["WTPERFIN"].sum() * 365, rel=1e-9)


# ---- extended crosswalks (0.6.0) on the real files ----------------------------------------------
def _cases():
    waves = {"purpose": (2017, 2022), "fuel": (2001, 2009, 2017)}
    return [(c, w) for c in harmonize.concepts() for w in waves.get(c, WAVES)]


@pytest.mark.parametrize(("concept", "wave"), _cases())
def test_crosswalk_maps_nearly_every_real_value(concept, wave):
    info = harmonize.concept_info(concept)
    d = pynhts.load(wave, offline=True)
    frame = d.table(info["table"], [info["variable"]], weight=False, keys=False)
    col = frame[info["variable"]]
    mapped = harmonize.apply_column(frame, info["variable"], concept)
    skip = d.schema(info["table"]).columns[info["variable"]].skip_code
    known = col.notna()
    if skip is not None:  # the skip code means "does not apply"
        known &= (col.astype("string") != skip).fillna(False)
    unmapped = (mapped.isna() & known).mean() / max(known.mean(), 1e-9)
    assert unmapped < 0.001, (concept, wave, unmapped)


def test_income_bands_are_ordered_and_nest_in_every_wave():
    order = ["lt_10k", "10_15k", "15_25k", "25_35k", "35_50k", "50_75k", "75_100k", "100k_plus"]
    for wave in WAVES:
        d = pynhts.load(wave, offline=True)
        hh = d.households(["HHFAMINC"], weight=False)
        band = harmonize.apply_column(hh, "HHFAMINC", "income")
        rank = band.map({b: i for i, b in enumerate(order)})
        raw = pd.to_numeric(hh["HHFAMINC"], errors="coerce")
        ok = rank.notna() & raw.notna()
        assert (rank[ok].groupby(raw[ok]).nunique() == 1).all()   # one band per code
        assert rank[ok].groupby(raw[ok]).first().is_monotonic_increasing, wave
        assert set(band.dropna().unique()) == set(order), wave


def test_urban_codes_are_swapped_in_2001_and_the_crosswalk_undoes_it():
    shares = {}
    for wave in WAVES:
        hh = pynhts.load(wave, offline=True).households(["URBAN"], weight=False)
        band = harmonize.apply_column(hh, "URBAN", "urban_area")
        shares[wave] = (band == "urban_area").mean()
        raw_one = (hh["URBAN"].astype("string").str.lstrip("0") == "1").mean()
        if wave == 2001:
            assert raw_one < 0.5 < shares[wave] + 0.5  # raw code 1 is the small class in 2001
    assert all(0.4 < v < 0.95 for v in shares.values()), shares


def test_whytrp90_non_answers_are_masked_and_vacation_exists_only_in_old_waves():
    for wave in WAVES:
        t = pynhts.load(wave, offline=True).trips(["WHYTRP90"], weight=False)
        assert not t["WHYTRP90"].isin(["98", "99"]).any(), wave
        cat = harmonize.apply_column(t, "WHYTRP90", "purpose_1990")
        assert ("vacation" in set(cat.dropna())) == (wave in (2001, 2009)), wave


def test_suppression_codes_are_not_places():
    d01 = pynhts.load(2001, offline=True)
    assert not (d01.households(["HHSTATE"], weight=False)["HHSTATE"] == "XX").any()
    for wave in (2009, 2017):
        hh = pynhts.load(wave, offline=True).households(["HH_CBSA"], weight=False)
        assert not (hh["HH_CBSA"] == "XXXXX").any(), wave


def test_numeric_fuel_codes_of_2001_map_like_the_string_codes_of_2017():
    v01 = pynhts.load(2001, offline=True).vehicles(["FUELTYPE"], weight=False)
    fuel = harmonize.apply_column(v01, "FUELTYPE", "fuel")
    assert set(fuel.dropna()) == {"diesel", "alt_fuel", "gasoline"}
    assert (fuel == "gasoline").sum() > (fuel == "diesel").sum() > 0


def test_age_bands_end_at_85_and_agree_across_top_codes():
    for wave in WAVES:
        p = pynhts.load(wave, offline=True).persons(["R_AGE"], weight=False)
        bands = harmonize.age_bands(p["R_AGE"], wave)
        assert (bands == "85+").sum() > 0 and bands.notna().sum() > 0.99 * p["R_AGE"].notna().sum()
        assert ("0-4" in set(bands.dropna())) == (wave == 2001)
