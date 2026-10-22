"""Word versions of the pynhts manuscript, English and Persian (python-docx; Persian = proper RTL paragraphs, complex-script fonts).

Run with a Python that has python-docx (+ arabic-reshaper not needed here):  python paper/softwarex/build_docx.py
Output: final/pynhts_softwarex_EN.docx and final/pynhts_softwarex_FA.docx
Same sources as the PDFs: content.py (English) and content_fa.py (Persian); every number comes from the repository's result files.
The equation is converted by pandoc (Quarto's copy) to a native Word equation; the figures are the PNG files in figures/.
"""

from __future__ import annotations

import copy
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT  # noqa: F401
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Cm, Pt, RGBColor
from lxml import etree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import content as C  # noqa: E402
import content_fa as F  # noqa: E402
import fa_text as T  # noqa: E402

FINAL = HERE / "final"
FINAL.mkdir(exist_ok=True)
PANDOC = "C:/Program Files/Quarto/bin/tools/pandoc.exe"
SEC_NUM = {"motivation": 1, "architecture": 2, "examples": 3, "impact": 4, "conclusions": 5}
LATIN_FONT = "Times New Roman"
FA_FONT = "B Nazanin"
CODE_FONT = "Consolas"


# ------------------------------------------------------------------------------------------------ low-level helpers
def _rpr(*, font: str, cs: str, size: float, bold=False, italic=False, rtl=False, vert: str | None = None, color: str | None = None):
    rpr = OxmlElement("w:rPr")
    f = OxmlElement("w:rFonts")
    for a in ("ascii", "hAnsi", "eastAsia"):
        f.set(qn(f"w:{a}"), font)
    f.set(qn("w:cs"), cs)
    rpr.append(f)
    if bold:
        rpr.append(OxmlElement("w:b"))
        rpr.append(OxmlElement("w:bCs"))
    if italic:
        rpr.append(OxmlElement("w:i"))
        rpr.append(OxmlElement("w:iCs"))
    if color:
        c = OxmlElement("w:color")
        c.set(qn("w:val"), color)
        rpr.append(c)
    for tag in ("w:sz", "w:szCs"):
        s = OxmlElement(tag)
        s.set(qn("w:val"), str(int(size * 2)))
        rpr.append(s)
    if vert:
        v = OxmlElement("w:vertAlign")
        v.set(qn("w:val"), vert)
        rpr.append(v)
    if rtl:
        rpr.append(OxmlElement("w:rtl"))
    lang = OxmlElement("w:lang")
    lang.set(qn("w:val"), "en-US")
    lang.set(qn("w:bidi"), "fa-IR")
    rpr.append(lang)
    return rpr


def run(par, text: str, **kw):
    r = OxmlElement("w:r")
    r.append(_rpr(**kw))
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    par._p.append(r)
    return r


def new_par(doc_or_cell, *, rtl: bool, align: str = "both", before: float = 0, after: float = 6, style: str | None = None,
            left: float | None = None, hanging: float | None = None, keep_next: bool = False, line: float = 1.15):
    p = doc_or_cell.add_paragraph(style=style) if style else doc_or_cell.add_paragraph()
    ppr = p._p.get_or_add_pPr()
    if rtl:
        ppr.append(OxmlElement("w:bidi"))
    if keep_next:
        p.paragraph_format.keep_with_next = True
    pf = p.paragraph_format
    pf.space_before, pf.space_after = Pt(before), Pt(after)
    pf.line_spacing = line
    if left is not None:
        pf.left_indent = Cm(left)
    if hanging is not None:
        pf.first_line_indent = Cm(-hanging)
    p.alignment = {"both": WD_ALIGN_PARAGRAPH.JUSTIFY, "center": WD_ALIGN_PARAGRAPH.CENTER, "left": WD_ALIGN_PARAGRAPH.LEFT,
                   "right": WD_ALIGN_PARAGRAPH.RIGHT}[align]
    return p


class Lang:
    """Everything that differs between the two versions."""

    def __init__(self, code: str):
        self.fa = code == "fa"
        self.size = 12.5 if self.fa else 11
        self.cs = FA_FONT

    def rich(self, par, text: str, num: dict, *, size: float | None = None, bold=False, italic=False, color=None) -> None:
        """Write text with tokens: Persian runs are RTL, ⟦ltr⟧ spans and citations are Latin runs."""
        size = size or self.size
        if self.fa:
            for kind, seg in T.tokens(text, num):
                if kind == "fa":
                    run(par, seg, font=FA_FONT, cs=FA_FONT, size=size, bold=bold, italic=italic, rtl=True, color=color)
                else:
                    run(par, seg, font=LATIN_FONT, cs=LATIN_FONT, size=size - 1.5, bold=bold, italic=italic, rtl=False, color=color)
        else:
            run(par, expand_en(text, num), font=LATIN_FONT, cs=LATIN_FONT, size=size, bold=bold, italic=italic, color=color)


