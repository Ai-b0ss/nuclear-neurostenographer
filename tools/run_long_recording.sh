#!/usr/bin/env bash
# One shell is required: emulator-runner executes each YAML script line separately.
set -euo pipefail
mkdir -p device-evidence
collect() {
  status=$?
  trap - EXIT
  adb logcat -d -s LongRecordingEvidence:I > device-evidence/long-recording-log.txt || true
  adb exec-out run-as ru.neurostenographer.app cat files/long-recording-evidence.json > device-evidence/long-recording.json || rm -f device-evidence/long-recording.json
  exit "$status"
}
trap collect EXIT
adb shell svc wifi disable
adb shell svc data disable
adb logcat -c
gradle --no-daemon -Pandroid.injected.androidTest.leaveApksInstalledAfterRun=true \
  -Pandroid.testInstrumentationRunnerArguments.class=ru.neurostenographer.app.LongRecordingTest \
  :app:connectedDebugAndroidTest
