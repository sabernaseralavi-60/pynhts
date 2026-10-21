r"""Camera-ready tables from survey estimates: LaTeX (``booktabs``), Markdown and plain frames.

The estimators of :class:`pynhts.stats.Survey` return DataFrames with ``estimate``, ``se``,
``moe``, ``ci_low``, ``ci_high``, ``cv`` and ``n`` (plus the group columns when ``by`` is used).
Collect them as :class:`Row` objects, one per line of the table:

>>> from pynhts import tables                                                # doctest: +SKIP
>>> rows = [                                                                 # doctest: +SKIP
...     tables.Row("Tours (millions)", s.total(), scale=1e-6, digits=1),
...     tables.Row("Work-based share (%)", s.proportion(c), scale=100),
...     tables.Row("Sex", s.proportion(c, by="R_SEX"), scale=100, group_labels=labels),
... ]
>>> table = tables.build(rows)                                              # doctest: +SKIP
>>> print(tables.to_latex(table, caption="Work tours", label="tab:work"))    # doctest: +SKIP

Conventions: values are rounded as Python formats the binary value; the margin of error is printed
with the same decimals as its estimate; NA prints as an en dash; ``n`` is the unweighted row
count.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

Style = Literal["pm", "ci", "se", "estimate"]

_LATEX_ESCAPES = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
    "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}


@dataclass(frozen=True)
class Row:
    """One line (or, with ``by``, one block of lines) of a table.

    Attributes:
        label: Row label (a prefix for grouped results: ``"Sex: Female"``).
        result: A one-row estimate frame, or several rows from a ``by=`` call.
        scale: Multiplier applied to estimate, standard error, margin of error and interval
            (``100`` for percentages, ``1e-6`` for millions).
        digits: Decimals printed.
        group_labels: For grouped results: ``code -> text`` for the first group column.
    """

    label: str
    result: pd.DataFrame
    scale: float = 1.0
    digits: int = 1
    group_labels: Mapping[object, str] | None = None


def _num(x: float, digits: int, thousands: bool = True) -> str:
    if x is None or not np.isfinite(x):
        return "–"
    s = f"{x:,.{digits}f}" if thousands else f"{x:.{digits}f}"
    return s[1:] if s.startswith("-") and float(s.replace(",", "")) == 0 else s


def _cell(r: pd.Series, row: Row, style: Style) -> str:
    sc, d = row.scale, row.digits
    est = _num(r["estimate"] * sc, d)
    if style == "estimate":
        return est
    if style == "se":
        return f"{est} ({_num(r['se'] * sc, d)})"
    if style == "ci":
        return f"{est} [{_num(r['ci_low'] * sc, d)}, {_num(r['ci_high'] * sc, d)}]"
    return f"{est} ± {_num(r['moe'] * sc, d)}"


def build(
    rows: Sequence[Row],
    *,
    style: Style = "pm",
    show_n: bool = True,
    level: float = 0.95,
    header: tuple[str, str, str] = ("Characteristic", "Estimate", "$n$"),
) -> pd.DataFrame:
    """Format :class:`Row` objects into a text table.

    Args:
        rows: Lines of the table.
        style: ``"pm"`` estimate ± margin of error; ``"se"`` estimate (standard error);
            ``"ci"`` estimate [low, high]; ``"estimate"`` estimate only.
        show_n: Add the unweighted sample size column.
        level: Confidence level (only used in the table note, see :func:`note`).
        header: Column titles (characteristic, estimate, n).

    Returns:
        A DataFrame of strings with the columns of ``header`` (without ``n`` when ``show_n`` is
        false). The ``level`` and ``style`` are kept in ``attrs`` for :func:`note`.
    """
    out: list[tuple[str, str, str]] = []
    for row in rows:
        res = row.result.reset_index(drop=True)
        grouped = [c for c in res.columns if c not in _STAT_COLUMNS]
        for i in range(len(res)):
            r = res.iloc[i]
            label = row.label
            if grouped:
                key = r[grouped[0]]
                text = (row.group_labels or {}).get(key, str(key))
                label = f"{row.label}: {text}" if row.label else text
            out.append((label, _cell(r, row, style), f"{int(r['n']):,}"))
    frame = pd.DataFrame(out, columns=list(header))
    if not show_n:
        frame = frame.drop(columns=header[2])
    frame.attrs.update(style=style, level=level)
    designs = {
        str(r.result.attrs.get("pynhts", {}).get("design", "")) for r in rows
    } - {""}
    if len(designs) == 1:
        frame.attrs["design"] = designs.pop()
    elif designs:  # rows from different waves: the note must not claim one method
        frame.attrs["design"] = "; ".join(sorted(designs))
    result: pd.DataFrame = frame
    return result


_STAT_COLUMNS = {"estimate", "se", "moe", "ci_low", "ci_high", "cv", "n"}


def note(frame: pd.DataFrame) -> str:
    """Standard footnote for a table made by :func:`build`."""
    style, level = frame.attrs.get("style", "pm"), frame.attrs.get("level", 0.95)
    pct = f"{100 * level:g}%"
    what = {
        "pm": f"Entries are weighted estimates ± the {pct} margin of error",
        "se": "Entries are weighted estimates with standard errors in parentheses",
        "ci": f"Entries are weighted estimates with {pct} confidence intervals in brackets",
        "estimate": "Entries are weighted estimates",
    }[style]
    design = frame.attrs.get("design")
    how = f" (standard errors: {design})" if design else ""
    return f"{what}{how}. $n$ is the unweighted number of records."


def latex_escape(text: str) -> str:
    """Escape LaTeX special characters."""
    return "".join(_LATEX_ESCAPES.get(ch, ch) for ch in text)


def to_latex(
    frame: pd.DataFrame,
    *,
    caption: str | None = None,
    label: str | None = None,
    notes: str | None = None,
    placement: str = "tbp",
    align: str | None = None,
) -> str:
    r"""Render a table made by :func:`build` as a ``booktabs`` ``table`` environment.

    Requires ``\usepackage{booktabs}``. Cell text is escaped; the ``±`` sign becomes ``$\pm$``
    and the en dash ``--``. The first column is left-aligned, the others right-aligned.

    Args:
        frame: Output of :func:`build`.
        caption: Table caption (escaped).
        label: LaTeX label, e.g. ``"tab:work"``.
        notes: Text under the table; ``None`` uses :func:`note`, ``""`` omits it.
        placement: Float placement.
        align: Column specification (default ``l`` followed by ``r`` columns).

    Returns:
        The LaTeX source.
    """
    def tex(s: str) -> str:
        s = latex_escape(s).replace(r"\$n\$", "$n$")
        return s.replace("±", r"$\pm$").replace("–", "--")

    spec = align or "l" + "r" * (frame.shape[1] - 1)
    lines = [rf"\begin{{table}}[{placement}]", r"\centering"]
    if caption:
        lines.append(rf"\caption{{{latex_escape(caption)}}}")
    if label:
        lines.append(rf"\label{{{label}}}")
    lines += [rf"\begin{{tabular}}{{{spec}}}", r"\toprule"]
    lines.append(" & ".join(tex(str(c)) for c in frame.columns) + r" \\")
    lines.append(r"\midrule")
    for rec in frame.itertuples(index=False):
        lines.append(" & ".join(tex(str(v)) for v in rec) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    text = note(frame) if notes is None else notes
    if text:
        lines += [r"\par\smallskip", rf"{{\footnotesize {tex(text)}}}"]
    lines.append(r"\end{table}")
    return "\n".join(lines) + "\n"


def to_markdown(frame: pd.DataFrame, *, notes: str | None = None) -> str:
    """Render a table made by :func:`build` as a GitHub-flavoured Markdown table.

    The first column is left-aligned, the others right-aligned. ``|`` inside cells is escaped.
    """
    def md(s: str) -> str:
        return s.replace("|", r"\|").replace("$n$", "n")

    head = "| " + " | ".join(md(str(c)) for c in frame.columns) + " |"
    sep = "| :-- | " + " | ".join("--:" for _ in frame.columns[1:]) + " |"
    body = ["| " + " | ".join(md(str(v)) for v in rec) + " |"
            for rec in frame.itertuples(index=False)]
    text = md(note(frame)) if notes is None else notes
    parts = [head, sep, *body]
    if text:
        parts += ["", f"*{text}*"]
    return "\n".join(parts) + "\n"
