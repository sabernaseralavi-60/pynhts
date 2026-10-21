"""Compare and harmonize NHTS waves (2001, 2009, 2017, 2022) without hiding what is lost.

Two tools:

* :func:`compare_waves` lists every variable of two waves and says whether it is the same
  column (same label and same coded values), the same column with other labels, a column whose
  codes changed, or a column that exists in one wave only. It is computed from the codebooks.
* :func:`crosswalk`, :func:`apply` and :func:`category_report` map the codes of the concepts that
  changed the most, **trip purpose** (``purpose``: the detailed WHYTO of 2017 and 2022;
  ``purpose_summary``: WHYTRP1S of all four waves) and **trip mode** (all four waves), to shared
  categories. Every code carries a status (``exact``, ``merge``, ``approximate``, ``only_here``)
  and the reason for it, taken from the 2022 User Guide's Appendix 2 for 2017 and 2022 and checked
  against the codebooks and, for 2001 and 2009, against the codebooks and the data.

>>> from pynhts import harmonize
>>> harmonize.crosswalk("mode").query("wave == 2022")                    # doctest: +SKIP
>>> trips["mode"] = harmonize.apply(trips["TRPTRANS"], "mode", wave=2017)  # doctest: +SKIP
"""

from __future__ import annotations

import re
from functools import cache
from importlib import resources
from typing import Any, Literal

import pandas as pd
import yaml

from pynhts.core.dictionary import dictionary
from pynhts.core.schema import load_schema, wave_tables

MISSING_CODES = frozenset({"-9", "-8", "-7", "-1", "-88", "-77"})
Level = Literal["category", "summary"]
# statuses of a crosswalk row; "nested" = several codes collapse exactly into the category
STATUSES = ("exact", "nested", "merge", "approximate", "only_here")
COMPARABLE = {"exact", "nested"}


@cache
def _load() -> dict[str, Any]:
    ref = resources.files("pynhts") / "harmonize" / "crosswalks.yaml"
    raw: dict[str, Any] = yaml.safe_load(ref.read_text(encoding="utf-8"))
    return raw


def concepts() -> list[str]:
    """Names of the concepts with a curated crosswalk (``crosswalk(name)`` lists them)."""
    return sorted(_load())


def crosswalk(concept: str) -> pd.DataFrame:
    """One row per (wave, code): ``category`` (and ``summary`` for mode), ``status``, ``note``.

    ``variable`` names the NHTS column the codes belong to (``WHYTO``/``WHYFROM`` for purpose,
    ``TRPTRANS`` for mode).
    """
    spec = _spec(concept)
    frame = pd.DataFrame(spec["rows"])
    for col in ("summary", "note"):
        if col not in frame.columns:
            frame[col] = None
    frame.insert(0, "variable", spec["variable"])
    frame.insert(1, "table", spec.get("table", "trip"))
    cols = ["wave", "variable", "table", "code", "hint", "category", "summary", "status", "note"]
    out: pd.DataFrame = frame[cols]
    return out


def concept_info(concept: str) -> dict[str, Any]:
    """Variable(s), table, source and note of a crosswalk concept.

    Keys: ``variable``, ``also`` (further variables with the same codes, e.g. ``WHYFROM``),
    ``table`` (the table the variable lives in), ``source``, ``note``.
    """
    spec = _spec(concept)
    return {
        "variable": spec["variable"], "also": list(spec.get("also", [])),
        "table": spec.get("table", "trip"), "source": spec.get("source", ""),
        "note": str(spec.get("note", "")).strip(),
    }


def _spec(concept: str) -> dict[str, Any]:
    data = _load()
    if concept not in data:
        raise ValueError(f"unknown concept {concept!r}; available: {concepts()}")
    spec: dict[str, Any] = data[concept]
    return spec


def _wave_of(codes: object, wave: int | None) -> int:
    """The wave of ``codes``: the argument, checked against the tag ``pynhts`` put on the frame."""
    attrs = getattr(codes, "attrs", {}) or {}
    tagged = (attrs.get("pynhts") or {}).get("wave")
    if wave is None:
        if tagged is None:
            raise ValueError("wave is required: these codes carry no pynhts wave tag")
        return int(tagged)
    if tagged is not None and int(tagged) != int(wave):
        raise ValueError(
            f"these codes come from NHTS {tagged} but wave={wave} was given; the same code means "
            "different things in different waves, so the crosswalk would map them wrongly"
        )
    return int(wave)


