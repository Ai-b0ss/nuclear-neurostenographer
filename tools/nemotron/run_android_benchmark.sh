#!/usr/bin/env bash
# One shell is required: emulator-runner executes each YAML script line separately.
set -euo pipefail
mkdir -p device-evidence
# adb exec-out exits 0 even when run-as fails, so keep a pulled file only if it is valid JSON.
pull_json() {
  local name=$1 target=$2
  adb exec-out run-as ru.neurostenographer.app.c2 cat "files/$name" > "$target.tmp" || true
  if python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$target.tmp" 2>/dev/null; then mv "$target.tmp" "$target"; else rm -f "$target.tmp"; fi
}
collect() {
  status=$?
  trap - EXIT
  adb logcat -d -s NemotronBench:I > device-evidence/bench-log-final.txt || true
  adb logcat -d | grep -E "FATAL|onnxruntime|UnsatisfiedLink|diarization" | tail -n 200 > device-evidence/related-log.txt || true
  [ -f device-evidence/nemotron-evidence.json ] || pull_json nemotron-evidence.json device-evidence/nemotron-evidence.json
  exit "$status"
}
trap collect EXIT
adb shell svc wifi disable
adb shell svc data disable
adb logcat -c
gradle --no-daemon -PnemotronPrototype=true -Pandroid.injected.androidTest.leaveApksInstalledAfterRun=true \
  -Pandroid.testInstrumentationRunnerArguments.class=ru.neurostenographer.app.NemotronBenchmarkTest \
  :app:connectedDebugAndroidTest
pull_json nemotron-evidence.json device-evidence/nemotron-evidence.json
test -f device-evidence/nemotron-evidence.json
adb logcat -d -s NemotronBench:I > device-evidence/bench-log.txt
mkdir -p device-evidence/prototype-junit
cp -r app/build/outputs/androidTest-results/connected/. device-evidence/prototype-junit/
# The ordinary build, without the flag, must keep passing its existing C0 tests.
gradle --no-daemon -Pandroid.testInstrumentationRunnerArguments.class=ru.neurostenographer.app.OfflineDiarizationTest :app:connectedDebugAndroidTest
mkdir -p device-evidence/ordinary-junit
cp -r app/build/outputs/androidTest-results/connected/. device-evidence/ordinary-junit/
