"""Run every paper audit script and write docs/paper_data_audit/results/summary.csv (status counts, runtime, code size).

The re-checks of the 0.8.0 session (``recheck_*.py``: the Study module and the race and medical-condition crosswalks) are run too
and summarised in ``summary_recheck.csv``; they do not change the first audit's files.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parents[1] / "docs" / "paper_data_audit" / "results"


def run(scripts: list[Path], out: str) -> pd.DataFrame:
    rows = []
    for s in scripts:
        t0 = time.time()
        r = subprocess.run([sys.executable, str(s)], capture_output=True, text=True, cwd=HERE)
        dt = time.time() - t0
        stem = s.stem
        csv = RESULTS / f"{stem}.csv"
        counts = {}
        if r.returncode == 0 and csv.exists():
            counts = pd.read_csv(csv)["status"].value_counts().to_dict()
        loc = sum(1 for line in s.read_text(encoding="utf8").splitlines() if line.strip() and not line.strip().startswith("#"))
        rows.append({"script": stem, "ok": r.returncode == 0, "seconds": round(dt, 1), "code_lines": loc, **counts,
                     "error": "" if r.returncode == 0 else r.stderr.strip().splitlines()[-1][:120]})
        print(rows[-1])
    df = pd.DataFrame(rows).fillna(0)
    df.to_csv(RESULTS / out, index=False)
    print(df.to_string(index=False))
    return df


run(sorted(HERE.glob("p[0-9][0-9]_*.py")), "summary.csv")
run(sorted(HERE.glob("recheck_*.py")), "summary_recheck.csv")
