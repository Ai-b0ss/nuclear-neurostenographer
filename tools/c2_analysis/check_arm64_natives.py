"""Static ARM64 check of the C2 native libraries, without any device: ELF machine, page alignment, links and symbols.

python tools/c2_analysis/check_arm64_natives.py --sherpa-aar AAR --out FILE.json
Answers: does libonnxruntime4j_jni.so from onnxruntime-android 1.17.1 find what it needs in the libonnxruntime.so the APK
actually ships (the one from the sherpa AAR), and which libraries would not load on a 16 KB page device.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

from elftools.elf.dynamic import DynamicSection
from elftools.elf.elffile import ELFFile

ORT_AAR = "https://repo1.maven.org/maven2/com/microsoft/onnxruntime/onnxruntime-android/1.17.1/onnxruntime-android-1.17.1.aar"
ORT_AAR_SHA256 = "35fc867b4d50942da3058f196d74c5669b4b34228794702cf15a05a4bd0b77c4"
SHERPA_NO_TTS_SHA256 = "771fda6a4abf845a6f84f48e05e887fdf159671beb88cbc9aae327806511c1c8"
ABIS = ("arm64-v8a", "x86_64")
MACHINE = {"arm64-v8a": "EM_AARCH64", "x86_64": "EM_X86_64"}


def describe(data):
    elf = ELFFile(io.BytesIO(data))
    loads = [s["p_align"] for s in elf.iter_segments() if s["p_type"] == "PT_LOAD"]
    needed, defined, undefined = [], set(), set()
    for section in elf.iter_sections():
        if isinstance(section, DynamicSection):
            needed = [t.needed for t in section.iter_tags() if t.entry.d_tag == "DT_NEEDED"]
        if section.name == ".dynsym":
            for symbol in section.iter_symbols():
                if not symbol.name:
                    continue
                (undefined if symbol["st_shndx"] == "SHN_UNDEF" else defined).add(symbol.name)
    versions = sorted({s for s in (b"1.17.1", b"1.17.0", b"1.18.0") if s in data})
    return {"machine": elf["e_machine"], "min_load_align": min(loads) if loads else None, "needed": needed,
            "defined": defined, "undefined": undefined, "version_strings": [v.decode() for v in versions]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sherpa-aar", type=Path, required=True, help="The verified no-TTS sherpa-onnx AAR the app ships")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    sherpa_bytes = args.sherpa_aar.read_bytes()
    if hashlib.sha256(sherpa_bytes).hexdigest() != SHERPA_NO_TTS_SHA256:
        raise SystemExit("Not the pinned no-TTS sherpa-onnx AAR")
    ort_bytes = urllib.request.urlopen(ORT_AAR, timeout=120).read()
    if hashlib.sha256(ort_bytes).hexdigest() != ORT_AAR_SHA256:
        raise SystemExit("onnxruntime-android AAR hash mismatch")
    sherpa, ort = zipfile.ZipFile(io.BytesIO(sherpa_bytes)), zipfile.ZipFile(io.BytesIO(ort_bytes))
    report = {"scope": "Static ELF inspection; nothing was installed or run on a device", "abis": {}}
    for abi in ABIS:
        runtime = describe(sherpa.read(f"jni/{abi}/libonnxruntime.so"))
        jni = describe(ort.read(f"jni/{abi}/libonnxruntime4j_jni.so"))
        sherpa_jni = describe(sherpa.read(f"jni/{abi}/libsherpa-onnx-jni.so"))
        missing = sorted(s for s in jni["undefined"] if s.startswith("Ort") and s not in runtime["defined"])
        report["abis"][abi] = {
            "machine_ok": all(x["machine"] == MACHINE[abi] for x in (runtime, jni, sherpa_jni)),
            "packaged_onnxruntime": {"from": "sherpa no-TTS AAR", "load_align": runtime["min_load_align"], "version_strings": runtime["version_strings"]},
            "onnxruntime4j_jni": {"load_align": jni["min_load_align"], "needed": jni["needed"],
                                  "onnxruntime_symbols_needed": sorted(s for s in jni["undefined"] if s.startswith("Ort")),
                                  "missing_in_packaged_onnxruntime": missing},
            "sherpa_onnx_jni_load_align": sherpa_jni["min_load_align"],
            "not_16kb_aligned": [name for name, x in (("libonnxruntime.so", runtime), ("libonnxruntime4j_jni.so", jni), ("libsherpa-onnx-jni.so", sherpa_jni)) if x["min_load_align"] < 16384],
        }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
