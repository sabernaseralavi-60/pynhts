#!/bin/bash
# splits 1-4: z-scores, C2ST null, C2ST + MIA for resample_fine / cart, then EMD calibration (acteval venv)
cd /d/ReproducibleResearch_R_Projects/NHTS/02_tools
for sp in 1 2 3 4; do
  python tools/pilot_bench/run_sprint.py $sp null resample_fine cart
  python tools/pilot_bench/export_for_acteval.py $sp
  mkdir -p "$TEMP/ext/run" && (cd "$TEMP/ext/run" && PYTHONUTF8=1 ../venv_caveat/Scripts/python /d/ReproducibleResearch_R_Projects/NHTS/02_tools/tools/pilot_bench/calibrate_emd.py $sp 3)
done
