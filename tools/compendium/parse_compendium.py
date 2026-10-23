"""Parse the FHWA/ORNL "NHTS Compendium of Uses" PDFs (2006-2022, plus the 2023 PDF) into one record per study.

The editions differ in layout (see `docs/compendium.md`):
  A  2006-2011   running category header, title, "Authors:", source lines, "Abstract:", "Subject areas and Index Terms"
  B  2012-2015   title and authors in ONE block (no separator), "Publication Date:", "Subject Area(s):"
  C  2016        "Title:" / "Author:" labels, chapter given only by the table of contents
  D  2018-2023   "N.M Title:" / "Author(s):" labels, chapter number in the entry number

The table of contents is the ground truth for what is in an edition: its entries carry a consecutive chain of printed
page numbers, and entry j occupies the PDF pages from its page number to the next one (long abstracts spill over).
Self-audit: the share of table-of-contents titles found on their computed PDF page, and the comparison of the number
of entries with the number of `Abstract:` anchors in the PDF. Nothing here is tuned to a number.
Needs `pdftotext` (poppler) on PATH.
"""

from __future__ import annotations

import difflib
import hashlib
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# canonical (current) domains and the names used by earlier editions
DOMAIN_ALIASES: dict[str, str] = {
    "bicycle and pedestrian studies": "Bicycle and pedestrian studies",
    "bike and pedestrian studies": "Bicycle and pedestrian studies",
    "energy consumption": "Energy consumption",
    "environment": "Environment",
    "health": "Health",
    "policy and mobility": "Policy and mobility",
    "special population groups": "Special population groups",
    "special populations": "Special population groups",
    "survey, data synthesis, and other applications": "Survey, data synthesis and other applications",
    "survey design, methodology, and other applications": "Survey, data synthesis and other applications",
    "traffic safety": "Traffic safety",
    "transit planning": "Transit planning",
    "public transportation": "Transit planning",
    "travel behavior": "Travel behavior",
    "trend analysis and market segmentation": "Trend analysis and market segmentation",
    "emerging travel modes": "Emerging travel modes",
    "passive od data product usage": "Passive OD data product usage",
    # chapters that were later dissolved (kept as their own domain, flagged legacy)
    "demographic trends": "Demographic trends (legacy)",
    "gas tax and fee scenarios": "Gas tax and fee scenarios (legacy)",
    "freight movement": "Freight movement (legacy)",
}
CURRENT_DOMAINS = [
    "Bicycle and pedestrian studies", "Energy consumption", "Environment", "Health", "Policy and mobility",
    "Special population groups", "Survey, data synthesis and other applications", "Traffic safety", "Transit planning",
    "Travel behavior", "Trend analysis and market segmentation", "Emerging travel modes", "Passive OD data product usage",
]

EDITIONS = {  # file stem -> (edition label, layout family, covered period)
    "2006-2011_compendium": ("2006-2011", "A", "April 2006 - May 2011"),
    "2012_compendium": ("2012", "B", "June 2011 - December 2012"),
    "2013_compendium": ("2013", "B", "January - December 2013"),
    "2014_compendium": ("2014", "B", "2014"),
    "2015_compendium": ("2015", "B", "2015"),
    "2016_compendium": ("2016", "C", "2016"),
    "2018_compendium": ("2018", "D", "January - June 2018"),
    "2019_compendium": ("2019", "D", "January - December 2019"),
    "2020_compendium": ("2020", "D", "January - December 2020"),
    "2021_compendium": ("2021", "D", "January - December 2021"),
    "2022_compendium": ("2022", "D", "2022"),
    "2023_compendium": ("2023-pdf", "D", "January - June 2023"),
}

_FFFD = "�"
_LABEL_AUTHORS = re.compile(r"^\s*Author(?:s|\(s\))?\s*:\s*", re.M | re.I)
_LABEL_ABSTRACT = re.compile(r"^\s*Abstract\s*:", re.M)
_LABEL_SUBJECT = re.compile(r"^\s*Subject\s+Areas?(?:\s+and\s+Index\s+Terms)?\s*:?", re.M | re.I)
_LABEL_AVAIL = re.compile(r"^\s*Availability\s*:", re.M)
_LABEL_PUBDATE = re.compile(r"^\s*Publication\s+Date\s*:\s*(.+)$", re.M | re.I)
_FOOTER = re.compile(r"^\s*(?:NHTS\s+Compendium\s+\d{4}\s+Page\s+\d+|\d{1,3}|Page\s+\d+)\s*$", re.I)
_TITLE_PREFIX = re.compile(r"^\s*(?:(\d+)\.(\d+)\.?\s+)?Title\s*:\s*", re.I)


def sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pdf_to_pages(path: Path) -> list[str]:
    """Extract the text of a PDF page by page with `pdftotext -layout`."""
    out = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, check=True)
    return out.stdout.decode("utf-8", errors="replace").split("\f")


def clean(s: str) -> str:
    """Collapse whitespace and repair the replacement glyph pdftotext leaves for curly quotes."""
    s = re.sub(r"(?<=\w)" + _FFFD + r"(?=\w)", "'", s)
    s = s.replace(_FFFD, '"').replace("â€™", "'").replace("â€œ", '"').replace("â€\x9d", '"').replace("â€¦", "...")
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip()


def norm(s: str) -> str:
    """Lower-case alphanumerics only, for matching titles."""
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def canon_domain(raw: str) -> str:
    """Map a chapter name of any edition onto the canonical domain list."""
    key = re.sub(r"\s+", " ", raw.strip().rstrip(".").lower()).replace("&", "and")
    return DOMAIN_ALIASES.get(key, raw.strip())


@dataclass
class Entry:
    """One parsed compendium entry."""

    edition: str
    source_file: str
    pdf_page: int
    seq: int
    title: str = ""
    authors: str = ""
    abstract: str = ""
    subject_areas: str = ""
    availability: str = ""
    pub_date_raw: str = ""
    chapter_raw: str = ""
    chapter_marker: str = ""
    chapter_no: int | None = None
    entry_no: str = ""
    split_status: str = "labelled"  # labelled | recovered_from_availability | unsplit
    continued: bool = False
    flags: list[str] = field(default_factory=list)


def _drop_footer(page: str) -> str:
    lines = page.split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and _FOOTER.match(lines[-1]):
        lines.pop()
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def _split_title_authors_by_availability(blob: str, availability: str) -> tuple[str, str, str]:
    """Title and authors share one block (layout B): the availability citation usually repeats the title."""
    na = norm(availability)
    words = blob.split()
    if not na or len(words) < 4:
        return blob, "", "unsplit"
    for k in range(len(words) - 1, 2, -1):
        pref = " ".join(words[:k])
        if len(norm(pref)) >= 12 and norm(pref) in na:
            return pref, " ".join(words[k:]), "recovered_from_availability"
    # second stage: the first author of the citation ("Surname, Given") marks where the authors begin in the blob
    ms = re.match(r"\s*([A-Z][A-Za-z'\-]{2,}),\s+[A-Z]", availability)
    if ms:
        sur = ms.group(1).lower()
        for i in range(3, len(words)):
            if re.sub(r"[^a-z'\-]", "", words[i].lower()) == sur:
                start = i - 1
                while start - 1 >= 3 and re.fullmatch(r"[A-Z]\.?|Dr\.?|Prof\.?", words[start]):
                    start -= 1
                return " ".join(words[:start]), " ".join(words[start:]), "heuristic_surname"
    return blob, "", "unsplit"


