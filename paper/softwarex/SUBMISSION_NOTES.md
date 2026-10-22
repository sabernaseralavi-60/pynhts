# SoftwareX submission notes (Original Software Publication), prepared 2026-10-22

Nothing has been submitted. Source of every rule below: the SoftwareX Guide for Authors text pasted by the author on 2026-10-22 and the
official OSP template v6 (March 2026), `template/softwarex-osp-template.docx` (sha256 9fcf40ed...b916d, from
legacyfileshare.elsevier.com; not committed). The Guide's list of pre-approved licences was NOT in the pasted text; BSD 3-Clause is
OSI-approved, which the Guide accepts ("recognized legal license ... by the Open Source Initiative").

## Files (generate with `python paper/softwarex/build_docx.py`; needs python-docx; `make_figures.py` makes the figures)

| File | Use |
|---|---|
| `pynhts_softwarex.docx` | the manuscript in the official template: upload in the field "Manuscript (Word or PDF file)" |
| `pynhts_softwarex.pdf` | a Word rendering for reading only |
| `highlights.txt` | upload as a separate file with "highlights" in the name (5 bullets, each at most 85 characters) |
| `cover_letter.md` | cover letter text for the submission system |
| `figures/` | the three figures (already embedded in the docx, which the Word route requires) |
| `content.py`, `build_docx.py`, `make_figures.py` | sources; numbers come from `docs/paper_data_audit/results/*.csv` |

## Checks against the Guide (done)

* Word limit 4,000 (abstract, text, captions, footnotes; not title, authors, references, metadata table): about 2,550 counted conservatively with the code listings; 2,800 with declarations.
* Figures: 3 (limit 6), embedded in the docx. Abstract 248 words (limit 250), no citations in it. Keywords 6 (limit 6). Highlights 5 x at most 85 characters.
* References: numbered in order of first appearance, journal-style; every journal reference was checked against Crossref (title, authors, year, volume, pages, DOI); the three web references were reachable on 2026-10-22; the software is cited with its Zenodo DOI (10.5281/zenodo.23575312, version 0.8.1; all versions 10.5281/zenodo.23573454).
* Repository: public GitHub, README.md, LICENSE.txt (added in 0.8.1), source in `src/`, BSD 3-Clause, tag `v0.8.1`, PyPI 0.8.1, Zenodo record.
* AI-use declaration section before the references (standing review sentence included). CRediT statement, funding, competing interests and data availability are included.
* The Impact section (the one reviewers weight most) states plainly that there are no external users and no publications that use the package.

## What only the author can supply (all marked `[[AUTHOR-TODO]]` in the files)

1. Corresponding author's e-mail (it is printed in the article); support e-mail for metadata row C8.
2. Funding statement (or the standard "no specific grant" sentence), competing-interests declaration (also entered in the submission system's declarations tool), confirmation of sole authorship and CRediT roles.
3. The open-access fee (APC). Not in the pasted text; the figure of USD 760 comes from third-party directories only. Check the journal's open-access page before submitting; the checklist says the corresponding author is responsible for it if the paper is accepted.
4. Optional: SSRN preprint during submission (free; default here is no).

## How to submit (Editorial Manager: https://www.editorialmanager.com/softx)

1. Log in or register (Elsevier account). Article type: **Original Software Publication**.
2. Upload `pynhts_softwarex.docx` as the manuscript; highlights as a separate file; the cover letter in the letter field.
3. Enter the GitHub URL (https://github.com/sabernaseralavi-60/pynhts) where asked; give the Zenodo DOI in the data statement.
4. Complete the declarations tool (competing interests, funding, generative AI: the manuscript already contains the statement).
5. Approve the PDF and submit. Review is single-anonymised; the AI-use rules for reviewers do not affect the author.

## Risks (honest)

* **Impact section.** The template calls it the main section. pynhts was made public on 2026-10-16 and has no external users, no citing publications and no commercial use; downloads cannot be told from mirrors. The evidence offered is validation (142 of 175 official figures; 1,096 graded numbers from 21 published studies). Reviewers may judge this too thin; we have not seen the journal's acceptance practice, so no chance of acceptance is claimed. Strengthening: a replication or methods paper that uses pynhts, outside users, citations.
* **Scope.** SoftwareX stresses software with impact across domains; this package is domain-specific (survey analysis of one national survey), with a general reproducibility message.
* **Audit wording.** The audit reports gaps as differences between what a paper prints and what the public files give under the paper's stated rules; it does not allege errors. Keep this wording if the text is edited.
* **Journal facts.** CiteScore, impact factor and indexing were read from third-party sites only (CiteScore about 4.1, impact factor 1.9 to 2.4, Q3 in software engineering); verify them in the journal's own pages if they matter to the decision.
* **JOSS** is not an option before about April 2027 (six months of public history required; evidence of research use).
