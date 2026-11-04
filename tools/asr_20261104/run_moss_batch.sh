#!/bin/bash
# Sequential MOSS (J1) run over every WAV in a dir; one process per file (clean RSS). Failures are recorded, never skipped.
SRC=${1:-/k/nn-bench/data/same}; OUT=${2:-/k/nn-asr-data/results/moss}; DEV=${3:-cpu}
for f in "$SRC"/*.wav; do b=$(basename "$f" .wav)
  [ -f "$OUT/$b.json" ] && continue
  /k/nn-moss-venv/Scripts/python.exe -I "$(dirname "$0")/run_moss.py" "K:/nn-bench/data/same/$b.wav" "K:/nn-asr-data/results/moss/$b.json" $DEV 4096 >> "$OUT/batch.log" 2>&1
done; echo finished > "$OUT/DONE"
