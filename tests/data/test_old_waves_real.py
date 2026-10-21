"""NHTS 2009 and 2001 on the real files. Run with: pytest -m data

Oracles: every code frequency printed in the codebook (unweighted and weighted), the row counts
of the User's Guides, the control totals of the *Summary of Travel Trends* reports (recipes
``stt2009`` and ``stt2001``) and the worked standard-error examples of the two User's Guides.
"""

from __future__ import annotations

import re

import numpy as np
import pytest

import pynhts
from pynhts import recipes
from pynhts.io import replicate_columns

pytestmark = pytest.mark.data
WAVES = (2009, 2001)
ROWS = {
    2009: {"household": 150147, "person": 308901, "trip": 1167321, "vehicle": 309163},
    2001: {"household": 69817, "person": 160758, "trip": 642292, "vehicle": 139382,
           "longdist": 45165},
}
# codebook lines that the CSV does not reproduce, with the reason (checked 2026-10-21)
KNOWN_GAPS = {
    # the printed VEHTYPE frequencies of 2009 codebook v2.1 do not match the v2.1 file; the four
    # classes sum to the same 294,409 vehicles, 3,355 of which sit in another class in the data
    (2009, "vehicle", "VEHTYPE"): {"01", "02", "03", "04"},
}
# unlabelled lines that describe a range ("0-200000", "01:00AM-12:57PM"), not a coded value
# code lines compared (range lines and the four documented gaps excluded)
CHECKED = {2009: 3435, 2001: 6327}
_RANGE = re.compile(r".*\d\s*-\s*\d.*|.*:.*")


@pytest.fixture(scope="module", params=WAVES)
def data(request) -> pynhts.NHTSData:
    return pynhts.load(request.param, offline=True)


def test_row_counts_and_keys(data):
    assert data.tables == tuple(ROWS[data.wave])
    for table, n in ROWS[data.wave].items():
        key = list(data.key(table))
        frame = data.table(table, key, weight=False)
        assert len(frame) == n, table
        assert not frame.duplicated().any(), table


def test_every_codebook_frequency_reproduces(data):
    """Unweighted and weighted count of every coded value, bar the documented gaps."""
    checked = 0
    for table in data.tables:
        schema, wcol = data.schema(table), data.weight_column(table)
        df = data.table(table, missing="keep", skip="keep")
        weights = df[wcol].to_numpy(dtype=float)
        for name, col in schema.columns.items():
            exempt = KNOWN_GAPS.get((data.wave, table, name), set())
            if col.is_string:
                series = df[name].str.strip()
            else:
                series = df[name]
            for k in col.codes:
                if k.code in exempt or (not k.label and _RANGE.fullmatch(k.code.lstrip("-"))):
                    continue
                if k.code == "[missing]":
                    mask = series.isna().to_numpy()
                elif col.is_string:
                    mask = (series == k.code).fillna(False).to_numpy()
                else:
                    # the codebook prints more digits than some files store (BTUCOST 2001)
                    mask = np.isclose(series.to_numpy(dtype=float, na_value=np.nan),
                                      float(k.code), rtol=1e-9, atol=0.0)
                # 2009 PTUSED: the codebook counts the value 99 as "-9" (see build_schema_pdf.py)
                if data.wave == 2009 and name == "PTUSED" and k.code == "-9":
                    mask = mask | (series == 99).fillna(False).to_numpy()
                assert int(mask.sum()) == k.n, (table, name, k.code, int(mask.sum()), k.n)
                if k.weighted is not None and wcol in df:
                    got = float(np.nansum(weights[mask]))
                    assert got == pytest.approx(k.weighted, rel=1e-5, abs=1.0), (
                        table, name, k.code)
                checked += 1
    assert checked == CHECKED[data.wave]


def test_summary_of_travel_trends_point_estimates(data):
    """Table 1 and Table 3 with the replicate weights: every estimate matches the print."""
    name = {2009: "stt2009", 2001: "stt2001"}[data.wave]
    table = recipes.run(name, data)
    wrong = table[table["status"] != table["expected"]]
    assert wrong.empty, wrong[["id", "published", "estimate", "published_moe", "moe", "status"]]


def test_2001_user_guide_standard_error_example():
    """User's Guide 7-E.1: 202,586,200 household vehicles, SE 672,072, interval = 2 x SE."""
    d = pynhts.load(2001, offline=True, replicates=True)
    row = d.survey("vehicle", ["VEHID"]).total().iloc[0]
    assert row["estimate"] == pytest.approx(202_586_200, abs=1)
    assert row["se"] == pytest.approx(672_072, rel=5e-4)


@pytest.mark.parametrize("level", ["household", "person", "trip"])
def test_replicate_files_agree_with_the_data_files(data, level):
    reps = data.replicate_weights(level)
    key = ["HOUSEID"] if level == "household" else ["HOUSEID", "PERSONID"]
    assert not reps.duplicated(key).any()
    job = data._registry.replicate_jobs[level]
    cols = replicate_columns(job.prefix, data._registry.n_replicates, job.pad)
    assert set(cols) <= set(reps.columns) and len(reps.columns) == len(key) + 1 + len(cols)
    ok = reps[job.weight].notna()
    # the jackknife replicates scatter around the full-sample total (a unit-level sanity check)
    total = reps.loc[ok, job.weight].sum()
    rep_totals = reps.loc[ok, cols].sum()
    assert abs(rep_totals.mean() / total - 1) < 0.005
    assert rep_totals.std() / total < 0.02


def test_2009_persons_without_a_day_weight_have_no_trips():
    d = pynhts.load(2009, offline=True, replicates=True)
    reps = d.replicate_weights("trip")
    missing = reps[reps["DAYWGT"].isna()][["HOUSEID", "PERSONID"]]
    assert len(missing) == 45967  # persons without a complete travel day
    trips = d.trips(weight=False)[["HOUSEID", "PERSONID"]].drop_duplicates()
    assert trips.merge(missing, on=["HOUSEID", "PERSONID"]).empty
    # NaN weights of unused units must not poison estimates
    assert np.isfinite(d.survey("trip", ["TRPMILES"]).total().iloc[0]["se"])


def test_trip_weight_is_365_times_the_person_weight(data):
    persons = data.persons(["WTPERFIN"], weight=False)
    day = data.replicate_weights("trip", dtype="float64")
    merged = persons.merge(day, on=["HOUSEID", "PERSONID"])
    ok = merged[day.columns[2]].notna()  # the full-sample day weight
    ratio = merged.loc[ok, day.columns[2]] / merged.loc[ok, "WTPERFIN"]
    assert ratio.min() == pytest.approx(365, rel=1e-6)
    assert ratio.max() == pytest.approx(365, rel=1e-6)


def test_mode_and_purpose_crosswalks_cover_the_trip_files(data):
    from pynhts import harmonize

    trips = data.trips(["TRPTRANS", "WHYTRP1S"], weight=False, missing="nan")
    for concept, col in (("mode", "TRPTRANS"), ("purpose_summary", "WHYTRP1S")):
        mapped = harmonize.apply(trips[col], concept, wave=data.wave)
        known = trips[col].notna()
        assert mapped[known].notna().mean() > 0.999, (data.wave, concept)


def test_2001_long_distance_survey_uses_the_person_replicates():
    d = pynhts.load(2001, offline=True, replicates=True)
    row = d.survey("longdist", ["TPTRPNUM"]).total().iloc[0]
    rows = d.longdist(["TPTRPNUM"], weight=True)
    assert row["estimate"] == pytest.approx(rows["WTPTPFIN"].sum(), rel=1e-12)
    assert 0 < row["se"] < 0.05 * row["estimate"]
