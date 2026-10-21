"""Generate src/pynhts/_schema/2009/<table>.yaml from the official 2009 NHTS codebook (PDF).

Usage: python tools/build_schema_pdf.py <2009|2001> path/to/Codebook.pdf (2001: UsersGuide.pdf)

The 2009 release has no machine-readable codebook (the data dictionary .xls lists names, types
and labels only), so the PDF codebook is the single source of truth. Its text layout is parsed
page by page with ``pdftotext -layout`` (poppler); the column offsets are read from each page's
own header line. Nothing is guessed: the generator only reshapes what the codebook prints
(type C/N, length, ``code = label`` lines, frequencies). The result is cross-checked against the
CSV files by tests/data/test_schema_vs_csv.py (every printed code frequency must reproduce).
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

# page title (as printed) -> (table, csv name)
TABLES = {
    "Household": ("household", "HHV2PUB.CSV"),
    "Person": ("person", "PERV2PUB.CSV"),
    "Day Trip": ("trip", "DAYV2PUB.CSV"),
    "Vehicle": ("vehicle", "VEHV2PUB.CSV"),
}
# 2001 Appendix B of the User's Guide: title -> (table, csv name); the file names are checked
# against the archive by the converter.
TABLES01 = {
    "Household": ("household", "HHPUB.CSV"),
    "Person": ("person", "PERPUB.CSV"),
    "Vehicle": ("vehicle", "VEHPUB.CSV"),
    "Day Trip": ("trip", "DAYPUB.CSV"),
    "Long Trip": ("longdist", "LDTPUB.CSV"),
}
TABLES_BY_WAVE = {2009: TABLES, 2001: TABLES01}
ANCESTORS = {
    "household": [],
    "person": ["household"],
    "trip": ["household", "person"],
    "vehicle": ["household"],
    "longdist": ["household", "person"],
}
MISSING = {"-9": "not_ascertained", "-8": "dont_know", "-7": "refused"}
SKIP = "-1"
# Evidence-based repairs of the printed codebook (checked against the CSV, 2026-10-21).
# (wave, table, column, printed code) -> repaired code. The 2009 PDF prints control character
# 0x16 for the digit 3 of "35 = NISSAN / DATSUN"; the CSV has MAKECODE "35" in 12,345 rows,
# exactly the printed frequency.
CODE_FIXES = {(2009, "vehicle", "MAKECODE", "5"): "35"}
# (wave, table, column) -> {code: kind}. 2009 PTUSED: the codebook prints 99,106 rows for "-9",
# the CSV has 98,498 rows "-9" and 608 rows "99"; 98,498 + 608 = 99,106, so the codebook counts
# the value 99 as not ascertained.
EXTRA_MISSING = {(2009, "person", "PTUSED"): {"99": "not_ascertained"}}
OUT_ROOT = Path(__file__).resolve().parents[1] / "src" / "pynhts" / "_schema"
_TITLE = re.compile(r"^\s*(\d{4}) NHTS (.+?) File - Public Use Codebook")
_NUM = r"-?[\d,]+(?:\.\d+)?"
_TAIL = re.compile(rf"^(.*?)\s{{2,}}({_NUM})\s+({_NUM})\s*$")
_FOOTER = re.compile(r"^\s*B-\d+\s*$")


def _norm(label: str) -> str:
    return " ".join(label.lower().split())


def _int(text: str) -> int:
    return int(text.replace(",", ""))


def parse(text: str) -> dict[str, dict[str, dict[str, Any]]]:
    """Return {table: {variable: spec}} from the layout text of the codebook."""
    tables: dict[str, dict[str, dict[str, Any]]] = {}
    state: dict[str, tuple[dict[str, Any] | None, dict[str, Any] | None]] = {}
    for page in text.split("\f"):
        lines = page.splitlines()
        title = next((m for ln in lines if (m := _TITLE.match(ln))), None)
        if title is None:
            continue
        table = TABLES[title.group(2)][0]
        header = next(ln for ln in lines if ln.startswith("Name") and "Label" in ln)
        c_label, c_type = header.index("Label"), header.index("Type")
        c_len, c_q = header.index("Length"), header.index("Question")
        # The header text is not aligned with the data, so the code column starts where the
        # code-only continuation lines start: the smallest indent right of the question header.
        c_code = min(
            len(ln) - len(ln.lstrip()) for ln in lines
            if ln.strip() and len(ln) - len(ln.lstrip()) >= c_q
        )
        cols = tables.setdefault(table, {})
        cur, last_code = state.get(table, (None, None))
        for ln in lines:
            if not ln.strip() or _TITLE.match(ln) or ln.startswith("Name") or _FOOTER.match(ln):
                continue
            head = ln[:c_label].strip()
            if head:
                name = head.split()[0]
                cur = {
                    "label": ln[c_label:c_type].strip(),
                    "type": ln[c_type:c_len].strip(),
                    "length": ln[c_len:c_q].strip(),
                    "codes": [],
                }
                cols[name] = cur
                last_code = None
            elif cur is not None and ln[c_label:c_code].strip():
                # wrapped label, or a wrapped question/type cell
                piece = ln[c_label:c_type].strip()
                if piece:
                    cur["label"] += " " + piece
            if cur is None:
                continue
            # a leading minus sign may sit one column left of the code column
            start = c_code - 1 if len(ln) >= c_code and ln[c_code - 1:c_code] == "-" else c_code
            right = ln[start:].rstrip() if len(ln) > c_code else ""
            if not right.strip():
                continue
            m = _TAIL.match(right)
            if m:
                code_text = m.group(1).strip()
                value, sep, lab = code_text.partition(" = ")
                if not sep:
                    value, lab = code_text, ""
                last_code = {
                    "code": value.strip(),
                    "label": lab.strip(),
                    "n": _int(m.group(2)),
                    "weighted": float(m.group(3).replace(",", "")),
                }
                cur["codes"].append(last_code)
            elif last_code is not None:
                last_code["label"] = (last_code["label"] + " " + right.strip()).strip()
        state[table] = (cur, last_code)
    return tables


_TITLE01 = re.compile(r"^NHTS (.+?) File Codebook", re.M)
_ROW01 = re.compile(
    r"^(\S+)\s+(?:([YN])\s+)?([NC])\s+(\d+)(?:\s+(NQR|NQ|NR|SD|Y|X))?(?=\s{2,}|$)"
)
_FOOT01 = re.compile(r"^\s*(\* For additional details|B ?-\s*\d+\s*$)")


def parse01(text: str) -> dict[str, dict[str, dict[str, Any]]]:
    """Return {table: {variable: spec}} from Appendix B of the 2001 User's Guide."""
    tables: dict[str, dict[str, dict[str, Any]]] = {}
    state: dict[str, tuple[dict[str, Any] | None, dict[str, Any] | None]] = {}
    for page in text.split("\f"):
        title = _TITLE01.search(page)
        lines = page.splitlines()
        if title is None or not any("Variable Name" in ln for ln in lines):
            continue
        table = TABLES01[title.group(1)][0]
        k = next(i for i, ln in enumerate(lines) if "Variable Name" in ln)
        h1, h2 = lines[k - 1], lines[k]
        c_q = h1.index("Question")
        c_label = h2.index("Label")
        # The header text is centred over its column, so the code column starts where the
        # code-only continuation lines start: the smallest indent right of the question column.
        c_code = min(
            len(ln) - len(ln.lstrip()) for ln in lines[k + 1:]
            if ln.strip() and len(ln) - len(ln.lstrip()) >= c_q + 8
        )
        cols = tables.setdefault(table, {})
        cur, last_code = state.get(table, (None, None))
        for ln in lines[k + 1:]:
            if not ln.strip() or _FOOT01.match(ln) or _TITLE01.match(ln):
                continue
            if ln.startswith(("Public Use File", "NHTS ")) or ln.strip() == "1995":
                continue
            m = _ROW01.match(ln)
            if m:
                cur = {
                    "label": ln[m.end():c_q].strip(),
                    "type": m.group(3),
                    "length": m.group(4),
                    "codes": [],
                }
                cols[m.group(1)] = cur
                last_code = None
            elif cur is not None and ln[:c_label].strip() == "" and ln[c_label - 8:c_q].strip():
                cur["label"] += " " + ln[c_label - 8:c_q].strip()
            if cur is None:
                continue
            # a leading minus sign may sit one column left of the code column
            start = c_code - 1 if len(ln) >= c_code and ln[c_code - 1:c_code] == "-" else c_code
            right = ln[start:].rstrip() if len(ln) > c_code else ""
            if not right.strip():
                continue
            t = _TAIL.match(right)
            if t:
                code_text = t.group(1).strip()
                value, sep, lab = code_text.partition("=")
                if not sep:
                    value, lab = code_text, ""
                last_code = {
                    "code": value.strip(),
                    "label": lab.strip(),
                    "n": _int(t.group(2)),
                    "weighted": float(t.group(3).replace(",", "")),
                }
                cur["codes"].append(last_code)
            elif last_code is not None:
                last_code["label"] = (last_code["label"] + " " + right.strip()).strip()
        state[table] = (cur, last_code)
    return tables


