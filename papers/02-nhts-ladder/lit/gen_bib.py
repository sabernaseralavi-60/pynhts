"""verified.csv -> refs.bib (only entries the Retraction Guard script resolved)."""
import csv, re
from pathlib import Path
H = Path(__file__).resolve().parent
rows = {}
for r in csv.DictReader(open(H / "verified.csv", encoding="utf-8")):
    rows[r["key"]] = r
def esc(s): return re.sub(r"\s+", " ", s.replace("&amp;", "&").replace("<i>", "").replace("</i>", "")).strip()
OVERRIDE = {'wolter2007': 'Wolter, Kirk M.', 'gelman2007': 'Gelman, Andrew', 'winship1994': 'Winship, Christopher and Radbill, Larry'}
out = []
for k, r in rows.items():
    au = " and ".join(a.strip() for a in r["authors"].split(";") if a.strip()) or "Anonymous"
    au = OVERRIDE.get(k, au)
    kind = "book" if r["crossref_type"] in ("book", "monograph") else "article"
    f = [f"  author = {{{esc(au)}}}", f"  title = {{{esc(r['title'])}}}", f"  year = {{{r['year']}}}", f"  doi = {{{r['doi']}}}"]
    if kind == "article":
        f.append(f"  journal = {{{esc(r['venue'])}}}")
        for fld in ("volume", "issue", "pages"):
            if r[fld]: f.append(f"  {fld} = {{{r[fld]}}}")
    else:
        f.append(f"  publisher = {{{esc(r['venue'] or 'Springer')}}}")
    out.append(f"@{kind}{{{k},\n" + ",\n".join(f) + "\n}\n")
(H / "refs.bib").write_text("\n".join(out), encoding="utf-8")
print(len(out), "entries")
