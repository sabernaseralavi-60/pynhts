"""Retraction Guard + metadata check for every reference of paper 02 (Crossref and OpenAlex REST).

    python lit/verify_refs.py refs_to_check.txt      # one DOI per line, optional "|key" suffix
    python lit/verify_refs.py --query "author title year"   # resolve a DOI from a bibliographic string

Writes lit/verified.csv (key, doi, title, authors, year, venue, volume, pages, crossref_type, retracted_openalex,
updated_by, checked) and prints one line per DOI. Nothing is cited that this script could not resolve.
"""

import csv
import datetime
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
UA = {"User-Agent": "pynhts-paper02/1.0 (mailto:saber_naseralavi@uk.ac.ir)"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def crossref(doi):
    return get("https://api.crossref.org/works/" + urllib.parse.quote(doi))["message"]


def openalex_retracted(doi):
    try:
        w = get("https://api.openalex.org/works/doi:" + urllib.parse.quote(doi))
        return bool(w.get("is_retracted"))
    except Exception:
        return None


def row(doi, key=""):
    m = crossref(doi)
    au = m.get("author", [])
    authors = "; ".join(f"{a.get('family', '')}, {a.get('given', '')}" for a in au[:40])
    yr = (m.get("issued", {}).get("date-parts") or [[None]])[0][0]
    upd = [f"{u.get('type')}:{u.get('DOI')}" for u in m.get("updated-by", [])]
    return {"key": key, "doi": doi, "title": (m.get("title") or [""])[0], "authors": authors, "year": yr,
            "venue": (m.get("container-title") or [""])[0], "volume": m.get("volume", ""), "issue": m.get("issue", ""),
            "pages": m.get("page", m.get("article-number", "")), "crossref_type": m.get("type", ""),
            "retracted_openalex": openalex_retracted(doi), "updated_by": " ".join(upd),
            "checked": datetime.date.today().isoformat()}


def main():
    if sys.argv[1] == "--query":
        q = " ".join(sys.argv[2:])
        r = get("https://api.crossref.org/works?rows=3&query.bibliographic=" + urllib.parse.quote(q))["message"]["items"]
        for it in r:
            print(it.get("DOI"), "|", (it.get("title") or [""])[0][:90], "|", (it.get("issued", {}).get("date-parts") or [[None]])[0][0],
                  "|", (it.get("container-title") or [""])[0][:40])
        return
    out = []
    for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        doi, _, key = line.partition("|")
        try:
            r = row(doi.strip(), key.strip())
        except Exception as e:  # noqa: BLE001
            print("FAIL", doi, e)
            continue
        out.append(r)
        flag = "RETRACTED?" if (r["retracted_openalex"] or r["updated_by"]) else "ok"
        print(f"{flag:10s} {r['key']:18s} {r['year']} {r['title'][:70]} | {r['venue'][:30]}")
    path = HERE / "verified.csv"
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        if new:
            w.writeheader()
        w.writerows(out)


if __name__ == "__main__":
    main()