def apply_column(
    frame: pd.DataFrame, column: str, concept: str, *, level: Level = "category"
) -> pd.Series:
    """Map ``frame[column]`` with the crosswalk of the wave the frame was loaded from.

    The wave is read from ``frame.attrs["pynhts"]``, which :meth:`pynhts.NHTSData.table` and its
    shortcuts set; a frame without that tag raises an error (use :func:`apply` with ``wave=``).
    """
    return apply(frame[column], concept, _wave_of(frame, None), level=level)


def apply(
    codes: pd.Series, concept: str, wave: int | None = None, *, level: Level = "category"
) -> pd.Series:
    """Map the raw codes of ``wave`` to the shared categories of ``concept``.

    Missing codes (-9, -8, -7) and any code that the crosswalk does not list become NA, so a
    frame loaded with ``missing="keep"`` is safe to pass. Use :func:`category_report` to see
    which categories are not equally defined in the two waves before pooling.

    Args:
        codes: Raw coded column (strings such as ``"03"``) of the wave.
        concept: ``"purpose"`` or ``"mode"``.
        wave: Survey year of ``codes``. May be omitted when ``codes`` carries the wave tag set by
            pynhts; if both are given and differ, an error is raised.
        level: ``"category"`` (default) or ``"summary"`` (mode only: the guide's summary groups).

    Returns:
        A string Series of category ids, NA where there is no category.
    """
    if level not in ("category", "summary"):
        raise ValueError("level must be 'category' or 'summary'")
    wave = _wave_of(codes, wave)
    frame = crosswalk(concept)
    if level == "summary" and frame["summary"].isna().all():
        raise ValueError(f"concept {concept!r} has no summary level")
    mapping = {_canon(str(k)): v for k, v in zip(frame.loc[frame["wave"] == wave, "code"],
                                                  frame.loc[frame["wave"] == wave, level],
                                                  strict=True)}
    if not mapping:
        raise ValueError(f"no crosswalk rows for wave {wave}")
    mapped = _as_codes(codes).map(mapping)
    return mapped.astype("string")


def _as_codes(codes: pd.Series) -> pd.Series:
    """Codes as zero-unpadded strings; whole numbers stored as floats (2001 ``FUELTYPE``) too."""
    if pd.api.types.is_numeric_dtype(codes):
        whole = codes.where(codes == codes.round())
        text = whole.astype("Int64").astype("string")
    else:
        text = codes.astype("string")
    result: pd.Series = text.map(lambda x: _canon(x) if isinstance(x, str) else x)
    return result.astype("string")


def category_report(concept: str, wave_a: int = 2017, wave_b: int = 2022) -> pd.DataFrame:
    """Per category: the codes of two waves, and whether the category is equally defined.

    ``comparable`` is true when the category exists in both waves and every code in it is
    ``exact`` or ``nested`` (an exact collapse of finer codes) in both. Everything else needs a
    decision from the analyst; ``issue`` says why.
    """
    frame = crosswalk(concept)
    rows = []
    for cat, g in frame.groupby("category", sort=False):
        per = {w: g[g["wave"] == w] for w in (wave_a, wave_b)}
        if not any(len(p) > 0 for p in per.values()):
            continue  # the category exists only in waves that are not being compared
        g = g[g["wave"].isin((wave_a, wave_b))]
        in_both = all(len(p) > 0 for p in per.values())
        statuses = set(g["status"])
        issue = ""
        if not in_both:
            issue = f"only in {wave_a if len(per[wave_a]) else wave_b}"
        elif statuses - COMPARABLE:
            issue = "; ".join(sorted({str(n) for n in g["note"].dropna()})) or "/".join(
                sorted(statuses - COMPARABLE))
        rows.append({
            "category": cat,
            f"codes_{wave_a}": ",".join(per[wave_a]["code"]),
            f"codes_{wave_b}": ",".join(per[wave_b]["code"]),
            "comparable": in_both and statuses <= COMPARABLE,
            "issue": issue,
        })
    report: pd.DataFrame = pd.DataFrame(rows)
    return report


