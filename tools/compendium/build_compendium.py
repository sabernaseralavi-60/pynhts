"""Build the unified NHTS Compendium corpus (2006-2025): parse, merge, deduplicate, tag, link, audit, export.

    python -I tools/compendium/build_compendium.py            # from the repository root

Inputs : compendium/*.pdf (2006-2023 editions) and compendium/2023_2024_2025_compendium.csv (interactive search export)
Outputs: compendium/nhts_compendium_2006_2025_master.xlsx  (local; holds abstracts, not committed)
         compendium/extraction_audit.csv, compendium/SOURCES.md      (committed: numbers and checksums only)
         src/pynhts/_data/compendium.parquet, compendium_audit.json  (shipped; no abstract text, a term index instead)
         papers/02-nhts-ladder/results/{numbers/compendium.json, tables/compendium_*.csv}  (manuscript numbers)
Requires pdftotext (poppler), pandas, pyarrow, openpyxl.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import docs_gen  # noqa: E402
import parse_compendium as pc  # noqa: E402

_spec = importlib.util.spec_from_file_location("_compendium_tags", ROOT / "src" / "pynhts" / "_compendium_tags.py")
assert _spec and _spec.loader
tags_mod = importlib.util.module_from_spec(_spec)
sys.modules["_compendium_tags"] = tags_mod
_spec.loader.exec_module(tags_mod)

COMP = ROOT / "compendium"
CSV = COMP / "2023_2024_2025_compendium.csv"
XLSX = COMP / "nhts_compendium_2006_2025_master.xlsx"
DATA_OUT = ROOT / "src" / "pynhts" / "_data"
PAPER = ROOT / "papers" / "02-nhts-ladder"
EDITION_ORDER = ["2006-2011", "2012", "2013", "2014", "2015", "2016", "2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025"]
STOP = set(
    "a an the of and or in on for to with by from at as is are was were be been this that these those it its into than then "
    "which who whom their there also such can may more most using use used based study paper results result analysis data "
    "model models approach method methods between among about over under both each other not but has have had will would "
    "should could our we they them he she his her if when where while how what why".split()
)
PLACEHOLDER_ABSTRACT = re.compile(r"^(?:blog|news|press release|not available|n/a|none|abstract not available)\.?$", re.I)
_URL = re.compile(r"https?://[^\s<>\"]+", re.I)
_DOI = re.compile(r"\b(10\.\d{4,9}/[^\s<>\"]+)", re.I)


def find_url(avail: str) -> str:
    """First URL of a citation; a URL wrapped over a line break was cut at a space after '-', '/', '_', '=' or '&'."""
    m = _URL.search(avail)
    if not m:
        return ""
    url, rest = m.group(0), avail[m.end():].split()
    while rest and url[-1] in "-/_=&?%" and re.match(r"[A-Za-z0-9._~%/?=&\-]+$", rest[0]):
        url += rest.pop(0)
    return url.rstrip(".,;)")


def find_doi(avail: str, url: str) -> str:
    """DOI from a doi.org URL or a bare 10.xxxx/ string."""
    for src in (url, avail):
        m = _DOI.search(src)
        if m:
            return m.group(1).rstrip(".,;)")
    return ""


def pub_year(raw_date: str, avail: str, edition: str) -> tuple[int | None, str]:
    """Publication year: explicit date field, then "(YYYY)" in the citation, then the first year before any URL."""
    cap = int(edition[:4]) + (1 if edition not in ("2006-2011",) else 0)
    cap = max(cap, 2011) if edition == "2006-2011" else cap
    for src, label in ((raw_date, "date_field"),):
        ys = re.findall(r"\b(19[89]\d|20[0-2]\d)\b", src)
        if ys:
            return int(ys[-1]), label
    text = _URL.sub(" ", avail)
    m = re.search(r"\((19[89]\d|20[0-2]\d)[a-z]?\)", text)
    if m:
        return int(m.group(1)), "citation_parentheses"
    ys = [int(y) for y in re.findall(r"\b(19[89]\d|20[0-2]\d)\b", text)]
    ys = [y for y in ys if y <= cap]
    if ys:
        return ys[0], "citation_first_year"
    return None, "none"


def source_kind(avail: str, abstract: str) -> str:
    """Heuristic class of the source: journal article, conference paper, thesis, report or news/blog."""
    a = avail.lower()
    if re.search(r"dissertation|thesis|\bdiss\.|ph\.?d\.? ", a):
        return "thesis"
    if re.search(r"annual meeting|trb\b.*compendium|transportation research board \d+", a) and not re.search(r"record|journal", a):
        return "conference_paper"
    if re.search(r"journal|transportation research part|\btransp\.|transport policy|proceedings|\bjtrg\b|sustainability|elsevier|springer|wiley|taylor", a):
        return "journal_article"
    if re.search(r"news|blog|press|times|post\b|magazine|forbes|curbed|streetsblog|\.com/|npr|cnn|medium\.com", a) and len(abstract) < 200:
        return "news_or_blog"
    if re.search(r"report|technical|administration|department of|dot\b|\bfhwa\b|laboratory|institute|center|working paper", a):
        return "report"
    return "other_or_unknown"


def term_index(*texts: str) -> str:
    """Sorted unique content words of the texts: a search index that does not redistribute the abstract itself."""
    words = set(re.findall(r"[a-z][a-z0-9\-]{2,}", " ".join(texts).lower()))
    return " ".join(sorted(w for w in words if w not in STOP and not w.isdigit()))


def gather() -> tuple[pd.DataFrame, list[dict]]:
    """Parse all PDFs and the CSV into one row per (edition, entry)."""
    rows: list[dict] = []
    audit: list[dict] = []
    for stem in pc.EDITIONS:
        r = pc.parse_edition(COMP / f"{stem}.pdf")
        pdf = COMP / f"{stem}.pdf"
        for e in r.entries:
            rows.append(dict(
                edition=e.edition, source_file=e.source_file, source_type="pdf", pdf_page=e.pdf_page, seq=e.seq, entry_no=e.entry_no,
                chapter_raw=e.chapter_raw, title=e.title, authors=e.authors, abstract=e.abstract, subject_areas=e.subject_areas,
                availability=e.availability, pub_date_raw=e.pub_date_raw, split_status=e.split_status, flags=",".join(e.flags),
            ))
        n = len(r.entries)
        # independent counts: Abstract anchors (+ entries without the label), "Title:" labels / 2 (layouts C, D), the total the
        # introduction states, and the table-of-contents chain only when it is nearly complete (a broken chain is a diagnostic)
        independent = [x for x in (r.n_abstract_anchors + r.n_anchorless, r.n_title_labels // 2 if r.family in ("C", "D") else None,
                                   r.n_toc_chain if r.n_toc_chain >= 0.99 * n else None, r.intro_stated_total) if x]
        audit.append(dict(
            edition=r.edition, file=pdf.name, sha256=pc.sha256(pdf), layout_family=r.family, period=r.period, pdf_pages=r.n_pdf_pages,
            entries_parsed=n, abstract_anchors=r.n_abstract_anchors, toc_chain_items=r.n_toc_chain,
            title_labels_div2=(r.n_title_labels // 2 if r.family in ("C", "D") else None), intro_stated_total=r.intro_stated_total,
            anchorless_entries=r.n_anchorless, multi_page_entries=r.n_multi_page, toc_page_match_share=round(r.toc_page_score, 4),
            max_abs_diff_to_independent_counts=(max(abs(n - x) for x in independent) if independent else None),
            with_abstract=sum(1 for e in r.entries if len(e.abstract) >= 150), with_availability=sum(1 for e in r.entries if e.availability),
            with_chapter=sum(1 for e in r.entries if e.chapter_raw), chapters=len(r.chapter_counts), notes="; ".join(r.notes),
        ))
    c = pd.read_csv(CSV)
    for i, rw in c.iterrows():
        rows.append(dict(
            edition=str(int(rw["year"])), source_file=CSV.name, source_type="csv", pdf_page=None, seq=i + 1, entry_no="",
            chapter_raw=pc.canon_domain(str(rw["chapter"])), title=pc.clean(str(rw["title"])), authors=pc.clean(str(rw["authors"])),
            abstract=pc.clean(str(rw["abstract"])) if pd.notna(rw["abstract"]) else "", subject_areas=pc.clean(str(rw["subjectAreas"])) if pd.notna(rw["subjectAreas"]) else "",
            availability=pc.clean(str(rw["availability"])) if pd.notna(rw["availability"]) else "", pub_date_raw="", split_status="labelled", flags="",
        ))
        _ = i
    for ed in ("2023", "2024", "2025"):
        sub = c[c["year"] == int(ed)]
        audit.append(dict(
            edition=ed, file=CSV.name, sha256=pc.sha256(CSV), layout_family="CSV", period=f"{ed} (interactive search export)", pdf_pages=None,
            entries_parsed=len(sub), abstract_anchors=None, toc_chain_items=None, title_labels_div2=None, intro_stated_total=None,
            anchorless_entries=0, multi_page_entries=0, toc_page_match_share=None, max_abs_diff_to_independent_counts=0,
            with_abstract=int((sub["abstract"].fillna("").str.len() >= 150).sum()), with_availability=int(sub["availability"].notna().sum()),
            with_chapter=int(sub["chapter"].notna().sum()), chapters=int(sub["chapter"].nunique()), notes="row count of the CSV is the count",
        ))
    df = pd.DataFrame(rows)
    df["domain"] = df["chapter_raw"].map(lambda x: pc.canon_domain(x) if x else "")
    # replacement glyph left by pdftotext for curly quotes, already repaired in clean(); do the same for the CSV text columns
    return df, audit


def enrich_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Add publication year, DOI/URL, source kind and abstract availability to each raw row."""
    y, ys, u, d, k, av = [], [], [], [], [], []
    for r in df.itertuples():
        yr, how = pub_year(r.pub_date_raw, r.availability, r.edition)
        url = find_url(r.availability)
        y.append(yr)
        ys.append(how)
        u.append(url)
        d.append(find_doi(r.availability, url))
        k.append(source_kind(r.availability, r.abstract))
        av.append(len(r.abstract) >= 150 and not PLACEHOLDER_ABSTRACT.match(r.abstract))
    df = df.assign(pub_year=y, pub_year_source=ys, url=u, doi=d, source_kind=k, abstract_available=av)
    return df