def expand_en(text: str, num: dict) -> str:
    def ref(m):
        kind, key = m.group(1), m.group(2)
        return {"fig": "Fig. ", "tab": "Table ", "sec": "Section "}[kind] + str(num[(kind, key)])

    text = re.sub(r"\{(fig|tab|sec):(\w+)\}", ref, text)
    return re.sub(r"(?<=\d)-(?=\d)", "\u2013", text)


# ------------------------------------------------------------------------------------------------ equation (pandoc -> OMML)
def omml(tex: str):
    with tempfile.TemporaryDirectory() as d:
        src, out = Path(d) / "e.md", Path(d) / "e.docx"
        src.write_text(f"$${tex}$$\n", encoding="utf8")
        subprocess.run([PANDOC, str(src), "-o", str(out)], check=True, capture_output=True)
        with zipfile.ZipFile(out) as z:
            xml = z.read("word/document.xml")
    root = etree.fromstring(xml)
    ns = {"m": "http://schemas.openxmlformats.org/officeDocument/2006/math"}
    found = root.xpath("//m:oMathPara", namespaces=ns) or root.xpath("//m:oMath", namespaces=ns)
    if not found:
        raise RuntimeError("pandoc produced no equation")
    return copy.deepcopy(found[0])


# ------------------------------------------------------------------------------------------------ tables, figures, code
def set_cell_borders_table(table, rtl: bool):
    tblpr = table._tbl.tblPr
    if rtl:
        bv = OxmlElement("w:bidiVisual")
        style = tblpr.find(qn("w:tblStyle"))
        (style.addnext(bv) if style is not None else tblpr.insert(0, bv))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER


def shade(cell, fill: str):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcpr.append(shd)


def add_code(doc, code: str):
    for line in code.split("\n"):
        p = new_par(doc, rtl=False, align="left", after=0, line=1.0, left=0.4)
        run(p, line if line else " ", font=CODE_FONT, cs=CODE_FONT, size=8.5, color="1F2937")
        ppr = p._p.get_or_add_pPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), "F3F4F6")
        ppr.insert_element_before(shd, "w:tabs", "w:suppressAutoHyphens", "w:bidi", "w:spacing", "w:ind", "w:contextualSpacing", "w:jc", "w:rPr")
    new_par(doc, rtl=False, after=4)


def caption(doc, L: Lang, label: str, text: str, num: dict, *, keep_next=False):
    p = new_par(doc, rtl=L.fa, align="center", after=8, before=2, keep_next=keep_next)
    L.rich(p, label + " ", num, size=L.size - 1, bold=True)
    L.rich(p, text, num, size=L.size - 1)


# ------------------------------------------------------------------------------------------------ the document
def numbering(secs: dict[str, list[tuple]]) -> dict:
    num: dict = {(("sec"), k): v for k, v in SEC_NUM.items()}
    f = t = 0
    t = 1  # the metadata table is Table 1
    for key in SEC_NUM:
        for b in secs[key]:
            if b[0] == "fig":
                f += 1
                num[("fig", b[1])] = f
            elif b[0] == "table":
                t += 1
                num[("tab", b[1])] = t
    return num


def refs_plain(entry: str) -> str:
    s = entry
    for a, b in ((r'H\"orl', "Hörl"), (r"Bala\'c", "Balać"), (r"\^Ile", "Île"), (r"\%", "%")):
        s = s.replace(a, b)
    return re.sub(r"\\url\{([^}]*)\}", r"\1", s)


