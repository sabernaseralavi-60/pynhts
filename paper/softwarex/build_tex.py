"""Build the SoftwareX manuscript in LaTeX from the official OSP template (elsarticle) and the text in content.py.

Input : paper/softwarex/template/softwarex-osp-template.tex (Elsevier, 2026; kept for the record, not redistributed)
Output: paper/softwarex/latex/pynhts_softwarex.tex, latex/figures/*.pdf, latex/pynhts_softwarex.pdf (when pdflatex is found),
        paper/softwarex/pynhts_softwarex_latex_sources.zip (what the submission system asks for with a LaTeX manuscript)
Checks: citation numbers follow the order of first appearance, every reference is cited, every figure and section token is
        resolved and every figure is referenced, the word count against the journal's 4,000-word limit.
Run   : python paper/softwarex/build_tex.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import content as C  # noqa: E402

OUTDIR = HERE / "latex"
OUTDIR.mkdir(exist_ok=True)
(OUTDIR / "figures").mkdir(exist_ok=True)
TEMPLATE = (HERE / "template" / "softwarex-osp-template.tex").read_text(encoding="utf8")

SEC_LABELS = {"motivation": 1, "architecture": 2, "examples": 3, "impact": 4, "conclusions": 5}
KEY2NUM = {k: i + 1 for i, k in enumerate(C.CITE_KEYS)}
NUM2KEY = {v: k for k, v in KEY2NUM.items()}
CITED: list[int] = []
FIG_ORDER: list[str] = []
FIG_USED: set[str] = set()
TAB_ORDER: list[str] = []
TAB_USED: set[str] = set()
SEC_USED: set[str] = set()
WORDS = {"abstract": 0, "text": 0, "other": 0}


def esc(s: str) -> str:
    """Escape LaTeX specials in plain text (citations and cross-references are replaced before this is called)."""
    s = s.replace("\\", r"\textbackslash{}")
    for a, b in (("&", r"\&"), ("$", r"\$"), ("#", r"\#"), ("_", r"\_"), ("{", r"\{"), ("}", r"\}")):
        s = s.replace(a, b)
    s = s.replace(' %', chr(1)).replace('%', chr(92) + '%').replace(chr(1), chr(92) + ',' + chr(92) + '%')
    s = s.replace("^", r"\^{}").replace("~", r"\textasciitilde{}")
    s = re.sub(r"(?<=\d)-(?=\d)", "--", s)  # numeric ranges: en dash
    s = re.sub(r'"([^"]*)"', r"``\1''", s)
    return s


def expand(group: str) -> list[int]:
    nums: list[int] = []
    for part in group.split(","):
        if "-" in part:
            a, b = part.split("-")
            nums += list(range(int(a), int(b) + 1))
        else:
            nums.append(int(part))
    return nums


def tex(text: str, count: str | None = None) -> str:
    """Plain text with [n] citations and {fig:x}/{sec:x} tokens -> LaTeX; also records words and citation order."""
    if count:
        WORDS[count] += len(re.findall(r"\S+", re.sub(r"\{(?:fig|sec|tab):\w+\}", "1", text)))
    holders: list[str] = []

    def hold(latex: str) -> str:
        holders.append(latex)
        return f"\x00{len(holders) - 1}\x00"

    def cite(m: re.Match) -> str:
        nums = expand(m.group(1))
        for n in nums:
            if n not in CITED:
                CITED.append(n)
        return hold(r"\cite{" + ",".join(NUM2KEY[n] for n in nums) + "}")

    text = re.sub(r"\[(\d+(?:[,-]\d+)*)\]", cite, text)

    def ref(m: re.Match) -> str:
        kind, key = m.group(1), m.group(2)
        if kind == "fig":
            FIG_USED.add(key)
            return hold(r"Fig.~\ref{fig:" + key + "}")
        if kind == "tab":
            TAB_USED.add(key)
            return hold(r"Table~\ref{tab:" + key + "}")
        SEC_USED.add(key)
        return hold(r"Section~\ref{sec:" + key + "}")

    text = re.sub(r"\{(fig|sec|tab):(\w+)\}", ref, text)
    out = esc(text)
    return re.sub(r"\x00(\d+)\x00", lambda m: holders[int(m.group(1))], out)


def blocks(items: list[tuple], count: str = "text") -> str:
    out: list[str] = []
    for b in items:
        kind = b[0]
        if kind == "p":
            out.append(tex(b[1], count) + "\n")
        elif kind == "h":
            WORDS[count] += len(b[1].split())
            out.append(r"\textbf{" + esc(b[1]) + "}\\\\[2pt]\n")
        elif kind == "eq":
            out.append("\\begin{equation}\n" + b[1] + "\n\\end{equation}\n")
        elif kind == "code":
            WORDS[count] += len(re.findall(r"\S+", b[1]))
            out.append("\\begin{footnotesize}\\begin{verbatim}\n" + b[1] + "\n\\end{verbatim}\\end{footnotesize}\n")
        elif kind == "table":
            _, key, cap, rows = b
            TAB_ORDER.append(key)
            WORDS[count] += sum(len(a.split()) + len(c.split()) for a, c in rows) + 2
            body = "".join("\\texttt{" + esc(a) + "} & " + esc(c) + " \\\\\n" for a, c in rows)
            out.append("\\begin{table}[!ht]\n\\centering\\small\n"
                       f"\\caption{{{tex(cap, count)}}}\n\\label{{tab:{key}}}\n"
                       "\\begin{tabular}{@{}p{3.7cm}p{11.0cm}@{}}\n\\hline\n\\textbf{Module} & \\textbf{Function} \\\\\n\\hline\n"
                       + body + "\\hline\n\\end{tabular}\n\\end{table}\n")
        elif kind == "fig":
            _, key, fname, cap = b
            FIG_ORDER.append(key)
            shutil.copy(HERE / "figures" / f"{fname}.pdf", OUTDIR / "figures" / f"{fname}.pdf")
            width = "0.92" if key == "arch" else "0.62"
            out.append("\\begin{figure}[!ht]\n\\centering\n"
                       f"\\includegraphics[width={width}\\textwidth]{{figures/{fname}.pdf}}\n"
                       f"\\caption{{{tex(cap, count)}}}\n\\label{{fig:{key}}}\n\\end{{figure}}\n")
    return "\n".join(out)


# ---- front matter ----------------------------------------------------------------------------------------------
head, rest = TEMPLATE.split("\\begin{document}", 1)
head = head.replace("\\usepackage{hyperref}", "\\usepackage{hyperref}\n\\usepackage{url}")
head = head.replace("\\setlength{\\parindent}{0pt}", "\\setlength{\\parindent}{0pt}\n\\setlength{\\parskip}{4pt}")  # readable paragraph gaps
authors = []
for i, a in enumerate(C.AUTHORS):
    cor = r"\corref{cor1}" if a["corresponding"] else ""
    authors.append(f"\\author[aff{a['aff']}]{{{esc(a['name'])}{cor}}}\n\\ead{{{a['email'].replace('_', r'\_')}}}")
affs = "\n".join(f"\\address[aff{k}]{{{esc(v)}}}" for k, v in C.AFFILS.items())
front = (
    "\\begin{document}\n\\renewcommand{\\labelenumii}{\\arabic{enumi}.\\arabic{enumii}}\n\n\\begin{frontmatter}\n\n"
    f"\\title{{{esc(C.TITLE)}}}\n\n" + "\n".join(authors) + "\n\\cortext[cor1]{Corresponding author}\n\n" + affs + "\n\n"
    "\\begin{abstract}\n" + tex(C.ABSTRACT, "abstract") + "\n\\end{abstract}\n\n"
    "\\begin{keyword}\n" + " \\sep ".join(esc(k) for k in C.KEYWORDS) + "\n\\end{keyword}\n\n\\end{frontmatter}\n\n"
    "%\\linenumbers\n\n"
)

meta_rows = {
    "C1": esc(C.META[0][1]), "C2": r"\url{" + C.META[1][1] + "}", "C3": esc(C.META[2][1]), "C4": esc(C.META[3][1]),
    "C5": esc(C.META[4][1]), "C6": esc(C.META[5][1]), "C7": r"\url{" + C.META[6][1] + "}", "C8": esc(C.META[7][1]).replace(r"\_", r"\_"),
}
names = {
    "C1": "Current code version", "C2": "Permanent GitHub link to code/repository used for this code version",
    "C3": "Legal Code License", "C4": "Code versioning system used", "C5": "Software code languages, tools, and services used",
    "C6": r"Compilation requirements, operating environments \& dependencies", "C7": "If available Link to developer documentation/manual",
    "C8": "Support email for questions",
}
table = ("\\section*{Required Metadata}\n\n\\section*{Current code version}\n\n"
         "\\begin{table}[!h]\n\\begin{tabular}{|l|p{6.5cm}|p{6.5cm}|}\n\\hline\n"
         "\\textbf{Nr.} & \\textbf{Code metadata description} & \\textbf{Please fill in this column} \\\\\n\\hline\n"
         + "".join(f"{k} & {names[k]} & {meta_rows[k]} \\\\\n\\hline\n" for k in meta_rows)
         + "\\end{tabular}\n\\caption{Code metadata (mandatory)}\n\\label{tab:meta}\n\\end{table}\n\n")

# ---- main text (the template's numbered list of the five mandatory sections) ----------------------------------------
arch = C.SECTIONS["architecture"]
split = next(i for i, b in enumerate(arch) if b[0] == "h")
main = (
    "\\textbf{Main text}\\\\\n\n\\begin{enumerate}\n\n"
    "\\item \\textbf{Motivation and significance}\\label{sec:motivation}\\\\\n\n" + blocks(C.SECTIONS["motivation"]) + "\n"
    "\\item \\textbf{Software description}\\label{sec:architecture}\\\\\n\n\\begin{enumerate}\n"
    "\\item \\textbf{Software architecture.} " + blocks(arch[:split]) + "\n"
    "\\item \\textbf{Software functionalities.} " + blocks(arch[split + 1:]) + "\\end{enumerate}\n\n"
    "\\item \\textbf{Illustrative examples}\\label{sec:examples}\\\\\n\n" + blocks(C.SECTIONS["examples"]) + "\n"
    "\\item \\textbf{Impact}\\label{sec:impact}\\\\\n\n" + blocks(C.SECTIONS["impact"]) + "\n"
    "\\item \\textbf{Conclusions}\\label{sec:conclusions}\\\\\n\n" + blocks(C.SECTIONS["conclusions"]) + "\n"
    "\\end{enumerate}\n\n"
)

decl = [
    ("Acknowledgements", C.ACK), ("Declaration of generative AI and AI-assisted technologies in the manuscript preparation process", C.AI),
    ("CRediT authorship contribution statement", C.CREDIT), ("Funding", C.FUNDING),
    ("Declaration of competing interest", C.COMPETING), ("Data availability", C.DATA),
]
tail = "".join(f"\\section*{{{esc(h)}}}\n\n{tex(t, 'other')}\n\n" for h, t in decl)
bib = "\\begin{thebibliography}{00}\n\n" + "\n\n".join(
    f"\\bibitem{{{k}}} {text}" for k, text in C.REFS) + "\n\n\\end{thebibliography}\n\n"
bib = bib.replace("\\bibitem{", "\\bibitem{")
final = ("\\section*{Current executable software version}\n\n" + esc(C.EXEC_VERSION) + "\n\n\\end{document}\n")

doc = head + front + table + main + tail + bib + final
(OUTDIR / "pynhts_softwarex.tex").write_text(doc, encoding="utf8")

# ---- checks ------------------------------------------------------------------------------------------------------------
assert CITED == sorted(CITED) == list(range(1, len(CITED) + 1)), f"citations out of order: {CITED}"
assert set(CITED) == set(KEY2NUM.values()), f"uncited references: {set(KEY2NUM.values()) - set(CITED)}"
assert set(FIG_ORDER) == FIG_USED, f"figures never referenced: {set(FIG_ORDER) - FIG_USED}"
assert set(TAB_ORDER) == TAB_USED, f"tables never referenced: {set(TAB_ORDER) - TAB_USED}"
assert SEC_USED <= set(SEC_LABELS)
total = WORDS["abstract"] + WORDS["text"]
print("words:", WORDS, "| counted against the 4,000-word limit (abstract + running text + captions + code):", total)
assert total <= 4000, "over the journal's word limit: cut text, do not squeeze the format"
assert WORDS["abstract"] <= 250, "abstract over 250 words"
print("figures:", FIG_ORDER, "| citations:", len(CITED), "| TODO tags:", len(re.findall(r"\[\[AUTHOR-", doc)))

# ---- compile ---------------------------------------------------------------------------------------------------------------
if "--no-pdf" not in sys.argv:
    exe = shutil.which("pdflatex")
    if exe:
        for _ in range(2):
            r = subprocess.run([exe, "-interaction=nonstopmode", "-halt-on-error", "pynhts_softwarex.tex"], cwd=OUTDIR,
                               capture_output=True, text=True)
            if r.returncode:
                print(r.stdout[-2500:])
                raise SystemExit("pdflatex failed")
        log = (OUTDIR / "pynhts_softwarex.log").read_text(encoding="utf8", errors="replace")
        print("LaTeX warnings:", [l for l in log.splitlines() if "Warning" in l and "float" not in l.lower()][:8])
    else:
        print("pdflatex not found: the .tex was written but not compiled")

# ---- the zip the submission system asks for with a LaTeX manuscript (sources, figures, bibliography inside the .tex) ----------
with zipfile.ZipFile(HERE / "pynhts_softwarex_latex_sources.zip", "w", zipfile.ZIP_DEFLATED) as z:
    z.write(OUTDIR / "pynhts_softwarex.tex", "pynhts_softwarex.tex")
    for f in sorted((OUTDIR / "figures").glob("*.pdf")):
        z.write(f, f"figures/{f.name}")
print("zip:", HERE / "pynhts_softwarex_latex_sources.zip")
