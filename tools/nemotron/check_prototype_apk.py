"""Inspect a prototype APK: no internet, no TTS or espeak code, the sherpa copy of ONNX Runtime, notices present."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import zipfile

FORBIDDEN = (b"espeak-ng-data", b"espeak_ng", b"libespeak")
EXPECTED_LIBS = {"libonnxruntime.so", "libsherpa-onnx-jni.so", "libonnxruntime4j_jni.so", "libandroidx.graphics.path.so"}
NOTICES = ("assets/nemotron-OpenMDW-1.1-LICENSE.txt", "assets/nemotron-onnx-NOTICE.txt", "assets/licenses/onnxruntime-LICENSE.txt", "assets/licenses/sherpa-onnx-LICENSE.txt")


def load_alignment(data):
    offset = struct.unpack_from("<Q", data, 32)[0]
    size, count = struct.unpack_from("<HH", data, 54)
    return min(struct.unpack_from("<Q", data, offset + i * size + 48)[0] for i in range(count) if struct.unpack_from("<I", data, offset + i * size)[0] == 1)


def inspect(apk, sherpa_aar, badging):
    problems = []
    with zipfile.ZipFile(apk) as z, zipfile.ZipFile(sherpa_aar) as source:
        names = z.namelist()
        native = [n for n in names if n.startswith("lib/") and n.endswith(".so")]
        report = {"apk_bytes": Path(apk).stat().st_size, "native_files": sorted(native), "onnxruntime_source": {}}
        for abi in ("arm64-v8a", "x86_64"):
            present = {Path(n).name for n in native if n.startswith(f"lib/{abi}/")}
            if present != EXPECTED_LIBS:
                problems.append(f"{abi}: unexpected libraries {sorted(present ^ EXPECTED_LIBS)}")
            for name in native:
                if name.startswith(f"lib/{abi}/") and any(mark in z.read(name) for mark in FORBIDDEN):
                    problems.append(f"Forbidden TTS marker in {name}")
            if f"lib/{abi}/libonnxruntime.so" in names:
                same = z.read(f"lib/{abi}/libonnxruntime.so") == source.read(f"jni/{abi}/libonnxruntime.so")
                report["onnxruntime_source"][abi] = "sherpa_aar" if same else "other"
                report[f"onnxruntime_sha256_{abi}"] = hashlib.sha256(z.read(f"lib/{abi}/libonnxruntime.so")).hexdigest()
        report["load_alignment"] = {n: load_alignment(z.read(n)) for n in native}
        # A warning, not a failure: it blocks 16 KB page devices, and the app's other libraries are 16 KB aligned.
        report["below_16kb_alignment"] = sorted(n for n, a in report["load_alignment"].items() if a < 0x4000)
        for notice in NOTICES:
            if notice not in names:
                problems.append(f"Missing notice {notice}")
        for bundled in (n for n in names if n.endswith((".wav", ".onnx", ".mp3"))):
            problems.append(f"Bundled audio or model in APK: {bundled}")
    if "android.permission.INTERNET" in badging:
        problems.append("INTERNET permission present")
    report["problems"] = problems
    return report


def main():
    apk, sherpa_aar, aapt, out = sys.argv[1:5]
    badging = subprocess.run([aapt, "dump", "permissions", apk], capture_output=True, text=True, check=True).stdout
    report = inspect(apk, sherpa_aar, badging)
    Path(out).write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1))
    return 1 if report["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
