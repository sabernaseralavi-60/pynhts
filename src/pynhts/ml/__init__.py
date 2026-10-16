"""Bridge from NHTS tables to machine-learning libraries.

NumPy is the only requirement. PyTorch and PyTorch Geometric are imported lazily, only by the
functions that need them, and raise a clear error when they are not installed.

>>> import pynhts                                                   # doctest: +SKIP
>>> from pynhts import ml                                           # doctest: +SKIP
>>> trips = pynhts.load(2017).trips(["TRPMILES", "TRPTRANS", "R_AGE"])   # doctest: +SKIP
>>> arr = ml.to_arrays(trips, ["TRPMILES", "R_AGE"], target="TRPTRANS")   # doctest: +SKIP
>>> X, y, w = arr.X, arr.y, arr.sample_weight                       # doctest: +SKIP
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd
from numpy.typing import NDArray

Encoding = Literal["onehot", "ordinal"]


@dataclass(frozen=True)
class Arrays:
    """Model-ready arrays and the metadata needed to interpret them."""

    X: NDArray[Any]
    y: NDArray[Any] | None
    sample_weight: NDArray[np.float64] | None
    feature_names: list[str]
    index: pd.Index
    classes: list[str] | None = None
    categories: dict[str, list[str]] = field(default_factory=dict)

    def as_tuple(self) -> tuple[NDArray[Any], NDArray[Any] | None, NDArray[np.float64] | None]:
        """``(X, y, sample_weight)``, the argument order of scikit-learn's ``fit``."""
        return self.X, self.y, self.sample_weight


def to_arrays(
    frame: pd.DataFrame,
    features: Sequence[str],
    target: str | None = None,
    *,
    weight: str | None = None,
    encode: Encoding = "onehot",
    dropna: bool = True,
    normalize_weight: bool = True,
    dtype: type[np.floating[Any]] = np.float32,
) -> Arrays:
    """Turn a table from :class:`pynhts.NHTSData` into arrays for scikit-learn or PyTorch.

    Coded (string) feature columns are one-hot encoded (``encode="onehot"``, one column per
    observed code, named ``COLUMN=code``) or mapped to integer codes (``"ordinal"``, codes
    sorted, so that ``"01" < "02"``). Numeric columns pass through. A string target becomes an
    integer class index with the sorted class list in :attr:`Arrays.classes`.

    Args:
        frame: Source table (use ``missing="nan"`` when loading so that survey codes are NA).
        features: Feature column names.
        target: Optional target column.
        weight: Optional weight column, returned as ``sample_weight``. The survey weight is a
            sampling weight; whether it is appropriate as a training weight is a modelling
            decision, not something this function decides for you.
        encode: ``"onehot"`` or ``"ordinal"`` for string feature columns.
        dropna: Drop rows with an NA in any feature, the target or the weight; otherwise raise.
        normalize_weight: Rescale the weight to mean 1 (keeps learning rates comparable).
        dtype: Floating dtype of ``X``.

    Raises:
        ValueError: unknown column, NA present with ``dropna=False``, or no rows left.
    """
    needed = [*features, *([target] if target else []), *([weight] if weight else [])]
    missing = [c for c in needed if c not in frame.columns]
    if missing:
        raise ValueError(f"columns not in the frame: {missing}")
    sub = frame[list(dict.fromkeys(needed))]
    bad = sub.isna().any(axis=1)
    if bad.any():
        if not dropna:
            raise ValueError(f"{int(bad.sum())} rows contain NA; load with missing='nan' and "
                             "pass dropna=True, or impute first")
        sub = sub.loc[~bad]
    if sub.empty:
        raise ValueError("no rows left after dropping NA")

    blocks: list[NDArray[Any]] = []
    names: list[str] = []
    categories: dict[str, list[str]] = {}
    for col in features:
        s = sub[col]
        if pd.api.types.is_numeric_dtype(s) and not isinstance(s.dtype, pd.StringDtype):
            blocks.append(s.to_numpy(dtype=dtype).reshape(-1, 1))
            names.append(col)
            continue
        cats = sorted(s.astype(str).unique())
        categories[col] = cats
        codes = pd.Categorical(s.astype(str), categories=cats).codes
        if encode == "ordinal":
            blocks.append(codes.astype(dtype).reshape(-1, 1))
            names.append(col)
        else:
            onehot = np.zeros((len(s), len(cats)), dtype=dtype)
            onehot[np.arange(len(s)), codes] = 1
            blocks.append(onehot)
            names.extend(f"{col}={c}" for c in cats)
    X = np.hstack(blocks) if blocks else np.empty((len(sub), 0), dtype=dtype)

    y: NDArray[Any] | None = None
    classes: list[str] | None = None
    if target:
        t = sub[target]
        if pd.api.types.is_numeric_dtype(t) and not isinstance(t.dtype, pd.StringDtype):
            y = t.to_numpy(dtype=np.float64)
        else:
            classes = sorted(t.astype(str).unique())
            y = pd.Categorical(t.astype(str), categories=classes).codes.astype(np.int64)

    w: NDArray[np.float64] | None = None
    if weight:
        w = sub[weight].to_numpy(dtype=np.float64)
        if normalize_weight:
            w = w / w.mean()
    return Arrays(X, y, w, names, sub.index, classes, categories)


