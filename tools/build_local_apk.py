"""Build the debug APK on this PC with the toolchain kept inside the repository's .local folder.

  python tools/build_local_apk.py            # core tests + assembleDebug + APK inspection

Uses .local/build-tools/jdk-17.0.17+10, .local/build-tools/gradle-8.9 and .local/android-sdk
(Gradle caches go to .local/gradle-home, so nothing is installed system-wide). The pinned no-TTS
runtime is provisioned first (checksum verified). Continuous integration builds the same sources;
the local APK has the same size but its own debug-signing key, hence its own SHA-256.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".local/build-tools"
JDK = TOOLS / "jdk-17.0.17+10"
GRADLE = TOOLS / "gradle-8.9/bin" / ("gradle.bat" if os.name == "nt" else "gradle")
SDK = ROOT / ".local/android-sdk"
APK = ROOT / "app/build/outputs/apk/debug/app-debug.apk"


def main():
    missing = [str(p) for p in (JDK, GRADLE, SDK / "platforms/android-35", SDK / "build-tools/35.0.0") if not p.exists()]
    if missing:
        sys.exit("Local toolchain incomplete: " + ", ".join(missing) + "\nUse GitHub Actions instead (docs/OFFLINE_KIT.md).")
    # local.properties is git-ignored; it tells Gradle where the SDK is.
    (ROOT / "local.properties").write_text("sdk.dir=" + SDK.as_posix().replace(":", "\\:") + "\n", encoding="utf-8")
    env = dict(os.environ, JAVA_HOME=str(JDK), ANDROID_HOME=str(SDK), GRADLE_USER_HOME=str(ROOT / ".local/gradle-home"))
    subprocess.run([sys.executable, str(ROOT / "tools/provision_asr.py")], cwd=ROOT, check=True)
    subprocess.run([str(GRADLE), "--no-daemon", ":core:runCoreTests", ":app:assembleDebug"], cwd=ROOT, env=env, check=True)
    aapt = SDK / "build-tools/35.0.0" / ("aapt.exe" if os.name == "nt" else "aapt")
    subprocess.run([sys.executable, str(ROOT / "tools/check_apk.py"), str(APK), "--aapt", str(aapt),
                    "--runtime-aar", str(ROOT / "app/libs/sherpa-onnx-1.12.20.aar"),
                    "--output", str(ROOT / ".local/local-apk-inspection.json")], cwd=ROOT, check=True)
    print(f"APK: {APK}\nNext: python tools/offline_kit.py assemble --apk {APK}")


if __name__ == "__main__":
    main()
