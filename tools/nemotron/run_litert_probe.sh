#!/usr/bin/env bash
# One shell is required: emulator-runner executes each YAML script line separately.
set -euo pipefail
mkdir -p device-evidence
collect() {
  status=$?
  trap - EXIT
  adb logcat -d -s NemotronBench:I > device-evidence/litert-log.txt || true
  adb logcat -d | grep -E "FATAL|litert|LiteRt|UnsatisfiedLink" | tail -n 100 > device-evidence/litert-related-log.txt || true
  adb exec-out run-as ru.neurostenographer.app cat files/litert-evidence.json > device-evidence/litert-evidence.json || true
  exit "$status"
}
trap collect EXIT
adb shell svc wifi disable
adb shell svc data disable
adb logcat -c
gradle --no-daemon -PlitertProbe=true -Pandroid.injected.androidTest.leaveApksInstalledAfterRun=true \
  -Pandroid.testInstrumentationRunnerArguments.class=ru.neurostenographer.app.LiteRtProbeTest \
  :app:connectedDebugAndroidTest
