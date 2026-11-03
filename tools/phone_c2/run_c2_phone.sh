#!/usr/bin/env bash
# C0 versus C2 on ONE physical ARM64 phone, next to the installed contest app, never over it.
# Run from the root of this research branch, only after the phone has been handed over (HANDOVER_CONFIRMED=1).
# Required: ANDROID_SERIAL (the only target) and EXPECTED_MODEL (must match ro.product.model).
# The phone must already be in airplane mode; this script never changes phone settings.
#
# What it touches: it installs ru.neurostenographer.app.c2 and ru.neurostenographer.app.c2.test, runs the C2 tests in
# them, copies their evidence and uninstalls exactly those two packages. The contest app ru.neurostenographer.app,
# its data and its model kit are only read (package dump and file listings, before and after) and must be unchanged.
set -euo pipefail
: "${ANDROID_SERIAL:?Set ANDROID_SERIAL to the phone under test (adb devices)}"
: "${EXPECTED_MODEL:?Set EXPECTED_MODEL to the exact ro.product.model of that phone}"
[ "${HANDOVER_CONFIRMED:-0}" = 1 ] || { echo "Set HANDOVER_CONFIRMED=1 only after the phone's current user has handed it over."; exit 2; }
export ANDROID_SERIAL
OUT=${OUT:-device-evidence/phone-$(date +%Y%m%d-%H%M%S)}
CONTEST=ru.neurostenographer.app
PROTOTYPE=ru.neurostenographer.app.c2
PROTOTYPE_TEST=ru.neurostenographer.app.c2.test
adb_() { adb -s "$ANDROID_SERIAL" "$@"; }
installed() { adb_ shell pm list packages "$1" | tr -d '\r' | grep -qx "package:$1"; }

[ "$(adb_ get-state 2>/dev/null)" = device ] || { echo "Device $ANDROID_SERIAL is not connected"; exit 2; }
model=$(adb_ shell getprop ro.product.model | tr -d '\r')
[ "$model" = "$EXPECTED_MODEL" ] || { echo "Model is '$model', expected '$EXPECTED_MODEL'. Stopping."; exit 2; }
abi=$(adb_ shell getprop ro.product.cpu.abi | tr -d '\r')
[ "$abi" = arm64-v8a ] || { echo "ABI is $abi, not arm64-v8a. Stopping."; exit 2; }
[ "$(adb_ shell settings get global airplane_mode_on | tr -d '\r')" = 1 ] || { echo "Turn on airplane mode on the phone first."; exit 2; }
for leftover in "$PROTOTYPE" "$PROTOTYPE_TEST"; do
  if installed "$leftover"; then echo "$leftover is already installed (an earlier run?). Remove it with: adb -s $ANDROID_SERIAL uninstall $leftover"; exit 2; fi
done
# The build must produce the .c2 package; refuse a checkout where the prototype would replace the contest app.
grep -q 'applicationIdSuffix = ".c2"' app/build.gradle.kts || { echo "app/build.gradle.kts has no .c2 suffix: the prototype would replace $CONTEST. Stopping."; exit 2; }

mkdir -p "$OUT"
# Read-only picture of the contest app: install times, version, file names, sizes and times. No file contents.
snapshot() {
  {
    echo "## package"
    adb_ shell dumpsys package "$CONTEST" | tr -d '\r' | grep -E "versionCode|versionName|firstInstallTime|lastUpdateTime|codePath|dataDir" | sed 's/^ *//' | sort -u
    echo "## external files"
    adb_ shell ls -lR "/sdcard/Android/data/$CONTEST/files" 2>&1 | tr -d '\r'
    echo "## private files"
    adb_ shell run-as "$CONTEST" ls -lR files 2>&1 | tr -d '\r'
  } > "$1"
}
contest_installed=0
if installed "$CONTEST"; then contest_installed=1; snapshot "$OUT/contest-before.txt"; fi

