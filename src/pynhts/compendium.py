"""The FHWA/ORNL *NHTS Compendium of Uses* (2006-2025) as a searchable, auditable corpus inside pynhts.

The compendium is the official, hand-curated list of publications that use the National Household Travel Survey. This
module ships it as one table (one row per unique study, with the editions it appeared in), tagged with what each
title, abstract and subject-area list *says* about waves, model families, survey weights, variance estimation and
validation. Three things are built on it:

* :func:`search` / :func:`to_bibtex` find prior work and cite it;
* :func:`advise` is a pre-flight check: what did earlier NHTS studies of a topic do, and which design pitfalls were
  measured by the pynhts audit of 22 published studies (``papers/02-nhts-ladder``)? A conversation with the data, not
  a replacement for reading the papers;
* :func:`register` bridges the corpus to the L0-L3 reproducibility ladder (L0 can the data be rebuilt, L1 the tables,
  L2 the model, L3 the model under the survey design), so that a compendium entry can gain a replication recipe.

Honesty rules: tags describe abstracts, not analyses (an abstract that names no weights may still have used them), and
the shipped table holds bibliographic metadata and a sorted *term index* instead of the abstracts themselves, which
belong to their publishers. The extraction audit (:func:`audit_summary`) reports how the 12 PDF editions and the
interactive-search export were parsed and checked. See ``docs/compendium.md``.

Example:
    >>> import pynhts
    >>> hits = pynhts.compendium.search("older adults trip chaining", wave=2017)   # doctest: +SKIP
    >>> print(pynhts.compendium.advise("EV adoption"))                              # doctest: +SKIP
    >>> print(pynhts.compendium.to_bibtex(hits.head(3)))                            # doctest: +SKIP
"""

from __future__ import annotations

import io
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources
from typing import Any

import pandas as pd

from pynhts import concepts
from pynhts._compendium_tags import MODEL_FAMILIES, TOPICS, Tags, tag

__all__ = ["Advice", "AuditSummary", "advise", "audit_summary", "domains", "get", "load", "model_families", "register",
           "search", "tag", "topics", "to_bibtex", "Tags"]

