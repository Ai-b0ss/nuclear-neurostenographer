#!/usr/bin/env bash
# Disposable Android benchmark. No audio/model artifacts are collected.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT=.local/dialogue-benchmark
BENCHMARK_SUITE="$(printenv BENCHMARK_SUITE || echo development)"
[[ "$BENCHMARK_SUITE" == development || "$BENCHMARK_SUITE" == holdout ]] || exit 2
# Bind device output to this invocation even if install/pm-clear fails and a
# previous app installation survives. A stale valid JSON must not be rescored.
INVOCATION=$(python3 - <<'PY'
import json, uuid
from pathlib import Path
invocation = uuid.uuid4().hex
Path('.local/dialogue-benchmark/invocation.json').write_text(json.dumps({'id': invocation}) + '\n')
print(invocation)
PY
)
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
gradle --no-daemon -PrussianBenchmark=true -Pandroid.injected.androidTest.leaveApksInstalledAfterRun=true -Pandroid.testInstrumentationRunnerArguments.benchmarkInvocation="$INVOCATION" -Pandroid.testInstrumentationRunnerArguments.benchmarkSuite="$BENCHMARK_SUITE" -Pandroid.testInstrumentationRunnerArguments.class=ru.neurostenographer.app.RussianDialogueBenchmarkTest :app:connectedDebugAndroidTest
