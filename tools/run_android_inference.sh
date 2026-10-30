#!/usr/bin/env bash
# One shell is required: emulator-runner executes each YAML script line separately.
set -euo pipefail
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
  exit "$status"
}
trap collect_evidence EXIT
adb shell svc wifi disable
adb shell svc data disable
adb logcat -c
# Do not let files from a previous test execution masquerade as this run.
adb shell pm clear ru.neurostenographer.app >/dev/null || true
gradle --no-daemon :core:runCoreTests :app:connectedDebugAndroidTest