def build(code: str) -> Path:
    L = Lang(code)
    M = F if L.fa else C
    secs = M.SECTIONS
    num = numbering(secs)
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.4)
    sec.top_margin = sec.bottom_margin = Cm(2.3)
    for st in ("Normal", "Heading 1", "Heading 2"):
        doc.styles[st].font.color.rgb = RGBColor(0, 0, 0)
    rtl = L.fa

    def H(text: str, level: int = 1):
        p = new_par(doc, rtl=rtl, align="both", before=12 if level == 1 else 8, after=4, style=f"Heading {level}", keep_next=True)
        L.rich(p, text, num, size=L.size + (2 if level == 1 else 1), bold=True)
        return p

    def P(text: str, *, align="both", after=6, size=None, bold=False, italic=False):
        p = new_par(doc, rtl=rtl, align=align, after=after)
        L.rich(p, text, num, size=size, bold=bold, italic=italic)
        return p

    # ---- title block
    p = new_par(doc, rtl=rtl, align="center", after=10)
    L.rich(p, M.TITLE, num, size=L.size + 5, bold=True)
    authors = M.AUTHORS_FA if L.fa else C.AUTHORS
    p = new_par(doc, rtl=rtl, align="center", after=4)
    for i, a in enumerate(authors):
        if i:
            L.rich(p, "،  " if L.fa else ",  ", num)
        L.rich(p, a["name"], num, size=L.size + 1, bold=True)
        run(p, a["aff"] + ("*" if a["corresponding"] else ""), font=LATIN_FONT, cs=LATIN_FONT, size=L.size, rtl=False, vert="superscript")
    affs = M.AFFILS_FA if L.fa else C.AFFILS
    for k, v in affs.items():
        p = new_par(doc, rtl=rtl, align="center", after=1)
        run(p, k + " ", font=LATIN_FONT, cs=LATIN_FONT, size=L.size - 1.5, rtl=False, vert="superscript")
        L.rich(p, v, num, size=L.size - 1.5, italic=not L.fa)
    cor = [a for a in authors if a["corresponding"]][0]
    p = new_par(doc, rtl=rtl, align="center", after=10)
    L.rich(p, ("* " + F.HEADINGS["corresponding"] + ": ") if L.fa else "* Corresponding author: ", num, size=L.size - 1.5)
    run(p, cor["email"], font=LATIN_FONT, cs=LATIN_FONT, size=L.size - 1.5, rtl=False)

    H(F.HEADINGS["abstract"] if L.fa else "Abstract", 2)
    P(M.ABSTRACT)
    p = new_par(doc, rtl=rtl, align="both", after=10)
    L.rich(p, (F.HEADINGS["keywords"] + ": ") if L.fa else "Keywords: ", num, bold=True)
    L.rich(p, ("، " if L.fa else "; ").join(M.KEYWORDS), num)

    # ---- metadata table (Table 1)
    H(F.HEADINGS["meta"] if L.fa else "Required metadata", 2)
    names = F.META_NAMES if L.fa else {
        "C1": "Current code version", "C2": "Permanent GitHub link to code/repository used for this code version",
        "C3": "Legal Code License", "C4": "Code versioning system used", "C5": "Software code languages, tools, and services used",
        "C6": "Compilation requirements, operating environments & dependencies",
        "C7": "If available Link to developer documentation/manual", "C8": "Support email for questions"}
    meta = F.META_FA if L.fa else C.META
    tbl = doc.add_table(rows=1 + len(meta), cols=3)
    tbl.style = "Table Grid"
    set_cell_borders_table(tbl, rtl)
    heads = ["شماره", "توضیح فراداده", "مقدار"] if L.fa else ["Nr.", "Code metadata description", "Please fill in this column"]
    widths = [Cm(1.6), Cm(6.4), Cm(8.2)]
    for j, h in enumerate(heads):
        c = tbl.rows[0].cells[j]
        c.width = widths[j]
        shade(c, "E5E7EB")
        cp = c.paragraphs[0]
        if rtl:
            cp._p.get_or_add_pPr().append(OxmlElement("w:bidi"))
        L.rich(cp, h, num, size=L.size - 1.5, bold=True)
    for i, (k, v) in enumerate(meta, start=1):
        for j, txt in enumerate((k, names[k], v)):
            c = tbl.rows[i].cells[j]
            c.width = widths[j]
            cp = c.paragraphs[0]
            if rtl:
                cp._p.get_or_add_pPr().append(OxmlElement("w:bidi"))
            if j == 2 and not L.fa:
                run(cp, txt, font=LATIN_FONT, cs=LATIN_FONT, size=L.size - 1.5)
            else:
                L.rich(cp, txt, num, size=L.size - 1.5)
    caption(doc, L, ("جدول 1." if L.fa else "Table 1."), "فراداده‌های کد (الزامی)" if L.fa else "Code metadata (mandatory)", num)

    # ---- main text
    H(F.HEADINGS["main"] if L.fa else "Main text", 2)
    titles = {
        "motivation": (F.HEADINGS["motivation"] if L.fa else "Motivation and significance"),
        "architecture": (F.HEADINGS["architecture"] if L.fa else "Software description"),
        "examples": (F.HEADINGS["examples"] if L.fa else "Illustrative examples"),
        "impact": (F.HEADINGS["impact"] if L.fa else "Impact"),
        "conclusions": (F.HEADINGS["conclusions"] if L.fa else "Conclusions"),
    }
    fa_n = lambda n: str(n).translate(T._DIG)  # noqa: E731

    def blocks(items: list[tuple]):
        for b in items:
            kind = b[0]
            if kind == "p":
                P(b[1])
            elif kind == "h":
                p = new_par(doc, rtl=rtl, align="both", before=4, after=3, keep_next=True)
                L.rich(p, b[1], num, bold=True)
            elif kind == "code":
                add_code(doc, b[1])
            elif kind == "eq":
                p = new_par(doc, rtl=False, align="center", after=6)
                p._p.append(omml(b[1]))
            elif kind == "fig":
                _, key, fname, cap = b
                n = num[("fig", key)]
                p = new_par(doc, rtl=False, align="center", after=2, keep_next=True)
                width = Cm(15.5) if key == "arch" else Cm(10.5)
                p.add_run().add_picture(str(HERE / "figures" / f"{fname}.png"), width=width)
                caption(doc, L, (f"شکل {fa_n(n)}." if L.fa else f"Fig. {n}."), cap, num)
            elif kind == "table":
                _, key, cap, rows = b
                n = num[("tab", key)]
                caption(doc, L, (f"جدول {fa_n(n)}." if L.fa else f"Table {n}."), cap, num, keep_next=True)
                t = doc.add_table(rows=1 + len(rows), cols=2)
                t.style = "Table Grid"
                set_cell_borders_table(t, rtl)
                for j, h in enumerate(("ماژول", "کارکرد") if L.fa else ("Module", "Function")):
                    c = t.rows[0].cells[j]
                    c.width = Cm(4.4) if j == 0 else Cm(11.8)
                    shade(c, "E5E7EB")
                    cp = c.paragraphs[0]
                    if rtl:
                        cp._p.get_or_add_pPr().append(OxmlElement("w:bidi"))
                    L.rich(cp, h, num, size=L.size - 1.5, bold=True)
                for i, (a, c_) in enumerate(rows, start=1):
                    for j, txt in enumerate((a, c_)):
                        c = t.rows[i].cells[j]
                        c.width = Cm(4.4) if j == 0 else Cm(11.8)
                        cp = c.paragraphs[0]
                        if rtl:
                            cp._p.get_or_add_pPr().append(OxmlElement("w:bidi"))
                        if j == 0:
                            run(cp, a, font=CODE_FONT, cs=CODE_FONT, size=8.5)
                        else:
                            L.rich(cp, txt, num, size=L.size - 1.5)
                new_par(doc, rtl=rtl, after=4)

    for i, key in enumerate(SEC_NUM, start=1):
        items = secs[key]
        label = (f"{fa_n(i)}. " if L.fa else f"{i}. ") + titles[key]
        H(label, 1)
        if key == "architecture":
            split = next(k for k, b in enumerate(items) if b[0] == "h")
            H((f"{fa_n(2)}.{fa_n(1)} " + F.HEADINGS["arch_sub"]) if L.fa else "2.1 Software architecture", 2)
            blocks(items[:split])
            H((f"{fa_n(2)}.{fa_n(2)} " + F.HEADINGS["func_sub"]) if L.fa else "2.2 Software functionalities", 2)
            blocks(items[split + 1:])
        else:
            blocks(items)

    # ---- declarations and references
    decl = [("ack", M.ACK), ("ai", M.AI), ("credit", M.CREDIT), ("funding", M.FUNDING), ("competing", M.COMPETING), ("data", M.DATA)]
    en_heads = {"ack": "Acknowledgements",
                "ai": "Declaration of generative AI and AI-assisted technologies in the manuscript preparation process",
                "credit": "CRediT authorship contribution statement", "funding": "Funding", "competing": "Declaration of competing interest",
                "data": "Data availability"}
    for k, text in decl:
        H(F.HEADINGS[k] if L.fa else en_heads[k], 2)
        P(text)
    H(F.HEADINGS["refs"] if L.fa else "References", 2)
    for n, (_, entry) in enumerate(C.REFS, start=1):
        p = new_par(doc, rtl=False, align="left", after=3, left=0.9, hanging=0.9, line=1.0)
        run(p, f"[{n}]  " + refs_plain(entry), font=LATIN_FONT, cs=LATIN_FONT, size=9.5)
    H(F.HEADINGS["exec"] if L.fa else "Current executable software version", 2)
    P(M.EXEC_VERSION)

    # ---- footer page number
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = fp.add_run()
    for kind, txt in (("begin", None), (None, " PAGE "), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = txt
        r._r.append(el)

    out = FINAL / f"pynhts_softwarex_{'FA' if L.fa else 'EN'}.docx"
    doc.save(out)
    return out


if __name__ == "__main__":
    for lg in ("en", "fa"):
        print(build(lg))