def same_study(na: str, nb: str, ta: str, tb: str) -> bool:
    """Two rows describe the same study when their normalised titles are equal, nested (title + authors blob) or very close."""
    if not na or not nb:
        return False
    if na == nb:
        return True
    short, long_ = (na, nb) if len(na) <= len(nb) else (nb, na)
    if len(short) >= 25 and long_.startswith(short):
        return True
    return len(short) >= 25 and abs(len(na) - len(nb)) < 0.2 * len(long_) and pc.title_similarity(ta, tb) >= 0.93


def dedupe(df: pd.DataFrame) -> pd.DataFrame:
    """Cluster rows into unique studies and merge fields; keep the full provenance."""
    order = {e: i for i, e in enumerate(EDITION_ORDER)}
    df = df.assign(_ord=df["edition"].map(lambda e: order.get(e.replace("-pdf", ""), 99))).sort_values(["_ord", "seq"]).reset_index(drop=True)
    norms = [pc.norm(t) for t in df["title"]]
    titles = df["title"].tolist()
    blocks: dict[str, list[int]] = {}
    cluster = [-1] * len(df)
    n_clusters = 0
    for i in range(len(df)):
        hit = -1
        keys = {norms[i][:25], norms[i][:14]}  # nested blobs share the first 25 characters; near-duplicates the first 14
        cand = [j for k in keys for j in blocks.get(k, [])]
        for j in cand:
            if same_study(norms[i], norms[j], titles[i], titles[j]):
                hit = cluster[j]
                break
        if hit < 0:
            hit = n_clusters
            n_clusters += 1
        cluster[i] = hit
        for k in keys:
            blocks.setdefault(k, []).append(i)
    df["cluster"] = cluster
    rank = {"labelled": 0, "recovered_from_availability": 1, "heuristic_surname": 2, "unsplit": 3}
    out = []
    for _cid, g in df.groupby("cluster", sort=True):
        g = g.assign(_rk=g["split_status"].map(rank)).sort_values(["_rk", "_ord"])
        best = g.iloc[0]
        first = g.sort_values("_ord").iloc[0]
        def longest(col: str, g: pd.DataFrame = g) -> str:
            return max(g[col].tolist(), key=lambda s: len(s or ""))

        yrs = [int(x) for x in g["pub_year"].dropna().tolist()]
        out.append(dict(
            title=best["title"], authors=best["authors"] or longest("authors"), abstract=longest("abstract"),
            subject_areas=longest("subject_areas"), availability=longest("availability"),
            domain=first["domain"], domains_all="; ".join(sorted(set(x for x in g["domain"] if x))),
            chapter_raw=first["chapter_raw"], first_edition=first["edition"].replace("-pdf", ""),
            editions="; ".join(dict.fromkeys(x.replace("-pdf", "") for x in g.sort_values("_ord")["edition"])), n_editions=g["edition"].map(lambda x: x.replace("-pdf", "")).nunique(),
            n_records_merged=len(g), source_files="; ".join(dict.fromkeys(g.sort_values("_ord")["source_file"])),
            provenance="; ".join(f"{r.edition.replace('-pdf', '')}:{r.source_type}:" + (f"p{int(r.pdf_page)}" if pd.notna(r.pdf_page) else f"row{int(r.seq)}") for r in g.sort_values("_ord").itertuples()),
            entry_no_first=first["entry_no"], pub_year=(int(pd.Series(yrs).mode().iloc[0]) if yrs else None),
            pub_year_source=g.sort_values("_ord").iloc[0]["pub_year_source"] if yrs else "none",
            url=longest("url"), doi=longest("doi"), source_kind=best["source_kind"], abstract_available=bool(g["abstract_available"].any()),
            title_includes_authors=bool(best["split_status"] == "unsplit"), split_status=best["split_status"], parse_flags=",".join(sorted(set(",".join(g["flags"]).split(",")) - {""})),
        ))
    m = pd.DataFrame(out)
    m["cid"] = m["title"].map(lambda t: "C" + hashlib.sha1(pc.norm(t).encode()).hexdigest()[:8])
    return m.sort_values(["first_edition", "domain", "title"], key=lambda s: s.map(lambda v: order.get(v, v)) if s.name == "first_edition" else s).reset_index(drop=True)


