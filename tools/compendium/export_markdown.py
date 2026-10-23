"""Export every sheet of nhts_compendium_2006_2025_master.xlsx as Markdown that can be given to an AI model.

    python -I -X utf8 tools/compendium/export_markdown.py

Output (compendium/ai_export/, local only: the full files contain abstracts):
  00_README_and_summary_sheets.md   all sheets except All_Papers (small; give this first)
  01_All_Papers_compact_NN.md       one table row per study, no abstract (fits in a context window per file)
  02_All_Papers_full_NN.md          one block per study with every column including the abstract
  INDEX.md                          which file holds which editions, row counts, character sizes
Files are cut at MAX_CHARS so that each can be pasted or uploaded on its own.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
XLSX = ROOT / "compendium" / "nhts_compendium_2006_2025_master.xlsx"
OUT = ROOT / "compendium" / "ai_export"
MAX_CHARS = 380_000  # about 95k tokens
COMPACT = ["cid", "title", "authors", "pub_year", "first_edition", "editions", "domain", "study_type", "model_families", "nhts_waves_mentioned",
           "mentions_nhts", "mentions_weights", "mentions_variance_design", "mentions_resampling", "accuracy_claim_pct", "topics",
           "linked_audit_id", "doi"]


def cell(v: object) -> str:
    """One table cell: no pipes or line breaks; empty for missing values."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, bool):
        return "yes" if v else "no"
    return str(v).replace("|", "/").replace("\r", " ").replace("\n", " ").strip()


def table(df: pd.DataFrame) -> str:
    """GitHub-flavoured Markdown table."""
    head = "| " + " | ".join(str(c) for c in df.columns) + " |\n|" + "|".join("---" for _ in df.columns) + "|\n"
    return head + "\n".join("| " + " | ".join(cell(v) for v in r) + " |" for r in df.itertuples(index=False)) + "\n"


def chunks(blocks: list[str], header: str) -> list[str]:
    """Group blocks into pieces below MAX_CHARS, each starting with the header."""
    out, cur, size = [], [], len(header)
    for b in blocks:
        if cur and size + len(b) > MAX_CHARS:
            out.append(header + "".join(cur))
            cur, size = [], len(header)
        cur.append(b)
        size += len(b)
    if cur:
        out.append(header + "".join(cur))
    return out


def main() -> None:
    """Write the Markdown files."""
    OUT.mkdir(exist_ok=True)
    for f in OUT.glob("*.md"):
        f.unlink()
    x = pd.ExcelFile(XLSX)
    # 00: every sheet except All_Papers
    parts = ["# NHTS Compendium of Uses 2006-2025: master workbook (summary sheets)\n\n"
             "Source: `nhts_compendium_2006_2025_master.xlsx` (built by `tools/compendium/build_compendium.py`). "
             "This file holds every sheet except `All_Papers`, which is split into the files listed in `INDEX.md`. "
             "Tags describe what an abstract says, not what the analysis did; read the README sheet below first.\n"]
    for s in x.sheet_names:
        if s == "All_Papers":
            continue
        d = x.parse(s)
        parts.append(f"\n## Sheet: {s}  ({len(d)} rows x {d.shape[1]} columns)\n\n{table(d)}")
    (OUT / "00_README_and_summary_sheets.md").write_text("".join(parts), encoding="utf-8")

    a = x.parse("All_Papers")
    a["_ord"] = a["first_edition"].astype(str)
    order = ["2006-2011", "2012", "2013", "2014", "2015", "2016", "2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025"]
    a = a.sort_values("_ord", key=lambda s: s.map({e: i for i, e in enumerate(order)})).reset_index(drop=True)
    index = ["# Index of the AI export\n\n| file | studies | first editions covered | characters |\n|---|---|---|---|\n"]
    index.append(f"| 00_README_and_summary_sheets.md | all other sheets | - | {(OUT / '00_README_and_summary_sheets.md').stat().st_size} |\n")

    # 01 compact: one row per study without abstract
    head = "| " + " | ".join(COMPACT) + " |\n|" + "|".join("---" for _ in COMPACT) + "|\n"
    rows = [("| " + " | ".join(cell(v) for v in r) + " |\n", str(r[COMPACT.index("first_edition")])) for r in a[COMPACT].itertuples(index=False)]
    pieces, cur, size = [], [], len(head)
    for line, ed in rows:
        if cur and size + len(line) > MAX_CHARS:
            pieces.append(cur)
            cur, size = [], len(head)
        cur.append((line, ed))
        size += len(line)
    pieces.append(cur)
    for i, p in enumerate(pieces, 1):
        txt = ("# All_Papers (compact, no abstracts), part %d of %d\n\nColumns: " % (i, len(pieces)) + ", ".join(COMPACT) + "\n\n" + head + "".join(l for l, _ in p))
        f = OUT / f"01_All_Papers_compact_{i:02d}.md"
        f.write_text(txt, encoding="utf-8")
        eds = sorted({e for _, e in p}, key=order.index)
        index.append(f"| {f.name} | {len(p)} | {eds[0]} to {eds[-1]} | {len(txt)} |\n")

    # 02 full: one block per study with every column
    blocks = []
    for r in a.drop(columns=["_ord"]).to_dict("records"):
        lines = [f"### {r['cid']} | {cell(r['title'])}\n"]
        for k, v in r.items():
            if k in ("cid", "title") or cell(v) == "":
                continue
            lines.append(f"- **{k}**: {cell(v)}\n")
        blocks.append("".join(lines) + "\n")
    full = chunks(blocks, "")
    for i, body in enumerate(full, 1):
        n = body.count("\n### ") + (1 if body.startswith("### ") else 0)
        txt = f"# All_Papers (full records with abstracts), part {i} of {len(full)}\n\n" + body
        f = OUT / f"02_All_Papers_full_{i:02d}.md"
        f.write_text(txt, encoding="utf-8")
        index.append(f"| {f.name} | {n} | (see first lines) | {len(txt)} |\n")
    (OUT / "INDEX.md").write_text("".join(index) + f"\nEach file is below {MAX_CHARS} characters. Give an AI model 00 first, then the compact or the full parts it needs.\n", encoding="utf-8")
    print("".join(index))


if __name__ == "__main__":
    main()
