"""Activity diary on hand-built days (minute 0 = 04:00)."""

from __future__ import annotations

import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")

from pynhts import viz  # noqa: E402


def trips():
    rows = [
        ("A", "01", "01", "01", "03", "0800", "0830"),
        ("A", "01", "02", "03", "01", "1700", "1730"),
        ("C", "01", "01", "01", "11", "2330", "0015"),  # ends after midnight
        ("D", "01", "01", "01", "03", "9999", "0830"),  # unreadable time
    ]
    return pd.DataFrame(rows, columns=["HOUSEID", "PERSONID", "TDTRPNUM", "WHYFROM", "WHYTO",
                                       "STRTTIME", "ENDTIME"])


def persons():
    return pd.DataFrame({
        "HOUSEID": ["A", "B", "C", "D"], "PERSONID": ["01"] * 4,
        "WTPERFIN": [2.0, 1.0, 1.0, 5.0], "grp": ["x", "x", "y", "y"],
    })


def at(p, minute, state):
    return float(p.loc[p["minute"] == minute, state].iloc[0])


def test_hand_computed_profile():
    p = viz.activity_profile(trips(), persons()[persons()["grp"] == "x"])
    assert len(p) == 1440
    assert at(p, 0, "Home") == 1.0
    assert at(p, 250, "In transit") == pytest.approx(2 / 3)   # 08:10
    assert at(p, 250, "Home") == pytest.approx(1 / 3)          # B never travels
    assert at(p, 300, "Work") == pytest.approx(2 / 3)
    assert at(p, 779, "Work") == pytest.approx(2 / 3)
    assert at(p, 790, "In transit") == pytest.approx(2 / 3)
    assert at(p, 900, "Home") == 1.0
    states = [c for c in p.columns if c != "minute"]
    np.testing.assert_allclose(p[states].sum(axis=1), 1.0)
    assert p.attrs["population"].iloc[0] == 3.0


def test_midnight_crossing_and_dropped_person():
    p = viz.activity_profile(trips(), persons(), by="grp")
    y = p[p["grp"] == "y"]
    assert at(y, 1170 + 5, "In transit") == 1.0     # 23:35, only C counted (D dropped)
    assert at(y, 1215 + 5, "Shopping and services") == 1.0
    assert at(y, 100, "Home") == 1.0
    assert p.attrs["n_dropped"] == 1
    assert y["Home"].iloc[0] == 1.0
    assert p.attrs["population"]["y"] == 1.0


def test_no_trip_persons_can_be_excluded():
    p = viz.activity_profile(trips(), persons()[persons()["grp"] == "x"], no_trip_state=None)
    assert at(p, 250, "In transit") == 1.0
    assert at(p, 0, "Home") == 1.0


def test_accepts_tour_result_and_rejects_bad_input():
    from pynhts.tours import build_tours

    good = trips().iloc[:2]
    res = build_tours(good.assign(TRPTRANS="03"))
    p = viz.activity_profile(res, persons()[persons()["grp"] == "x"])
    assert at(p, 300, "Work") == pytest.approx(2 / 3)
    with pytest.raises(ValueError, match="required columns"):
        viz.activity_profile(good.drop(columns="ENDTIME"), persons())
    with pytest.raises(ValueError, match="two groups"):
        viz.activity_profile(good, persons(), groups={"Home": ("01",), "Work": ("01",)})


def test_plot_returns_figure_and_saves(tmp_path):
    out = tmp_path / "f.png"
    fig = viz.plot_activity_diary(trips(), persons(), by="grp", title="t", savepath=out)
    assert out.stat().st_size > 1000
    assert len(fig.axes) >= 2
    fig2 = viz.plot_activity_diary(trips(), persons()[persons()["grp"] == "x"])
    assert fig2.axes[0].get_ylim() == (0, 100)
