"""Unit tests for the JKn engine against brute-force row-level computations."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pynhts.stats import JKN_FACTOR, Survey, jackknife_variance, ratio_across, t_cdf, t_ppf


# -- Student t ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("p", "df", "expected"),
    [
        (0.975, 98, 1.984467),
        (0.975, 10, 2.228139),
        (0.975, 1, 12.706205),
        (0.975, 1000, 1.962339),
        (0.995, 5, 4.032143),
        (0.95, 30, 1.697261),
    ],
)
def test_t_ppf_matches_reference_values(p, df, expected):
    assert t_ppf(p, df) == pytest.approx(expected, abs=2e-6)


def test_t_ppf_symmetry_roundtrip_and_limits():
    assert t_ppf(0.5, 7) == 0.0
    assert t_ppf(0.025, 98) == pytest.approx(-t_ppf(0.975, 98))
    assert t_cdf(t_ppf(0.9, 12.5), 12.5) == pytest.approx(0.9, abs=1e-12)
    assert t_ppf(0.975, 1e7) == pytest.approx(1.959964, abs=1e-5)
    with pytest.raises(ValueError):
        t_ppf(1.0, 5)
    with pytest.raises(ValueError):
        t_ppf(0.9, 0)


# -- jackknife ----------------------------------------------------------------------------
def test_jackknife_variance_formula_and_vectorised_form():
    reps = np.arange(98, dtype=float).reshape(98, 1) @ np.array([[1.0, 2.0]])
    full = np.array([48.5, 97.0])
    v = jackknife_variance(full, reps)
    expected = JKN_FACTOR * ((reps - full) ** 2).sum(axis=0)
    np.testing.assert_allclose(v, expected)
    assert JKN_FACTOR == pytest.approx(6 / 7)


def test_jackknife_variance_needs_98_replicates():
    with pytest.raises(ValueError, match="98"):
        jackknife_variance(1.0, np.ones(10))


# -- Survey vs brute force ----------------------------------------------------------------
@pytest.fixture
def toy():
    rng = np.random.default_rng(7)
    n_units = 60
    w = rng.uniform(50, 500, n_units)
    reps = w[:, None] * rng.uniform(0.85, 1.15, (n_units, 98))
    counts = rng.integers(0, 5, n_units)  # trips per person-day, some zero
    unit = np.repeat(np.arange(n_units), counts)
    n = len(unit)
    rows = pd.DataFrame({
        "y": rng.normal(10, 3, n),
        "x": rng.uniform(1, 4, n),
        "g": rng.choice(["a", "b", "c"], n),
        "flag": rng.random(n) < 0.4,
    })
    rows.loc[rng.choice(n, 7, replace=False), "y"] = np.nan
    return rows, unit, w, reps


def _brute(rows, unit, w, reps, num, den=None, mask=None):
    """Explicit row-level loops (the textbook formula, no unit aggregation)."""
    mask = np.ones(len(rows), bool) if mask is None else mask
    def tot(wvec):
        s = np.zeros(wvec.shape[1] if wvec.ndim > 1 else 1)
        for i in range(len(rows)):
            if mask[i]:
                s = s + wvec[unit[i]] * num[i] * (1 if den is None else 1)
        return s
    def tot2(wvec, v):
        out = 0.0 if wvec.ndim == 1 else np.zeros(wvec.shape[1])
        for i in range(len(rows)):
            if mask[i]:
                out = out + wvec[unit[i]] * v[i]
        return out
    if den is None:
        full, rr = tot2(w, num), tot2(reps, num)
    else:
        full = tot2(w, num) / tot2(w, den)
        rr = tot2(reps, num) / tot2(reps, den)
    return full, np.sqrt(JKN_FACTOR * np.sum((rr - full) ** 2))


def test_total_matches_brute_force(toy):
    rows, unit, w, reps = toy
    s = Survey(rows, unit, w, reps)
    valid = rows["y"].notna().to_numpy()
    full, se = _brute(rows, unit, w, reps, rows["y"].fillna(0).to_numpy(), mask=valid)
    r = s.total("y").iloc[0]
    assert r["estimate"] == pytest.approx(full) and r["se"] == pytest.approx(se)
    assert r["n"] == valid.sum()
    assert r["moe"] == pytest.approx(t_ppf(0.975, 98) * se)
    assert r["ci_low"] == pytest.approx(full - r["moe"])


def test_mean_proportion_ratio_domain_and_na_handling(toy):
    rows, unit, w, reps = toy
    s = Survey(rows, unit, w, reps)
    y, x = rows["y"], rows["x"]
    ok = y.notna().to_numpy()
    ones = np.ones(len(rows))
    f, se = _brute(rows, unit, w, reps, y.fillna(0).to_numpy(), ones, mask=ok)
    m = s.mean("y").iloc[0]
    assert m["estimate"] == pytest.approx(f) and m["se"] == pytest.approx(se)

    dom = (rows["g"] == "b").to_numpy()
    f, se = _brute(rows, unit, w, reps, y.fillna(0).to_numpy(), ones, mask=ok & dom)
    m = s.mean("y", domain=rows["g"] == "b").iloc[0]
    assert m["estimate"] == pytest.approx(f) and m["se"] == pytest.approx(se)

    f, se = _brute(rows, unit, w, reps, rows["flag"].astype(float).to_numpy(), ones)
    p = s.proportion(rows["flag"]).iloc[0]
    assert p["estimate"] == pytest.approx(f) and p["se"] == pytest.approx(se)
    assert 0 < p["estimate"] < 1

    f, se = _brute(rows, unit, w, reps, y.fillna(0).to_numpy(), x.to_numpy(), mask=ok)
    r = s.ratio("y", "x").iloc[0]
    assert r["estimate"] == pytest.approx(f) and r["se"] == pytest.approx(se)


def test_by_groups_partition_the_total_and_keep_labels(toy):
    rows, unit, w, reps = toy
    s = Survey(rows, unit, w, reps)
    whole = s.total("y").iloc[0]["estimate"]
    parts = s.total("y", by="g")
    assert list(parts["g"]) == ["a", "b", "c"]
    assert parts["estimate"].sum() == pytest.approx(whole)
    assert parts["n"].sum() == rows["y"].notna().sum()
    two = s.total("y", by=["g", "flag"])
    assert len(two) == 6 and two["estimate"].sum() == pytest.approx(whole)


def test_count_when_no_variable_and_na_group_dropped(toy):
    rows, unit, w, reps = toy
    rows = rows.copy()
    rows.loc[rows.index[:5], "g"] = None
    s = Survey(rows, unit, w, reps)
    all_rows = s.total().iloc[0]["estimate"]
    by = s.total(by="g")
    assert by["estimate"].sum() < all_rows  # rows with a missing group are excluded
    brute, _ = _brute(rows, unit, w, reps, np.ones(len(rows)))
    assert all_rows == pytest.approx(brute)


def test_row_to_unit_aggregation_equals_expanded_replicates(toy):
    """Trips sharing one person-day weight: unit aggregation == per-trip replicate matrix."""
    rows, unit, w, reps = toy
    s = Survey(rows, unit, w, reps)
    expanded = Survey(rows, np.arange(len(rows)), w[unit], reps[unit])
    a, b = s.mean("y").iloc[0], expanded.mean("y").iloc[0]
    assert a["estimate"] == pytest.approx(b["estimate"]) and a["se"] == pytest.approx(b["se"])


def test_ratio_across_two_surveys(toy):
    rows, unit, w, reps = toy
    persons = Survey(rows, unit, w, reps)
    hh = Survey(pd.DataFrame({"k": np.arange(10)}), np.arange(10), w[:10] * 3, reps[:10] * 3)
    r = ratio_across(persons, "y", hh).iloc[0]
    n_full, n_rep = persons.total_replicates("y")
    d_full, d_rep = hh.total_replicates()
    full = n_full / d_full
    se = np.sqrt(JKN_FACTOR * np.sum((n_rep / d_rep - full) ** 2))
    assert r["estimate"] == pytest.approx(full) and r["se"] == pytest.approx(se)


def test_validation_errors(toy):
    rows, unit, w, reps = toy
    with pytest.raises(ValueError):
        Survey(rows, unit[:-1], w, reps)
    s = Survey(rows, unit, w, reps)
    with pytest.raises(ValueError):
        s.total("y", domain=[True, False])
    with pytest.raises(ValueError):
        s.proportion([True])
    assert Survey(rows, unit, w, reps, level=0.90).total("y").iloc[0]["moe"] < \
        s.total("y").iloc[0]["moe"]
