# The NHTS Compendium of Uses inside pynhts

`pynhts.compendium` ships the official FHWA/ORNL **Compendium of Uses of the National Household Travel Survey**
(2006-2025) as one searchable, tagged table, linked to the L0-L3 reproducibility register of
[paper 02](https://github.com/sabernaseralavi-60/pynhts/tree/main/papers/02-nhts-ladder). It is for three jobs: finding and citing
prior NHTS work, a pre-flight check before you model a topic, and a bridge from "this study exists" to "this study can be rebuilt".

```python
import pynhts
c = pynhts.compendium
print(c.audit_summary())                                   # how the corpus was built, headline counts, the caveat
hits = c.search("bikeshare", wave=2017, model="logit")     # words (AND), wave, model family, domain, topic, years ...
print(c.to_bibtex(hits.head(3)))                           # authors, title, year, DOI/URL, original citation in `note`
print(c.advise("EV adoption"))                             # what earlier studies did + measured design pitfalls
print(c.advise("classification"))                          # an analysis mode instead of a topic
c.register(only_found=True)                                # the audited studies (P01-P24) and their compendium rows
```

Command line: `pynhts compendium search bikeshare --wave 2017`, `pynhts compendium advise "older adults"`,
`pynhts compendium audit`, `pynhts compendium bibtex "trip chaining" --limit 5`.

## What is in the table

One row per **unique study** (a study repeated in several editions is one row; `editions` and `provenance` list where it appeared).

| Column | Meaning |
|---|---|
| `cid` | stable id: `C` plus eight hex digits of the normalised title |
| `title`, `authors`, `pub_year`, `doi`, `url`, `availability` | bibliographic data from the entry; the publisher's citation string is kept in `availability` |
| `first_edition`, `editions`, `domain`, `domains_all` | compendium edition(s) and chapter (planning domain; 13 current domains, three legacy ones flagged) |
| `nhts_waves_mentioned` | `1995`, `2001`, `2009`, `2017`, `2022`, `NextGen OD`, `NPTS (year unstated)` named near a survey token |
| `model_families`, `study_type`, `is_ml` | Logit/Choice, Count (Poisson/NB/ZINB), OLS/Linear, SEM/Path, PSM/Causal, Hazard, Multilevel, Spatial, Machine learning, Clustering, Simulation/Optimisation |
| `mentions_weights`, `mentions_variance_design` | the abstract names survey weights / a design-based variance estimator (replicate weights, jackknife, BRR, Taylor, complex-survey procedures, clustered errors) |
| `mentions_resampling`, `mentions_validation`, `mentions_imbalance_or_leakage_risk`, `accuracy_claim_pct` | SMOTE/oversampling/class imbalance; cross-validation/ROC/AUC wording; the largest accuracy or AUC the abstract states |
| `topics` | 28 topic tags (bikeshare, older adults, EV adoption, e-shopping ...) used by `advise` |
| `linked_audit_id`, `repro_level` | P01-P24 id and the highest rung reached in the pynhts ladder (L0 rebuild the data, L1 the tables, L2 the model, L3 the model under the survey design) |

**What is not in it.** The abstracts belong to their publishers, so the package ships a sorted *term index* (the unique
content words of title, abstract and subject areas) instead of the text. Search works on titles, subject areas and the
index; the full workbook with abstracts is produced locally by `tools/compendium/build_compendium.py` from the raw
editions (kept out of git; checksums in `compendium/SOURCES.md`).

## Honest limits

* **Tags read abstracts.** An abstract that does not name weights may still have used them; the counts are a lower bound of
  *reporting*, not a measure of practice. This is why paper 02 rebuilds the analyses instead of counting words.
* **Precision.** Every positive among the modelling abstracts was read once (by Claude, not independent of the author of the
  patterns): `compendium/tag_precision_review.csv`. Recall was checked on the unflagged abstracts that contain "weight".
* **The compendium is not the literature.** It lists what the NHTS team found through TRB's portal, Google Scholar and alerts; it
  includes grid-optimisation and news items; only a minority of entries name the NHTS in the text (the summary below gives the count). Some of the 22 audited studies are
  not in it.
* **Titles of 2012-2015 entries** are one block with the authors; they are separated with the publisher citation, or a surname
  heuristic (`split_status`). `title_includes_authors` marks the rest.

## Building and checking the corpus

`tools/compendium/parse_compendium.py` reads each PDF page by page (`pdftotext -layout`). The editions have four layouts
(running category header; title and authors in one block; `Title:`/`Author:` labels; numbered `1.2 Title:`), so one global
regular expression silently loses entries. The parser instead anchors on the **table of contents**: printed page numbers
form a chain, the entry of page *p* is parsed from the PDF pages up to the next entry, and chapter comes from the entry number,
the running header, the chapter heading on the first page of each chapter or an alignment with the table-of-contents text.

Self-audit (per edition): entries parsed against three independent counts (the `Abstract:` anchors; the `Title:` labels;
the total the introduction states, "approximately N") and the share of table-of-contents titles found on their computed page. The
interactive-search export for 2023-2025 is counted by its rows. Deduplication uses the normalised title (equal, nested because one
edition fused title and authors, or very close).

<!-- AUTO:extraction:start -->
Entries parsed against independent counts, per edition (the 2023-2025 rows are the rows of the interactive-search CSV; the 2023 PDF covers January-June only and overlaps the CSV, which deduplication removes):

| edition | layout | PDF pages | entries parsed | Abstract: anchors | Title: labels / 2 | stated total | no abstract label | multi-page | TOC titles on computed page | max difference |
|---|---|---|---|---|---|---|---|---|---|---|
| 2006-2011 | A | 113 | 106 | 106 |  |  | 0 | 0 | 0.81 | 0 |
| 2012 | B | 226 | 210 | 208 |  | 210 | 2 | 0 | 1 | 0 |
| 2013 | B | 302 | 283 | 283 |  | 282 | 0 | 0 | 1 | 1 |
| 2014 | B | 343 | 322 | 321 |  | 322 | 1 | 0 | 1.00 | 1 |
| 2015 | B | 398 | 377 | 377 |  | 379 | 0 | 2 | 0.89 | 2 |
| 2016 | C | 408 | 376 | 376 | 376 | 375 | 0 | 11 | 0.96 | 1 |
| 2018 | D | 184 | 172 | 172 | 172 |  | 0 | 1 | 0.89 | 0 |
| 2019 | D | 204 | 192 | 192 | 192 |  | 0 | 2 | 0.94 | 0 |
| 2020 | D | 440 | 412 | 412 | 412 |  | 0 | 9 | 0.96 | 1 |
| 2021 | D | 493 | 454 | 454 | 454 |  | 0 | 18 | 0.96 | 1 |
| 2022 | D | 451 | 420 | 420 | 420 |  | 0 | 11 | 0.96 | 1 |
| 2023-pdf | D | 232 | 214 | 214 | 214 |  | 0 | 6 | 0.96 | 0 |
| 2023 | CSV |  | 381 |  |  |  | 0 | 0 |  | 0 |
| 2024 | CSV |  | 363 |  |  |  | 0 | 0 |  | 0 |
| 2025 | CSV |  | 337 |  |  |  | 0 | 0 |  | 0 |
<!-- AUTO:extraction:end -->

## The Methodological Advisor

`advise(topic_or_mode, wave=None)` returns an `Advice` object (`print()` it). It reports how many studies cover the topic, the
waves they name, their model families, how many modelling abstracts name weights or a variance estimator, and **pitfalls with
numbers from the pynhts audit of 22 published studies** (`compendium_findings.json`, generated from `papers/02-nhts-ladder`):
the median ratio of design-aware to unweighted standard errors, the share of significant coefficients that lose significance under
the design, the share that change sign, and the inflation of a random-forest AUC when SMOTE precedes the split. It lists the
audited studies in the topic, the pynhts concepts to read (top-codes, universes, comparability) and recent precedents.
The audit is a convenience set of 22 studies, not a sample of the literature.

## Extending the register

A compendium entry gains an L0-L3 recipe the same way the 22 studies did (`tools/paper_audit/`, `papers/02-nhts-ladder/`):
rebuild the sample (`pynhts.study`), grade the printed tables, refit the model, refit it under the design
(`pynhts.models.fit(regime="design")`). Add the study to `papers/02-nhts-ladder/results/tables/studies.csv` and its bibliography key to
`build_compendium.case_study_links`; rebuilding the corpus links it.

## Corpus summary

<!-- AUTO:summary:start -->
* 4619 listed records (3538 in 12 PDFs, 1081 in the 2023-2025 search export) = **4301 unique studies** (318 repeated across editions); 3983 have an abstract.
* 868 studies name the NHTS/NPTS in title, abstract or subject areas; waves named: 2017 in 301, 2009 in 208, 2001 in 105, 2022 in 42; 275 name the survey but no wave.
* Modelling abstracts (regression or machine learning, abstract present): 1039; **31 name survey weights, 4 a design-based variance estimator** (every positive was read: 29 of 31 weight flags and 2 of 4 variance flags are correct).
* Machine learning: 215 studies, 9 mention oversampling/SMOTE/class imbalance, 11 state an accuracy or AUC of 90 % or more.
* Audited studies found in the compendium: 19 of 22, in 6 domains.

Studies by planning domain (chapter of first appearance), with the tags of their abstracts:

| domain | studies | mention_nhts | regression | ml | weights | variance |
|---|---|---|---|---|---|---|
| Energy consumption | 1038 | 118 | 50 | 68 | 3 | 0 |
| Survey, data synthesis and other applications | 476 | 122 | 92 | 71 | 8 | 2 |
| Travel behavior | 470 | 176 | 166 | 20 | 5 | 0 |
| Policy and mobility | 419 | 55 | 64 | 10 | 3 | 0 |
| Special population groups | 394 | 119 | 116 | 3 | 4 | 0 |
| Bicycle and pedestrian studies | 344 | 70 | 82 | 5 | 5 | 1 |
| Trend analysis and market segmentation | 334 | 84 | 81 | 8 | 7 | 0 |
| Environment | 217 | 15 | 21 | 6 | 1 | 0 |
| Traffic safety | 215 | 32 | 51 | 10 | 1 | 1 |
| Transit planning | 170 | 39 | 54 | 3 | 1 | 0 |
| Health | 93 | 13 | 20 | 4 | 4 | 0 |
| Emerging travel modes | 64 | 8 | 14 | 3 | 1 | 1 |
| Passive OD data product usage | 33 | 8 | 5 | 4 | 2 | 0 |
| Demographic trends (legacy) | 24 | 5 | 8 | 0 | 1 | 0 |
| Gas tax and fee scenarios (legacy) | 9 | 4 | 2 | 0 | 1 | 0 |
| Freight movement (legacy) | 1 | 0 | 0 | 0 | 0 | 0 |

Audited studies by domain:

| domain | case_studies |
|---|---|
| Bicycle and pedestrian studies | 2 |
| Special population groups | 4 |
| Survey, data synthesis and other applications | 2 |
| Transit planning | 2 |
| Travel behavior | 7 |
| Trend analysis and market segmentation | 2 |
<!-- AUTO:summary:end -->
