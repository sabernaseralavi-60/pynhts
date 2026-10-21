"""Check the 2017 <-> 2022 crosswalks against ORNL's own derived variables, on the real files.

The guide's tables were written for humans, so the crosswalk is tested a second way: every code
that lands in one harmonized category must also land in the same ORNL summary purpose
(``WHYTRP1S``) in both waves, and 2022 modes must land in the summary mode ``TRIPMODE`` that the
guide's summary group predicts. Run with: pytest -m data
"""

from __future__ import annotations

import pandas as pd
import pytest

import pynhts
from pynhts import harmonize

pytestmark = pytest.mark.data

# categories whose members are NOT expected to share one WHYTRP1S across waves, and why
PURPOSE_EXCEPTIONS = {
    "other": "2022 'Rest or relaxation' (WHYTRP1S 50) is folded into 'other' following the guide",
}
# the guide and ORNL's derived variable disagree on recreational vehicles (see the crosswalk)
TRIPMODE_EXCEPTIONS = {"06": {"01", "02"}}
TRIPMODE_OF_SUMMARY = {
    "private_vehicle": {"01", "02"}, "public_transit": {"03"}, "school_bus": {"04"},
    "walk": {"05"}, "bike": {"06"}, "other_vehicle": {"07"}, "other_transit": {"07"},
    "other": {"07"},
}


@pytest.fixture(scope="module")
def trips() -> dict[int, pd.DataFrame]:
    out = {}
    for wave in (2017, 2022):
        d = pynhts.load(wave, offline=True)
        cols = ["WHYTO", "WHYFROM", "WHYTRP1S", "TRPTRANS"]
        cols += ["TRIPMODE"] if wave == 2022 else []
        out[wave] = d.trips(cols, missing="keep")
    return out


def test_purpose_categories_agree_with_whytrp1s_in_both_waves(trips):
    sets: dict[int, dict[str, frozenset[str]]] = {}
    for wave, t in trips.items():
        cat = harmonize.apply(t["WHYTO"], "purpose", wave)
        ok = cat.notna()
        sets[wave] = {
            c: frozenset(g["WHYTRP1S"].unique())
            for c, g in t[ok].groupby(cat[ok], observed=True)
        }
        # every non-missing code is mapped
        real = t.loc[~t["WHYTO"].isin({"-9", "-8", "-7"}), "WHYTO"]
        assert harmonize.apply(real, "purpose", wave).notna().all()
    for cat in set(sets[2017]) & set(sets[2022]):
        if cat in PURPOSE_EXCEPTIONS:
            assert sets[2017][cat] != sets[2022][cat], cat  # the exception is real
        else:
            assert sets[2017][cat] == sets[2022][cat], (cat, sets[2017][cat], sets[2022][cat])
    # a category lives inside a single ORNL summary purpose (except the documented one)
    for wave, per_cat in sets.items():
        for cat, vals in per_cat.items():
            if cat not in PURPOSE_EXCEPTIONS:
                assert len(vals) == 1, (wave, cat, vals)


def test_2022_summary_modes_match_ornl_tripmode(trips):
    t = trips[2022]
    cw = harmonize.crosswalk("mode")
    cw22 = cw[cw["wave"] == 2022].set_index("code")
    for code, group in t.groupby("TRPTRANS", observed=True):
        want = TRIPMODE_OF_SUMMARY[cw22.loc[code, "summary"]]
        if code in TRIPMODE_EXCEPTIONS:
            want = TRIPMODE_EXCEPTIONS[code]
        assert set(group["TRIPMODE"]) <= want, (code, set(group["TRIPMODE"]), want)


def test_raw_mode_codes_cannot_be_pooled_but_categories_can(trips):
    raw = {w: t["TRPTRANS"].value_counts(normalize=True) for w, t in trips.items()}
    # walking is 20 in 2022 and 01 in 2017; the raw code 20 in 2017 is a boat
    assert raw[2017]["01"] > 0.05 and raw[2022]["20"] > 0.05
    assert raw[2017].get("20", 0) < 0.001
    shares = {}
    for wave, t in trips.items():
        cat = harmonize.apply(t["TRPTRANS"], "mode", wave)
        shares[wave] = cat.value_counts(normalize=True)
        assert cat.notna().mean() > 0.999
    assert 0.05 < shares[2017]["walk"] < 0.15 and 0.05 < shares[2022]["walk"] < 0.15
