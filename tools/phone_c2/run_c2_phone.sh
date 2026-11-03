#!/usr/bin/env bash
# C2 acceptance on ONE physical ARM64 phone. Run from the root of this research branch, on the tester's own computer.
# Required: ANDROID_SERIAL (the only target) and EXPECTED_MODEL (must match ro.product.model). Nothing runs on any
# other device. The phone must already be in airplane mode; this script never changes phone settings.
set -euo pipefail
: "${ANDROID_SERIAL:?Set ANDROID_SERIAL to the phone under test (adb devices)}"
: "${EXPECTED_MODEL:?Set EXPECTED_MODEL to the exact ro.product.model of that phone}"
export ANDROID_SERIAL
OUT=${OUT:-device-evidence/phone-$(date +%Y%m%d-%H%M%S)}
PACKAGE=ru.neurostenographer.app
adb_() { adb -s "$ANDROID_SERIAL" "$@"; }

[ "$(adb_ get-state 2>/dev/null)" = device ] || { echo "Device $ANDROID_SERIAL is not connected"; exit 2; }
model=$(adb_ shell getprop ro.product.model | tr -d '\r')
[ "$model" = "$EXPECTED_MODEL" ] || { echo "Model is '$model', expected '$EXPECTED_MODEL'. Stopping."; exit 2; }
abi=$(adb_ shell getprop ro.product.cpu.abi | tr -d '\r')
[ "$abi" = arm64-v8a ] || { echo "ABI is $abi, not arm64-v8a. Stopping."; exit 2; }
[ "$(adb_ shell settings get global airplane_mode_on | tr -d '\r')" = 1 ] || { echo "Turn on airplane mode on the phone first."; exit 2; }
# The prototype has the same package as the main app: installing it replaces that app and its data.
if adb_ shell pm list packages "$PACKAGE" | tr -d '\r' | grep -qx "package:$PACKAGE" && [ "${ALLOW_REPLACE:-0}" != 1 ]; then
  echo "$PACKAGE is installed on this phone. Installing the prototype replaces it and its data. Re-run with ALLOW_REPLACE=1 only if the owner agrees."
  exit 2
fi

mkdir -p "$OUT"
# Only these properties are recorded: no serial number, IMEI, accounts or phone number.
python3 - "$OUT/device.json" <<PY
import json, sys
json.dump({"model": "$model", "abi": "$abi",
           "soc": "$(adb_ shell getprop ro.soc.model | tr -d '\r')",
           "android": "$(adb_ shell getprop ro.build.version.release | tr -d '\r')",
           "sdk": "$(adb_ shell getprop ro.build.version.sdk | tr -d '\r')",
           "page_size": "$(adb_ shell getconf PAGE_SIZE | tr -d '\r')",
           "mem_total": "$(adb_ shell grep MemTotal /proc/meminfo | tr -d '\r')"}, open(sys.argv[1], "w"), indent=1)
PY
adb_ shell dumpsys battery | grep -E "level|temperature" > "$OUT/battery-before.txt" || true
adb_ shell dumpsys thermalservice | grep -iE "status|temperature" | head -20 > "$OUT/thermal-before.txt" || true

pull_json() {
  adb_ exec-out run-as "$PACKAGE" cat "files/$1" > "$2.tmp" || true
  if python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$2.tmp" 2>/dev/null; then mv "$2.tmp" "$2"; else rm -f "$2.tmp"; fi
}
adb_ logcat -c
started=$(date +%s)
set +e
gradle --no-daemon -PnemotronPrototype=true -Pandroid.injected.androidTest.leaveApksInstalledAfterRun=true \
  -Pandroid.testInstrumentationRunnerArguments.class=ru.neurostenographer.app.NemotronBenchmarkTest \
  :app:connectedDebugAndroidTest
prototype_status=$?
set -e
pull_json nemotron-evidence.json "$OUT/nemotron-evidence.json"
adb_ logcat -d -s NemotronBench:I > "$OUT/bench-log.txt" || true
adb_ logcat -d | grep -E "FATAL|onnxruntime|UnsatisfiedLink|dlopen|diarization|lowmemorykiller" | tail -n 300 > "$OUT/related-log.txt" || true
mkdir -p "$OUT/prototype-junit" && cp -r app/build/outputs/androidTest-results/connected/. "$OUT/prototype-junit/" || true
adb_ shell dumpsys battery | grep -E "level|temperature" > "$OUT/battery-after.txt" || true
adb_ shell dumpsys thermalservice | grep -iE "status|temperature" | head -20 > "$OUT/thermal-after.txt" || true

# The ordinary build, without the flag, must still pass its C0 tests on the same phone.
set +e
gradle --no-daemon -Pandroid.testInstrumentationRunnerArguments.class=ru.neurostenographer.app.OfflineDiarizationTest :app:connectedDebugAndroidTest
ordinary_status=$?
set -e
mkdir -p "$OUT/ordinary-junit" && cp -r app/build/outputs/androidTest-results/connected/. "$OUT/ordinary-junit/" || true
echo "{\"prototype_gradle_exit\": $prototype_status, \"ordinary_gradle_exit\": $ordinary_status, \"elapsed_s\": $(( $(date +%s) - started ))}" > "$OUT/exit-codes.json"
echo "Evidence in $OUT. Next: python3 tools/phone_c2/check_phone_gate.py --evidence $OUT ..."