def to_torch(arrays: Arrays) -> dict[str, Any]:
    """Convert :class:`Arrays` to a dict of PyTorch tensors (``X``, and ``y``/``w`` if present).

    Raises:
        ImportError: PyTorch is not installed.
    """
    try:
        import torch
    except ImportError as exc:  # pragma: no cover - exercised only without torch
        raise ImportError("to_torch needs PyTorch: pip install torch") from exc
    out: dict[str, Any] = {"X": torch.from_numpy(np.ascontiguousarray(arrays.X))}
    if arrays.y is not None:
        out["y"] = torch.from_numpy(np.ascontiguousarray(arrays.y))
    if arrays.sample_weight is not None:
        out["w"] = torch.from_numpy(arrays.sample_weight.astype(np.float32))
    return out


def household_edges(persons: pd.DataFrame) -> NDArray[np.int64]:
    """Edges linking every ordered pair of different persons in the same household.

    Args:
        persons: A person table with a ``HOUSEID`` column.

    Returns:
        ``edge_index`` of shape ``(2, E)`` whose entries are row positions in ``persons``
        (the COO format used by PyTorch Geometric).
    """
    if "HOUSEID" not in persons.columns:
        raise ValueError("persons must contain HOUSEID")
    codes = pd.factorize(persons["HOUSEID"].to_numpy())[0]
    order = np.argsort(codes, kind="stable")
    sizes = np.bincount(codes)
    starts = np.concatenate(([0], np.cumsum(sizes)[:-1]))
    src: list[NDArray[np.int64]] = []
    dst: list[NDArray[np.int64]] = []
    for start, size in zip(starts, sizes, strict=True):
        if size < 2:
            continue
        members = order[start:start + size]
        a, b = np.meshgrid(members, members, indexing="ij")
        keep = a != b
        src.append(a[keep])
        dst.append(b[keep])
    if not src:
        return np.empty((2, 0), dtype=np.int64)
    return np.vstack([np.concatenate(src), np.concatenate(dst)]).astype(np.int64)


def to_pyg(arrays: Arrays, edge_index: NDArray[np.int64]) -> Any:
    """Build a ``torch_geometric.data.Data`` object from arrays and an ``edge_index``.

    Raises:
        ImportError: PyTorch Geometric is not installed.
    """
    try:
        import torch
        from torch_geometric.data import Data
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "to_pyg needs torch_geometric: pip install torch torch_geometric"
        ) from exc
    tensors = to_torch(arrays)
    return Data(x=tensors["X"], y=tensors.get("y"), edge_index=torch.from_numpy(edge_index),
                w=tensors.get("w"))


__all__ = ["Arrays", "household_edges", "to_arrays", "to_pyg", "to_torch"]
