#!/usr/bin/env bash
set -euo pipefail
args=(--case "${QA_CASE:-all}")
if [[ "${RUN_LONG:-true}" == true ]]; then args+=(--long); fi
python tools/run_speakerbook_emulator_qa.py --aapt "$ANDROID_HOME/build-tools/35.0.0/aapt" "${args[@]}"
