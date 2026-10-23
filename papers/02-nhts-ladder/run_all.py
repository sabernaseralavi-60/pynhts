"""One command for paper 02: studies -> summaries -> numbers -> figures -> tests (-> manuscript).

    python run_all.py               # everything except the long machine-learning runs (about 15 minutes)
    python run_all.py --ml          # also the classifier and boosting runs (about 1.5 hours; tuned run another 1 hour)
    python run_all.py --manuscript  # also builds manuscript/final/*.docx and *.pdf (needs Quarto)

Precondition: the NHTS parquet cache (pynhts.load downloads and verifies the files on first use) and an environment with
scipy, scikit-learn, statsmodels, semopy, matplotlib and pynhts (see requirements.txt).
"""

import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDIES = ["p01_yang2011", "p03_quinn2016", "p18_jiao2020", "p11_alberini2021", "p20_shirgaokar2021", "p14_zhang2018_vehicles",
           "p13_p15_zhang2018", "p02_zhou2014_sem", "p22_wu2021"]
ML = ["p06_p17_jia", "p21_barua2021", "p06_p17_tuned"]
TAIL = ["summarize.py", "studies_table.py", "numbers_json.py", "make_figures.py"]


def run(script, cwd):
    t0 = time.time()
    r = subprocess.run([sys.executable, script], cwd=cwd, capture_output=True, text=True)
    print(f"{script:34s} {'ok' if r.returncode == 0 else 'FAILED'}  {time.time() - t0:7.1f}s", flush=True)
    if r.returncode:
        sys.exit(r.stderr[-3000:])


def main():
    src = HERE / "src"
    for s in STUDIES + (ML if "--ml" in sys.argv else []):
        run(f"{s}.py", src / "studies")
    for s in TAIL:
        run(s, src)
    rc = subprocess.call([sys.executable, "-m", "pytest", "-q"], cwd=HERE)
    if "--manuscript" in sys.argv and rc == 0:
        for lang in ("en", "fa"):
            rc = rc or subprocess.call([sys.executable, "build.py", "--lang", lang], cwd=HERE / "manuscript")
    sys.exit(rc)


if __name__ == "__main__":
    main()
