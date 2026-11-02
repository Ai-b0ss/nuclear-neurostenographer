#!/usr/bin/env bash
# One shell is required: emulator-runner executes each YAML script line separately.
set -euo pipefail
mkdir -p device-evidence
collect() {
  status=$?
  trap - EXIT
  adb logcat -d -s NemotronBench:I > device-evidence/bench-log.txt || true
  adb logcat -d | grep -E "FATAL|onnxruntime|UnsatisfiedLink|diarization" | tail -n 200 > device-evidence/related-log.txt || true
  adb exec-out run-as ru.neurostenographer.app cat files/nemotron-evidence.json > device-evidence/nemotron-evidence.json.tmp && mv device-evidence/nemotron-evidence.json.tmp device-evidence/nemotron-evidence.json || true
  exit "$status"
}
trap collect EXIT
adb shell svc wifi disable
adb shell svc data disable
adb logcat -c
gradle --no-daemon -PnemotronPrototype=true -Pandroid.injected.androidTest.leaveApksInstalledAfterRun=true \
  -Pandroid.testInstrumentationRunnerArguments.class=ru.neurostenographer.app.NemotronBenchmarkTest \
  :app:connectedDebugAndroidTest
adb exec-out run-as ru.neurostenographer.app cat files/nemotron-evidence.json > device-evidence/nemotron-evidence.json
adb logcat -d -s NemotronBench:I > device-evidence/bench-log.txt
mkdir -p device-evidence/prototype-junit
cp -r app/build/outputs/androidTest-results/connected/. device-evidence/prototype-junit/
# The ordinary build, without the flag, must keep passing its existing C0 tests.
gradle --no-daemon -Pandroid.testInstrumentationRunnerArguments.class=ru.neurostenographer.app.OfflineDiarizationTest :app:connectedDebugAndroidTest
mkdir -p device-evidence/ordinary-junit
cp -r app/build/outputs/androidTest-results/connected/. device-evidence/ordinary-junit/
