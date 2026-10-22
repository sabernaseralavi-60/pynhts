"""Text of the SoftwareX manuscript (Original Software Publication). Numbers come from the repository's result files.

Blocks: ("p", text) paragraph, ("code", text) code listing, ("fig", key, file, caption), ("h", text) run-in subheading,
("eq", latex) display equation. Cross-references are tokens: {fig:key}, {sec:key}; citations are [n], [n,m], [n-m] and are
converted by build_tex.py, which checks that the numbers follow the order of first appearance.
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

# authors and affiliations (source: ~/.claude/research-kit/AUTHORS.yaml; e-mails and addresses given by the user 2026-10-22)
AFFILS = {
    "a": "Department of Civil Engineering, Shahid Bahonar University of Kerman, Kerman 7616914111, Iran",
    "b": "Department of Civil and Environmental Engineering, Tarbiat Modares University, Tehran 1411944961, Iran",
}
AUTHORS = [
    {"name": "Seyed Saber Naseralavi", "aff": "a", "email": "saber_naseralavi@uk.ac.ir", "corresponding": True},
    {"name": "Akram Mazaheri", "aff": "b", "email": "akram.mazaheri.010@gmail.com", "corresponding": False},
]
SUPPORT_EMAIL = "saber_naseralavi@uk.ac.ir"

ABSTRACT = (
    "The US National Household Travel Survey (NHTS) is the main public source of US household travel data, and four waves "
    "(2001, 2009, 2017 and 2022) are freely available. Using them correctly is harder than it looks: weights and variance "
    "designs differ by wave, the same code can mean different things in different waves, skipped questions are stored as "
    "numbers, and trip weights give annual rather than daily totals. These details are rarely stated in papers, so published "
    "results are difficult to reproduce or to compare. pynhts is an open-source Python library that downloads and verifies the "
    "official files, converts them to typed Parquet, joins the four tables without silent errors, and computes estimates with "
    "the variance method of each wave (jackknife replicate weights for 2001, 2009 and 2017; Taylor linearisation for 2022). "
    "It adds validated crosswalks between waves, guards for top-coded and non-answer values, and a study module that turns a "
    "written research statement into an analysis file with a sample-flow table. Validation is part of the package: 142 of 175 "
    "figures printed in official reports reproduce completely, Taylor-series errors agree with R to 1e-9, and 21 published "
    f"studies were rebuilt and {AUD_N:,} printed numbers graded. The rebuilding recovered unstated rules, such as the base of "
    "a percentage and the definition of a weekend, that move published values by several per cent. The package is young and "
    "has no external users yet; its contribution is a tested, documented way to state and check the assumptions of NHTS analyses."
)

KEYWORDS = ["National Household Travel Survey", "travel survey", "replicate weights", "survey statistics", "reproducibility", "Python"]

META = [
    ("C1", f"v{VERSION}"),
    ("C2", REPO),
    ("C3", "BSD 3-Clause License"),
    ("C4", "git"),
    ("C5", "Python 3; NumPy, pandas, PyArrow, pooch, PyYAML; optional: matplotlib, PyTorch"),
    ("C6", "Python 3.10 or newer on Linux, Windows or macOS (continuous integration on Linux and Windows); "
           "about 0.4 GB of Parquet per wave and 1.8 GB of raw CSV for 2017, which can be deleted after conversion"),
    ("C7", REPO + "/tree/main/docs"),
    ("C8", SUPPORT_EMAIL),
]

SECTIONS: dict[str, list[tuple]] = {}

SECTIONS["motivation"] = [
    ("p", "The National Household Travel Survey (NHTS), sponsored by the US Federal Highway Administration (FHWA), is the "
          "main public source of information on how US households travel: who makes trips, by which mode, for which purpose "
          "and over what distance [1]. Public-use files exist for 2001, 2009, 2017 and 2022, each with four linked tables "
          "(households, persons, trips, vehicles), sampling weights and, for three waves, replicate weights. The files are used "
          "for many topics. Recent examples are access to health care [2], the mobility of older adults across waves [3-5], "
          "taxi and ridehailing use [6,7], ridesharing and vehicle ownership [8], alternative fuel vehicles [9], vehicle miles "
          "travelled [10,11], active travel [12] and online shopping [13]."),
    ("p", "Working with the files is less simple than the number of such studies suggests. Several authors have shown how the "
          "survey itself shapes results: respondents who agree to be contacted again differ from those who do not [14], proxy "
          "responses contain more rounded departure and arrival times [15], and a representation measure built from sampling "
          "weights found under-representation of vulnerable traveller groups in 43 US household travel surveys, the 2017 NHTS "
          "among them [16]. Beyond the properties of the survey, correct use requires work that every project repeats and that "
          "is easy to get wrong. A skipped question is stored as the number -1, so the mean of the 2009 vehicle miles driven "
          "(VMT_MILE) is 5.36 instead of 9.72 and its total is 7 % low. The same code means different things in different "
          "waves: transport mode \"01\" is a car in 2009, where it is 44 % of trips, and walking in 2017, where it is 10.5 %. "
          "Trip weights add up to annual, not daily, totals; the 2001 file contains children aged 0-4 and the others do not; "
          "ages and vehicle ages are top-coded; and 2022 uses a different variance design from the earlier waves. Such mistakes "
          "change estimates and, more often, understate their uncertainty. Papers rarely state the rules they applied, which "
          "makes their numbers hard to reproduce."),
    ("p", "This matters beyond one survey. Calls for reproducible transportation research ask for open code and documented "
          "methods [17,18], and name insufficient methodological detail and the lack of code sharing among the barriers [18]; "
          "agent-based travel-demand research is rarely replicable when it rests on proprietary data and tools [19]. In the "
          "wider research-software community, the FAIR principles have been adapted to software [20,21] and principles for "
          "software citation have been proposed [22]. pynhts follows them in practice: every release is archived with a "
          "persistent identifier and a machine-readable citation file."),
    ("p", "pynhts addresses these problems in one Python package. It (i) fetches and verifies the official files and exposes them "
          "as typed tables that cannot be merged wrongly, (ii) computes every estimate with the variance method of its wave, "
          "(iii) maps codes between waves only where the meaning is shown to be the same, (iv) requires the analyst to state "
          "sample rules, missing-value policy and weighting, and (v) ships its own validation against published numbers. "
          "Scientifically, the contribution is not a new estimator but a way to make the assumptions of an NHTS analysis "
          "explicit, testable and reusable. A user installs the package, downloads a wave with one command, loads it lazily, "
          "and asks for weighted statistics, rates, harmonised categories or a complete study ({sec:examples}). Results carry "
          "the wave, weight, variance design and unit, so a table footnote can be written from the result itself."),
    ("p", "Related work. The R package summarizeNHTS [23] downloads and summarises NHTS data, and the R survey package [24] "
          "offers general replicate-weight and Taylor-series analysis that users can apply to NHTS data after setting up the "
          "design themselves. The Python package samplics [25] covers complex-sample estimation in general but does not know "
          "the NHTS files, codes or weights. A search of GitHub and PyPI on 22 October 2026 (queries \"NHTS python\" and "
          "\"national household travel survey\", and the package names nhts, nhts-py and summarizenhts) found analysis scripts "
          "for single projects and no other general Python package for NHTS access. The variance estimators follow the "
          "standard replicate-weight theory [26] and the weighting report of the 2017 survey [27]."),
]

SECTIONS["architecture"] = [
    ("p", "pynhts is organised in layers ({fig:arch}). The input and statistics layers handle the data; the harmonisation and "
          "analysis layers help the analyst to ask correct questions; the validation layer checks the result against "
          "published numbers."),
    ("fig", "arch", "fig1_architecture", "Architecture of pynhts. Blue: data access and statistics; amber: harmonisation and analysis; "
            "green: validation and bridges. Every result frame records how it was computed."),
    ("p", "pynhts.io keeps a registry with the SHA-256 hash of every official archive and member, downloads with pooch, and "
          "writes Parquet deterministically. The data server answers HTTP 200 with an HTML page for files that do not exist, so "
          "content type and size are checked. pynhts.core derives a typed schema from the codebook (all 3,807 coded values of "
          "2017 and all 2,639 of 2022 reproduce the printed frequencies) and loads columns lazily, joining each requested column "
          "from the table that owns it through a validated many-to-one join. The skip code is converted to a missing value in "
          "numeric columns by default, and non-answer codes are masked on request."),
    ("p", "pynhts.stats implements the stratified jackknife of the 2017 weighting design. With 14 variance strata of 7 units, the "
          "variance of an estimate is 6/7 times the sum over the 98 replicates of the squared deviation of the replicate "
          "estimate from the full estimate, and the margin of error (MOE) is the t quantile with 98 degrees of freedom times "
          "the standard error [26,27]:"),
    ("eq", r"\hat V(\hat\theta)=\frac{6}{7}\sum_{r=1}^{98}\bigl(\hat\theta_r-\hat\theta\bigr)^{2},\qquad "
           r"\mathrm{MOE}=t_{0.975,\,98}\,\sqrt{\hat V(\hat\theta)}."),
    ("p", "The 2009 and 2001 files have 100 and 99 replicates with their own factors. The 2022 file has no replicate weights, so "
          "pynhts uses Taylor linearisation with strata and households; its errors equal those of the R survey package to 1e-9. "
          "All trips of a person share one weight, so trip estimates are computed on person-day units and need a 98-column "
          "matrix for 264,234 units rather than 923,572 trips. Subpopulations are handled as domains, never by dropping rows."),
    ("p", "pynhts.concepts and pynhts.harmonize describe 44 concepts across the four waves, each graded as comparable, "
          "comparable with care, or not comparable, and provide 19 crosswalks (trip purpose, mode, race and Hispanic origin, "
          "medical condition, and others). A crosswalk reads the wave from the frame and refuses a mismatch; each category is marked "
          "exact, approximate or nested, with the evidence in the data. The analysis layer contains aggregate (trips to persons or "
          "households with an explicit missing-value policy and true zeros), features (93 documented variables with lineage), "
          "study (below), trends (per-wave estimates; pooling is refused for non-comparable concepts), transform (splits by "
          "household so that train and test sets do not share a household) and tables and viz for reporting. "
          "pynhts.recipes encodes the numbers printed in official reports together with the expected status of each, and a "
          "generated report lists every gap. A small bridge exports tables to NumPy arrays, PyTorch tensors and household graphs."),
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
             "# 223.3 million drivers, MOE 0.83 million\n"
             "s.total(domain=s.rows[\"DRIVER\"] == \"01\")\n"
             "# 10.70 miles per trip, MOE 0.40\n"
             "d.survey(\"trip\", [\"TRPMILES\"]).mean(\"TRPMILES\")\n"
             "# 3.37 daily trips per person, MOE 0.04\n"
             "rates.daily_rate(d, \"trips\", per=\"person\")"),
    ("p", "These values equal the figures printed in the official summary report [1], including the margins of error."),
    ("p", "Example 2 shows why a stated base matters. Lidbe et al. [5] report that 5.49 % of 2001 trips were made by persons "
          "with a medical condition that makes travel difficult. The question was asked only of persons aged 16 or older; younger "
          "persons carry the skip code. Counting them as having no condition gives 4.40 %; using the trips of persons who answered "
          "gives the printed value. The crosswalk returns a missing value for the skip, so the second base is the natural one."),
    ("code", "from pynhts import harmonize\nd = pynhts.load(2001)\n"
             "p = d.persons([\"MEDCOND\"], missing=\"keep\", skip=\"keep\")\n"
             "p[\"med\"] = harmonize.apply_column(\n"
             "    p, \"MEDCOND\", \"medical_condition\")\n"
             "# the skip and the non-answers are now missing, not \"no\"\n"
             "k = [\"HOUSEID\", \"PERSONID\"]\n"
             "t = d.trips([\"TRPMILES\"]).merge(p[k + [\"med\"]], on=k)\n"
             "w = t[\"WTTRDFIN\"]; yes = t[\"med\"].eq(\"yes\")\n"
             "# 4.399: all trips as the base\n"
             "100 * w[yes].sum() / w.sum()\n"
             "# 5.489: trips of persons who answered\n"
             "100 * w[yes].sum() / w[t[\"med\"].notna()].sum()"),
    ("p", "Example 3 states a whole study as data. The sample rules of Zhang and Zhang [8] (15 low-use states excluded, only persons who "
          "answered the ridesharing question, complete model variables, no weights) become a Study, which returns the sample-flow "
          "table and the descriptive table. The result has 218,831 persons against 219,026 printed (0.09 % fewer), after removing "
          "9,142, 27,090 and 9,171 persons by the three rules from the 264,234 in the file, and the mean number of ridesharing "
          "uses in 30 days is 0.309 as printed."),
    ("code", "from pynhts import study as S\n"
             "spec = S.Study.from_yaml(\n"
             "    \"docs/examples/ridesharing_35_states.yaml\")\n"
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
          f"{AUD['GAP']} gaps ({{fig:audit}}). In nine studies the analysis data could be rebuilt convincingly; in the others the printed "
          "numbers depend on sample rules or external variables that the paper does not state or that the public files do not "
          "contain. We treat each gap as a statement about the information available in the paper, not about its authors' work."),
    ("fig", "audit", "fig2_audit_overview", "Outcome of the audit of 21 published NHTS studies (P01-P23; listed in the repository, first-audit "
            "scripts). Bars show the share of each study's printed numbers that pynhts reproduces exactly, closely (2 %), "
            "acceptably (5 %) or not."),
    ("p", "The exercise produced 32 recovered conventions, written down with their evidence, and several of them change published "
          f"numbers. A re-check of one study [5] with the crosswalks and the study module illustrates this: {LID_EXACT} of {LID_N} "
          "cells of its Tables 3 and 4 are reproduced exactly ({fig:lidbe}). The percentages in its Table 3 use the trips of persons "
          "with a valid answer as the base (Example 2); its weekend is Saturday and Sunday of the travel-day variable, whereas "
          "the NHTS weekend flag also contains part of Friday and gives values 5 to 8 % higher; trip duration is the calculated "
          "minutes variable; the six items on how the condition changes travel are reproduced exactly (72 of 72 cells) through the "
          "condition-effect crosswalk; and its race groups follow a rule in which Hispanic origin overrides only the White, Black and "
          "Asian groups, which is not what a combined race-and-ethnicity variable does. In another study [12] the sample of "
          "130,222 persons is reproduced exactly as a Study, and its race variable is the household respondent's single race code; "
          "mapping it through the combined variable would give a different sample (133,538 persons). These findings became "
          "package features (crosswalks, caps, warnings) or documentation."),
    ("fig", "lidbe", "fig3_agreement_lidbe", "Values printed in Tables 3 and 4 of Lidbe et al. [5] against the values computed with pynhts "
            "(279 cells with a positive value; one printed zero is not shown). The diagonal is exact agreement."),
    ("h", "New research questions and changed practice"),
    ("p", "Design-correct uncertainty for every wave, guarded comparisons across waves, and sample-flow tables make it cheaper to ask "
          "questions that depend on trends and on subpopulations, and to report them so that others can repeat them. The "
          "study module is meant to change the daily practice of analysts by making the sample rules and the missing-value policy part of "
          "the code. We have not measured any change in practice yet."),
    ("h", "Extent of use"),
    ("p", "The first version was released on PyPI in October 2026 and the package has had 13 releases in total; version "
          f"{VERSION} is archived on Zenodo [28]. The package has no known external users, no publication has used it, and it has no "
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

AI = ("During the preparation of this work the authors used Claude (Anthropic) as an assistant for software design, writing and "
      "running code and tests, checking the code against the official documents and data, literature screening, and drafting "
      "and editing the text. After using this tool, the authors reviewed, verified and edited the material (code, results, "
      "references and text) and take full responsibility for the content of the publication. Numbers in the text are taken by "
      "code from the result files of the repository, and the references were checked against a bibliographic database.")

CREDIT = ("Seyed Saber Naseralavi: Conceptualization, Data curation, Formal analysis, Investigation, Methodology, Project "
          "administration, Resources, Software, Validation, Visualization, Writing - original draft, Writing - review and editing. "
          "Akram Mazaheri: [[AUTHOR-TODO: CRediT roles of A. Mazaheri; not stated by the authors]]")

FUNDING = "This research did not receive any specific grant from funding agencies in the public, commercial, or not-for-profit sectors."
COMPETING = ("The authors declare that they have no known competing financial interests or personal relationships that could "
             "have appeared to influence the work reported in this paper.")
DATA = (f"The software is available at {REPO} (archived at Zenodo, DOI {VERSION_DOI}). The NHTS public-use data are "
        "distributed by Oak Ridge National Laboratory (https://nhts.ornl.gov); pynhts downloads them from there and does not redistribute them.")
EXEC_VERSION = (f"Not applicable: pynhts is a Python library without a separate executable. Install version {VERSION} with "
                f"pip install pynhts=={VERSION}.")

# (key, reference in the journal's style, LaTeX). The order is the order of first citation; numbers are 1..28.
REFS = [
    ("mcguckin", "McGuckin N, Fucci A. Summary of travel trends: 2017 National Household Travel Survey. Report FHWA-PL-18-019. "
                 "Washington (DC): US Department of Transportation, Federal Highway Administration; 2018. "
                 r"\url{https://nhts.ornl.gov/assets/2017_nhts_summary_travel_trends.pdf} [accessed 22 October 2026]."),
    ("labban", "Labban M, Chen CR, Frego N, Nguyen DD, Lipsitz SR, Reich AJ, et al. Disparities in travel-related barriers to accessing "
               r"health care from the 2017 National Household Travel Survey. JAMA Netw Open 2023;6:e2325291. \url{https://doi.org/10.1001/jamanetworkopen.2023.25291}."),
    ("buehler", "Buehler R, Pucher J, Wittwer R, Gerike R. Travel behavior of older adults in the USA, 2001-2017. Travel Behav Soc "
                r"2024;36:100783. \url{https://doi.org/10.1016/j.tbs.2024.100783}."),
    ("akinlotan", "Akinlotan M, Khodakarami N, Primm K, Bolin J, Ferdinand AO. Travel for medical or dental care by race/ethnicity and "
                  "rurality in the U.S.: findings from the 2001, 2009 and 2017 National Household Travel Surveys. Prev Med Rep "
                  r"2023;35:102297. \url{https://doi.org/10.1016/j.pmedr.2023.102297}."),
    ("lidbe", "Lidbe A, Adanu EK, Penmetsa P, Jones S. Changes in the travel patterns of older Americans with medical conditions: a "
              r"comparison of 2001 and 2017 NHTS data. Transp Res Interdiscip Perspect 2021;11:100463. "
              r"\url{https://doi.org/10.1016/j.trip.2021.100463}."),
    ("conway", "Conway MW, Salon D, King DA. Trends in taxi use and the advent of ridehailing, 1995-2017: evidence from the US National "
               r"Household Travel Survey. Urban Sci 2018;2:79. \url{https://doi.org/10.3390/urbansci2030079}."),
    ("rafiq", "Rafiq R, McNally MG. An exploratory analysis of alternative travel behaviors of ride-hailing users. Transportation "
              r"2023;50:571-605. \url{https://doi.org/10.1007/s11116-021-10254-9}."),
    ("zhang", "Zhang Y, Zhang Y. Examining the relationship between household vehicle ownership and ridesharing behaviors in the United "
              r"States. Sustainability 2018;10:2720. \url{https://doi.org/10.3390/su10082720}."),
    ("li", "Li X, Liu C, Jia J. Ownership and usage analysis of alternative fuel vehicles in the United States with the 2017 National "
           r"Household Travel Survey data. Sustainability 2019;11:2262. \url{https://doi.org/10.3390/su11082262}."),
    ("alberini", "Alberini A, Teja Burra L, Cirillo C, Shen C. Counting vehicle miles traveled: what can we learn from the NHTS? "
                 r"Transp Res Part D Transp Environ 2021;98:102984. \url{https://doi.org/10.1016/j.trd.2021.102984}."),
    ("wu", "Wu X, MacKenzie D. Assessing the VMT effect of ridesourcing services in the US. Transp Res Part D Transp Environ "
           r"2021;94:102816. \url{https://doi.org/10.1016/j.trd.2021.102816}."),
    ("yang", "Yang Y, Diez Roux AV, Bingham CR. Variability and seasonality of active transportation in USA: evidence from the 2001 NHTS. "
             r"Int J Behav Nutr Phys Act 2011;8:96. \url{https://doi.org/10.1186/1479-5868-8-96}."),
    ("zhou", "Zhou Y, Wang X(C). Explore the relationship between online shopping and shopping trips: an analysis with the 2009 NHTS "
             r"data. Transp Res Part A Policy Pract 2014;70:1-9. \url{https://doi.org/10.1016/j.tra.2014.09.014}."),
    ("wang", "Wang X, Shaw FA, Mokhtarian PL, Watkins KE. Response willingness in consecutive travel surveys: an investigation based on "
             "the National Household Travel Survey using a sample selection model. Transportation 2023;50:2339-73. "
             r"\url{https://doi.org/10.1007/s11116-022-10312-w}."),
    ("yoshikawa", "Yoshikawa S, Maruyama T. Proxy responses contain more rounded trip departure/arrival times: evidence from the 2017 US "
                  r"National Household Travel Survey. J JSCE 2023;11. \url{https://doi.org/10.2208/journalofjsce.23-00137}."),
    ("esekhaigbe", "Esekhaigbe EO, Bills TS, Broaddus A. Group representation of vulnerable travelers in household travel surveys: an "
                   r"assessment of 43 U.S. surveys. Transportation 2026. \url{https://doi.org/10.1007/s11116-026-10795-x}."),
    ("zheng", "Zheng Z. Reasons, challenges, and some tools for doing reproducible transportation research. Commun Transp Res "
              r"2021;1:100004. \url{https://doi.org/10.1016/j.commtr.2021.100004}."),
    ("wood", "Wood J, van Schalkwyk I. Reproducibility in transportation research: importance, best practices, and dealing with protected "
             r"and sensitive data. J Transp Technol 2025;15:179-202. \url{https://doi.org/10.4236/jtts.2025.151010}."),
    ("horl", r"H\"orl S, Bala\'c M. Synthetic population and travel demand for Paris and \^Ile-de-France based on open and publicly "
             r"available data. Transp Res Part C Emerg Technol 2021;130:103291. \url{https://doi.org/10.1016/j.trc.2021.103291}."),
    ("lamprecht", "Lamprecht AL, Garcia L, Kuzak M, Martinez C, Arcila R, Martin Del Pico E, et al. Towards FAIR principles for research "
                  r"software. Data Sci 2020;3:37-59. \url{https://doi.org/10.3233/ds-190026}."),
    ("barker", "Barker M, Chue Hong NP, Katz DS, Lamprecht AL, Martinez-Ortiz C, Psomopoulos F, et al. Introducing the FAIR principles "
               r"for research software. Sci Data 2022;9:622. \url{https://doi.org/10.1038/s41597-022-01710-x}."),
    ("smith", "Smith AM, Katz DS, Niemeyer KE; FORCE11 Software Citation Working Group. Software citation principles. PeerJ Comput Sci "
              r"2016;2:e86. \url{https://doi.org/10.7717/peerj-cs.86}."),
    ("summarize", "Westat Transportation. summarizeNHTS: R package for summarizing NHTS data [software]. "
                  r"\url{https://github.com/Westat-Transportation/summarizeNHTS} [accessed 22 October 2026]."),
    ("lumley", r"Lumley T. Analysis of complex survey samples. J Stat Softw 2004;9(8). \url{https://doi.org/10.18637/jss.v009.i08}."),
    ("samplics", "Diallo M. samplics: a Python package for selecting, weighting and analyzing data from complex sampling designs. "
                 r"J Open Source Softw 2021;6:3376. \url{https://doi.org/10.21105/joss.03376}."),
    ("wolter", "Wolter KM. Introduction to variance estimation. 2nd ed. New York: Springer; 2007. "
               r"\url{https://doi.org/10.1007/978-0-387-35099-8}."),
    ("weighting", "Roth SB, DeMatteis J, Dai Y. 2017 NHTS weighting report. Westat, prepared for the Federal Highway Administration; "
                  r"2017. \url{https://nhts.ornl.gov/assets/2017\%20NHTS\%20Weighting\%20Report.pdf} [accessed 22 October 2026]."),
    ("software", "Naseralavi SS. pynhts: survey-weight-aware access to US National Household Travel Survey microdata. "
                 f"Version {VERSION} [software]. Zenodo; 2026 Oct 22. "
                 r"\url{https://doi.org/" + VERSION_DOI + "}."),
]
CITE_KEYS = [k for k, _ in REFS]
