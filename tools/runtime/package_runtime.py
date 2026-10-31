"""Keep pinned official Kotlin API bytes; replace ALL JNI with built no-TTS JNI.

Avoid rebuilding unrelated upstream Android UI/dependency configuration. This is
a candidate packager, not proof of legal clearance or Android execution.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

OFFICIAL_SHA256 = "e3905b1258b577d8d374db798618602ceaaff5805cbf9b356ab25267cd98144d"
ABIS = {"arm64-v8a": "build-android-arm64-v8a", "x86_64": "build-android-x86-64"}
METADATA = {"R.txt", "AndroidManifest.xml", "classes.jar", "proguard.txt",
            "META-INF/com/android/build/gradle/aar-metadata.properties"}


def package(official, source, output):
    if hashlib.sha256(official.read_bytes()).hexdigest() != OFFICIAL_SHA256:
        raise ValueError("Unrecognized official API AAR")
    entries = {}
    with zipfile.ZipFile(official) as z:
        if {n for n in z.namelist() if not n.startswith("jni/")} != METADATA:
            raise ValueError("Unexpected non-JNI entries")
        for name in METADATA:
            entries[name] = z.read(name)
    for abi, build in ABIS.items():
        directory = source / build
        cache = (directory / "CMakeCache.txt").read_text()
        if "SHERPA_ONNX_ENABLE_TTS:BOOL=OFF" not in cache.splitlines():
            raise ValueError("TTS must be OFF in actual CMake cache")
        if any("espeak" in p.name.lower() for p in (directory / "_deps").glob("*")):
            raise ValueError("espeak dependency found")
        for name in ["libsherpa-onnx-jni.so", "libonnxruntime.so"]:
            data = (directory / "install/lib" / name).read_bytes()
            if not data.startswith(b"\x7fELF") or b"espeak-ng-data" in data:
                raise ValueError("Unexpected native binary")
            entries[f"jni/{abi}/{name}"] = data
    # Sorted names, fixed timestamps and ZIP_STORED make packaging deterministic.
    with zipfile.ZipFile(output, "w") as z:
        for name, data in sorted(entries.items()):
            z.writestr(zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0)), data)
    report = {"kind": "NO_TTS_CANDIDATE_NOT_DEVICE_VERIFIED",
        "api_aar_sha256": OFFICIAL_SHA256,
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "bytes": output.stat().st_size,
        "entries": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(entries.items())},
        "patch": json.loads((source / "runtime-patch.json").read_text())}
    output.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("official", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    package(args.official, args.source, args.output)
