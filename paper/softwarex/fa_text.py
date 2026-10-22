"""Text helpers shared by the Persian builders (Word and XeLaTeX): tokenising, Persian digits, reference tokens.

Markup of content_fa.py: ⟦ltr⟧ spans, [n] citations, {fig:k} {tab:k} {sec:k} cross-references, ASCII digits in Persian text.
"""

from __future__ import annotations

import re

TOKEN = re.compile(r"⟦(?P<ltr>.*?)⟧|(?P<cite>\[\d+(?:[,-]\d+)*\])|\{(?P<kind>fig|tab|sec):(?P<key>\w+)\}", re.S)
_DIG = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
FA_WORD = {"fig": "شکل", "tab": "جدول", "sec": "بخش"}


def to_fa_digits(seg: str) -> str:
    """Persian digits, decimal separator ٫, thousands separator ٬ and percent sign ٪ in a stretch of Persian text."""
    seg = re.sub(r"(\d)\s*%", r"\1٪", seg).replace("%", "٪")

    def conv(m: re.Match) -> str:
        t = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "٬", m.group(0))
        t = re.sub(r"(?<=\d)\.(?=\d)", "٫", t)
        return t.translate(_DIG)

    return re.sub(r"\d+(?:[.,]\d+)*", conv, seg)


def normalise(seg: str) -> str:
    """Typographic clean-up: hamza-izafe written as ه + ZWNJ + ی (fonts without U+0654 show a box), Arabic yeh/kaf to Persian."""
    seg = seg.replace("هٔ", "ه‌ی").replace("ٔ", "")
    return seg.replace("ي", "ی").replace("ك", "ک")


def tokens(text: str, number: dict[tuple[str, str], int]) -> list[tuple[str, str]]:
    """[('fa'|'ltr', text)]; cross-references become Persian words with Persian digits (number maps (kind, key) -> n)."""
    out: list[tuple[str, str]] = []
    pos = 0
    for m in TOKEN.finditer(text):
        if m.start() > pos:
            out.append(("fa", to_fa_digits(normalise(text[pos:m.start()]))))
        if m.group("ltr") is not None:
            out.append(("ltr", m.group("ltr")))
        elif m.group("cite") is not None:
            out.append(("ltr", m.group("cite")))
        else:
            n = number[(m.group("kind"), m.group("key"))]
            out.append(("fa", f"{FA_WORD[m.group('kind')]} {str(n).translate(_DIG)}"))
        pos = m.end()
    if pos < len(text):
        out.append(("fa", to_fa_digits(normalise(text[pos:]))))
    return out


def plain_fa(text: str, number: dict[tuple[str, str], int]) -> str:
    """Tokens joined back to one string (for places that cannot carry direction runs)."""
    return "".join(t for _, t in tokens(text, number))