_DATA = resources.files("pynhts") / "_data"
_FAMILY_ALIASES = {
    "ml": "Machine learning", "machine learning": "Machine learning", "classification": "Machine learning", "classifier": "Machine learning",
    "logit": "Logit/Choice", "choice": "Logit/Choice", "mode choice": "Logit/Choice", "probit": "Logit/Choice", "mnl": "Logit/Choice",
    "count": "Count (Poisson/NB/ZINB)", "poisson": "Count (Poisson/NB/ZINB)", "nb": "Count (Poisson/NB/ZINB)", "negative binomial": "Count (Poisson/NB/ZINB)",
    "zinb": "Count (Poisson/NB/ZINB)", "ols": "OLS/Linear", "linear": "OLS/Linear", "regression": "OLS/Linear", "sem": "SEM/Path",
    "path": "SEM/Path", "psm": "PSM/Causal", "propensity": "PSM/Causal", "causal": "PSM/Causal", "hazard": "Hazard/Duration",
    "multilevel": "Multilevel/Mixed", "mixed": "Multilevel/Mixed", "spatial": "Spatial", "cluster": "Clustering/Segmentation",
    "clustering": "Clustering/Segmentation", "simulation": "Simulation/Optimisation", "optimisation": "Simulation/Optimisation",
    "optimization": "Simulation/Optimisation",
}
_TOPIC_ALIASES = {
    "bikeshare": "bikeshare / micromobility", "bike share": "bikeshare / micromobility", "scooter": "bikeshare / micromobility",
    "micromobility": "bikeshare / micromobility", "cycling": "cycling / walking / active travel", "walking": "cycling / walking / active travel",
    "active travel": "cycling / walking / active travel", "older adults": "older adults", "elderly": "older adults", "seniors": "older adults",
    "children": "children / school travel", "school": "children / school travel", "ev": "EV / alternative fuel adoption",
    "electric vehicle": "EV / alternative fuel adoption", "ev adoption": "EV / alternative fuel adoption", "afv": "EV / alternative fuel adoption",
    "alternative fuel": "EV / alternative fuel adoption", "ride-hailing": "ride-hailing / shared mobility", "ridehailing": "ride-hailing / shared mobility",
    "ridesharing": "ride-hailing / shared mobility", "tnc": "ride-hailing / shared mobility", "e-shopping": "online shopping / e-commerce",
    "online shopping": "online shopping / e-commerce", "e-commerce": "online shopping / e-commerce", "telework": "telework / telecommuting",
    "telecommuting": "telework / telecommuting", "autonomous": "automated vehicles", "av": "automated vehicles", "transit": "transit",
    "health": "health / physical activity", "physical activity": "health / physical activity", "safety": "traffic safety", "crash": "traffic safety",
    "fuel": "energy / fuel", "energy": "energy / fuel", "emissions": "emissions / climate", "equity": "equity / low income", "covid": "COVID-19",
    "vmt": "VMT / vehicle use", "freight": "freight / trucks", "rural": "rural", "immigrants": "race / ethnicity / immigrants", "race": "race / ethnicity / immigrants",
    "disability": "disability", "vehicle ownership": "vehicle ownership", "commuting": "commuting", "built environment": "built environment / land use",
    "land use": "built environment / land use", "gender": "gender", "data synthesis": "travel-survey methods / data synthesis",
    "survey methods": "travel-survey methods / data synthesis", "big data": "passive OD / big data", "trip chaining": "trip chaining / activity patterns",
}
# pynhts concepts to read before analysing a topic (each documents top-codes, universes and cross-wave comparability)
_TOPIC_CONCEPTS = {
    "older adults": ["age", "medical_condition", "condition_effect", "driver"],
    "children / school travel": ["age", "trip_purpose_summary", "trip_distance"],
    "EV / alternative fuel adoption": ["vehicle_fuel", "vehicle_type", "vehicle_age", "household_vehicles"],
    "VMT / vehicle use": ["annual_miles_best", "annual_miles_self", "vehicle_miles_of_trip", "trip_counting", "weight_trip"],
    "commuting": ["commute_time", "worker", "trip_distance", "trip_mode"],
    "cycling / walking / active travel": ["trip_mode", "trip_distance", "trip_counting"],
    "bikeshare / micromobility": ["trip_mode", "trip_distance"],
    "transit": ["transit_use", "trip_mode", "urban_rural"],
    "online shopping / e-commerce": ["trip_purpose_detailed", "trip_counting"],
    "equity / low income": ["household_income", "race_person", "hispanic_person"],
    "race / ethnicity / immigrants": ["race_person", "hispanic_person", "race_household"],
    "vehicle ownership": ["household_vehicles", "vehicle_type", "vehicle_age"],
    "trip chaining / activity patterns": ["trip_counting", "trip_purpose_detailed", "dwell_time"],
    "telework / telecommuting": ["worker", "commute_time"],
    "ride-hailing / shared mobility": ["trip_mode", "trip_counting"],
    "travel-survey methods / data synthesis": ["weight_person", "weight_household", "replicate_design"],
    "built environment / land use": ["block_group_density", "urban_rural", "urbanized_area"],
}
_ALWAYS_CONCEPTS = ["weight_person", "weight_household", "weight_trip", "replicate_design"]
_HIDE = ("terms",)


def _read(name: str) -> bytes:
    return (_DATA / name).read_bytes()


@lru_cache(maxsize=1)
def _table() -> pd.DataFrame:
    df = pd.read_parquet(io.BytesIO(_read("compendium.parquet")))
    df["_hay_title"] = df["title"].str.lower()
    df["_hay_subject"] = df["subject_areas"].fillna("").str.lower()
    df["_hay_terms"] = df["terms"].fillna("")
    reg = _register_table()
    lvl = {}
    for r in reg.to_dict("records"):
        if not r["in_compendium"]:
            continue
        if pd.notna(r["L3_coef"]) and r["L3_coef"] > 0:
            lvl[r["cid"]] = "L3"
        elif str(r["L2_attempted"]) == "yes":
            lvl[r["cid"]] = "L2"
        elif pd.notna(r["L1_graded"]) and r["L1_graded"] > 0:
            lvl[r["cid"]] = "L1"
        else:
            lvl[r["cid"]] = "L0"
    df["repro_level"] = df["cid"].map(lvl).fillna("")
    return df


@lru_cache(maxsize=1)
def _register_table() -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(_read("compendium_case_studies.csv")))


@lru_cache(maxsize=1)
def _audit() -> dict[str, Any]:
    return json.loads(_read("compendium_audit.json").decode("utf-8"))  # type: ignore[no-any-return]


