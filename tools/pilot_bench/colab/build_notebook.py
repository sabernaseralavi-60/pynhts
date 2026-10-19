"""Build a self-contained Colab notebook: regenerates the caveat inputs from public NHTS 2017 inside
Colab (pynhts from PyPI), verifies them against local checksums, trains caveat at the paper's scale and
downloads the synthetic schedules. Run: python build_notebook.py > caveat_nhts_colab.ipynb"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PB = HERE.parent
ROOT = PB.parents[1]
run_dir = ROOT / "local_data" / "caveat_run"


def pid_hash(path):
    import pandas as pd
    return hashlib.sha256(",".join(map(str, pd.read_csv(path)["pid"])).encode()).hexdigest()


H_TRAIN = pid_hash(run_dir / "train_attributes.csv")
H_TEST = pid_hash(run_dir / "test_attributes.csv")
H_SCHED = hashlib.sha256((run_dir / "train_schedules.csv").read_bytes()).hexdigest()

EXPORT = '''
import hashlib, sys
import numpy as np, pandas as pd
sys.path.insert(0, "/content/pb")
import pynhts
from diary import build_diaries, person_covariates
from schedule import diary_to_schedule

d = pynhts.load(2017)
persons = d.persons(["R_AGE_IMP", "WORKER", "HHVEHCNT", "TRAVDAY"])
trips = d.trips(["TDTRPNUM", "STRTTIME", "ENDTIME", "WHYTO", "WHYFROM"], keys=True)
diary, rep = build_diaries(persons, trips); print(rep)
cov = person_covariates(persons)
hh = persons["HOUSEID"].to_numpy(); uh = np.unique(hh)
rng = np.random.default_rng(1000)  # split 0, same as the local pipeline
te = np.isin(hh, list(set(rng.choice(uh, size=len(uh) // 2, replace=False)))); tr = ~te
sched = diary_to_schedule(diary)
n = sched.groupby("pid").size(); keep = n.index[n <= 16]
def attrs(mask):
    c = cov[mask]
    return pd.DataFrame({"pid": np.flatnonzero(mask), "age": c["age"].astype(str).to_numpy(),
        "worker": c["worker"].astype(str).to_numpy(), "veh": c["veh"].astype(str).to_numpy(),
        "weekend": c["weekend"].astype(str).to_numpy()})
tr_pids = np.intersect1d(np.flatnonzero(tr), keep)
out = "/content/caveat_run"
import os; os.makedirs(out, exist_ok=True)
sched[sched.pid.isin(tr_pids)].to_csv(out + "/train_schedules.csv", index=False)
attrs(np.isin(np.arange(len(tr)), tr_pids)).to_csv(out + "/train_attributes.csv", index=False)
attrs(te).to_csv(out + "/test_attributes.csv", index=False)
h = lambda p: hashlib.sha256(",".join(map(str, pd.read_csv(p)["pid"])).encode()).hexdigest()
ok = (h(out + "/train_attributes.csv") == "%(H_TRAIN)s", h(out + "/test_attributes.csv") == "%(H_TEST)s",
      hashlib.sha256(open(out + "/train_schedules.csv", "rb").read()).hexdigest() == "%(H_SCHED)s")
print("matches local export (train pids, test pids, train schedules):", ok)
assert all(ok[:2]), "household split differs from the local one: stop and tell Claude"
if not ok[2]:
    print("WARNING: schedule bytes differ from local (formatting?); pids match, continuing")
''' % dict(H_TRAIN=H_TRAIN, H_TEST=H_TEST, H_SCHED=H_SCHED)

CFG = (PB / "colab" / "run_full.yaml").read_text()


def code(src):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": src.splitlines(True)}


def md(src):
    return {"cell_type": "markdown", "metadata": {}, "source": src.splitlines(True)}


cells = [
    md("# Train UCL caveat at the paper's scale on NHTS 2017 (split 0)\n"
       "Runtime > Change runtime type > **T4 GPU**, then **Runtime > Run all**. No upload needed: inputs are regenerated from public NHTS 2017 and checked against checksums.\n"
       "At the end `caveat_outputs.zip` downloads automatically to your Downloads folder."),
    code("import torch, sys\nprint(sys.version)\nprint('cuda:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO GPU: switch the runtime to T4')"),
    code("!pip install -q pynhts==0.1.1 pyarrow\n!mkdir -p /content/pb"),
    code("%%writefile /content/pb/diary.py\n" + (PB / "diary.py").read_text()),
    code("%%writefile /content/pb/schedule.py\n" + (PB / "schedule.py").read_text()),
    code("%%writefile /content/export_inputs.py\n" + EXPORT),
    code("![ -f /content/caveat_run/train_schedules.csv ] && echo 'inputs already exist, skipping' || python /content/export_inputs.py"),
    code("%%writefile /content/caveat_run/run_full.yaml\n" + CFG),
    md("## caveat needs Python 3.12 (numpy<2, scipy<=1.13); Colab now ships 3.13, so use a separate 3.12 environment"),
    code("!pip install -q uv\n"
         "!uv venv /content/venv --python 3.12\n"
         "!rm -rf /content/caveat && git clone -q https://github.com/big-ucl/caveat.git /content/caveat\n"
         "!cd /content/caveat && git checkout -q f4a231e79c24a60f0db9a003ea1ac1fd8eeaa194 && git log -1 --format=%H\n"
         "!uv pip install --python /content/venv/bin/python torch \"scipy<=1.13\" \"numpy<2\" \"pandas<3\" pytorch-lightning pot click tabulate matplotlib tensorboard optuna optuna-integration pyproj xlrd acteval\n"
         "!uv pip install --python /content/venv/bin/python --no-deps cml-pam\n"
         "!uv pip install --python /content/venv/bin/python --no-deps -e /content/caveat\n"
         "!cd /tmp && /content/venv/bin/python -c \"import torch, pam, caveat.cli; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())\""),
    code("# STOP here if the previous cell printed an ImportError: copy its text to Claude.\n"
         "!cd /content/caveat && PYTHONUTF8=1 stdbuf -oL /content/venv/bin/caveat run /content/caveat_run/run_full.yaml 2>&1 | tee /content/train.log | tr '\\r' '\\n' | grep --line-buffered -E 'Epoch [0-9]+: 100%|Generation took|Results saved|rror|Traceback'\n"
         "!tail -n 25 /content/train.log | tr '\\r' '\\n' | tail -n 25"),
    code("import glob, os\n"
         "found = glob.glob('/content/caveat_run/logs/**/synthetic_schedules.csv', recursive=True)\n"
         "print('synthetic_schedules.csv found:', found)\n"
         "if not found:\n"
         "    print(open('/content/train.log').read()[-3000:])\n"
         "    raise SystemExit('training produced no output: send the text above to Claude')\n"
         "!cd /content/caveat_run && find logs \\( -name synthetic_schedules.csv -o -name synthetic_attributes.csv -o -name hparams.yaml -o -name timer.csv \\) | zip -@ /content/caveat_outputs.zip\n"
         "from google.colab import files\nfiles.download('/content/caveat_outputs.zip')"),
]
nb = {"nbformat": 4, "nbformat_minor": 5,
      "metadata": {"accelerator": "GPU", "colab": {"provenance": []}, "kernelspec": {"name": "python3", "display_name": "Python 3"},
                   "language_info": {"name": "python"}},
      "cells": cells}
print(json.dumps(nb, indent=1))
