"""verified.csv -> refs.bib (only entries the Retraction Guard script resolved)."""
import csv, re
from pathlib import Path
H = Path(__file__).resolve().parent
rows = {}
for r in csv.DictReader(open(H / "verified.csv", encoding="utf-8")):
    rows[r["key"]] = r
# resolved and retraction-checked, but not cited: the subject did not support the sentence it was proposed for (2026-10-23, LeapSpace batch)
PUB = {'korn1999': 'Wiley', 'wolter2007': 'Springer'}
SKIP = {"brown2018", "chauhan2024", "ha2023", "he2022", "liu2011", "matsuo2016", "mcdonald2008", "morrison2018", "su2011", "yan2020",
        "rimjha2021", "elango2007", "sikder2011", "brick2024", "deka2022", "nayeem2026", "fisher2026"}
def esc(s): return re.sub(r"\s+", " ", s.replace("&amp;", "&").replace("<i>", "").replace("</i>", "")).strip()
OVERRIDE = {'desousa2000': '{de Sousa}, Maria Helena and {da Silva}, Nilza Nunes', 'wolter2007': 'Wolter, Kirk M.', 'gelman2007': 'Gelman, Andrew', 'winship1994': 'Winship, Christopher and Radbill, Larry'}
out = []
for k, r in rows.items():
    if k in SKIP:
        continue
    au = " and ".join(a.strip() for a in r["authors"].split(";") if a.strip()) or "Anonymous"
    au = OVERRIDE.get(k, au)
    kind = "book" if r["crossref_type"] in ("book", "monograph") else "article"
    f = [f"  author = {{{esc(au)}}}", f"  title = {{{esc(r['title'])}}}", f"  year = {{{r['year']}}}", f"  doi = {{{r['doi']}}}"]
    if kind == "article":
        f.append(f"  journal = {{{esc(r['venue'])}}}")
        for fld in ("volume", "issue", "pages"):
            if r[fld]: f.append(f"  {fld} = {{{r[fld]}}}")
    else:
        f.append(f"  publisher = {{{esc(PUB.get(k) or r['venue'] or 'Springer')}}}")
    out.append(f"@{kind}{{{k},\n" + ",\n".join(f) + "\n}\n")
(H / "refs.bib").write_text("\n".join(out), encoding="utf-8")
print(len(out), "entries")
