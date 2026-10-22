"""Text of the SoftwareX manuscript (Original Software Publication). Numbers come from the repository's result files.

Blocks: ("p", text) paragraph, ("code", text) code listing, ("fig", file, caption), ("h", text) run-in subheading.
In-text citations are written as [key]; build_docx.py numbers them in order of first appearance.
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "docs" / "paper_data_audit" / "results"

VERSION = "0.8.1"
VERSION_DOI = "10.5281/zenodo.23575312"
CONCEPT_DOI = "10.5281/zenodo.23573454"
REPO = "https://github.com/sabernaseralavi-60/pynhts"


def _rows(pattern: str) -> list[dict]:
    out = []
    for f in sorted(RES.glob(pattern)):
        out += list(csv.DictReader(f.open(encoding="utf8")))
    return out


_a = [r for r in _rows("p[0-9][0-9]_*.csv") if r["status"] in ("EXACT", "CLOSE", "ACCEPTABLE", "GAP")]
AUD = {s: sum(r["status"] == s for r in _a) for s in ("EXACT", "CLOSE", "ACCEPTABLE", "GAP")}
AUD_N = len(_a)
_l = [r for r in _rows("recheck_p10_lidbe2021.csv") if r["status"] in AUD and "race reading v2" not in r["item"] and "TDWKND flag" not in r["item"]]
LID_N = len(_l)
LID_EXACT = sum(r["status"] == "EXACT" for r in _l)

TITLE = "pynhts: survey-weight-aware Python access to the US National Household Travel Survey"

ABSTRACT = (
    "The US National Household Travel Survey (NHTS) is the main public source of US household travel data, and four waves (2001, 2009, 2017 and 2022) are freely available. Using them correctly is harder "
    "than it looks: weights and variance designs differ by wave, the same code can mean different things in different "
    "waves, skipped questions are stored as numbers, and trip weights give annual rather than daily totals. These details "
    "are rarely stated in papers, so published results are difficult to reproduce or to compare. pynhts is an open-source "
    "Python library that downloads and verifies the official files, converts them to typed Parquet, joins the four tables "
    "without silent errors, and computes estimates with the variance method of each wave (jackknife replicate weights for "
    "2001, 2009 and 2017; Taylor linearisation for 2022). It adds validated crosswalks between waves, guards for top-coded "
    "and non-answer values, and a study module that turns a written research statement into an analysis file with a "
    "sample-flow table. Validation is part of the package: 142 of 175 figures printed in official reports reproduce "
    "completely, Taylor-series errors agree with R to 1e-9, and 21 published studies were rebuilt "
    f"and {AUD_N:,} printed numbers graded. The rebuilding recovered unstated rules, such as the base of a percentage and "
    "the definition of a weekend, that move published values by several per cent. The package is young and has no external "
    "users yet; its contribution is a tested, documented way to state and check the assumptions of NHTS analyses."
)

KEYWORDS = "National Household Travel Survey; travel survey; replicate weights; survey statistics; reproducibility; Python"

META = [
    ("C1", f"v{VERSION}"),
    ("C2", REPO),
    ("C3", "BSD 3-Clause License"),
    ("C4", "git"),
    ("C5", "Python 3; NumPy, pandas, PyArrow, pooch, PyYAML; optional: matplotlib, PyTorch"),
    ("C6", "Python 3.10 or newer on Linux, Windows or macOS (continuous integration on Linux and Windows); "
           "about 0.4 GB of Parquet per wave and 1.8 GB of raw CSV for 2017, which can be deleted after conversion"),
    ("C7", REPO + "/tree/main/docs"),
    ("C8", "[[AUTHOR-TODO: support e-mail; the GitHub issue tracker is " + REPO + "/issues]]"),
]

SECTIONS: dict[str, list[tuple]] = {}

SECTIONS["motivation"] = [
    ("p", "The National Household Travel Survey (NHTS), sponsored by the US Federal Highway Administration (FHWA), is the "
          "main public source of information on how US households travel: who makes trips, by which mode, for which purpose, "
          "and over what distance [1]. Public-use files exist for 2001, 2009, 2017 and 2022, each with four linked tables "
          "(households, persons, trips, vehicles), sampling weights and, for three waves, replicate weights. The files "
          "underpin studies of active travel [2], ridesharing [3], older travellers [4], vehicle miles travelled [5,6] and "
          "online shopping [7]."),
    ("p", "Using the files correctly requires work that every project repeats and that is easy to get wrong. A skipped question is "
          "stored as the number -1, so the mean of the 2009 vehicle miles driven (VMT_MILE) is 5.36 instead of 9.72 and its total is 7 % low. "
          "The same code means different things in different waves: transport mode \"01\" is a car in 2009, where it is 44 % of "
          "trips, and walking in 2017, where it is 10.5 %. Trip weights add up to annual, not daily, totals; the 2001 file "
          "contains children aged 0-4 and the others do not; ages and vehicle ages are top-coded; and 2022 uses a different "
          "variance design from the earlier waves. Such mistakes change estimates and, more often, understate their "
          "uncertainty. Papers rarely state the rules they applied, which makes their numbers hard to reproduce."),
    ("p", "pynhts addresses these problems in one Python package. It (i) fetches and verifies the official files and exposes them "
          "as typed tables that cannot be merged wrongly, (ii) computes every estimate with the variance method of its wave, "
          "(iii) maps codes between waves only where the meaning is shown to be the same, (iv) forces the analyst to state "
          "sample rules, missing-value policy and weighting, and (v) ships its own validation against published numbers. "
          "Scientifically, the contribution is not a new estimator but a way to make the assumptions of an NHTS analysis "
          "explicit, testable and reusable."),
    ("p", "A user installs the package, downloads a wave with one command, loads it lazily, and asks for weighted statistics, "
          "rates, harmonised categories or a complete study (Section 3). Results carry the wave, weight, variance design and "
          "unit, so a table footnote can be written from the result itself."),
    ("p", "Related work. The R package summarizeNHTS [8] downloads and summarises NHTS data, and the R survey package [9] "
          "offers general replicate-weight and Taylor-series analysis that users can apply to NHTS data after setting up the "
          "design themselves. The Python package samplics [10] covers complex-sample estimation in general but does not know "
          "the NHTS files, codes or weights. A search of GitHub and PyPI on 22 October 2026 (queries \"NHTS python\" and "
          "\"national household travel survey\", and the package names nhts, nhts-py and summarizenhts) found analysis scripts "
          "for single projects and no other general Python package for NHTS access. The variance estimators follow the "
          "standard replicate-weight theory [11] and the weighting report of the 2017 survey [12]."),
]

SECTIONS["architecture"] = [
    ("p", "pynhts is organised in layers (Fig. 1). The input and statistics layers handle the data; the harmonisation and "
          "analysis layers help the analyst to ask correct questions; the validation layer checks the result against "
          "published numbers."),
    ("fig", "fig1_architecture.png", "Architecture of pynhts. Blue: data access and statistics; amber: harmonisation and analysis; "
            "green: validation and bridges. Every result frame records how it was computed."),
    ("p", "pynhts.io keeps a registry with the SHA-256 hash of every official archive and member, downloads with pooch, and "
          "writes Parquet deterministically. The data server answers HTTP 200 with an HTML page for files that do not exist, so "
          "content type and size are checked. pynhts.core derives a typed schema from the codebook (all 3,807 coded values of "
          "2017 and all 2,639 of 2022 reproduce the printed frequencies) and loads columns lazily, joining each requested column "
          "from the table that owns it through a validated many-to-one join. The skip code is converted to a missing value in "
          "numeric columns by default, and non-answer codes are masked on request."),
    ("p", "pynhts.stats implements the stratified jackknife of the 2017 weighting design: with 14 variance strata of 7 units the "
          "variance is 6/7 times the sum over the 98 replicates of the squared deviation of the replicate estimate from the full "
          "estimate, and the margin of error is the t quantile with 98 degrees of freedom times the standard error [11,12]. The 2009 "
          "and 2001 files have 100 and 99 replicates with their own factors, and 2022, which has no replicate weights, uses "
          "Taylor linearisation with strata and households; its errors equal those of the R survey package to 1e-9. All trips of a person share "
          "one weight, so trip estimates are computed on person-day units and need a 98-column matrix for 264,234 units rather "
          "than 923,572 trips. Subpopulations are handled as domains, never by dropping rows."),
    ("p", "pynhts.concepts and pynhts.harmonize describe 44 concepts across the four waves, each graded as comparable, "
          "comparable with care, or not comparable, and provide 19 crosswalks (trip purpose, mode, race and Hispanic origin, "
          "medical condition, and others). A crosswalk reads the wave from the frame and refuses a mismatch; each category is marked "
          "exact, approximate or nested, with the evidence in the data. The analysis layer contains aggregate (trips to persons or "
          "households with an explicit missing-value policy and true zeros), features (93 documented variables with lineage), "
          "study (below), trends (per-wave estimates; pooling is refused for non-comparable concepts), transform (splits by "
          "household so that train and test sets do not share a household) and tables and viz for reporting."),
    ("p", "pynhts.recipes encodes the numbers printed in official reports together with the expected status of each, and a generated "
          "report lists every gap. A small bridge exports tables to NumPy arrays, PyTorch tensors and household graphs."),
    ("h", "Software functionalities"),
    ("p", "The main functions are: verified download and offline use (pynhts fetch, register, docs); typed lazy loading of the four "
          "tables of each wave; survey totals, means, ratios and rates with standard errors and margins of error "
          "(rates.daily_rate gives daily rates and states when a total is annual); crosswalks between waves and a combined "
          "race-and-ethnicity variable; warnings for top-coded values, national-sample-only columns and caps; and the study module. "
          "A Study object takes the wave, the unit of analysis, ordered sample rules (Keep, Drop, Complete), variables, the weight "
          "(or an explicit none) and stated assumptions. It returns the analysis file, a sample-flow table with the number "
          "removed by each rule, a descriptive table, a methods paragraph and a comparison with published numbers graded exact, close, "
          "acceptable or gap. It never tunes a rule to reach a number."),
]

SECTIONS["examples"] = [
    ("p", "Example 1 produces national estimates of the 2017 survey with design-correct margins of error."),
    ("code", "import pynhts\nfrom pynhts import rates\nd = pynhts.load(2017)\ns = d.survey(\"person\", [\"DRIVER\"])\n"
             "s.total(domain=s.rows[\"DRIVER\"] == \"01\")   # 223.3 million drivers, MOE 0.83 million\n"
             "d.survey(\"trip\", [\"TRPMILES\"]).mean(\"TRPMILES\")   # 10.70 miles per trip, MOE 0.40\n"
             "rates.daily_rate(d, \"trips\", per=\"person\")   # 3.37 daily trips per person, MOE 0.04"),
    ("p", "These values equal the figures printed in the official summary report [1], including the margins of error."),
    ("p", "Example 2 shows why a stated base matters. Lidbe et al. [4] report that 5.49 % of 2001 trips were made by persons "
          "with a medical condition that makes travel difficult. The question was asked only of persons aged 16 or older; younger "
          "persons carry the skip code. Counting them as having no condition gives 4.40 %; using the trips of persons who answered "
          "gives the printed value. The crosswalk returns a missing value for the skip, so the second base is the natural one."),
    ("code", "from pynhts import harmonize\nd = pynhts.load(2001)\n"
             "p = d.persons([\"MEDCOND\"], missing=\"keep\", skip=\"keep\")\n"
             "p[\"med\"] = harmonize.apply_column(p, \"MEDCOND\", \"medical_condition\")\n"
             "# the skip and the non-answers are now missing, not \"no\"\n"
             "k = [\"HOUSEID\", \"PERSONID\"]\n"
             "t = d.trips([\"TRPMILES\"]).merge(p[k + [\"med\"]], on=k)\n"
             "w = t[\"WTTRDFIN\"]; yes = t[\"med\"].eq(\"yes\")\n"
             "100 * w[yes].sum() / w.sum()                    # 4.399: all trips\n"
             "100 * w[yes].sum() / w[t[\"med\"].notna()].sum()  # 5.489: persons who answered"),
    ("p", "Example 3 states a whole study as data. The sample rules of Zhang and Zhang [3] (15 low-use states excluded, only persons who "
          "answered the ridesharing question, complete model variables, no weights) become a Study, which returns the sample-flow "
          "table and the descriptive table. The result has 218,831 persons against 219,026 printed (0.09 % fewer), after removing "
          "9,142, 27,090 and 9,171 persons by the three rules from the 264,234 in the file, and the mean number of ridesharing "
          "uses in 30 days is 0.309 as printed."),
    ("code", "from pynhts import study as S\n"
             "spec = S.Study.from_yaml(\"docs/examples/ridesharing_35_states.yaml\")\n"
             "res = spec.run(pynhts.load(2017))\n"
             "res.flow     # persons before and after each rule\n"
             "res.table()  # mean, sd, min, max, share of zeros\n"
             "S.compare(res, [{\"variable\": \"ride\", \"stat\": \"mean\",\n"
             "                 \"value\": 0.309}])   # EXACT"),
]

SECTIONS["impact"] = [
    ("h", "Validation against official figures"),
    ("p", "Five recipes encode 175 figures printed in official documents: Tables 1 and 3 of the Summary of Travel Trends for 2001, "
          "2009 and 2017, the control totals of the 2022 user guide, and a transit-tour study. Of these, 142 reproduce completely, "
          "8 reproduce the estimate but not the printed margin of error (the report uses another multiplier), and 25 do not; each "
          "gap is explained in the generated report where a cause is known, and no rule was changed to hide one. For 2022, "
          "the Taylor-series errors equal those of the R survey package. There are 333 unit tests that need no data and more "
          "than 600 tests when the real files are present, run on Linux and Windows."),
    ("h", "Rebuilding published studies"),
    ("p", "To test whether the package supports real analyses, the data of 21 published NHTS studies were rebuilt with the package "
          "only, one script per study, and every number the study prints about its data was graded against the result: exact "
          "(equal at the printed precision), close (within 2 %), acceptable (within 5 %) or gap. No rule was adjusted to reach a "
          f"number. Of {AUD_N:,} graded values, {AUD['EXACT']} are exact, {AUD['CLOSE']} close, {AUD['ACCEPTABLE']} acceptable and "
          f"{AUD['GAP']} gaps (Fig. 2). In nine studies the analysis data could be rebuilt convincingly; in the others the printed "
          "numbers depend on sample rules or external variables that the paper does not state or that the public files do not "
          "contain. We treat each gap as a statement about the information available in the paper, not about its authors' work."),
    ("fig", "fig2_audit_overview.png", "Outcome of the audit of 21 published NHTS studies (P01-P23; listed in the repository). "
            "Bars show the share of each study's printed numbers that pynhts reproduces exactly, closely (2 %), acceptably (5 %) or not."),
    ("p", "The exercise produced 32 recovered conventions, written down with their evidence, and several of them change published "
          f"numbers. A re-check of one study [4] with the crosswalks and the study module illustrates this: {LID_EXACT} of {LID_N} "
          "cells of its Tables 3 and 4 are reproduced exactly (Fig. 3). The percentages in its Table 3 use the trips of persons "
          "with a valid answer as the base (Example 2); its weekend is Saturday and Sunday of the travel-day variable, whereas "
          "the NHTS weekend flag also contains part of Friday and gives values 5 to 8 % higher; trip duration is the calculated "
          "minutes variable; the six items on how the condition changes travel are reproduced exactly (72 of 72 cells) through the "
          "condition-effect crosswalk; and its race groups follow a rule in which Hispanic origin overrides only the White, Black and "
          "Asian groups, which is not what a combined race-and-ethnicity variable does. In another study [2] the sample of "
          "130,222 persons is reproduced exactly as a Study, and its race variable is the household respondent's single race code; "
          "mapping it through the combined variable would give a different sample (133,538 persons). These findings became "
          "package features (crosswalks, caps, warnings) or documentation."),
    ("fig", "fig3_agreement_lidbe.png", "Values printed in Tables 3 and 4 of Lidbe et al. [4] against the values computed with pynhts "
            "(279 cells with a positive value; one printed zero is not shown). The diagonal is exact agreement."),
    ("h", "New research questions and changed practice"),
    ("p", "Design-correct uncertainty for every wave, guarded comparisons across waves, and sample-flow tables make it cheaper to ask "
          "questions that depend on trends and on subpopulations, and to report them so that others can repeat them. The "
          "study module is meant to change the daily practice of analysts by making the sample rules and the missing-value policy part of "
          "the code. We have not measured any change in practice yet."),
    ("h", "Extent of use"),
    ("p", "The first version was released on PyPI in October 2026 and the package has had 12 releases since; version "
          f"{VERSION} is archived on Zenodo [13]. The package has no known external users, no publication has used it, and it has no "
          "commercial use. PyPI records downloads, but they include automated mirrors, so we do not report them as users. The "
          "evidence of impact is therefore the validation and the audit, which can be repeated by anyone with the public files, "
          "and the intended use is by researchers who analyse the NHTS and by those who review such analyses."),
]

SECTIONS["conclusions"] = [
    ("p", "pynhts gives researchers typed, survey-weighted access to the four NHTS waves with the variance method of each wave, "
          "crosswalks that are checked against the data, and a way to state the sample and the missing-value policy as code. Its "
          "validation against official figures and published studies shows both that it reproduces most numbers and that the "
          "remaining differences usually come from rules that publications do not state."),
    ("p", "Limitations are clear. The package is at an alpha stage and its interface may change. It handles the public-use files "
          "only; variables that need the restricted files (for example census-tract identifiers) are out of reach. It does not fit "
          "models, so standard errors of regression coefficients, which need the weights to be refitted for each replicate, are not "
          "yet provided. National weights of the 2001 national sample are not available. The replicate-weight archives of 2001 "
          "and 2009 are large. Next steps are variance estimates for model coefficients, more crosswalks, and a repeated audit "
          "as new studies appear."),
]

ACK = ("The NHTS is conducted by the US Department of Transportation, Federal Highway Administration, and distributed by Oak Ridge "
       "National Laboratory. The package does not redistribute the survey data.")

AI = ("During the preparation of this work the author used Claude (Anthropic) as an assistant for software design, writing and "
      "running code and tests, checking the code against the official documents and data, and drafting and editing the text. "
      "After using this tool, the author reviewed, verified and edited the material (code, results, references and text) and "
      "takes full responsibility for the content of the publication. Numbers in the text are taken by code from the result files "
      "of the repository, and the references were checked against a bibliographic database.")

CREDIT = ("Seyed Saber Naseralavi: Conceptualization, Data curation, Formal analysis, Investigation, Methodology, Project "
          "administration, Resources, Software, Validation, Visualization, Writing - original draft, Writing - review and editing. "
          "[[AUTHOR-TODO: confirm sole authorship and roles]]")

FUNDING = "[[AUTHOR-TODO: funding statement. Standard sentence if none: This research did not receive any specific grant from funding agencies in the public, commercial, or not-for-profit sectors.]]"
COMPETING = "[[AUTHOR-TODO: confirm no competing interests; the declarations tool of the submission system also needs this]]"
DATA = (f"The software is available at {REPO} (archived at Zenodo, DOI {VERSION_DOI}). The NHTS public-use data are "
        "distributed by Oak Ridge National Laboratory (https://nhts.ornl.gov); pynhts downloads them from there and does not redistribute them.")

REFS = [
    ("mcguckin", "McGuckin N, Fucci A. Summary of travel trends: 2017 National Household Travel Survey. Report FHWA-PL-18-019. "
                 "Washington (DC): US Department of Transportation, Federal Highway Administration; 2018. "
                 "https://nhts.ornl.gov/assets/2017_nhts_summary_travel_trends.pdf [accessed 22 October 2026]."),
    ("yang", "Yang Y, Diez Roux AV, Bingham CR. Variability and seasonality of active transportation in USA: evidence from the 2001 NHTS. "
             "Int J Behav Nutr Phys Act 2011;8:96. https://doi.org/10.1186/1479-5868-8-96."),
    ("zhang", "Zhang Y, Zhang Y. Examining the relationship between household vehicle ownership and ridesharing behaviors in the United "
              "States. Sustainability 2018;10:2720. https://doi.org/10.3390/su10082720."),
    ("lidbe", "Lidbe A, Adanu EK, Penmetsa P, Jones S. Changes in the travel patterns of older Americans with medical conditions: a "
              "comparison of 2001 and 2017 NHTS data. Transp Res Interdiscip Perspect 2021;11:100463. "
              "https://doi.org/10.1016/j.trip.2021.100463."),
    ("alberini", "Alberini A, Teja Burra L, Cirillo C, Shen C. Counting vehicle miles traveled: what can we learn from the NHTS? "
                 "Transp Res Part D Transp Environ 2021;98:102984. https://doi.org/10.1016/j.trd.2021.102984."),
    ("wu", "Wu X, MacKenzie D. Assessing the VMT effect of ridesourcing services in the US. Transp Res Part D Transp Environ "
           "2021;94:102816. https://doi.org/10.1016/j.trd.2021.102816."),
    ("zhou", "Zhou Y, Wang X(C). Explore the relationship between online shopping and shopping trips: an analysis with the 2009 NHTS "
             "data. Transp Res Part A Policy Pract 2014;70:1-9. https://doi.org/10.1016/j.tra.2014.09.014."),
    ("summarize", "Westat Transportation. summarizeNHTS: R package for summarizing NHTS data [software]. "
                  "https://github.com/Westat-Transportation/summarizeNHTS [accessed 22 October 2026]."),
    ("lumley", "Lumley T. Analysis of complex survey samples. J Stat Softw 2004;9(8). https://doi.org/10.18637/jss.v009.i08."),
    ("samplics", "Diallo M. samplics: a Python package for selecting, weighting and analyzing data from complex sampling designs. "
                 "J Open Source Softw 2021;6:3376. https://doi.org/10.21105/joss.03376."),
    ("wolter", "Wolter KM. Introduction to variance estimation. 2nd ed. New York: Springer; 2007. "
               "https://doi.org/10.1007/978-0-387-35099-8."),
    ("weighting", "Roth SB, DeMatteis J, Dai Y. 2017 NHTS weighting report. Westat, prepared for the Federal Highway Administration; "
                  "2017. https://nhts.ornl.gov/assets/2017%20NHTS%20Weighting%20Report.pdf [accessed 22 October 2026]."),
    ("software", f"Naseralavi SS. pynhts: survey-weight-aware access to US National Household Travel Survey microdata. Version {VERSION} "
                 f"[software]. Zenodo; 2026 Oct 22. https://doi.org/{VERSION_DOI}."),
]

# in-text keys, in the order the keys appear in the text (build_docx.py checks this against the numbers used above)
CITE_NUMBERS = {"mcguckin": 1, "yang": 2, "zhang": 3, "lidbe": 4, "alberini": 5, "wu": 6, "zhou": 7, "summarize": 8,
                "lumley": 9, "samplics": 10, "wolter": 11, "weighting": 12, "software": 13}
