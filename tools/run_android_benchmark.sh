#!/usr/bin/env bash
# Disposable Android benchmark. No audio/model artifacts are collected.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT=.local/dialogue-benchmark
collect() {
  status=$?
  trap - EXIT
  if ! adb exec-out run-as ru.neurostenographer.app cat files/dialogue-benchmark-hypothesis.json > "$OUTPUT/hypothesis.json"; then
    rm -f "$OUTPUT/hypothesis.json"
  fi
  # Invalid JSON (including adb zero-exit error text) becomes an explicit ERROR,
  # not stale favorable evidence. Preserve an earlier instrumentation failure.
  if ! python3 "$SCRIPT_DIR/evaluate_dialogue_benchmark.py" "$OUTPUT"; then
    if [[ "$status" == 0 ]]; then status=1; fi
  fi
  exit "$status"
}
trap collect EXIT
adb shell svc wifi disable
adb shell svc data disable
adb shell pm clear ru.neurostenographer.app >/dev/null || true
gradle --no-daemon -PrussianBenchmark=true -Pandroid.injected.androidTest.leaveApksInstalledAfterRun=true -Pandroid.testInstrumentationRunnerArguments.class=ru.neurostenographer.app.RussianDialogueBenchmarkTest :app:connectedDebugAndroidTest
