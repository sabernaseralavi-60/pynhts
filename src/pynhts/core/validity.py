"""What counts as a real answer: :func:`valid` and :func:`answer_status`.

NHTS columns carry three different kinds of "no value": a **skip** (code ``-1``: the question did not
apply to this person), a **non-answer** (``-7`` refused, ``-8`` don't know, ``-9`` not ascertained, and
the ``-77``/``-88`` variants of numeric columns) and a real **blank**. In coded (string) columns
pynhts keeps ``-1`` as a category by default, so ``Series.notna()`` is *not* a validity test there:
in the 2009 person file it counts 308,619 non-missing ``WKFTPT`` values where only 138,786 persons gave a
real answer. Use :func:`valid` for the answer mask and :func:`answer_status` to see the reasons.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SKIP = "skip"
NONANSWER = "nonanswer"
BLANK = "blank"
ANSWERED = "answered"


def answer_status(series: pd.Series) -> pd.Series:
    """Classify every value as ``answered``, ``skip``, ``nonanswer`` or ``blank``.

    Works on string-coded columns (``"-1"``, ``"-7"``...) and on numeric columns loaded with
    ``missing="keep"`` (``-1``, ``-7``, ``-77``...). A numeric value of NaN is ``blank`` (it may have
    been masked by the loader; use ``missing="keep"`` to tell the reasons apart).
    """
    if pd.api.types.is_numeric_dtype(series):
        num = pd.to_numeric(series, errors="coerce")
        out = np.where(
            num.isna(), BLANK, np.where(num == -1, SKIP, np.where(num < 0, NONANSWER, ANSWERED))
        )
    else:
        text = series.astype("string")
        neg = text.str.startswith("-").fillna(False).astype(bool)
        skip = text.eq("-1").fillna(False).astype(bool)
        out = np.where(text.isna(), BLANK, np.where(skip, SKIP, np.where(neg, NONANSWER, ANSWERED)))
    return pd.Series(out, index=series.index, dtype="string")


def valid(series: pd.Series) -> pd.Series:
    """Boolean mask of values that are real answers (not NA, not a skip, not a non-answer code).

    Examples:
        >>> import pandas as pd
        >>> valid(pd.Series(["01", "-1", "-7", None, "02"])).tolist()
        [True, False, False, False, True]
    """
    return answer_status(series).eq(ANSWERED)
