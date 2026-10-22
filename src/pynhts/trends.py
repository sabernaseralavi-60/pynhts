"""Cross-wave comparison that refuses the common mistakes.

Two workflows, kept apart on purpose:

1. **Harmonized descriptive trends** (:func:`trip_shares`, :func:`wave_means`): each wave is analysed
   on its own with its own weights and variance design, then the estimates are put side by side.
   Nothing is pooled.
2. **Pooled modelling** (:func:`pool`): rows of several waves are stacked with a ``wave`` column,
   restricted to concepts whose comparability is established, with weights rescaled *within* wave.
   The caller accepts the assumptions listed in the warning.

The waves are independent cross-sections: different households, different sampling frames (random
digit dialling until 2009, address-based since 2017), different modes of collection, a change from
self-reported to routed trip distances between 2009 and 2017, and from 2022 a methods adjustment in
the trip weights. Combining them is not a panel and a naive pooled weight is not a population weight.
"""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

import pynhts
from pynhts import concepts, harmonize
from pynhts.core.flags import PynhtsWarning

_POOL_NOTE = (
    "pooling NHTS waves stacks independent cross-sections: weights are rescaled within wave (w_norm "
    "averages 1 in every wave, so a wave counts by its sample size), not made comparable; the sampling "
    "frame, mode of collection and trip definition changed between waves, and trip distance changed "
    "its measurement; include wave effects and interact wave with the effects you wish to compare"
)


def trip_shares(
    concept: str = "mode",
    waves: Sequence[int] = (2001, 2009, 2017, 2022),
    *,
    level: str = "summary",
    min_age: int | None = 5,
    level_conf: float = 0.95,
) -> pd.DataFrame:
    """Weighted trip shares of a harmonized category (``mode`` or ``purpose_summary``) per wave.

    Each wave is estimated with its own trip weights and variance design (jackknife replicates for
    2001-2017, Taylor series for 2022). ``min_age=5`` drops the 2001 children aged 0-4 so that the
    universes agree (trips of persons with an unknown age are dropped too and are not in the shares).
    Returns one row per wave and category (``share``, ``se``, ``moe``, ``n``).
    """
    if concept not in ("mode", "purpose", "purpose_summary"):
        raise ValueError("concept must be 'mode', 'purpose' or 'purpose_summary'")
    # each crosswalk is defined on its own variable: purpose -> WHYTO (detailed), purpose_summary -> WHYTRP1S
    var = {"mode": "TRPTRANS", "purpose": "WHYTO", "purpose_summary": "WHYTRP1S"}[concept]
    rows: list[dict[str, Any]] = []
    for w in waves:
        d = pynhts.load(w, replicates=True)
        cols = [var] + (["R_AGE"] if min_age is not None else [])
        s = d.survey("trip", cols, level=level_conf)
        kwargs: dict[str, Any] = {"level": level} if concept == "mode" else {}
        cat = harmonize.apply(s.rows[var], concept, w, **kwargs)
        known: np.ndarray[Any, Any] = cat.notna().to_numpy()
        if min_age is not None:
            known = known & (pd.to_numeric(s.rows["R_AGE"]) >= min_age).to_numpy()
        for c in sorted(cat.dropna().unique()):
            hit = ((cat == c).fillna(False)).to_numpy() & known  # same universe as the denominator
            r = s.ratio(hit.astype(float), known.astype(float))
            rows.append(
                {
                    "wave": w,
                    "category": c,
                    "share": float(r["estimate"].iloc[0]),
                    "se": float(r["se"].iloc[0]),
                    "moe": float(r["moe"].iloc[0]),
                    "n": int((hit & known).sum()),
                }
            )
    out = pd.DataFrame(rows)
    out.attrs["note"] = (
        "shares of trips with a known category, per wave; 2017 and 2022 count change-of-mode "
        "segments as trips and 2022 trip weights contain the methods adjustment: compare "
        "shares, not counts"
    )
    return out


