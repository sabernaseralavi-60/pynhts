"""Generate src/pynhts/_schema/2017/<table>.yaml from the official NHTS 2017 codebook (xlsx).

Usage: python tools/build_schema.py path/to/codebook_v1.2.xlsx

The codebook is the single source of truth. Nothing is guessed: the generator only reshapes
what the codebook says (type C/N, length, code=label lines, response ranges, frequencies).
Needs openpyxl (dev extra).
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

import openpyxl
import yaml

SHEETS = {
    "CODEBOOK_HH": ("household", "hhpub.csv"),
    "CODEBOOK_PER": ("person", "perpub.csv"),
    "CODEBOOK_TRIP": ("trip", "trippub.csv"),
    "CODEBOOK_VEH": ("vehicle", "vehpub.csv"),
}
# A column that appears in several tables is owned by the first table in this order.
OWNER_ORDER = ["household", "person", "trip", "vehicle"]
# -88 and -77 are the codebook's "I don't know" / "I prefer not to answer" in fields where -8/-7 could be real values.
MISSING = {
    "-9": "not_ascertained",
    "-8": "dont_know",
    "-7": "refused",
    "-88": "dont_know",
    "-77": "refused",
}
SKIP = "-1"
OUT = Path(__file__).resolve().parents[1] / "src" / "pynhts" / "_schema" / "2017"


def parse_sheet(ws: Any) -> dict[str, dict[str, Any]]:
    """Return {variable: spec} for one codebook sheet, in codebook order."""
    variables: dict[str, dict[str, Any]] = {}
    cur: dict[str, Any] | None = None
    for row in list(ws.iter_rows(values_only=True))[1:]:
        name, label, typ, length, code, freq, weighted = (list(row) + [None] * 7)[:7]
        if name and str(name).strip():
            cur = {
                "label": str(label).strip() if label else "",
                "type": str(typ).strip(),
                "length": int(length) if length not in (None, "") else None,
                "codes": [],
            }
            variables[str(name).strip()] = cur
        if cur is None or code in (None, ""):
            continue
        text = str(code).strip()
        n = int(freq) if isinstance(freq, (int, float)) else None
        w = float(weighted) if isinstance(weighted, (int, float)) else None
        if text.startswith("Responses="):
            cur["range"] = text.split("=", 1)[1].strip()
            cur["range_n"], cur["range_weighted"] = n, w
            continue
        value, _, lab = text.partition("=")
        cur["codes"].append(
            {"code": value.strip(), "label": lab.strip(), "n": n, "weighted": w}
        )
    return variables


def build(codebook: Path) -> None:
    """Write one YAML per table plus an ownership index."""
    wb = openpyxl.load_workbook(codebook, read_only=True)
    digest = hashlib.sha256(codebook.read_bytes()).hexdigest()
    parsed = {sheet: parse_sheet(wb[sheet]) for sheet in SHEETS}
    tables = {SHEETS[s][0]: v for s, v in parsed.items()}
    owner: dict[str, str] = {}
    for t in OWNER_ORDER:
        for var in tables[t]:
            owner.setdefault(var, t)
    OUT.mkdir(parents=True, exist_ok=True)
    for sheet, (table, csv_name) in SHEETS.items():
        cols: dict[str, Any] = {}
        for var, spec in tables[table].items():
            codes = spec["codes"]
            cols[var] = {
                "label": spec["label"],
                "dtype": "string" if spec["type"] == "C" else "float64",
                "length": spec["length"],
                "owner": owner[var],
                "missing_codes": {c["code"]: MISSING[c["code"]] for c in codes
                                  if c["code"] in MISSING},
                "skip_code": SKIP if any(c["code"] == SKIP for c in codes) else None,
                "range": spec.get("range"),
                "codes": codes,
            }
        doc = {
            "wave": 2017,
            "table": table,
            "csv": csv_name,
            "codebook": {"file": codebook.name, "sha256": digest},
            "n_columns": len(cols),
            "columns": cols,
        }
        (OUT / f"{table}.yaml").write_text(
            yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100),
            encoding="utf-8",
        )
        print(f"{table}: {len(cols)} columns, {sum(len(c['codes']) for c in cols.values())} codes")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    build(Path(sys.argv[1]))