# Only these properties are recorded: no serial number, IMEI, accounts or phone number.
python3 - "$OUT/device.json" <<PY
import json, sys
json.dump({"model": "$model", "abi": "$abi",
           "soc": "$(adb_ shell getprop ro.soc.model | tr -d '\r')",
           "android": "$(adb_ shell getprop ro.build.version.release | tr -d '\r')",
           "sdk": "$(adb_ shell getprop ro.build.version.sdk | tr -d '\r')",
           "page_size": "$(adb_ shell getconf PAGE_SIZE | tr -d '\r')",
           "mem_total": "$(adb_ shell grep MemTotal /proc/meminfo | tr -d '\r')",
           "prototype_package": "$PROTOTYPE", "contest_app_installed": bool($contest_installed)}, open(sys.argv[1], "w"), indent=1)
PY
adb_ shell dumpsys battery | grep -E "level|temperature" > "$OUT/battery-before.txt" || true
adb_ shell dumpsys thermalservice | grep -iE "status|temperature" | head -20 > "$OUT/thermal-before.txt" || true

pull_json() {
  adb_ exec-out run-as "$PROTOTYPE" cat "files/$1" > "$2.tmp" || true
  if python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$2.tmp" 2>/dev/null; then mv "$2.tmp" "$2"; else rm -f "$2.tmp"; fi
}
remove_prototype() {
  for package in "$PROTOTYPE_TEST" "$PROTOTYPE"; do
    case "$package" in "$CONTEST") echo "Refusing to uninstall $CONTEST"; exit 3;; esac
    installed "$package" && adb_ uninstall "$package" > /dev/null || true
  done
}
trap remove_prototype EXIT
adb_ logcat -c
started=$(date +%s)
set +e
gradle --no-daemon -PnemotronPrototype=true -Pandroid.injected.androidTest.leaveApksInstalledAfterRun=true \
  -Pandroid.testInstrumentationRunnerArguments.class=ru.neurostenographer.app.NemotronBenchmarkTest \
  :app:connectedDebugAndroidTest
prototype_status=$?
set -e
installed "$PROTOTYPE" && echo '{"installed_as": "'"$PROTOTYPE"'"}' > "$OUT/prototype-package.json" || true
pull_json nemotron-evidence.json "$OUT/nemotron-evidence.json"
adb_ logcat -d -s NemotronBench:I > "$OUT/bench-log.txt" || true
adb_ logcat -d | grep -E "FATAL|onnxruntime|UnsatisfiedLink|dlopen|diarization|lowmemorykiller" | tail -n 300 > "$OUT/related-log.txt" || true
mkdir -p "$OUT/prototype-junit" && cp -r app/build/outputs/androidTest-results/connected/. "$OUT/prototype-junit/" || true
adb_ shell dumpsys battery | grep -E "level|temperature" > "$OUT/battery-after.txt" || true
adb_ shell dumpsys thermalservice | grep -iE "status|temperature" | head -20 > "$OUT/thermal-after.txt" || true
remove_prototype
trap - EXIT

untouched=null
if [ "$contest_installed" = 1 ]; then
  snapshot "$OUT/contest-after.txt"
  if cmp -s "$OUT/contest-before.txt" "$OUT/contest-after.txt"; then untouched=true; else untouched=false
    echo "WARNING: the contest app's package or files changed during the run. See $OUT/contest-before.txt and contest-after.txt."; fi
fi
leftover=false
installed "$PROTOTYPE" || installed "$PROTOTYPE_TEST" && leftover=true || true
echo "{\"prototype_gradle_exit\": $prototype_status, \"contest_app_untouched\": $untouched, \"prototype_left_installed\": $leftover, \"elapsed_s\": $(( $(date +%s) - started ))}" > "$OUT/exit-codes.json"
cat "$OUT/exit-codes.json"
echo "Evidence in $OUT. Next: python3 tools/c2_same_tracks/score_phone_run.py ... and tools/phone_c2/check_phone_gate.py --evidence $OUT ..."