@lru_cache(maxsize=1)
def _findings() -> dict[str, Any]:
    return json.loads(_read("compendium_findings.json").decode("utf-8"))  # type: ignore[no-any-return]


def load() -> pd.DataFrame:
    """Return the whole corpus as a DataFrame (one row per unique study; no abstracts, see the module notes)."""
    t = _table()
    out: pd.DataFrame = t.drop(columns=[c for c in t.columns if c.startswith("_hay") or c in _HIDE])
    return out


def domains() -> list[str]:
    """Return the planning domains (chapters) present in the corpus, largest first."""
    return [str(x) for x in _table()["domain"].value_counts().index]


def topics() -> list[str]:
    """Return the topic tags that :func:`search` and :func:`advise` understand."""
    return list(TOPICS)


def model_families() -> list[str]:
    """Return the model-family tags."""
    return [*MODEL_FAMILIES, "Regression (unspecified)"]


def get(cid: str) -> pd.Series:
    """Return one study by its stable id (``C`` plus eight hex digits)."""
    t = _table()
    hit = t[t["cid"] == cid]
    if hit.empty:
        raise KeyError(f"no compendium study with id {cid!r}")
    row: pd.Series = hit.iloc[0].drop(labels=[c for c in hit.columns if c.startswith("_hay") or c in _HIDE])
    return row


def _resolve_topic(text: str) -> str | None:
    t = text.strip().lower()
    for k in TOPICS:
        if t == k.lower():
            return k
    if t in _TOPIC_ALIASES:
        return _TOPIC_ALIASES[t]
    for alias, key in sorted(_TOPIC_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if re.search(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])", t):
            return key
    for k in TOPICS:
        if t and t in k.lower():
            return k
    return None


def _resolve_family(text: str) -> str | None:
    t = text.strip().lower()
    for f in model_families():
        if t == f.lower():
            return f
    if t in _FAMILY_ALIASES:
        return _FAMILY_ALIASES[t]
    for f in model_families():
        if t and t in f.lower():
            return f
    return None


