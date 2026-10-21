from __future__ import annotations

import pandas as pd
import pytest

from pynhts import recipes
from pynhts.recipes.base import STATUSES, Target, classify, comparison_frame, load_spec


def _t(published=8.60, moe=0.10, decimals=2, expected="reproduced"):
    return Target("x", "3a", "x", 1.0, decimals, published, moe, "f", expected)


def test_classify_rules():
    t = _t()
    assert classify(t, 8.6022, 0.1019) == "reproduced"
    assert classify(t, 8.6022, 0.2) == "estimate_only"
    assert classify(t, 8.7, 0.1) == "not_reproduced"
    assert classify(t, 8.604, 0.1) == "reproduced"  # within half a unit of the last digit
    assert classify(_t(moe=None), 8.60, 5.0) == "reproduced"  # printed "-": MOE not compared
    big = _t(published=985.0, moe=985.0, decimals=0)
    assert classify(big, 985.0, 985.5351) == "reproduced"  # 0.05 percent tolerance on MOE
    assert classify(big, 985.0, 987.0) == "estimate_only"
    zero = _t(published=47657, moe=0, decimals=0)
    assert classify(zero, 47657.06, 0.009) == "reproduced"


def test_packaged_spec_is_well_formed():
    spec = load_spec("stt2017")
    ids = [t.id for t in spec.targets]
    assert len(ids) == len(set(ids)) == 24
    from pynhts.recipes.stt2017 import COMPUTE
    assert {t.compute for t in spec.targets} <= set(COMPUTE)
    mr = load_spec("mcnally_rafiq2021")
    from pynhts.recipes.mcnally_rafiq2021 import COMPUTE as MR_COMPUTE
    assert {t.compute for t in mr.targets} <= set(MR_COMPUTE)
    assert len({t.id for t in mr.targets}) == len(mr.targets)
    assert all(t.note for t in mr.targets if t.expected != "reproduced")
    assert all(t.expected in STATUSES for t in spec.targets)
    gaps = [t for t in spec.targets if t.expected != "reproduced"]
    assert all(t.note for t in gaps)  # every known gap is explained in the file
    assert "McGuckin" in spec.citation


def test_unknown_recipe_and_available():
    assert recipes.available() == ["mcnally_rafiq2021", "stt2017", "ug2022"]
    with pytest.raises(ValueError):
        load_spec("nope")
    with pytest.raises(ValueError):
        recipes.run("nope", None)  # type: ignore[arg-type]


def test_comparison_frame_and_markdown():
    spec = load_spec("stt2017")
    results = {t.id: (t.published, t.moe or 0.0) for t in spec.targets}
    frame = comparison_frame(spec, results)
    assert (frame["status"] == "reproduced").all()
    md = recipes.to_markdown(frame)
    assert md.startswith("| Table |") and md.count("\n") == len(frame) + 2
    assert isinstance(frame, pd.DataFrame)
