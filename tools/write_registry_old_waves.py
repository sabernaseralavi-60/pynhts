"""Write src/pynhts/_registry/2009.yaml and 2001.yaml from files that were downloaded and hashed.

Usage: python tools/write_registry_old_waves.py <parts.json> [replicates.json]

``parts.json`` holds archives, members and documents (each with SHA-256, size and row count)
as measured on the official downloads; ``replicates.json`` the same for the replicate archive.
The variance blocks below come from the official User's Guides (chapter 7) and the 2009
Weighting Report; see docs/data_notes.md for the evidence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

OUT = Path(__file__).resolve().parents[1] / "src" / "pynhts" / "_registry"

HEAD = {
    2009: (
        "# NHTS 2009 (Version 2.1, October 2011) file registry. Hashes verified 2026-10-21 by\n"
        "# downloading the archives from the official ORNL server and hashing every member.\n"
        "# NOTE: nhts.ornl.gov answers HTTP 200 with an HTML page for missing files, so only the\n"
        "# SHA-256 below proves that a download is the real file. The CSV files sit in the\n"
        "# archive folder Ascii/ (zip_path).\n"
    ),
    2001: (
        "# NHTS 2001 (Version 4, national sample with add-ons) file registry. Hashes verified\n"
        "# 2026-10-21 by downloading the archives from the official ORNL server and hashing\n"
        "# every member. The archive is called Ascii.zip but holds comma-separated CSV files.\n"
        "# NOTE: nhts.ornl.gov answers HTTP 200 with an HTML page for missing files.\n"
    ),
}
CITATION = {
    2009: (
        "U.S. Department of Transportation, Federal Highway Administration, 2009 National "
        "Household Travel Survey, Version 2.1 (2011). URL: https://nhts.ornl.gov"
    ),
    2001: (
        "U.S. Department of Transportation, Federal Highway Administration, 2001 National "
        "Household Travel Survey, Version 4 (2004). URL: https://nhts.ornl.gov"
    ),
}
VARIANCE = {
    # User's Guide V2 ch. 7: 100 replicate weights, Jackknife2; Var = 99/100 * sum (REP_i - x)^2
    2009: {
        "method": "jkn", "replicates": 100, "factor": 0.99, "df": 100,
        "description": (
            "jackknife-2 (JK2) with 100 replicate weights as in the 2009 User's Guide "
            "(variance = 99/100 times the sum of squared deviations; t multiplier on 100 "
            "degrees of freedom)"),
        "replicate_files": {
            "hh50wt.csv": [
                {"level": "household", "weight": "HHWGT", "keys": ["HOUSEID"],
                 "out": "repw_household.parquet"},
            ],
            "per50wt.csv": [
                {"level": "person", "weight": "WTPERFIN", "keys": ["HOUSEID", "PERSONID"],
                 "out": "repw_person.parquet"},
                {"level": "trip", "weight": "DAYWGT", "keys": ["HOUSEID", "PERSONID"],
                 "out": "repw_trip.parquet",
                 # persons without trips have no DAYWGT; WTTRDFIN = 365 x WTPERFIN everywhere else
                 "fill_from": {"level": "person", "factor": 365}},
            ],
        },
    },
    # User's Guide V3 ch. 7-E: 99 replicate weights, delete-one jackknife; Var = 98/99 * sum
    2001: {
        "method": "jkn", "replicates": 99, "factor": 98 / 99, "df": 99,
        "description": (
            "delete-one jackknife with 99 replicate weights as in the 2001 User's Guide "
            "(variance = 98/99 times the sum of squared deviations; t multiplier on 99 "
            "degrees of freedom)"),
        "default_weights": {"longdist": "WTPTPFIN"},
        # the long-distance file prints WTPTPFIN with 4 decimals, its replicate file with 6
        # (largest relative difference 7.6e-11)
        "weight_rtol": 1e-9,
        "replicate_files": {
            "hh50wt.csv": [
                {"level": "household", "weight": "WTHHFIN", "prefix": "WTHFIN",
                 "keys": ["HOUSEID"], "out": "repw_household.parquet",
                 "rename": {"ID9": "HOUSEID"}},
            ],
            "pr50wt.csv": [
                {"level": "person", "weight": "WTPERFIN", "prefix": "WTPFIN",
                 "keys": ["HOUSEID", "PERSONID"], "out": "repw_person.parquet",
                 "rename": {"ID9": "HOUSEID"}},
                {"level": "trip", "weight": "WTTRDFIN", "prefix": "WTTDFN",
                 "keys": ["HOUSEID", "PERSONID"], "out": "repw_trip.parquet",
                 "rename": {"ID9": "HOUSEID"}},
            ],
            "ldt50wt.csv": [
                {"level": "longdist", "weight": "WTPTPFIN", "prefix": "FPTPWT",
                 "keys": ["HOUSEID", "PERSONID"], "out": "repw_longdist.parquet", "pad": 2},
            ],
        },
    },
}


def main(wave: int, parts: Path, reps: Path | None) -> None:
    archives, members, docs = json.loads(parts.read_text())[str(wave)]
    if reps is not None:
        r_archives, r_members = json.loads(reps.read_text())[str(wave)]
        archives.update(r_archives)
        members.update(r_members)
    doc = {
        "wave": wave,
        "source_page": "https://nhts.ornl.gov",
        "variance": VARIANCE[wave],
        "citation": CITATION[wave],
        "archives": archives,
        "members": members,
        "documentation": docs,
    }
    text = HEAD[wave] + yaml.safe_dump(doc, sort_keys=False, width=100)
    (OUT / f"{wave}.yaml").write_text(text, encoding="utf-8")
    print(f"wrote {wave}.yaml with {len(members)} members")


if __name__ == "__main__":
    main(int(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]) if len(sys.argv) > 3 else None)