def search(
    query: str | None = None,
    *,
    wave: int | str | None = None,
    model: str | None = None,
    domain: str | None = None,
    topic: str | None = None,
    edition: int | str | None = None,
    years: tuple[int | None, int | None] | None = None,
    weights: bool | None = None,
    variance: bool | None = None,
    ml: bool | None = None,
    resampling: bool | None = None,
    nhts_in_text: bool | None = None,
    audited: bool | None = None,
    match: str = "all",
    limit: int | None = None,
) -> pd.DataFrame:
    """Search the corpus.

    Args:
        query: Words that must all occur (as word starts) in the title, subject areas or term index of the study.
        wave: NHTS wave named in the text, e.g. ``2017``; ``"NextGen"`` for the origin-destination products.
        model: Model family or alias (``"ZINB"``, ``"logit"``, ``"ML"``, ``"SEM"``, ``"PSM"`` ...; see :func:`model_families`).
        domain: Substring of the compendium chapter (``"Health"``, ``"transit"``); a study can sit in several editions' chapters.
        topic: A topic tag or alias (``"bikeshare"``, ``"EV adoption"``; see :func:`topics`).
        edition: Compendium edition in which the study appeared (``2006-2011``, 2012 ... 2025).
        years: ``(first, last)`` publication-year bounds; ``None`` leaves a side open.
        weights: Keep studies whose abstract names (True) or does not name (False) survey weights.
        variance: Same for a design-based variance estimator (replicate weights, jackknife, Taylor, complex survey procedures ...).
        ml: Keep machine-learning studies (True) or exclude them (False).
        resampling: Keep studies that mention oversampling/SMOTE/class imbalance.
        nhts_in_text: Keep studies whose title, abstract or subject areas name the NHTS/NPTS themselves.
        audited: Keep studies that are in the pynhts L0-L3 register (True) or not (False).
        match: ``"all"`` (default) requires every query word; ``"any"`` keeps studies with at least one and ranks by how many.
        limit: Maximum number of rows.

    Returns:
        A DataFrame sorted by relevance (when a query is given) and publication year (newest first).
    """
    t = _table()
    mask = pd.Series(True, index=t.index)
    score = pd.Series(0, index=t.index)
    any_hit: pd.Series | None = None
    if match not in ("all", "any"):
        raise ValueError("match must be 'all' or 'any'")
    if query:
        for w in re.findall(r"[a-z0-9][a-z0-9\-]*", query.lower()):
            rx = r"(?<![a-z0-9])" + re.escape(w)
            in_t = t["_hay_title"].str.contains(rx, regex=True)
            in_s = t["_hay_subject"].str.contains(rx, regex=True)
            in_x = t["_hay_terms"].str.contains(rx, regex=True)
            hit = in_t | in_s | in_x
            if match == "all":
                mask &= hit
            else:
                any_hit = hit if any_hit is None else (any_hit | hit)
            score += 3 * in_t.astype(int) + 2 * in_s.astype(int) + in_x.astype(int)
        if match == "any" and any_hit is not None:
            mask &= any_hit
    if wave is not None:
        w = str(wave)
        mask &= t["nhts_waves_mentioned"].fillna("").str.contains(w, case=False, regex=False)
    if model is not None:
        fam = _resolve_family(model)
        if fam is None:
            raise ValueError(f"unknown model family {model!r}; choose from {model_families()}")
        mask &= t["model_families"].fillna("").str.contains(fam, regex=False)
    if domain is not None:
        mask &= t["domains_all"].fillna("").str.contains(domain, case=False, regex=False)
    if topic is not None:
        key = _resolve_topic(topic)
        if key is None:
            raise ValueError(f"unknown topic {topic!r}; choose from {topics()}")
        mask &= t["topics"].fillna("").str.contains(key, regex=False)
    if edition is not None:
        e = str(edition)
        mask &= t["editions"].fillna("").str.split("; ").map(lambda L: e in L)
    if years is not None:
        lo, hi = years
        if lo is not None:
            mask &= t["pub_year"].fillna(-1) >= lo
        if hi is not None:
            mask &= t["pub_year"].fillna(9999) <= hi
    for col, val in (("mentions_weights", weights), ("mentions_variance_design", variance), ("is_ml", ml),
                     ("mentions_resampling", resampling), ("mentions_nhts", nhts_in_text)):
        if val is not None:
            mask &= t[col].astype(bool) == bool(val)
    if audited is not None:
        mask &= (t["linked_audit_id"].fillna("") != "") == bool(audited)
    out = t[mask].assign(_score=score[mask]).sort_values(["_score", "pub_year"], ascending=[False, False], na_position="last")
    out = out.drop(columns=[c for c in out.columns if c.startswith("_hay") or c in _HIDE or c == "_score"])
    res: pd.DataFrame = out.head(limit) if limit else out
    return res


_ENTRY = {"journal_article": "article", "conference_paper": "inproceedings", "thesis": "phdthesis", "report": "techreport"}


def _bib_escape(s: str) -> str:
    return re.sub(r"([&%$#_])", r"\\\1", s.replace("\\", " ")).replace("{", "(").replace("}", ")")


def to_bibtex(studies: pd.DataFrame | Iterable[str] | str) -> str:
    """Format studies as BibTeX.

    The compendium lists title, authors and the publisher's citation string, but not the journal, volume or pages; the
    entries therefore carry the authors verbatim (in double braces so that BibTeX does not re-parse them), the title, the
    year, the DOI or URL when one was recoverable, and the original citation in ``note``. Check each entry before
    submitting a manuscript; entries whose title still contains the author list (``title_includes_authors``) are marked.

    Args:
        studies: A DataFrame from :func:`search`, one study id or an iterable of ids.

    Returns:
        The BibTeX text.
    """
    if isinstance(studies, pd.DataFrame):
        frame = studies
    else:
        ids = [studies] if isinstance(studies, str) else list(studies)
        t = _table()
        frame = t[t["cid"].isin(ids)]
    seen: dict[str, int] = {}
    out: list[str] = []
    for r in frame.to_dict("records"):
        authors, title = str(r.get("authors") or ""), str(r.get("title") or "")
        first = re.split(r"[,;]| and ", authors or "anon")[0].strip()
        sur = re.sub(r"[^A-Za-z]", "", first.split()[0] if first else "anon") or "anon"
        yr = "" if pd.isna(r.get("pub_year")) else str(int(float(r["pub_year"])))
        word = re.sub(r"[^a-z]", "", next(iter(re.findall(r"[A-Za-z]{4,}", title)), "x").lower())
        key = f"{sur.lower()}{yr}{word}"
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            key += chr(96 + seen[key])
        kind = _ENTRY.get(str(r.get("source_kind", "")), "misc")
        doi, url = str(r.get("doi") or ""), str(r.get("url") or "")
        fields: list[str] = []
        if authors:
            fields.append(f"  author = {{{{{_bib_escape(authors)}}}}}")
        fields.append(f"  title = {{{{{_bib_escape(title)}}}}}")
        if yr:
            fields.append(f"  year = {{{yr}}}")
        if doi:
            fields.append(f"  doi = {{{doi}}}")
        elif url:
            fields.append(f"  url = {{{url}}}")
        note = f"Listed in the FHWA/ORNL NHTS Compendium of Uses, edition(s) {r.get('editions', '')}."
        if r.get("title_includes_authors", False):
            note += " Title field still contains the author list (layout of the source edition)."
        cite = _bib_escape(str(r.get("availability") or "")[:300])
        lead = " Venue not recorded here; see the citation: " if kind != "misc" else " "
        fields.append("  note = {" + _bib_escape(note) + lead + cite + "}")
        out.append(f"@{kind}{{{key},\n" + ",\n".join(fields) + "\n}")
    return "\n\n".join(out) + ("\n" if out else "")