def parse_entry_text(text: str, family: str) -> Entry:
    """Parse the text of one entry (all of its pages, footers removed).

    The `Abstract:` anchor is used when present; a few entries have no abstract label, in which case the header runs
    to the first `Subject Areas:`/`Availability:` label and the entry is flagged.
    """
    m_abs = _LABEL_ABSTRACT.search(text)
    e = Entry(edition="", source_file="", pdf_page=0, seq=0)
    if m_abs:
        header, rest = text[: m_abs.start()], text[m_abs.end():]
    else:
        e.flags.append("no_abstract_label")
        cut = [m.start() for m in (_LABEL_SUBJECT.search(text), _LABEL_AVAIL.search(text)) if m]
        header, rest = (text[: min(cut)], text[min(cut):]) if cut else (text, "")
    m_av = _LABEL_AVAIL.search(rest)
    if m_av:
        e.availability = clean(rest[m_av.end():])
        rest_main = rest[: m_av.start()]
    else:
        rest_main = rest
        e.flags.append("no_availability")
    m_sub = _LABEL_SUBJECT.search(rest_main)
    if m_sub:
        e.abstract = clean(rest_main[: m_sub.start()]) if m_abs else ""
        e.subject_areas = clean(rest_main[m_sub.end():])
    else:
        e.abstract = clean(rest_main) if m_abs else ""
        e.flags.append("no_subject_areas")

    hl = [ln.rstrip() for ln in header.split("\n") if ln.strip()]
    if family == "A" and hl:  # running category header on the first line
        e.chapter_raw = clean(hl[0])
        hl = hl[1:]
    if hl and family != "A":  # first page of a chapter carries its heading ("4. Environment"), alone or glued to the title
        htxt = "\n".join(hl)  # `\s+` below also spans the line break of a wrapped heading
        for alias in sorted(DOMAIN_ALIASES, key=len, reverse=True):
            mh = re.match(r"^\s*((?:Chapter\s+)?\d{1,2}\.?\s+)?" + re.escape(alias).replace(r"\ ", r"\s+") + r"\b[ \t\.]*", htxt, re.I)
            if mh and (mh.group(1) or mh.end() >= len(hl[0].rstrip())):
                e.chapter_marker = DOMAIN_ALIASES[alias]
                hl = [x for x in htxt[mh.end():].split("\n") if x.strip()]
                break
    hdr = "\n".join(hl)
    mt = _TITLE_PREFIX.match(hdr)
    if mt:
        if mt.group(1):
            e.chapter_no, e.entry_no = int(mt.group(1)), f"{mt.group(1)}.{mt.group(2)}"
        hdr = hdr[mt.end():]
    ma = _LABEL_AUTHORS.search(hdr)
    if ma:
        e.title, e.authors = clean(hdr[: ma.start()]), clean(hdr[ma.end():])
        e.split_status = "labelled"
    else:
        pd_m = _LABEL_PUBDATE.search(hdr)
        if pd_m:
            e.pub_date_raw = clean(pd_m.group(1))
            hdr = hdr[: pd_m.start()]
        e.title, e.authors, e.split_status = _split_title_authors_by_availability(clean(hdr), e.availability)
    if family == "A":  # authors line is followed by source lines (journal, year): keep the last year as publication date
        yrs = re.findall(r"\b(19[89]\d|20[0-2]\d)\b", e.authors)
        if yrs and not e.pub_date_raw:
            e.pub_date_raw = yrs[-1]
    return e


@dataclass
class Toc:
    """Table of contents: a stream of (chapter, line) for title alignment and a chain of items with printed page numbers."""

    stream: list[tuple[str, str]]
    chain: list[tuple[int, str, str]]  # (printed page number, chapter, text)
    chapter_names: dict[int, str]  # chapter number -> canonical domain (layout D)


_HEAD_NUM = re.compile(r"^\s*(?:Chapter\s+)?(\d{1,2})\.?\s+(.+?)\s*$")
_END_NUM = re.compile(r"(\d{1,3})\s*$")


def _heading(line: str) -> tuple[int | None, str] | None:
    """Return (chapter number or None, canonical domain) when the line is a chapter heading of the table of contents."""
    core = re.sub(r"\.{2,}.*$", "", line).strip()
    core = re.sub(r"\s{3,}\d{1,3}$", "", core).strip()
    m = _HEAD_NUM.match(core)
    for num, cand in ((int(m.group(1)) if m else None, m.group(2) if m else None), (None, core)):
        if cand:
            key = cand.strip().rstrip(".").lower().replace("&", "and")
            if key in DOMAIN_ALIASES:
                return num, canon_domain(key)
    return None


def parse_toc(pages: list[str], first_body: int, family: str) -> Toc:
    """Read the pages before the first entry.

    The chain takes a line that ends in a number as an item terminator when the number follows the previous one by 1 to 4
    (long abstracts span two or three pages); chapter headings are recognised by name and are not items.
    """
    cand: list[tuple[str, str, int | None]] = []
    names: dict[int, str] = {}
    loose = family in ("A", "B")  # layouts without dot leaders on every line
    for p in pages[1:first_body]:
        for raw in p.split("\n"):
            ln = re.sub(r"(?:\s?\.){4,}", " ... ", raw)
            if not ln.strip() or _FOOTER.match(ln) or re.search(r"NHTS Compendium \d{4}\s+Page\s+\d+", ln):
                continue
            h = _heading(ln)
            if h and (re.search(r"\.{3,}", ln) or re.match(r"^\s*(Chapter\s+)?\d{1,2}\.?\s", ln) or re.match(r"^\s*[A-Z ,&]+\s*$", ln)):
                if h[0] is not None:
                    names.setdefault(h[0], h[1])
                cand.append(("head", h[1], None))
                continue
            m = _END_NUM.search(ln.rstrip())
            ok = re.search(r"\.{3,}\s*\d{1,3}\s*$", ln) is not None
            if loose and not ok:
                ok = re.search(r"[A-Za-z\)\.,]\s{1,}\d{1,3}\s*$", ln) is not None
            cand.append(("line", ln.strip(), int(m.group(1)) if m and ok else None))

    def run(start: int) -> list[int]:
        prev, hit = start - 1, []
        for i, (kind, _t, n) in enumerate(cand):
            if kind == "line" and n is not None and prev < n <= prev + 4 and (n == start or hit):
                hit.append(i)
                prev = n
        return hit

    nums = sorted({c[2] for c in cand if c[0] == "line" and c[2] is not None and c[2] <= 60})
    best: list[int] = []
    for start in nums[:6]:
        r = run(start)
        if len(r) > len(best):
            best = r
    chosen = set(best)
    stream: list[tuple[str, str]] = []
    chain: list[tuple[int, str, str]] = []
    chapter, buf = "", []
    for i, (kind, text, num) in enumerate(cand):
        if kind == "head":
            chapter, buf = text, []
            continue
        stream.append((chapter, text))
        buf.append(text)
        if i in chosen and num is not None:
            chain.append((num, chapter, clean(" ".join(buf))))
            buf = []
    return Toc(stream, chain, names)


