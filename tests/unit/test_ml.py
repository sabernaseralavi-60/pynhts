from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pynhts import ml


@pytest.fixture
def frame():
    return pd.DataFrame({
        "HOUSEID": ["A", "A", "A", "B", "C", "C"],
        "age": [30.0, 8.0, np.nan, 50.0, 41.0, 12.0],
        "mode": pd.array(["03", "01", "03", "06", "03", "01"], dtype="string"),
        "purpose": pd.array(["HBW", "HBO", "HBW", "NHB", pd.NA, "HBO"], dtype="string"),
        "w": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
    })


def test_onehot_ordinal_target_and_weights(frame):
    a = ml.to_arrays(frame, ["age", "mode"], target="purpose", weight="w")
    # rows with NA in a feature (row 2) or the target (row 4) are dropped
    assert list(a.index) == [0, 1, 3, 5]
    assert a.feature_names == ["age", "mode=01", "mode=03", "mode=06"]
    np.testing.assert_array_equal(a.X[:, 1:].sum(axis=1), 1)  # one active code per row
    assert a.X.dtype == np.float32 and a.X.shape == (4, 4)
    assert a.classes == ["HBO", "HBW", "NHB"] and a.y.tolist() == [1, 0, 2, 0]
    assert a.sample_weight.mean() == pytest.approx(1.0)
    X, y, w = a.as_tuple()
    assert X is a.X and y is a.y and w is a.sample_weight


def test_ordinal_and_unnormalised_weight(frame):
    a = ml.to_arrays(frame, ["mode"], weight="w", encode="ordinal", normalize_weight=False,
                     dropna=True)
    assert a.feature_names == ["mode"] and a.y is None
    assert a.X[:, 0].tolist() == [1.0, 0.0, 1.0, 2.0, 1.0, 0.0]  # sorted codes 01<03<06
    assert a.sample_weight.tolist() == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    assert a.categories == {"mode": ["01", "03", "06"]}


def test_numeric_target_keeps_values(frame):
    a = ml.to_arrays(frame, ["mode"], target="age")
    assert a.y.dtype == np.float64 and a.classes is None


def test_errors(frame):
    with pytest.raises(ValueError, match="not in the frame"):
        ml.to_arrays(frame, ["nope"])
    with pytest.raises(ValueError, match="contain NA"):
        ml.to_arrays(frame, ["age"], dropna=False)
    with pytest.raises(ValueError, match="no rows"):
        ml.to_arrays(frame.assign(age=np.nan), ["age"])


def test_household_edges(frame):
    e = ml.household_edges(frame)
    # household A has 3 persons -> 6 ordered pairs; C has 2 -> 2; B is alone -> 0
    assert e.shape == (2, 8) and e.dtype == np.int64
    pairs = set(zip(e[0].tolist(), e[1].tolist(), strict=True))
    assert (0, 1) in pairs and (1, 0) in pairs and (4, 5) in pairs and (0, 3) not in pairs
    assert all(a != b for a, b in pairs)
    assert ml.household_edges(frame.iloc[[3]]).shape == (2, 0)
    with pytest.raises(ValueError):
        ml.household_edges(frame.drop(columns="HOUSEID"))


def test_to_torch_roundtrip(frame):
    torch = pytest.importorskip("torch")
    a = ml.to_arrays(frame, ["age"], target="purpose", weight="w")
    t = ml.to_torch(a)
    assert isinstance(t["X"], torch.Tensor) and t["X"].shape == (4, 1)
    assert t["y"].dtype == torch.int64 and t["w"].dtype == torch.float32