@dataclass
class AuditSummary:
    """How the corpus was built and what its abstracts say about survey design."""

    numbers: dict[str, Any]
    extraction: pd.DataFrame
    by_edition: pd.DataFrame
    by_domain: pd.DataFrame
    by_family: pd.DataFrame
    built: str = ""

    def __str__(self) -> str:
        n = self.numbers
        def pct(x: float) -> str:
            return f"{100 * x:.1f} %"

        lines = [
            f"NHTS Compendium of Uses, 2006-2025 (built {self.built})",
            f"  {n['n_records']} listed records ({n['n_pdf_records']} from 12 PDF editions, {n['n_csv_records']} from the 2023-2025 search export) "
            f"= {n['n_unique']} unique studies ({n['n_duplicates_removed']} repeated across editions).",
            f"  {n['n_with_abstract']} studies have an abstract; {n['n_mention_nhts']} name the NHTS/NPTS in their title, abstract or subject areas "
            f"({pct(n['share_mention_nhts'])}).",
            f"  Modelling abstracts (regression or machine learning, abstract present): {n['mod_n']}. Of these {n['mod_weights_n']} name survey weights "
            f"({pct(n['mod_weights_share'])}) and {n['mod_variance_n']} a design-based variance estimator ({pct(n['mod_variance_share'])}).",
            f"  Machine-learning studies: {n['ml_n']}; {n['ml_resampling_n']} mention oversampling/SMOTE/class imbalance; "
            f"{n['ml_accuracy_ge90_n']} state an accuracy or AUC of 90 % or more ({n['ml_acc90_resampling_n']} of them with resampling).",
            f"  Extraction audit: largest difference between parsed entries and an independent count in any edition: {n['audit_max_abs_diff']}.",
            "  Caveat: tags read abstracts; an abstract that does not name weights may still have used them.",
        ]
        return "\n".join(lines)


def audit_summary() -> AuditSummary:
    """Return the extraction audit and the headline counts of the shipped corpus."""
    a = _audit()
    return AuditSummary(
        numbers=a["numbers"], extraction=pd.DataFrame(a["extraction_audit"]), by_edition=pd.DataFrame(a["by_edition"]),
        by_domain=pd.DataFrame(a["by_chapter"]), by_family=pd.DataFrame(a["by_family"]), built=a.get("built", ""),
    )


def register(only_found: bool = False) -> pd.DataFrame:
    """Return the L0-L3 register of the audited case studies and their rows in the compendium.

    ``in_compendium`` is False for studies that the compendium does not list (the compendium is itself incomplete).
    """
    r = _register_table().copy()
    res: pd.DataFrame = r[r["in_compendium"]] if only_found else r
    return res


