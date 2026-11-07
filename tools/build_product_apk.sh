#!/bin/bash
# Build the signed product APK (A3 + C2 inside, 0.3.0-contest and later; 0.3.2-contest = versionCode 5, 0.3.3-contest = versionCode 6) on the owner's Windows PC (Git Bash).
#
#   bash tools/build_product_apk.sh            # core tests + signed release APK
#
# Needs, all outside Git:
#   app/libs/sherpa-onnx-1.12.20.aar           pinned no-TTS runtime (python tools/provision_asr.py)
#   .local/productAssets/gigaam-v3-e2e-rnnt.zip A3 bundle, SHA-256 3a4057b9...3225 (tools/asr_20261104/make_a3_bundle.py
#                                              from the Smirnov75 files after tools/asr_20261104/strip_unused_opsets.py)
#   .local/productAssets/nemotron.zip          C2 bundle, SHA-256 a9a4f0fd...8bec (python tools/provision_nemotron.py)
#   .local/realtimeAssets/silero_vad.onnx      live-mode VAD (0.3.8+), SHA-256 9e2449e1...1fd6, MIT (assets/silero-LICENSE.txt)
#   $TOOLCHAIN                                 JDK 17, Android SDK 35, Gradle 8.9 with a warm cache (default: the C2 toolchain)
#   $KEYS/nn-release.jks + $KEYS/pw.txt        release key (alias nn); the password is passed via env, never printed
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
TOOLCHAIN=${TOOLCHAIN:-K:/nn-c2-android/.local/toolchain}
KEYS=${KEYS:-K:/nn-release-keys}
for f in app/libs/sherpa-onnx-1.12.20.aar .local/productAssets/gigaam-v3-e2e-rnnt.zip .local/productAssets/nemotron.zip .local/realtimeAssets/silero_vad.onnx; do
  [ -f "$ROOT/$f" ] || { echo "Missing $f (see header)"; exit 2; }
done
export JAVA_HOME=$TOOLCHAIN/jdk/jdk-17.0.21+9 ANDROID_HOME=$TOOLCHAIN/sdk GRADLE_USER_HOME=$TOOLCHAIN/gradle-home ANDROID_USER_HOME=$TOOLCHAIN/android-user
export ORG_GRADLE_PROJECT_releaseStorePassword="$(tr -d '\r\n' < "$KEYS/pw.txt")"
printf 'sdk.dir=%s\n' "$(echo "$ANDROID_HOME" | sed 's/:/\\:/')" > "$ROOT/local.properties"
cd "$ROOT"
"$TOOLCHAIN/gradle/gradle-8.9/bin/gradle" --no-daemon --offline :core:runCoreTests :app:assembleRelease \
  -PnemotronProduct=true -PasrA3=true -PreleaseStore="$KEYS/nn-release.jks" -PreleaseKeyAlias=nn 2>&1 \
  | grep -vE "^> Task .*(UP-TO-DATE|NO-SOURCE)$" | grep -vi password | tail -30
ls -la app/build/outputs/apk/release/*.apk