def tag_all(m: pd.DataFrame) -> pd.DataFrame:
    """Methodological tags plus the term index."""
    rows = []
    for r in m.itertuples():
        t = tags_mod.tag(r.title, r.abstract, r.subject_areas)
        d = t.as_dict()
        for k in ("nhts_waves_mentioned", "model_families", "weight_terms", "variance_terms", "topics"):
            d[k] = "; ".join(d[k])
        d["terms"] = term_index(r.title, r.abstract, r.subject_areas)
        rows.append(d)
    return pd.concat([m.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


def case_study_links(m: pd.DataFrame) -> pd.DataFrame:
    """Link the case studies P01..P24 of paper 02 to compendium rows by title (or report that none was found)."""
    studies = pd.read_csv(PAPER / "results" / "tables" / "studies.csv")
    keys = ["yang2011", "zhou2014", "quinn2016", "deka2019", "jia2019", "krizek2019", "fu2020", "lidbe2021", "alberini2021", "xue2021",
            "zhang2018bike", "zhang2018veh", "zhang2018ride", "sabouri2020", "jia2020", "jiao2020", "sadeghvaziri2020", "shirgaokar2021",
            "barua2021", "wu2021", "su2021", "naseralavi2025"]
    bib = (PAPER / "manuscript" / "refs.bib").read_text(encoding="utf-8")
    titles = {}
    for k in keys:
        mm = re.search(r"@\w+\{" + k + r",(.*?)\n\}", bib, re.S)
        tt = re.search(r"title\s*=\s*\{(.*?)\},?\s*\n", mm.group(1), re.S) if mm else None
        titles[k] = pc.clean(tt.group(1).replace("{", "").replace("}", "")) if tt else ""
    studies["bib_key"] = keys
    studies["paper_title"] = studies["bib_key"].map(titles)
    out = []
    for r in studies.itertuples():
        best, ratio = None, 0.0
        nt = pc.norm(r.paper_title)
        for j, c in m.iterrows():
            nc = pc.norm(c["title"])
            if not nt or not nc:
                continue
            s = 1.0 if (len(nt) >= 25 and (nc.startswith(nt[:60]) or nt.startswith(nc[:60]))) else pc.title_similarity(r.paper_title, c["title"])
            if s > ratio:
                best, ratio = j, s
        found = best is not None and ratio >= 0.85
        out.append(dict(
            audit_id=r.id, study=r.study, wave=r.wave, family=r.family, paper_title=r.paper_title, match_ratio=round(ratio, 3), in_compendium=found,
            L0_verdict=r.L0_verdict, L1_graded=r.L1_graded, L1_share_exact_close=r.L1_share_exact_close, L2_attempted=r.L2_attempted, L2_grade=r.L2_grade,
            L3_coef=r.L3_coef, L3_sig_naive=r.L3_sig_naive, L3_sig_lost=r.L3_sig_lost, L3_sign_flips=r.L3_sign_flips,
            L3_median_se_ratio=r.L3_median_se_ratio,
            cid=(m.at[best, "cid"] if found else ""), compendium_title=(m.at[best, "title"] if best is not None else ""),
            domain=(m.at[best, "domain"] if found else ""), editions=(m.at[best, "editions"] if found else ""),
            nearest_title_if_not_matched=("" if found or best is None else m.at[best, "title"]),
        ))
    return pd.DataFrame(out)


def summaries(m: pd.DataFrame, links: pd.DataFrame, raw: pd.DataFrame, audit: pd.DataFrame) -> dict[str, pd.DataFrame | dict]:
    """Aggregate tables for the Excel workbook and the manuscript numbers."""
    nh = m["mentions_nhts"]
    mod = m["study_type"].isin(["regression_inference", "machine_learning"])
    # per edition (counts of the raw records of each edition, not de-duplicated, plus the new-in-edition count)
    raw = raw.assign(ed=raw["edition"].str.replace("-pdf", "", regex=False))
    first_ct = m.groupby("first_edition").size()
    by_ed = []
    for ed in EDITION_ORDER:
        sub = m[m["editions"].str.split("; ").map(lambda L, ed=ed: ed in L)]
        am = sub[sub["abstract_available"]]
        modsub = am[am["study_type"].isin(["regression_inference", "machine_learning"])]
        by_ed.append(dict(
            edition=ed, records_in_edition=len(raw[raw["ed"] == ed]), unique_studies=len(sub), new_in_this_edition=int(first_ct.get(ed, 0)),
            with_abstract=len(am), mention_nhts_in_text=int(sub["mentions_nhts"].sum()),
            share_regression=round((sub["study_type"] == "regression_inference").mean(), 4), share_ml=round((sub["study_type"] == "machine_learning").mean(), 4),
            share_simulation_opt=round((sub["study_type"] == "simulation_or_optimisation").mean(), 4),
            modelling_abstracts=len(modsub), mod_weights=int(modsub["mentions_weights"].sum()), mod_variance=int(modsub["mentions_variance_design"].sum()),
            mod_weights_share=round(modsub["mentions_weights"].mean(), 4) if len(modsub) else None,
            mod_variance_share=round(modsub["mentions_variance_design"].mean(), 4) if len(modsub) else None,
            ml_with_resampling=int(sub[sub["is_ml"]]["mentions_resampling"].sum()), ml_n=int(sub["is_ml"].sum()),
        ))
    by_edition = pd.DataFrame(by_ed)
    by_year = (m[m["pub_year"].notna()].assign(py=lambda d: d["pub_year"].astype(int)).groupby("py")
               .agg(studies=("cid", "size"), ml=("is_ml", "sum"), regression=("study_type", lambda s: int((s == "regression_inference").sum())),
                    weights=("mentions_weights", "sum"), variance=("mentions_variance_design", "sum"), resampling=("mentions_resampling", "sum")).reset_index())
    by_chapter = (m.groupby("domain").agg(
        studies=("cid", "size"), with_abstract=("abstract_available", "sum"), mention_nhts=("mentions_nhts", "sum"),
        regression=("study_type", lambda s: int((s == "regression_inference").sum())), ml=("is_ml", "sum"),
        weights=("mentions_weights", "sum"), variance=("mentions_variance_design", "sum"), first_year=("first_edition", "min"),
    ).reset_index().sort_values("studies", ascending=False))
    fam_rows = []
    fams = [f for f in tags_mod.MODEL_FAMILIES] + ["Regression (unspecified)"]
    for f in fams:
        sub = m[m["model_families"].str.contains(re.escape(f), regex=True)]
        asub = sub[sub["abstract_available"]]
        fam_rows.append(dict(
            model_family=f, studies=len(sub), share_of_all=round(len(sub) / len(m), 4), abstract_available=len(asub),
            mention_weights=int(asub["mentions_weights"].sum()), mention_variance=int(asub["mentions_variance_design"].sum()),
            weights_share=round(asub["mentions_weights"].mean(), 4) if len(asub) else None, variance_share=round(asub["mentions_variance_design"].mean(), 4) if len(asub) else None,
            first_pub_year=(int(sub["pub_year"].min()) if sub["pub_year"].notna().any() else None), last_pub_year=(int(sub["pub_year"].max()) if sub["pub_year"].notna().any() else None),
        ))
    by_family = pd.DataFrame(fam_rows)
    # chapters of the case studies
    cs = links.copy()
    cs_by_domain = cs[cs["in_compendium"]].groupby("domain").size().rename("case_studies").reset_index()
    # headline numbers
    ml = m[m["is_ml"]]
    ml_a = ml[ml["abstract_available"]]
    moda = m[mod & m["abstract_available"]]
    modn = moda[moda["mentions_nhts"]]
    num: dict = {
        "n_pdf_records": int((raw["source_type"] == "pdf").sum()), "n_csv_records": int((raw["source_type"] == "csv").sum()),
        "n_records": len(raw), "n_unique": len(m), "n_duplicates_removed": len(raw) - len(m), "n_editions": int(raw["ed"].nunique()),
        "first_pub_year": int(m["pub_year"].min()), "last_edition": "2025", "n_domains_current": 13,
        "n_with_abstract": int(m["abstract_available"].sum()), "share_with_abstract": float(m["abstract_available"].mean()),
        "n_mention_nhts": int(nh.sum()), "n_modelling_abstracts": len(moda), "n_modelling_mention_nhts": len(modn),
        "n_regression": int((m["study_type"] == "regression_inference").sum()), "n_ml": int(m["is_ml"].sum()),
        "mod_n": len(moda), "mod_weights_n": int(moda["mentions_weights"].sum()), "mod_variance_n": int(moda["mentions_variance_design"].sum()),
        "mod_weights_share": float(moda["mentions_weights"].mean()), "mod_variance_share": float(moda["mentions_variance_design"].mean()),
        "mod_neither_n": int((~moda["mentions_weights"] & ~moda["mentions_variance_design"]).sum()),
        "mod_both_n": int((moda["mentions_weights"] & moda["mentions_variance_design"]).sum()),
        "mod_weights_not_variance_n": int((moda["mentions_weights"] & ~moda["mentions_variance_design"]).sum()),
        "modn_n": len(modn), "modn_weights_n": int(modn["mentions_weights"].sum()), "modn_variance_n": int(modn["mentions_variance_design"].sum()),
        "modn_weights_share": float(modn["mentions_weights"].mean()), "modn_variance_share": float(modn["mentions_variance_design"].mean()),
        "weights_to_variance_ratio": (float(moda["mentions_weights"].sum() / max(1, moda["mentions_variance_design"].sum()))),
        "ml_n": len(ml), "ml_abstract_n": len(ml_a), "ml_resampling_n": int(ml["mentions_resampling"].sum()),
        "ml_validation_n": int(ml["mentions_validation"].sum()), "ml_accuracy_ge90_n": int((ml["accuracy_claim_pct"].fillna(0) >= 90).sum()),
        "ml_accuracy_claim_n": int(ml["accuracy_claim_pct"].notna().sum()),
        "ml_since_2023_n": int(ml[ml["first_edition"].isin(["2023", "2024", "2025"])].shape[0]),
        "ml_resampling_since_2023_n": int(ml[ml["first_edition"].isin(["2023", "2024", "2025"])]["mentions_resampling"].sum()),
        "ml_acc90_resampling_n": int(((ml["accuracy_claim_pct"].fillna(0) >= 90) & ml["mentions_resampling"]).sum()),
        "n_case_studies": len(cs), "n_case_in_compendium": int(cs["in_compendium"].sum()), "n_case_not_in_compendium": int((~cs["in_compendium"]).sum()),
        "n_case_domains": int(cs[cs["in_compendium"]]["domain"].nunique()),
        "mentions_2017_n": int(m["nhts_waves_mentioned"].str.contains("2017").sum()), "mentions_2009_n": int(m["nhts_waves_mentioned"].str.contains("2009").sum()),
        "mentions_2001_n": int(m["nhts_waves_mentioned"].str.contains("2001").sum()), "mentions_2022_n": int(m["nhts_waves_mentioned"].str.contains("2022").sum()),
        "mentions_nextgen_n": int(m["nhts_waves_mentioned"].str.contains("NextGen").sum()),
        "no_wave_stated_n": int((m["mentions_nhts"] & (m["nhts_waves_mentioned"] == "")).sum()),
        "title_includes_authors_n": int(m["title_includes_authors"].sum()),
        "audit_max_abs_diff": int(pd.to_numeric(audit["max_abs_diff_to_independent_counts"], errors="coerce").max()),
        "audit_min_toc_page_match": float(pd.to_numeric(audit["toc_page_match_share"], errors="coerce").min()),
        "entries_without_abstract_n": int((~m["abstract_available"]).sum()),
        "news_or_blog_n": int((m["source_kind"] == "news_or_blog").sum()),
    }
    rev_path = COMP / "tag_precision_review.csv"  # manual reading of every positive among the modelling abstracts
    if rev_path.exists():
        rev = pd.read_csv(rev_path)
        for tg, short in (("mentions_weights", "weights"), ("mentions_variance_design", "variance")):
            r_ = rev[rev["tag"] == tg]
            num[f"review_{short}_n"] = len(r_)
            num[f"review_{short}_tp_n"] = int((r_["judged"] == "TP").sum())
            num[f"review_{short}_precision"] = float((r_["judged"] == "TP").mean()) if len(r_) else None
    num["top_domain"] = str(by_chapter.iloc[0]["domain"])
    num["top_domain_n"] = int(by_chapter.iloc[0]["studies"])
    num["top_domain_share"] = float(by_chapter.iloc[0]["studies"] / len(m))
    num["n_domains_with_case_study"] = int(cs[cs["in_compendium"]]["domain"].nunique())
    num["n_published_before_2012"] = int((m["pub_year"] < 2012).sum())
    num["share_mention_nhts"] = float(m["mentions_nhts"].mean())
    num["share_modelling_among_abstracts"] = float((mod & m["abstract_available"]).sum() / m["abstract_available"].sum())
    num["mod_neither_share"] = float(num["mod_neither_n"] / num["mod_n"])
    case_domains = set(cs[cs["in_compendium"]]["domain"])
    num["cs_domains_share_of_studies"] = float(by_chapter[by_chapter["domain"].isin(case_domains)]["studies"].sum() / len(m))
    num["ml_acc90_not_resampling_n"] = int(num["ml_accuracy_ge90_n"] - num["ml_acc90_resampling_n"])
    num["ml_resampling_share"] = float(num["ml_resampling_n"] / num["ml_n"]) if num["ml_n"] else 0.0
    return dict(by_edition=by_edition, by_year=by_year, by_chapter=by_chapter, by_family=by_family, cs_by_domain=cs_by_domain, numbers=num)


def main() -> None:
    """Run the whole build."""
    cache = COMP / "_parsed_cache.pkl"  # PDF parsing takes about a minute; reuse it unless the parser or a source changed
    stamp = max(p.stat().st_mtime for p in [HERE / "parse_compendium.py", Path(__file__), CSV, *COMP.glob("*.pdf")])
    if cache.exists() and cache.stat().st_mtime > stamp and "--reparse" not in sys.argv:
        raw, audit_rows = pd.read_pickle(cache)
    else:
        raw, audit_rows = gather()
        pd.to_pickle((raw, audit_rows), cache)
    raw = enrich_rows(raw)
    audit = pd.DataFrame(audit_rows)
    m = dedupe(raw)
    m = tag_all(m)
    links = case_study_links(m)
    # mark linked rows
    m["linked_audit_id"] = m["cid"].map(links[links["in_compendium"]].set_index("cid")["audit_id"].to_dict()).fillna("")
    S = summaries(m, links, raw, audit)
    num = S["numbers"]
    assert isinstance(num, dict)

    # spot-check sample for the precision of the tags (reproducible seed): written for manual labelling
    sample = m[m["abstract_available"]].sample(n=min(120, int(m["abstract_available"].sum())), random_state=20261023)[
        ["cid", "title", "mentions_weights", "weight_terms", "mentions_variance_design", "variance_terms", "model_families", "study_type", "nhts_waves_mentioned"]]
    sample.to_csv(COMP / "tag_precision_sample.csv", index=False, encoding="utf-8-sig")

    # ---------- exports
    audit.to_csv(COMP / "extraction_audit.csv", index=False)
    cols_front = ["cid", "title", "authors", "pub_year", "first_edition", "editions", "domain", "domains_all", "study_type", "model_families", "nhts_waves_mentioned",
                  "mentions_nhts", "mentions_weights", "weight_terms", "mentions_variance_design", "variance_terms", "mentions_bootstrap_or_robust_se",
                  "mentions_resampling", "mentions_validation", "mentions_imbalance_or_leakage_risk", "accuracy_claim_pct", "topics", "linked_audit_id",
                  "source_kind", "abstract_available", "doi", "url", "subject_areas", "availability", "abstract", "provenance", "n_editions", "n_records_merged",
                  "split_status", "title_includes_authors", "pub_year_source", "parse_flags"]
    allp = m[cols_front].rename(columns={"availability": "availability_citation", "url": "url_or_doi_link"})
    notes = pd.DataFrame({"item": [
        "What this is", "Sources", "Built", "Unit", "Tags", "Denominators", "Caveat", "Reproduce"], "text": [
        "Unified NHTS Compendium of Uses (FHWA/ORNL), 2006-2025, one row per unique study.",
        "12 PDF editions (2006-2011 ... 2023) parsed with tools/compendium/parse_compendium.py; interactive-search CSV for 2023-2025; SHA-256 in Extraction_Audit.",
        f"{dt.date.today().isoformat()}",
        "A unique study; the same study can appear in several editions (editions, provenance).",
        "Regex tags on title + abstract + subject areas (src/pynhts/_compendium_tags.py). They describe what the abstract SAYS, not what the analysis did.",
        "'Modelling abstracts' = unique studies with an abstract of at least 150 characters whose tags are regression inference or machine learning.",
        "An abstract that does not name weights or a variance estimator may still have used them; the counts are a lower bound of reporting, not a measure of practice.",
        "python -I tools/compendium/build_compendium.py (needs pdftotext)."]})
    with pd.ExcelWriter(XLSX, engine="openpyxl") as xw:
        notes.to_excel(xw, sheet_name="README", index=False)
        allp.to_excel(xw, sheet_name="All_Papers", index=False)
        S["by_edition"].to_excel(xw, sheet_name="Summary_By_Edition", index=False)
        S["by_year"].to_excel(xw, sheet_name="Summary_By_PubYear", index=False)
        S["by_chapter"].to_excel(xw, sheet_name="Summary_By_Chapter", index=False)
        S["by_family"].to_excel(xw, sheet_name="Summary_By_Model_Family", index=False)
        pd.DataFrame([{"metric": k, "value": v} for k, v in num.items()]).to_excel(xw, sheet_name="Methodological_Audit", index=False)
        links.to_excel(xw, sheet_name="Case_Study_Map", index=False)
        S["cs_by_domain"].to_excel(xw, sheet_name="Case_Studies_By_Chapter", index=False)
        audit.to_excel(xw, sheet_name="Extraction_Audit", index=False)
        for ws in xw.book.worksheets:
            ws.freeze_panes = "A2"
            for col in ws.columns:
                w = min(60, max(len(str(c.value)) if c.value is not None else 0 for c in list(col)[:60]) + 2)
                ws.column_dimensions[col[0].column_letter].width = max(8, w)
    # package data: no abstract text, a term index instead
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    pkg = m[["cid", "title", "authors", "pub_year", "first_edition", "editions", "domain", "domains_all", "study_type", "model_families", "nhts_waves_mentioned",
             "mentions_nhts", "mentions_weights", "mentions_variance_design", "mentions_bootstrap_or_robust_se", "mentions_resampling", "mentions_validation",
             "mentions_imbalance_or_leakage_risk", "is_ml", "accuracy_claim_pct", "topics", "linked_audit_id", "source_kind", "abstract_available", "doi", "url",
             "subject_areas", "availability", "title_includes_authors", "terms"]].copy()
    pkg["pub_year"] = pkg["pub_year"].astype("Int64")
    pkg.to_parquet(DATA_OUT / "compendium.parquet", index=False, compression="zstd")
    links.to_csv(DATA_OUT / "compendium_case_studies.csv", index=False)
    nums = PAPER / "results" / "numbers"
    summ, mlj, ladj = (json.loads((nums / f"{f}.json").read_text(encoding="utf-8")) for f in ("summary", "ml", "ladder"))
    findings = dict(
        source="papers/02-nhts-ladder/results/numbers/{summary,ml,ladder}.json: design-aware re-estimation of 22 NHTS studies, pynhts 0.9.0",
        n_studies=ladj["n_studies"], n_coef=summ["n_coef"], median_se_ratio=summ["median_se_ratio"], q25_se_ratio=summ["q25_se_ratio"],
        q75_se_ratio=summ["q75_se_ratio"], median_r_weights=summ["median_r_weights"], h3_share=summ["h3_share"], h3_ci_lo=summ["h3_ci_lo"],
        h3_ci_hi=summ["h3_ci_hi"], share_sign_flip=summ["share_sign_flip"], share_sig_lost=summ["share_sig_lost"],
        afv_rf_auc_leaky=mlj["afv"]["leaky"]["rf"], afv_rf_auc_grouped=mlj["afv"]["grouped"]["rf"], afv_dt_auc_leaky=mlj["afv"]["leaky"]["dt"],
        afv_dt_auc_grouped=mlj["afv"]["grouped"]["dt"], afv_infl_rf=mlj["afv"]["infl_rf"], share_l1_exact_close=ladj["share_l1_exact_close"])
    (DATA_OUT / "compendium_findings.json").write_text(json.dumps(findings, indent=1, default=float), encoding="utf-8")
    pkg_audit = dict(numbers=num, extraction_audit=json.loads(audit.drop(columns=["file"]).to_json(orient="records")),
                     by_edition=json.loads(S["by_edition"].to_json(orient="records")), by_chapter=json.loads(S["by_chapter"].to_json(orient="records")),
                     by_family=json.loads(S["by_family"].to_json(orient="records")), built=dt.date.today().isoformat())
    (DATA_OUT / "compendium_audit.json").write_text(json.dumps(pkg_audit, indent=1, default=float), encoding="utf-8")
    # manuscript numbers and tables
    (PAPER / "results" / "numbers").mkdir(parents=True, exist_ok=True)
    (PAPER / "results" / "numbers" / "compendium.json").write_text(json.dumps(num, indent=1, default=float), encoding="utf-8")
    S["by_chapter"].to_csv(PAPER / "results" / "tables" / "compendium_by_chapter.csv", index=False)
    S["by_edition"].to_csv(PAPER / "results" / "tables" / "compendium_by_edition.csv", index=False)
    S["by_family"].to_csv(PAPER / "results" / "tables" / "compendium_by_family.csv", index=False)
    links.to_csv(PAPER / "results" / "tables" / "compendium_case_studies.csv", index=False)
    audit.drop(columns=["file"]).to_csv(PAPER / "results" / "tables" / "compendium_extraction_audit.csv", index=False)
    docs_gen.write_docs(ROOT, audit, num, S)
    print(json.dumps(num, indent=1, default=float))
    print(audit[["edition", "entries_parsed", "abstract_anchors", "toc_chain_items", "title_labels_div2", "intro_stated_total", "anchorless_entries",
                 "max_abs_diff_to_independent_counts"]].to_string())


if __name__ == "__main__":
    main()