@dataclass
class Advice:
    """Pre-flight advice for a topic or an analysis mode (see :func:`advise`)."""

    query: str
    topic: str | None
    family: str | None
    n_studies: int
    summary: dict[str, Any] = field(default_factory=dict)
    pitfalls: list[str] = field(default_factory=list)
    concepts_to_read: list[str] = field(default_factory=list)
    register: pd.DataFrame = field(default_factory=pd.DataFrame)
    examples: pd.DataFrame = field(default_factory=pd.DataFrame)
    design_aware_examples: pd.DataFrame = field(default_factory=pd.DataFrame)
    watch_list: pd.DataFrame = field(default_factory=pd.DataFrame)

    def __str__(self) -> str:
        s = self.summary
        head = f"pynhts.compendium.advise({self.query!r})" + (f"  [topic: {self.topic}]" if self.topic else "") + (f"  [family: {self.family}]" if self.family else "")
        if not self.n_studies:
            return head + "\n  No study in the compendium matches; try compendium.topics() or compendium.search(<words>)."
        lines = [head, f"  {self.n_studies} studies in the NHTS Compendium ({s['year_range']}); {s['n_recent']} published since 2020."]
        lines.append(f"  Waves named: {s['waves']}.")
        lines.append(f"  Model families: {s['families']}.")
        lines.append(f"  Of {s['mod_n']} modelling abstracts: {s['mod_weights_n']} name survey weights, {s['mod_variance_n']} a design-based variance estimator.")
        if self.pitfalls:
            lines.append("  Watch for:")
            lines += [f"   - {p}" for p in self.pitfalls]
        if self.concepts_to_read:
            lines.append("  Read before you code: " + ", ".join(f"pynhts.concepts.find({c!r}, wave)" for c in self.concepts_to_read[:4]) + " ...")
        if len(self.register):
            lines.append("  In the pynhts L0-L3 register: " + "; ".join(f"{r['audit_id']} {r['study']}" for r in self.register.to_dict("records")))
        if len(self.examples):
            lines.append("  Recent studies" + (" naming the NHTS" if self.summary.get("examples_name_nhts") else "") + ":")
            lines += [f"   - {int(float(r['pub_year'])) if pd.notna(r['pub_year']) else '----'}  {str(r['title'])[:100]}  [{r['cid']}]"
                      for r in self.examples.to_dict("records")]
        return "\n".join(lines)


def _count_top(series: pd.Series, k: int = 4) -> str:
    c: dict[str, int] = {}
    for v in series.fillna(""):
        for x in str(v).split("; "):
            if x:
                c[x] = c.get(x, 0) + 1
    top = sorted(c.items(), key=lambda kv: -kv[1])[:k]
    return ", ".join(f"{a} ({b})" for a, b in top) or "none stated"


