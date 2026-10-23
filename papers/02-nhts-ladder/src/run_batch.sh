#!/bin/bash
# usage: run_batch.sh study1 study2 ...   (studies in src/studies, sequential)
cd "$(dirname "$0")/studies"
export OMP_NUM_THREADS=6 PYTHONUTF8=1
PY="$TEMP/ml310/Scripts/python.exe"
for s in "$@"; do
  t0=$(date +%s)
  $PY $s.py > "$TEMP/$s.log" 2>&1
  echo "== $s exit $? in $(( $(date +%s) - t0 )) s"; tail -n 2 "$TEMP/$s.log" | cut -c1-160
done
