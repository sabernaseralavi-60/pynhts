# SoftwareX submission notes (Original Software Publication), LaTeX route, prepared 2026-10-22

**کارهای دستیِ نویسندگان پیش از ارسال (فارسی):**
۱. نقش‌های CRediT خانم مظاهری را بنویسید (در `content.py`، متغیر `CREDIT`، یک برچسب `[[AUTHOR-TODO]]` مانده). ۲. تأیید کنید بیانیهٔ «تعارض منافع ندارند» درست است
(جملهٔ استاندارد گذاشته شده). ۳. هزینهٔ APC را در صفحهٔ رسمی مجله ببینید. ۴. اگر خانم مظاهری در نوشتن **نرم‌افزار** هم سهم داشته، نامش به `CITATION.cff` و Zenodo
اضافه شود (الان فقط نویسندهٔ نرم‌افزار آقای ناصرعلوی است). ۵. ORCID خانم مظاهری (`0009-0000-1439-3915`) فقط با نام و دانشگاه در ORCID پیدا شد و تأیید نشده؛
در مقاله چاپ نشده. ۶. سپس فایل‌ها را طبق بخش «How to submit» آپلود کنید.

Nothing has been submitted. Sources of every rule: the SoftwareX Guide for Authors text pasted by the author on 2026-10-22, and the official OSP
templates v6 (March 2026): `template/softwarex-osp-template.tex` (sha256 2b18dfd1...3b8649) and `.docx` (sha256 9fcf40ed...b916d), both from
legacyfileshare.elsevier.com (Elsevier, LPPL for the .tex; kept locally, not committed). The Guide's list of pre-approved licences was not in the pasted text;
BSD 3-Clause is OSI-approved, which the Guide accepts ("recognized legal license ... by the Open Source Initiative").

## Authors (from `~/.claude/research-kit/AUTHORS.yaml`)

1. Seyed Saber Naseralavi, Department of Civil Engineering, Shahid Bahonar University of Kerman, Kerman 7616914111, Iran; corresponding author;
   saber_naseralavi@uk.ac.ir (institutional, given by the author 2026-10-22; also the support e-mail, C8).
2. Akram Mazaheri, Department of Civil and Environmental Engineering, Tarbiat Modares University, Tehran 1411944961, Iran; akram.mazaheri.010@gmail.com.

The Guide says authors must have contributed to conception/design or analysis, drafting or revising, and final approval, and that changes of authorship
after submission are nearly impossible: both authors should read and approve the manuscript before it is submitted.

## Files (all generated: `python paper/softwarex/make_figures.py` then `python paper/softwarex/build_tex.py`)

| File | Use |
|---|---|
| `latex/pynhts_softwarex.pdf` | the compiled manuscript: upload in the field "Manuscript (Word or PDF file)" |
| `pynhts_softwarex_latex_sources.zip` | `.tex` and the figures (PDF), upload in the field "Zip file containing LaTeX source files" (the references are inside the `.tex`, as in the template) |
| `highlights.txt` | separate file with "highlights" in the name (5 bullets, each at most 85 characters) |
| `cover_letter.md` | text for the cover-letter field |
| `figures/` | PNG and PDF of the three figures (six allowed) |
| `literature/` | `refs.bib` rebuilt from Crossref, `retraction_check.csv`, `LITERATURE_LOG.md` (queries, what was read, verification) |
| `content.py`, `build_tex.py`, `make_figures.py` | sources; every number comes from `docs/paper_data_audit/results/*.csv` or is a stated constant |

## Checks against the Guide (done by `build_tex.py` or by reading the PDF)

* Template: the official `softwarex-osp-template.tex` (elsarticle, preprint 12 pt), five mandatory numbered sections, metadata table C1-C8, "Before you begin"
  block deleted; additions: AI-use section, CRediT, funding, competing interests, data availability (the Guide requires them), a thin `\parskip` for readability.
* Word limit 4,000 (abstract, text, captions, code; not title, authors, metadata, references): 2,744 counted. Abstract 248 words (limit 250), no citations in it. Keywords 6 (limit 6). Highlights 5 x at most 85 characters. Figures 3 (limit 6).
* References: 28, numbered in order of first appearance (asserted by the build), journal style of the Guide with abbreviated journal names; 25 have a DOI that was checked in Crossref
  and screened for retraction; the three web references and the software record were checked on 2026-10-22; the software is cited with its Zenodo DOI (version 10.5281/zenodo.23575312; all versions 10.5281/zenodo.23573454).
* Figures and sections are cross-referenced by `\ref` (no typed numbers); every figure is referenced; the equation is typeset.
* Repository: public GitHub, README.md, LICENSE.txt (added in 0.8.1), source in `src/`, BSD 3-Clause, tag `v0.8.1`, PyPI 0.8.1, Zenodo record.
* Standing rules of the research factory: no citations in the abstract; neutral framing of the audit (differences between a paper and the public files under its stated rules, no allegation
  of error); AI-use declaration with the review sentence; figures made by code and inspected; Persian version not needed for this journal.

## Open items (all marked `[[AUTHOR-TODO]]` in the sources)

1. CRediT roles of A. Mazaheri (not stated by the authors).
2. Competing interests: the standard "no known competing interests" sentence is written; the authors must confirm it (also in the submission system's declarations tool).
3. Funding: "no specific grant" was stated by the author on 2026-10-22 and is written as the standard sentence.
4. Open-access fee (APC): not in the pasted text; USD 760 appears only in third-party directories. Check the journal's open-access page. The checklist says the corresponding author is responsible if the paper is accepted.
5. Optional: SSRN preprint at submission (free, no effect on review; default here: no).

## How to submit (Editorial Manager: https://www.editorialmanager.com/softx)

1. Log in or register (Elsevier account). Article type: **Original Software Publication**.
2. Upload `latex/pynhts_softwarex.pdf` as the manuscript and `pynhts_softwarex_latex_sources.zip` as the LaTeX source archive; highlights as a separate file; cover letter text in the letter field.
3. Enter the GitHub URL https://github.com/sabernaseralavi-60/pynhts where asked, and give the Zenodo DOI in the data statement.
4. Complete the declarations tool (competing interests, funding, generative AI: the manuscript already contains the statement).
5. Approve the PDF and submit. Review is single-anonymised.

## Risks (honest)

* **Impact section.** The template calls it the main section. pynhts was made public on 2026-10-16 and has no external users, no citing publications and no commercial use; downloads cannot be told from mirrors.
  The evidence offered is validation (142 of 175 official figures; 1,096 graded numbers from 21 published studies). Reviewers may judge this too thin; no chance of acceptance is claimed.
  Strengthening: a replication or methods paper that uses pynhts, outside users, citations.
* **Scope.** SoftwareX stresses software with impact across domains; this package is domain-specific (survey analysis of one national survey), with a general reproducibility message.
* **Audit wording.** Keep the neutral wording if the text is edited.
* **Journal facts** (CiteScore about 4.1, impact factor 1.9 to 2.4, Q3 in software engineering) come from third-party sites only; verify in the journal's own pages if they matter to the decision.
* **JOSS** is not an option before about April 2027 (six months of public history; evidence of research use).