def wave_means(
    table: str,
    variable: str,
    waves: Sequence[int] = (2001, 2009, 2017, 2022),
    *,
    min_age: int | None = None,
    level_conf: float = 0.95,
) -> pd.DataFrame:
    """Weighted mean of one variable per wave, each with its own design; warns when not comparable."""
    for w in waves:
        hits = [h for h in concepts.find(variable, w) if h["comparability"] == "N"]
        if hits:
            first = hits[0]["pitfalls"][0] if hits[0].get("pitfalls") else ""
            warnings.warn(
                f"{variable} is NOT comparable across waves (concept dictionary): {first}",
                PynhtsWarning,
                stacklevel=2,
            )
            break
    rows = []
    for w in waves:
        d = pynhts.load(w, replicates=True)
        cols = [variable] + (["R_AGE"] if min_age is not None else [])
        s = d.survey(table, cols, level=level_conf)
        dom = (
            (pd.to_numeric(s.rows["R_AGE"]) >= min_age).to_numpy() if min_age is not None else None
        )
        r = s.mean(variable, domain=dom)
        rows.append(
            {
                "wave": w,
                "mean": float(r["estimate"].iloc[0]),
                "se": float(r["se"].iloc[0]),
                "moe": float(r["moe"].iloc[0]),
                "n": int(r["n"].iloc[0]),
            }
        )
    return pd.DataFrame(rows)


def pool(
    waves: Sequence[int],
    table: str,
    columns: Sequence[str],
    *,
    harmonize_concepts: dict[str, str] | None = None,
    allow_noncomparable: bool = False,
    min_age: int | None = 5,
    allow_raw_codes: bool = False,
) -> pd.DataFrame:
    """Stack several waves of one table for pooled modelling (see the module docstring).

    Args:
        waves: Waves to stack.
        table: Table to load (``"person"``, ``"trip"``...).
        columns: Columns to load. A column whose concept is marked non-comparable (``N``) raises unless
            ``allow_noncomparable``; code-bearing columns must be listed in ``harmonize_concepts``
            (``{"TRPTRANS": "mode"}``), otherwise raw codes would be stacked, which is wrong because
            the same code means different things in different waves.
        harmonize_concepts: ``{column: crosswalk concept}``; the harmonized column is named ``<col>_h``.
        allow_noncomparable: Proceed for ``N`` concepts (distance, trip counts) knowing the consequences.
        min_age: Keep persons (and their trips) aged at least this, default 5, because 2001 also lists
            children aged 0-4 and the other waves do not; ignored for tables without ``R_AGE``. Rows with an
            unknown age are dropped when it is applied. ``None`` keeps everyone.
        allow_raw_codes: Coded columns without a crosswalk raise unless this is True; then their codes are
            only zero-unpadded ("01" and "1" agree), which does not make different meanings agree.

    Returns:
        Stacked rows with ``wave``, ``w`` (original weight), ``w_norm`` (weight / mean weight of the
        wave) and the harmonized columns.
    """
    hc = harmonize_concepts or {}
    frames = []
    for w in waves:
        for col in columns:
            for hit in concepts.find(col, w):
                if hit["comparability"] == "N" and not allow_noncomparable:
                    raise ValueError(
                        f"{col} is not comparable across waves ({hit.get('title', '')}); "
                        "pass allow_noncomparable=True to pool it anyway"
                    )
        d = pynhts.load(w)
        use_age = min_age is not None and "R_AGE" in d.columns(table)
        load = list(columns) + (["R_AGE"] if use_age and "R_AGE" not in columns else [])
        f = d.table(table, load)
        wcol = d.weight_column(table)
        if use_age:
            keep = pd.to_numeric(f["R_AGE"], errors="coerce") >= min_age
            f = f[keep].reset_index(drop=True)
            if "R_AGE" not in columns:
                f = f.drop(columns="R_AGE")
        for col, cw in hc.items():
            f[f"{col}_h"] = harmonize.apply(f[col], cw, w)
            f = f.rename(
                columns={col: f"{col}_raw"}
            )  # a raw code means different things in different waves
        raw = [c for c in columns if c not in hc and str(f[c].dtype) == "string"]
        if raw and not allow_raw_codes:
            raise ValueError(
                f"coded columns {raw} have no crosswalk: raw codes differ between waves; give them in "
                "harmonize_concepts or pass allow_raw_codes=True to stack zero-unpadded codes"
            )
        for col in raw:
            f[col] = f[col].astype("string").str.replace(r"^(-?)0+(?=\d)", r"\1", regex=True)
        f["wave"] = w
        f["w"] = f[wcol]
        f["w_norm"] = f[wcol] / f[wcol].mean()
        frames.append(f.drop(columns=[wcol]))
    out = pd.concat(frames, ignore_index=True)
    warnings.warn(_POOL_NOTE, PynhtsWarning, stacklevel=2)
    out.attrs["pynhts_pooled"] = {"waves": list(waves), "table": table, "note": _POOL_NOTE}
    return out
