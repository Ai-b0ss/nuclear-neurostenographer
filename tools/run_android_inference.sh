#!/usr/bin/env bash
# One shell is required: emulator-runner executes each YAML script line separately.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p device-evidence
collect_evidence() {
  status=$?
  trap - EXIT
  adb logcat -d -s AsrEvidence:I > asr-evidence.txt || true
  adb logcat -d -s DiarizationEvidence:I > diarization-evidence.txt || true
  adb shell dumpsys meminfo ru.neurostenographer.app > device-evidence/final-meminfo.txt || true
  for name in asr-0 asr-1 diarization-0 diarization-1; do
    if adb exec-out run-as ru.neurostenographer.app cat "files/inference-evidence/$name.json" > "device-evidence/$name.json"; then
      :
    else
      # The file is a collector-owned output, never an audio/model/user file.
      rm -f "device-evidence/$name.json"
    fi
  done
  if ! adb exec-out run-as ru.neurostenographer.app cat files/codec-import-evidence.json > device-evidence/codec-import.json; then
    rm -f device-evidence/codec-import.json
  fi
  if ! adb exec-out run-as ru.neurostenographer.app cat files/recording-evidence.json > device-evidence/recording.json; then
    rm -f device-evidence/recording.json
  fi
  if ! adb exec-out run-as ru.neurostenographer.app cat files/worker-lifecycle-evidence.json > device-evidence/worker-lifecycle.json; then
    rm -f device-evidence/worker-lifecycle.json
  fi
  if ! adb exec-out run-as ru.neurostenographer.app cat files/mixture-evidence.json > device-evidence/mixture.json; then
    rm -f device-evidence/mixture.json
  fi
  if ! adb exec-out run-as ru.neurostenographer.app cat files/recording-pipeline-evidence.json > device-evidence/recording-pipeline.json; then
    rm -f device-evidence/recording-pipeline.json
  fi
  if [[ "$status" == 0 ]]; then
    python3 "$SCRIPT_DIR/validate_android_collection.py" device-evidence --require-complete || status=1
  else
    python3 "$SCRIPT_DIR/validate_android_collection.py" device-evidence || true
  fi
  exit "$status"
}
trap collect_evidence EXIT
adb shell svc wifi disable
adb shell svc data disable
adb logcat -c
# Do not let files from a previous test execution masquerade as this run.
adb shell pm clear ru.neurostenographer.app >/dev/null || true
# AGP 8.7.3 BooleanOption: keep this disposable test installation for collection.
# Otherwise connectedDebugAndroidTest uninstalls it before the EXIT trap can read.
gradle --no-daemon -Pandroid.injected.androidTest.leaveApksInstalledAfterRun=true :core:runCoreTests :app:connectedDebugAndroidTest
