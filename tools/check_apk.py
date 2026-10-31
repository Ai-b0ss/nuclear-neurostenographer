"""Inspect a built APK without installing an emulator. Does not prove inference."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import re
import subprocess
import zipfile


def runtime_identity(apk, runtime):
    """Compare packaged native bytes to the selected AAR, not its filename/claim."""
    with zipfile.ZipFile(apk) as installed, zipfile.ZipFile(runtime) as source:
        names = [f"lib/{abi}/{lib}.so" for abi in ["arm64-v8a", "x86_64"]
                 for lib in ["libonnxruntime", "libsherpa-onnx-jni"]]
        hashes = {}
        for name in names:
            data = installed.read(name)
            if data != source.read(name.replace("lib/", "jni/", 1)):
                raise AssertionError(f"Packaged JNI differs: {name}")
            hashes[name] = hashlib.sha256(data).hexdigest()
        digest = hashlib.sha256(runtime.read_bytes()).hexdigest()
        dex = b"".join(installed.read(n) for n in installed.namelist() if n.endswith(".dex"))
        if digest.encode("ascii") not in dex:
            raise AssertionError("BuildConfig does not identify actual runtime AAR")
    return {"aar_sha256": digest, "packaged_native_sha256": hashes,
            "build_config_digest": "MATCH", "native_bytes": "MATCH"}


def inspect(apk, aapt, runtime=None):
    permissions = subprocess.check_output([str(aapt), "dump", "permissions", str(apk)]).decode("utf-8")
    if "android.permission.INTERNET" in permissions:
        raise AssertionError(permissions)
    manifest = subprocess.check_output([str(aapt), "dump", "xmltree", str(apk), "AndroidManifest.xml"]).decode("utf-8")
    services = [block.split("E:", 1)[0] for block in manifest.split("E: service")[1:]]
    worker = next(block for block in services if '"ru.neurostenographer.app.DiarizationService"' in block)
    if not ('":diarization"' in worker and
            re.search(r'android:exported[^\n]*=\(type 0x12\)0x0\b', worker)):
        raise AssertionError(worker)
    with zipfile.ZipFile(apk) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise AssertionError("Duplicate ZIP entries")
        if any(n.lower().endswith((".onnx", ".wav", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".amr"))
               for n in names):
            raise AssertionError("Model/audio accidentally bundled")
        native = {n for n in names if n.startswith("lib/") and n.endswith(".so")}
        expected = {f"lib/{abi}/{lib}.so" for abi in ["arm64-v8a", "x86_64"]
                    for lib in ["libonnxruntime", "libsherpa-onnx-jni", "libandroidx.graphics.path"]}
        if native != expected:
            raise AssertionError(f"Unexpected native libraries: {sorted(native ^ expected)}")
        alignment = {}
        machines = {}
        for name in sorted(native):
            b = z.read(name)
            if b[:6] != b"\x7fELF\x02\x01":
                raise AssertionError(f"Invalid ELF header: {name}")
            machine = struct.unpack_from("<H", b, 18)[0]
            expected_machine = {"arm64-v8a": 183, "x86_64": 62}[name.split("/")[1]]
            if machine != expected_machine:
                raise ValueError(f"ELF machine does not match ABI: {name} ({machine})")
            machines[name] = machine
            offset = struct.unpack_from("<Q", b, 32)[0]
            size, count = struct.unpack_from("<HH", b, 54)
            loads = [struct.unpack_from("<IIQQQQQQ", b, offset + i * size)[-1]
                     for i in range(count) if struct.unpack_from("<I", b, offset + i * size)[0] == 1]
            if not loads or any(n < 16384 for n in loads):
                raise AssertionError(f"Invalid ELF load alignment: {name}: {loads}")
            alignment[name] = loads
        if "assets/licenses/sherpa-onnx-LICENSE.txt" not in names:
            raise AssertionError("Missing sherpa-onnx license notice")
        if "assets/licenses/onnxruntime-LICENSE.txt" not in names:
            raise AssertionError("Missing onnxruntime license notice")
    identity = runtime_identity(apk, runtime) if runtime else None
    return {"apk_sha256": hashlib.sha256(apk.read_bytes()).hexdigest(), "apk_bytes": apk.stat().st_size,
            "runtime_identity": identity,
            "permissions": permissions.splitlines(), "native_load_alignment": alignment,
            "native_elf_machine": machines,
            "diarization_worker": {"process": ":diarization", "exported": False, "runtime_test": "NOT_RUN"},
            "android_inference": "NOT_RUN_BY_THIS_CHECK", "distribution_cleared": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("apk", type=Path)
    p.add_argument("--aapt", required=True, type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--runtime-aar", type=Path)
    args = p.parse_args()
    result = json.dumps(inspect(args.apk, args.aapt, args.runtime_aar), indent=2)
    if args.output:
        args.output.write_text(result + "\n", encoding="utf-8")
    print(result)
