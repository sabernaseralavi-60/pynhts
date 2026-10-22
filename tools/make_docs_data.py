"""Generate docs/data/{FEATURES,VARIABLE_REGISTRY,CROSSWALK_HARMONIZATION}.md from the machine-readable sources.

The registry of features, the concept dictionary, the schemas and the crosswalks are the single
source of truth; these pages are rendered from them, never edited by hand.  Run: python tools/make_docs_data.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("PYNHTS_CACHE_DIR", str(ROOT / "local_data" / "cache"))

import pandas as pd  # noqa: E402

import pynhts  # noqa: E402
from pynhts import concepts, features, harmonize  # noqa: E402

OUT = ROOT / "docs" / "data"
OUT.mkdir(parents=True, exist_ok=True)


def md_table(df: pd.DataFrame) -> str:
    head = "| " + " | ".join(map(str, df.columns)) + " |"
    sep = "| " + " | ".join("---" for _ in df.columns) + " |"
    body = ["| " + " | ".join(str(v).replace("|", "/").replace("\n", " ") for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join([head, sep, *body])


# ---- FEATURES.md
reg = features.registry()
parts = [
    "# Feature registry\n",
    "Generated from `pynhts.features.registry()`; each feature lists its scientific meaning, sources, exact formula, "
    "eligibility, missing-value rule, denominator, weight and the waves in which it exists. "
    "Creators: `create_person_features`, `create_household_features`, `create_trip_features`, `create_vehicle_features`.\n",
    "Conventions: zero is not missing (counts of nothing are 0; unknown member values are counted separately and, with `strict=True`, "
    "make the count NaN); eligibility is explicit; household values are never repeated onto child rows; household features carry the "
    "household weight, never the trip weight; survey-day quantities are observed, not annual. Validation of the member counts: in every "
    "household whose person file is a complete roster they equal the survey's own `WRKCOUNT` and `DRVRCNT` in all four waves "
    "(`tests/data/test_features_real.py`).\n",
]
for level in ("person", "household", "trip", "vehicle"):
    sub = reg[reg["level"] == level]
    parts.append(f"\n## {level.capitalize()} level ({len(sub)} features)\n")
    for group, g in sub.groupby("group", sort=False):
        parts.append(f"\n### {group}\n")
        cols = g[["name", "description", "sources", "formula", "missing", "denominator", "waves"]].rename(
            columns={"description": "meaning", "sources": "source variables"})
        parts.append(md_table(cols))
    parts.append(f"\nWeight to use: {sub['weighting'].iloc[0]}.\n")
(OUT / "FEATURES.md").write_text("\n".join(parts), encoding="utf-8")

# ---- VARIABLE_REGISTRY.md
rows = []
for w in (2001, 2009, 2017, 2022):
    d = pynhts.dictionary(w)
    rows.append({"wave": w, "variables": len(d), "tables": ", ".join(pynhts.load(w).tables),
                 "with a code list or range": int((d["n_codes"] > 0).sum())})
ct = concepts.table()
comp = ct["comparability"].value_counts().to_dict()
vr = [
    "# Variable registry and data model\n",
    "pynhts keeps three machine-readable layers, none of which replaces the original variable names or values:\n",
    "1. **Schema** (`src/pynhts/_schema/<wave>/*.yaml`): every CSV column per wave, parsed from the official codebook (XLSX or PDF): owner table, type, length, missing codes, skip code, range, every code with label and unweighted/weighted frequency. "
    "`pynhts.dictionary(wave)` and `pynhts.describe(variable, wave)` read it; the codebook frequencies reproduce from the data (codebook quirks found on the way are listed in docs/data_notes.md).",
    "2. **Registry** (`src/pynhts/_registry/<wave>.yaml`): files, SHA-256 hashes, weights, replicate-weight design (variance method as data).",
    "3. **Concept dictionary** (`src/pynhts/concepts.yaml`): what a variable means in each wave, universe, unit, comparability, pitfalls and the evidence for each statement.\n",
    "Cross-wave comparability categories used in the concept dictionary: `C` comparable as is, `H` comparable after the named harmonization, "
    "`N` do not compare (definition or universe changed). Not-yet-assessed variables have no concept entry; absence is not a claim of comparability.\n",
    "## Size per wave\n", md_table(pd.DataFrame(rows)),
    f"\n## Concepts ({len(ct)}): comparability {comp}\n",
    md_table(ct[["concept", "table", "2001", "2009", "2017", "2022", "comparability", "harmonize"]].fillna("")),
    "\n## Derived variables\n",
    "Official derived variables (for example `TRPMILES`, `R_AGE_IMP`, `WTTRDFIN`) are part of the schema like any other column and keep their original "
    "names. Features created by pynhts are named with a level prefix (`p_`, `hh_`, `t_`, `v_`), are listed in the feature registry with their formula "
    "and source variables, and carry `attrs[\"pynhts_features\"]` lineage when created (source variables, formula, missing rule). "
    "pynhts never modifies the downloaded data.\n",
    "## Lineage of a result\n",
    "Every table and every estimate carries `attrs[\"pynhts\"]` (wave, table, weight column, variance design, unit); aggregation results add "
    "`attrs[\"pynhts_aggregate\"]` (source, keys, row counts, missing-value policy, missing inputs per output); feature frames add `attrs[\"pynhts_features\"]`.\n",
]
(OUT / "VARIABLE_REGISTRY.md").write_text("\n".join(vr), encoding="utf-8")

# ---- CROSSWALK_HARMONIZATION.md
cwr = ["# Cross-wave harmonization\n",
       "Generated from `pynhts.harmonize` and `pynhts.concepts`. See also `docs/waves.md` for the narrative and pitfalls.\n",
       "## Available crosswalks\n"]
tab = []
for c in harmonize.concepts():
    x = harmonize.crosswalk(c)
    st = x["status"].value_counts().to_dict()
    tab.append({"concept": c, "waves": ", ".join(map(str, sorted(x["wave"].unique()))), "rows": len(x), "status counts": st})
cwr.append(md_table(pd.DataFrame(tab)))
cwr += [
    "\nStatus values: `exact` same meaning; `nested` finer categories collapse into the shared one; `merge` several codes map to one; "
    "`approximate` the groups differ in a documented way; `only_here` no counterpart in the other wave (the category is kept, flagged).\n",
    "## Two workflows, deliberately separate (`pynhts.trends`)\n",
    "1. **Harmonized descriptive trends**: `trends.trip_shares(...)` and `trends.wave_means(...)` estimate each wave with its own weights and variance design "
    "(jackknife replicates 2001-2017, Taylor series 2022) and put the estimates side by side. Nothing is pooled. A variable whose concept is `N` "
    "(trip distance, trip counts, trip weights) raises a `PynhtsWarning`.",
    "2. **Pooled modelling**: `trends.pool(...)` stacks waves with a `wave` column, refuses `N` concepts unless told otherwise, requires an explicit crosswalk "
    "for coded columns (raw codes are never stacked silently) and rescales weights within wave (`w_norm`). It always warns: the waves are independent "
    "cross-sections, not a panel; the sampling frame (random-digit dialling until 2009, address-based since 2017), collection mode, trip definition and "
    "distance measurement changed; model the wave effect.\n",
    "## Documented breaks that matter before comparing\n",
    "* **Trip distance** (`N`): 2001 and 2009 self-reported; 2017 routed shortest path; 2022 route computed for the trip date. In the 2009-2017 pair the mean "
    "distance of a trip rises from 9.7 to 10.7 miles with no change in behaviour implied. `TRPMILAD` (2017) scales back for 2001/2009 comparisons.",
    "* **Trip counting** (`N`): telephone interview with prompts (2001, 2009), web diary (2017: about 66 % web; 2022: about 99 % web); 2022 trip weights contain a methods adjustment (+9.5 % overall).",
    "* **Universe**: 2001 includes children aged 0-4; the other waves start at 5 (`min_age=5`).",
    "* **Weights**: the trip weight is annual (365 x the person weight) in 2001-2017; wave weights have different population bases and must not be pooled as they are.",
    "* **Codes**: the same code means different things in different waves (`TRPTRANS` 08, `URBAN` 1/2 swapped in 2001, `WHYTRP1S` two numbering systems): always map through a crosswalk.",
]
(OUT / "CROSSWAVE_HARMONIZATION.md").write_text("\n".join(cwr), encoding="utf-8")
print("written:", [p.name for p in OUT.glob("*.md")])
