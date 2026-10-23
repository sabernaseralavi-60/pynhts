"""Generated parts of docs/compendium.md and compendium/SOURCES.md (so that no number in the docs is typed by hand)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def _cell(v: object) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else f"{v:.2f}"
    return str(v)


def md_table(df: pd.DataFrame) -> str:
    """Render a DataFrame as a GitHub-flavoured Markdown table."""
    head = "| " + " | ".join(str(c) for c in df.columns) + " |\n|" + "|".join("---" for _ in df.columns) + "|\n"
    rows = ["| " + " | ".join(_cell(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return head + "\n".join(rows) + "\n"


def fill_block(text: str, name: str, body: str) -> str:
    """Replace the content between <!-- AUTO:name:start --> and <!-- AUTO:name:end -->."""
    a, b = f"<!-- AUTO:{name}:start -->", f"<!-- AUTO:{name}:end -->"
    i, j = text.index(a) + len(a), text.index(b)
    return text[:i] + "\n" + body + text[j:]


def write_docs(root: Path, audit: pd.DataFrame, num: dict, S: dict) -> None:
    """Write the generated tables of docs/compendium.md and the checksum list compendium/SOURCES.md."""
    comp = root / "compendium"
    ex = audit[["edition", "layout_family", "pdf_pages", "entries_parsed", "abstract_anchors", "title_labels_div2", "intro_stated_total",
                "anchorless_entries", "multi_page_entries", "toc_page_match_share", "max_abs_diff_to_independent_counts"]].copy()
    ex.columns = ["edition", "layout", "PDF pages", "entries parsed", "Abstract: anchors", "Title: labels / 2", "stated total",
                  "no abstract label", "multi-page", "TOC titles on computed page", "max difference"]
    body_ex = ("Entries parsed against independent counts, per edition (the 2023-2025 rows are the rows of the interactive-search CSV; "
               "the 2023 PDF covers January-June only and overlaps the CSV, which deduplication removes):\n\n" + md_table(ex))
    dom = S["by_chapter"][["domain", "studies", "mention_nhts", "regression", "ml", "weights", "variance"]].copy()
    lines = [
        f"* {num['n_records']} listed records ({num['n_pdf_records']} in 12 PDFs, {num['n_csv_records']} in the 2023-2025 search export) = "
        f"**{num['n_unique']} unique studies** ({num['n_duplicates_removed']} repeated across editions); {num['n_with_abstract']} have an abstract.",
        f"* {num['n_mention_nhts']} studies name the NHTS/NPTS in title, abstract or subject areas; waves named: 2017 in {num['mentions_2017_n']}, "
        f"2009 in {num['mentions_2009_n']}, 2001 in {num['mentions_2001_n']}, 2022 in {num['mentions_2022_n']}; "
        f"{num['no_wave_stated_n']} name the survey but no wave.",
        f"* Modelling abstracts (regression or machine learning, abstract present): {num['mod_n']}; **{num['mod_weights_n']} name survey weights, "
        f"{num['mod_variance_n']} a design-based variance estimator** (every positive was read: {num.get('review_weights_tp_n')} of "
        f"{num.get('review_weights_n')} weight flags and {num.get('review_variance_tp_n')} of {num.get('review_variance_n')} variance flags are correct).",
        f"* Machine learning: {num['ml_n']} studies, {num['ml_resampling_n']} mention oversampling/SMOTE/class imbalance, "
        f"{num['ml_accuracy_ge90_n']} state an accuracy or AUC of 90 % or more.",
        f"* Audited studies found in the compendium: {num['n_case_in_compendium']} of {num['n_case_studies']}, in {num['n_case_domains']} domains.",
        "", "Studies by planning domain (chapter of first appearance), with the tags of their abstracts:\n", md_table(dom),
        "Audited studies by domain:\n", md_table(S["cs_by_domain"]),
    ]
    d = root / "docs" / "compendium.md"
    t = d.read_text(encoding="utf-8")
    t = fill_block(t, "extraction", body_ex)
    t = fill_block(t, "summary", "\n".join(lines))
    d.write_text(t, encoding="utf-8")
    src = audit[["file", "edition", "sha256"]].drop_duplicates("file")
    sizes = {p.name: p.stat().st_size for p in comp.glob("*") if p.is_file()}
    src = src.assign(bytes=src["file"].map(sizes))[["file", "edition", "bytes", "sha256"]]
    (comp / "SOURCES.md").write_text(
        "# Sources of the NHTS Compendium corpus\n\n"
        "Official FHWA/ORNL *NHTS Compendium of Uses* editions, placed in this folder by the user (2026-10-23). They are public "
        "documents but large and are not redistributed in this repository (see `.gitignore`). Re-obtain them from the NHTS website, compare "
        "the SHA-256 below and rebuild with `python -I -X utf8 tools/compendium/build_compendium.py` (needs `pdftotext`).\n\n"
        + md_table(src)
        + "\nNo 2017 edition was supplied; 2018 covers January-June 2018 and the 2023 PDF January-June 2023; the CSV holds the "
        "interactive-search records of 2023, 2024 and 2025.\n",
        encoding="utf-8",
    )
