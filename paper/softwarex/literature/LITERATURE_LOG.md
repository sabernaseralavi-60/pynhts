# Literature log for the SoftwareX paper (lit-evidence, light version for a software paper), 2026-10-22

Depth: a software paper needs a focused Motivation section, not a systematic review (no PRISMA). Aim: show (a) how widely the NHTS
is used, (b) that data-quality and weighting issues are known in the literature, (c) the reproducibility and research-software
context, (d) existing software. No claim of novelty beyond "no other general Python package for NHTS access was found".

## Searches (FastTrack Literature Open = OpenAlex + Semantic Scholar; Crossref for verification)
| Query | Used for |
|---|---|
| National Household Travel Survey 2017 analysis of travel behavior (2019+, articles) | breadth of use; data-quality studies |
| comparing NHTS waves 2001 2009 2017 changes in survey method trip rates comparability | multi-wave studies, survey methodology |
| reproducibility and open data and code sharing in transportation research | reproducibility context |
| replication methods variance estimation complex surveys jackknife replicate weights review | variance theory (nothing better than the textbook [26] and the weighting report was found; the hits were off-topic or not NHTS) |
| software citation principles OR FAIR principles for research software | research-software context |
| GitHub: "NHTS python", "national household travel survey" (language python); PyPI names nhts, nhts-py, summarizenhts, pynhts | existing software (see the search sentence in the paper) |

## What was read
Only the **abstracts** returned by the search tool (and, for the studies of the audit, the full papers in the project folder
`some papers/`). Claims in the Motivation section are limited to what those abstracts say. Full texts of the new references were not read.

## Verification
All 24 references with a DOI were rebuilt from Crossref with `bib_from_dois.py` (`refs.bib`) and passed `retraction_check.py`
(`retraction_check.csv`: OK = 24, retracted/flagged = 0). The three references without a DOI are official documents (FHWA summary report,
Westat weighting report, summarizeNHTS repository), reachable on 2026-10-22. The Zenodo record is verified through the Zenodo API
(it is a DataCite DOI, so Crossref does not know it).