def align_chapters(entries: list[Entry], toc: Toc) -> int:
    """Give each entry the chapter of the table-of-contents line that holds its title (monotone search); return hits."""
    text, owner, pos = "", [], 0
    for chap, ln in toc.stream:
        t = norm(ln)
        owner.append((pos, chap))
        text += t
        pos += len(t)
    starts = [o[0] for o in owner]
    import bisect

    cursor, hits = 0, 0
    found: list[str | None] = []
    for e in entries:
        key = norm(e.title)[:26]
        i = -1
        if len(key) >= 12:
            i = text.find(key, cursor)  # table of contents and body share the order: prefer the next match
            if i < 0:
                i = text.find(key)
            if i < 0:
                i = text.find(key[:16])
        if i >= 0:
            found.append(owner[bisect.bisect_right(starts, i) - 1][1])
            cursor = max(cursor, i + 10) if i >= cursor else cursor
            hits += 1
        else:
            found.append(None)
    for k, e in enumerate(entries):  # unmatched titles inherit the chapter when both neighbours agree
        c = found[k]
        if c is None:
            prev = next((found[j] for j in range(k - 1, -1, -1) if found[j]), None)
            nxt = next((found[j] for j in range(k + 1, len(found)) if found[j]), None)
            if prev and prev == nxt:
                c = prev
                e.flags.append("chapter_inherited")
        if c:
            e.chapter_raw = c
    return hits


@dataclass
class EditionResult:
    """Entries of one PDF plus the numbers the self-audit needs."""

    stem: str
    edition: str
    family: str
    period: str
    n_pdf_pages: int
    entries: list[Entry]
    n_abstract_anchors: int
    n_toc_chain: int
    n_toc_stream_lines: int
    page_offset: int
    toc_page_score: float
    n_anchorless: int
    n_multi_page: int
    n_chapter_aligned: int
    chapter_counts: dict[str, int]
    notes: list[str]
    n_title_labels: int = 0
    intro_stated_total: int | None = None


def _first_body_page(pages: list[str]) -> int:
    for i, p in enumerate(pages):
        if _LABEL_ABSTRACT.search(p):
            return i
    return len(pages)


def _find_offset(pages: list[str], chain: list[tuple[int, str, str]], first_abs: int) -> tuple[int, float]:
    """Find offset so that printed page p sits on PDF page index offset + p - 1; score = share of titles found there."""
    norms = [norm(p) for p in pages]
    keys = [norm(re.sub(r"^\s*(?:\d+\.\d+\.?\s+)?Title\s*:\s*", "", t))[:24] for _n, _c, t in chain]
    best, best_s = 0, -1.0
    for off in range(max(0, first_abs - 45), first_abs + 4):
        hit = tot = 0
        for (n, _c, _t), k in zip(chain, keys, strict=True):
            if not k:
                continue
            tot += 1
            i = off + n - 1
            if 0 <= i < len(pages) and k in norms[i]:
                hit += 1
        s = hit / tot if tot else 0.0
        if s > best_s:
            best, best_s = off, s
    return best, best_s


