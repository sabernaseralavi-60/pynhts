# Training caveat at the authors' scale on Google Colab (GPU)

No NVIDIA GPU was found on this machine (only Intel UHD Graphics 730; `torch.cuda.is_available()` is False), so the 100-300 epoch, 4x256 configuration is not practical on CPU (the 2x128, 40-epoch run took about 55 s/epoch; the larger one would be several minutes per epoch, i.e. many hours).

## Steps (about 30-90 minutes on a free T4, not measured)
1. Upload to Colab, under `/content/caveat_run/`: `train_schedules.csv`, `train_attributes.csv`, `test_attributes.csv` (from `local_data/caveat_run/` on this machine; produced by `tools/pilot_bench/export_caveat.py 0`).
2. Upload `run_full.yaml` (this folder) to `/content/caveat_run/`.
3. Cells:
```
!git clone https://github.com/big-ucl/caveat.git
!pip install -q "scipy<=1.13" "numpy<2" "pandas<3" pytorch-lightning cml-pam pot click tabulate matplotlib tensorboard optuna optuna-integration
!pip install -q --no-deps -e ./caveat
%cd /content/caveat
!PYTHONUTF8=1 caveat run /content/caveat_run/run_full.yaml
```
4. Download `/content/caveat_run/logs/nhts_split0_full/version_*/synthetic_schedules.csv` to
   `local_data/caveat_run/logs/nhts_split0_full/version_0/` on this machine.
5. Score it: set the run name in `run_sprint.py` (`CAVEAT_RUN`) or copy it over the `nhts_split0_paper` folder name, then `python tools/pilot_bench/run_sprint.py 0 caveat`. Note: caveat renumbers persons 0..n-1 in the order of `test_attributes.csv`; the scorer maps them back.

Caveat versions: pin the commit (we used f4a231e79c24a60f0db9a003ea1ac1fd8eeaa194, 2026-09-18). Colab's Python version may differ from the py3.12 venv used here; if `cml-pam` fails to build, install it with `--no-deps` and add missing packages one by one (pyproj, xlrd, acteval).