def build(wave: int, pdf: Path) -> None:
    """Write one YAML per table."""
    text = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"], check=True, capture_output=True, text=True,
        encoding="utf-8",
    ).stdout
    tables = parse01(text) if wave == 2001 else parse(text)
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    out_dir = OUT_ROOT / str(wave)
    out_dir.mkdir(parents=True, exist_ok=True)

    def owner_of(table: str, var: str) -> str:
        for anc in ANCESTORS[table]:
            other = tables.get(anc, {}).get(var)
            if other and _norm(other["label"]) == _norm(tables[table][var]["label"]):
                return anc
        return table

    for _, (table, csv_name) in TABLES_BY_WAVE[wave].items():
        cols: dict[str, Any] = {}
        for var, spec in tables[table].items():
            codes = spec["codes"]
            rng = None
            kept = []
            for c in codes:
                if not c["label"] and re.fullmatch(r"-?[\d.,]+\s*-\s*-?[\d.,]+", c["code"]):
                    rng = c["code"].replace(" ", "")
                kept.append(c)
            for c in codes:
                c["code"] = CODE_FIXES.get((wave, table, var, c["code"]), c["code"])
            missing = {c["code"]: MISSING[c["code"]] for c in codes if c["code"] in MISSING}
            missing.update(EXTRA_MISSING.get((wave, table, var), {}))
            cols[var] = {
                "label": spec["label"],
                "dtype": "string" if spec["type"] == "C" else "float64",
                "length": int(spec["length"]) if spec["length"].isdigit() else None,
                "owner": owner_of(table, var),
                "missing_codes": missing,
                "skip_code": SKIP if any(c["code"] == SKIP for c in codes) else None,
                "range": rng,
                "codes": kept,
            }
        doc = {
            "wave": wave,
            "table": table,
            "csv": csv_name,
            "codebook": {"file": pdf.name, "sha256": digest},
            "n_columns": len(cols),
            "columns": cols,
        }
        (out_dir / f"{table}.yaml").write_text(
            yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
        )
        print(f"{table}: {len(cols)} columns, {sum(len(c['codes']) for c in cols.values())} codes")


if __name__ == "__main__":
    if len(sys.argv) != 3 or int(sys.argv[1]) not in TABLES_BY_WAVE:
        raise SystemExit(__doc__)
    build(int(sys.argv[1]), Path(sys.argv[2]))