def parse_edition(path: Path) -> EditionResult:
    """Parse one PDF edition end to end."""
    stem = path.stem
    edition, family, period = EDITIONS[stem]
    pages = pdf_to_pages(path)
    if edition == "2018":  # the LaTeX edition hyphenates at line ends
        pages = [re.sub(r"(?<=[a-z])-\n\s*(?=[a-z])", "", p) for p in pages]
    first_abs = _first_body_page(pages)
    toc = parse_toc(pages, first_abs, family)
    off, score = _find_offset(pages, toc.chain, first_abs) if toc.chain else (first_abs, 0.0)
    stripped = [_drop_footer(p) for p in pages]
    anchor_pages = {i for i, p in enumerate(pages) if i >= first_abs - 1 and _LABEL_ABSTRACT.search(p)}
    chain_pages = {off + n - 1 for n, _c, _t in toc.chain} if score >= 0.8 else set()
    starts = sorted(anchor_pages | {i for i in chain_pages if 0 <= i < len(pages)})
    # walk the body: a start page opens an entry; other pages continue it unless they carry a second set of labels
    groups: list[list[int]] = []
    anchorless = 0
    for i in range(starts[0] if starts else len(pages), len(pages)):
        txt = stripped[i].strip()
        if not txt:
            continue
        if i in starts:
            groups.append([i])
        elif groups:
            prev_txt = "\n".join(stripped[j] for j in groups[-1])
            if (_LABEL_AVAIL.search(txt) or _LABEL_SUBJECT.search(txt)) and _LABEL_AVAIL.search(prev_txt):
                groups.append([i])  # a new entry whose first page was not in the chain and has no abstract label
            else:
                groups[-1].append(i)
    entries: list[Entry] = []
    multi = 0
    for g in groups:
        e = parse_entry_text("\n".join(stripped[i] for i in g), family)
        if "no_abstract_label" in e.flags:
            anchorless += 1
        e.edition, e.source_file, e.pdf_page, e.seq = edition, path.name, g[0] + 1, len(entries) + 1
        if len(g) > 1:
            e.continued, multi = True, multi + 1
        entries.append(e)
    # chapters
    aligned = 0
    if family == "A":
        for e in entries:
            e.chapter_raw = canon_domain(e.chapter_raw)
    else:
        by_page = {off + n - 1: c for n, c, _t in toc.chain} if score >= 0.8 else {}
        aligned = align_chapters(entries, toc)
        markers_used = sum(1 for e in entries if e.chapter_marker) >= 5
        for e in entries:
            if e.pdf_page - 1 in by_page and by_page[e.pdf_page - 1]:
                e.chapter_raw = by_page[e.pdf_page - 1]
        if markers_used:  # the body marks every chapter start: carry the marker forward, audit it against the table of contents
            cur = ""
            for e in entries:
                cur = e.chapter_marker or cur
                if e.chapter_raw and cur and e.chapter_raw != cur:
                    e.flags.append("chapter_marker_disagrees_with_toc")
                e.chapter_raw = cur or e.chapter_raw
        if family == "D":  # the entry number carries the chapter and beats the alignment
            for e in entries:
                if e.chapter_no and e.chapter_no in toc.chapter_names:
                    if e.chapter_raw and e.chapter_raw != toc.chapter_names[e.chapter_no]:
                        e.flags.append("chapter_alignment_disagrees")
                    e.chapter_raw = toc.chapter_names[e.chapter_no]
    counts: dict[str, int] = {}
    for e in entries:
        counts[e.chapter_raw or "(none)"] = counts.get(e.chapter_raw or "(none)", 0) + 1
    n_anchor = sum(len(_LABEL_ABSTRACT.findall(p)) for p in pages)
    notes: list[str] = []
    if toc.chain and len(toc.chain) != len(entries):
        notes.append(f"table-of-contents chain ({len(toc.chain)}) != entries ({len(entries)})")
    return EditionResult(
        stem=stem, edition=edition, family=family, period=period, n_pdf_pages=len(pages), entries=entries,
        n_abstract_anchors=n_anchor, n_toc_chain=len(toc.chain), n_toc_stream_lines=len(toc.stream), page_offset=off,
        toc_page_score=score, n_anchorless=anchorless, n_multi_page=multi, n_chapter_aligned=aligned, chapter_counts=counts, notes=notes,
        n_title_labels=len(re.findall(r"^\s*(?:\d+\.\d+\.?\s+)?Title\s*:", "\n".join(pages), re.M)),
        intro_stated_total=_intro_total(pages[:first_abs]),
    )


def _intro_total(front: list[str]) -> int | None:
    m = re.search(r"approximately\s+(\d{2,4})\s+(?:research\s+)?(?:papers|articles|studies)", " ".join(front), re.I)
    return int(m.group(1)) if m else None


def title_similarity(a: str, b: str) -> float:
    """Ratio of the normalised titles, for the deduplication step."""
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()
