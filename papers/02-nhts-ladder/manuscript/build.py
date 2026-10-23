"""Manuscript build for paper 01: results/ -> tokens -> template -> Quarto (docx + Typst PDF), English and Persian.

    python build.py --lang en [--no-render]
    python build.py --lang fa

* Every number in the text is a token {{key:fmt}}; keys are dotted paths into results/numbers/*.json
  (file name first: {{grid.us101.fcm5m.all.xgb.P1.macro_f1:3}}, {{design.n_features:i}}, {{prospective.us101_E1_L0_auc:2}}).
* fmt: i integer with separators | 0..3 decimals | s1..s3 signed | a1..a3 absolute | p0..p2 fraction as percent (no sign)
  | r raw integer | m decimal with at most 3 significant digits.
* Tables come from tokens {{tbl:name}} generated in tables.py; figures are plain Quarto includes of results/figures/*.png.
* lint(): any number above 10 or with a decimal typed in a template outside a token is an error.
* Persian: same tokens; digits and decimal separator are localised at substitution time; figures keep English axis text.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
RES = ROOT / "results"
NUM = RES / "numbers"
BUILD, FINAL = HERE / "build", HERE / "final"
FA_DIGITS = str.maketrans("0123456789.,%", "۰۱۲۳۴۵۶۷۸۹٫٬٪")
FA_DIGITS_ONLY = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
NAME = "Paper02_NHTS_design_aware_ladder"


def load_numbers():
    """All JSON files in results/numbers flattened to {'file.a.b.c': value}."""
    out = {}

    def walk(prefix, o):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(f"{prefix}.{k}", v)
        elif isinstance(o, list):
            return
        else:
            out[prefix] = o
    for f in sorted(NUM.glob("*.json")):
        walk(f.stem, json.loads(f.read_text(encoding="utf-8")))
    return out


def fmt(spec, v, lang):
    if isinstance(v, str):
        return v
    if v is None or (isinstance(v, float) and v != v):
        sys.exit("NaN/None value injected into the text")
    if spec == "r":
        s = str(int(v))
    elif spec == "i":
        s = f"{int(round(v)):,}"
    elif spec[0] in "sS" and spec[1:].isdigit():
        s = f"{v:+.{int(spec[1:])}f}".replace("-", "−")
    elif spec[0] == "a" and spec[1:].isdigit():
        s = f"{abs(v):.{int(spec[1:])}f}"
    elif spec[0] == "p" and spec[1:].isdigit():
        s = f"{v * 100:.{int(spec[1:])}f}"
    elif spec == "pv":
        if lang == "fa":
            s = "کمتر از 0.001" if v < 0.001 else f"برابر {v:.3f}" if v < 0.1 else f"برابر {v:.2f}"
        else:
            s = "< 0.001" if v < 0.001 else f"= {v:.3f}" if v < 0.1 else f"= {v:.2f}"
    elif spec == "m":
        s = f"{v:.3g}"
    elif spec in ("0", "1", "2", "3", "4"):
        s = f"{v:.{int(spec)}f}".replace("-", "−")
    else:
        sys.exit(f"unknown format {spec}")
    return s.translate(FA_DIGITS) if lang == "fa" else s


def md_table(df, caption, label, lang, widths=None, align=None):
    """Pipe table with relative column widths and per-column alignment ('l' or 'r'). Persian: digits localised, ' to ' -> ' تا '."""
    cols = list(df.columns)
    widths = widths or [max(18, 70 - 12 * (len(cols) - 1))] + [11] * (len(cols) - 1)
    align = align or "l" + "r" * (len(cols) - 1)
    seps = [(":" + "-" * widths[k]) if align[k] == "l" else ("-" * widths[k] + ":") for k in range(len(cols))]
    head = "| " + " | ".join(cols) + " |\n|" + "|".join(seps) + "|\n"
    body = "".join("| " + " | ".join(str(x) for x in r) + " |\n" for r in df.itertuples(index=False))
    if lang == "fa":
        head, body = (re.sub(r"(?<=\d)–(?=\d)", " تا ", x).replace(" to ", " تا ") for x in (head, body))
        keep = lambda x: re.sub(r"(?<=[A-Za-z])[۰-۹]+", lambda m: m.group(0).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")), x)
        head, body, caption = keep(head.translate(FA_DIGITS)), keep(body.translate(FA_DIGITS)), caption.translate(FA_DIGITS_ONLY)
    return head + body + f"\n: {caption} {{#tbl-{label} tbl-colwidths=\"[{','.join(str(x) for x in widths)}]\"}}\n"


ALLOWED_YEAR = re.compile(r"\b(19|20)\d\d\b")


def lint(text, name):
    body = re.sub(r"^---.*?---", "", text, count=1, flags=re.S).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٫٪", "0123456789.%"))
    body = re.sub(r"^\*\*(Seyed|سید).*$", " ", body, flags=re.M)
    body = re.sub(r"\d+(st|nd|rd|th)", " ", body)
    body = re.sub(r"\$\$.*?\$\$", " ", body, flags=re.S)
    body = re.sub(r"\$[^$\n]*\$", " ", body)
    body = re.sub(r"\$\$.*?\$\$", " ", body, flags=re.S)
    body = re.sub(r"\$[^$\n]*\$", " ", body)
    body = re.sub(r"\{\{.*?\}\}", " ", body)
    body = re.sub(r"\[@[^\]]*\]|@[A-Za-z0-9_:-]+", " ", body)
    body = re.sub(r"\(\.\./[^)]*\)|\{#[^}]*\}|https?://\S+|\]\([^)]*\)", " ", body)
    body = re.sub(r"(US-101|I-80|CO~2~e|CO~2~|H[1-7]|P[0-4][abs]?|L-[A-Z]+|E[0-2]|Tier [IE]0?|R[0-3]|k = \d|SHA-256|95%|ISO \d+|10 Hz|10-Hz|ORCID)", " ", body)
    bad = []
    for m in re.finditer(r"[−+-]?\d[\d.,]*\d|\d", body):
        tok = m.group(0)
        if body[m.end():m.end() + 2] in ('st', 'nd', 'rd', 'th') or body[max(0, m.start() - 5):m.start()] in ('covid', 'کووید'):
            continue
        if ALLOWED_YEAR.fullmatch(tok) or (tok.isdigit() and int(tok) <= 10):
            continue
        bad.append(tok + ' …' + body[max(0, m.start() - 25):m.end() + 10].replace(chr(10), ' ') + '…')
    if bad:
        sys.exit(f"lint: typed numbers in {name}: {sorted(set(bad))}")


def render_text(tmpl, n, tbl, lang):
    def sub(m):
        k = m.group(1).strip()
        if k.startswith("tbl:"):
            return tbl[k[4:]]
        key, _, spec = k.rpartition(":")
        if not key:
            key, spec = spec, "2"
        if key not in n:
            sys.exit(f"unknown token {{{{{k}}}}}")
        return fmt(spec, n[key], lang)
    out = re.sub(r"\{\{(.*?)\}\}", sub, tmpl)
    if "{{" in out or "}}" in out:
        sys.exit("unresolved token")
    return out


def rtl_tables(path):
    import docx
    from docx.oxml import OxmlElement
    d = docx.Document(str(path))
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    for t in d.tables:
        pr = t._tbl.tblPr
        if pr.find(ns + "bidiVisual") is None:
            el = OxmlElement("w:bidiVisual")
            later = [c for c in pr if c.tag in {ns + x for x in ("tblW", "jc", "tblCellSpacing", "tblInd", "tblBorders", "shd", "tblLayout", "tblCellMar", "tblLook", "tblCaption", "tblDescription")}]
            (later[0].addprevious(el) if later else pr.append(el))
    d.save(str(path))


def write_highlights(n):
    lines = [render_text(l, n, {}, "en").strip() for l in (HERE / "highlights.tmpl.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    too_long = [l for l in lines if len(l) > 85]
    if too_long:
        sys.exit(f"highlights over 85 characters: {too_long}")
    FINAL.mkdir(exist_ok=True)
    (FINAL / "Highlights_EN.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    import tables as TBL
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="en")
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()
    parts = sorted((HERE / a.lang).glob("part_*.qmd"))
    tmpl_path = parts[0]
    tmpl = chr(10).join(p.read_text(encoding="utf-8").strip() + chr(10) for p in parts)
    lint(tmpl, str(tmpl_path))
    n = load_numbers()
    out_dir = BUILD / a.lang
    out_dir.mkdir(parents=True, exist_ok=True)
    (BUILD / "numbers.json").write_text(json.dumps({k: (v if isinstance(v, (str, bool)) else float(v)) for k, v in n.items()}, indent=0), encoding="utf-8")
    text = render_text(tmpl, n, TBL.tables(a.lang, n, md_table), a.lang)
    shutil.copy(HERE / "refs.bib", out_dir / "refs.bib")
    shutil.copy(HERE / "typst-template.typ", out_dir / "typst-template.typ")
    csl = HERE / "elsevier-harvard.csl"
    if csl.exists():
        shutil.copy(csl, out_dir / csl.name)
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(exist_ok=True)
    for f in (RES / "figures").glob("*.png"):
        shutil.copy(f, fig_dir / f.name)
    (out_dir / "manuscript.qmd").write_text(text, encoding="utf-8")
    print(f"rendered {out_dir / 'manuscript.qmd'} ({len(text.split())} words incl. tables)")
    write_highlights(n)
    if a.no_render:
        return
    for f in ("docx", "typst"):
        r = subprocess.run(["quarto", "render", "manuscript.qmd", "--to", f], cwd=out_dir, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode:
            sys.exit(r.stderr[-2500:])
    if a.lang == "fa":
        rtl_tables(out_dir / "manuscript.docx")
    FINAL.mkdir(exist_ok=True)
    tag = a.lang.upper()
    shutil.copy(out_dir / "manuscript.docx", FINAL / f"{NAME}_{tag}.docx")
    shutil.copy(out_dir / "manuscript.pdf", FINAL / f"{NAME}_{tag}.pdf")
    print("final:", *(p.name for p in sorted(FINAL.glob(f"*_{tag}.*"))))


if __name__ == "__main__":
    main()