def advise(topic_or_mode: str, wave: int | str | None = None) -> Advice:
    """Say what earlier NHTS studies did on a topic or with a model family, and which design pitfalls to check.

    Args:
        topic_or_mode: A topic (``"bikeshare"``, ``"older adults"``, ``"EV adoption"``, ``"e-shopping"`` ...), a model family or analysis
            mode (``"classification"``, ``"ZINB"``, ``"logit"``), or free words.
        wave: Restrict to studies that name this wave.

    Returns:
        An :class:`Advice`; ``print(advice)`` gives the report. The pitfalls cite the numbers of the pynhts audit of 22 published
        NHTS studies, which are *not* a random sample of the literature.
    """
    topic = _resolve_topic(topic_or_mode)
    fam = None if topic else _resolve_family(topic_or_mode)
    kw: dict[str, Any] = {}
    if topic:
        kw["topic"] = topic
    elif fam:
        kw["model"] = fam
    else:
        kw["query"] = topic_or_mode
    sub = search(wave=wave, **kw)
    adv = Advice(query=topic_or_mode, topic=topic, family=fam, n_studies=len(sub))
    if sub.empty:
        return adv
    f = _findings()
    mod = sub[sub["abstract_available"].astype(bool) & sub["study_type"].isin(["regression_inference", "machine_learning"])]
    yr = sub["pub_year"].dropna()
    adv.summary = dict(
        year_range=f"{int(yr.min())}-{int(yr.max())}" if len(yr) else "years unknown", n_recent=int((yr >= 2020).sum()),
        waves=_count_top(sub["nhts_waves_mentioned"]), families=_count_top(sub["model_families"]),
        mod_n=len(mod), mod_weights_n=int(mod["mentions_weights"].sum()), mod_variance_n=int(mod["mentions_variance_design"].sum()),
        ml_n=int(sub["is_ml"].sum()), ml_resampling_n=int(sub["mentions_resampling"].sum()),
        acc90_n=int((sub["accuracy_claim_pct"].fillna(0) >= 90).sum()), examples_name_nhts=int(sub["mentions_nhts"].astype(bool).sum()) >= 5,
    )
    s = adv.summary
    pit: list[str] = []
    if len(mod):
        pit.append(
            f"Weights and variance: {s['mod_weights_n']} of {s['mod_n']} modelling abstracts on this topic name survey weights and "
            f"{s['mod_variance_n']} a design-based variance estimator (abstracts understate what analyses did). In the pynhts audit of "
            f"{f['n_studies']} studies, design-aware standard errors were a median {f['median_se_ratio']:.2f} times the unweighted ones "
            f"(IQR {f['q25_se_ratio']:.2f}-{f['q75_se_ratio']:.2f}), mostly from the unequal weights ({f['median_r_weights']:.2f}); "
            f"{100 * f['h3_share']:.0f} % of coefficients significant under each study's own inference lost significance under the design "
            f"and {100 * f['share_sign_flip']:.0f} % changed sign between the unweighted and the weighted fit. Use data.survey(...)/models.fit(regime='design')."
        )
    if fam == "Machine learning" or (s["ml_n"] and s["ml_n"] / max(1, s["mod_n"] + 1) >= 0.1) or s["ml_resampling_n"]:
        pit.append(
            f"Leakage: {s['ml_n']} machine-learning studies here, {s['ml_resampling_n']} mention oversampling/SMOTE/class imbalance and "
            f"{s['acc90_n']} state an accuracy or AUC of 90 % or more. In the pynhts re-score, oversampling before the split raised the random-forest "
            f"AUC for alternative-fuel-vehicle ownership from {f['afv_rf_auc_grouped']:.2f} (split by household, oversample the training part only) "
            f"to {f['afv_rf_auc_leaky']:.2f}. Split by household (transform.split_by_household), resample the training part only, "
            f"and run validate.audit_classifier."
        )
    waves = set(re.findall(r"\b(1995|2001|2009|2017|2022)\b", s["waves"]))
    if len(waves) >= 2:
        pit.append(f"Several waves are named ({', '.join(sorted(waves))}): raw codes, trip distance and weights are not comparable across waves; "
                   "use harmonize.apply_column, trends (per-wave estimates) and never pool weights.")
    reg = register(only_found=True)
    reg = reg[reg["cid"].isin(sub["cid"])]
    adv.register = reg[["audit_id", "study", "wave", "family", "L0_verdict", "L1_share_exact_close", "L2_grade", "L3_median_se_ratio", "L3_sig_lost",
                        "L3_sign_flips"]].reset_index(drop=True)
    if len(reg):
        done = reg[reg["L3_coef"].fillna(0) > 0]
        if len(done):
            pit.append(
                f"{len(reg)} audited studies belong to this topic ({', '.join(reg['audit_id'])}); for the {len(done)} re-estimated under the design, the median "
                f"standard-error ratio was {done['L3_median_se_ratio'].median():.2f} and {int(done['L3_sig_lost'].sum())} of {int(done['L3_sig_naive'].sum())} "
                f"significant coefficients lost significance, {int(done['L3_sign_flips'].sum())} changed sign."
            )
    if s["mod_n"] < 5 and s["ml_n"] < 3:
        pit.append("The literature on this topic in the compendium is thin: check the full texts before relying on what 'earlier studies did'.")
    adv.pitfalls = pit
    adv.concepts_to_read = [c for c in (_TOPIC_CONCEPTS.get(topic or "", []) + _ALWAYS_CONCEPTS) if c in concepts.names()]
    cols = ["cid", "pub_year", "title", "domain", "model_families", "nhts_waves_mentioned"]
    focus = sub[sub["mentions_nhts"].astype(bool)]  # studies that name the survey themselves make better precedents
    pool = focus if len(focus) >= 5 else sub
    adv.examples = pool.sort_values("pub_year", ascending=False).head(8)[cols].reset_index(drop=True)
    adv.design_aware_examples = sub[sub["mentions_weights"] | sub["mentions_variance_design"]].head(8)[cols].reset_index(drop=True)
    adv.watch_list = sub[sub["mentions_resampling"] | (sub["accuracy_claim_pct"].fillna(0) >= 90)].head(8)[cols + ["accuracy_claim_pct"]].reset_index(drop=True)
    return adv