def _norm(text: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def _canon(code: str) -> str:
    """Code without zero padding: 2001 writes "1", 2009 "01" for the same answer."""
    return str(int(code)) if re.fullmatch(r"\d+", code) else code


def age_bands(age: pd.Series, wave: int | None = None) -> pd.Series:
    """Age in comparable bands that end at "85+" (the top-codes differ: 88 = 85+, 92 = 89+).

    Bands: 0-4 (2001 only), 5-15, 16-17, 18-24, 25-34, 35-44, 45-54, 55-64, 65-74, 75-84, 85+.
    Missing ages stay missing. The wave is only needed to refuse a frame from another wave.
    """
    if wave is not None:
        _wave_of(age, wave)
    edges = [-1, 4, 15, 17, 24, 34, 44, 54, 64, 74, 84, 200]
    labels = ["0-4", "5-15", "16-17", "18-24", "25-34", "35-44", "45-54", "55-64", "65-74",
              "75-84", "85+"]
    banded: pd.Series = pd.cut(pd.to_numeric(age), edges, labels=labels).astype("string")
    return banded


def _raw(text: object) -> str:
    """Label with case and spacing folded but symbols kept ("Estimate/4" is not "Estimate*4")."""
    return " ".join(str(text).lower().split())


def _similar(a: str, b: str) -> bool:
    """Same meaning, judged by wording: equal after normalising, or sharing a third of the words."""
    na, nb = _norm(a), _norm(b)
    if na == nb:
        return True
    wa, wb = set(na.split()), set(nb.split())
    return bool(wa and wb) and len(wa & wb) / len(wa | wb) >= 1 / 3


def compare_waves(wave_a: int = 2017, wave_b: int = 2022) -> pd.DataFrame:
    """Inventory of every variable name in two waves, from the codebooks.

    ``status`` is

    * ``identical``    same label, type and coded values;
    * ``relabelled``   same coded values, different wording of the variable or of the labels;
    * ``codes_changed`` the set of coded values differs, so pooling the raw column is unsafe;
    * ``codes_permuted`` the same codes but the meaning of some moved to another code (the label
      of code 1 in one wave is the label of code 2 in the other): the most dangerous case,
      because the values look compatible;
    * ``review_labels`` the same codes, but a label shares less than a third of its words with the
      other wave's (listed in ``conflicting_codes``). This is a wording heuristic: ``Yes`` against
      ``Worker`` is a false alarm, a permuted meaning is not, so read the labels;
    * ``type_changed`` string in one wave and numeric in the other;
    * ``only_<wave>``  the variable exists in one wave only.

    Numeric columns are compared by label and type only (their values are not coded).
    """
    da = dictionary(wave_a).drop_duplicates("variable").set_index("variable")
    db = dictionary(wave_b).drop_duplicates("variable").set_index("variable")
    codes = {w: _codes(w) for w in (wave_a, wave_b)}
    rows = []
    for name in sorted(set(da.index) | set(db.index)):
        row: dict[str, Any] = {"variable": name, f"label_{wave_a}": None, f"label_{wave_b}": None,
                               "conflicting_codes": ""}
        if name not in db.index:
            row.update(status=f"only_{wave_a}", **{f"label_{wave_a}": da.loc[name, "label"]})
        elif name not in da.index:
            row.update(status=f"only_{wave_b}", **{f"label_{wave_b}": db.loc[name, "label"]})
        else:
            a, b = da.loc[name], db.loc[name]
            row[f"label_{wave_a}"], row[f"label_{wave_b}"] = a["label"], b["label"]
            same_label = _norm(a["label"]) == _norm(b["label"])
            if a["dtype"] != b["dtype"]:
                row["status"] = "type_changed"
            elif a["dtype"] != "string":
                row["status"] = "identical" if same_label else "relabelled"
            else:
                raw_a, raw_b = codes[wave_a].get(name, {}), codes[wave_b].get(name, {})
                ca = {_canon(k): v for k, v in raw_a.items()}
                cb = {_canon(k): v for k, v in raw_b.items()}
                shared = (set(ca) & set(cb)) - MISSING_CODES
                conflict = sorted(c for c in shared if not _similar(ca[c], cb[c]))
                same_set = set(ca) - MISSING_CODES == set(cb) - MISSING_CODES
                row["conflicting_codes"] = ",".join(conflict)
                moved = sorted(c for c in shared if _raw(ca[c]) != _raw(cb[c]) and any(
                    _raw(cb[j]) == _raw(ca[c]) for j in cb if j != c and j not in MISSING_CODES
                ))
                row["padding_differs"] = bool(
                    (set(raw_a) - MISSING_CODES) != (set(raw_b) - MISSING_CODES) and same_set
                )
                if not same_set:
                    row["status"] = "codes_changed"
                elif moved:
                    row["status"] = "codes_permuted"
                    row["conflicting_codes"] = ",".join(moved)
                elif conflict:
                    row["status"] = "review_labels"
                else:
                    row["status"] = "identical" if same_label else "relabelled"
        rows.append(row)
    inventory: pd.DataFrame = pd.DataFrame(rows)
    return inventory


def _codes(wave: int) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for table in wave_tables(wave):
        for name, col in load_schema(table, wave).columns.items():
            if col.owner == table and col.is_string and name not in out:
                out[name] = {c.code: c.label for c in col.codes}
    return out


__all__ = ["age_bands", "apply", "apply_column", "category_report", "compare_waves",
           "concept_info", "concepts", "crosswalk"]
