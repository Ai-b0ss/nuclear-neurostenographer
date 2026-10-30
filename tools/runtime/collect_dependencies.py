"""Capture actual no-TTS build dependency/license inputs; no legal-clearance claim.

Only bounded license/notice text is copied. Source, models, audio and native
binaries are never copied into this inventory artifact.
"""
import argparse
import hashlib
import json
from pathlib import Path


def inventory(source, output):
    source = source.resolve()
    records, notices = [], []
    for abi, build in {"arm64-v8a": "build-android-arm64-v8a", "x86_64": "build-android-x86-64"}.items():
        directory = source / build
        cache = (directory / "CMakeCache.txt").read_text(encoding="utf-8")
        if "SHERPA_ONNX_ENABLE_TTS:BOOL=OFF" not in cache.splitlines():
            raise ValueError("Expected actual no-TTS build cache")
        for dependency in sorted((directory / "_deps").glob("*-src")):
            if not dependency.resolve().is_relative_to(source):
                raise ValueError("Dependency escapes owned source checkout")
            if any(word in dependency.name.lower() for word in ("espeak", "piper", "phonemize")):
                raise ValueError("Unexpected TTS dependency")
            licenses = {}
            # ASIO's pinned archive has its project/notices one level below the
            # FetchContent root. Keep this mapping explicit, not recursive.
            roots = [dependency]
            if dependency.name == "asio-src" and (dependency / "asio").is_dir():
                roots.append(dependency / "asio")
            for file in sorted(file for root in roots for file in root.iterdir()):
                if not file.is_file() or not file.name.upper().startswith(("LICENSE", "COPYING", "NOTICE")):
                    continue
                if not file.resolve().is_relative_to(dependency.resolve()) or file.stat().st_size > 256 * 1024:
                    raise ValueError("External/oversized license input")
                data = file.read_bytes()
                text = data.decode("utf-8")
                if "\x00" in text:
                    raise ValueError("Binary license input")
                name = file.relative_to(dependency).as_posix()
                licenses[name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
                notices.append(f"===== {abi}/{dependency.name}/{name} =====\n{text}\n")
            cmake = dependency / "CMakeLists.txt"
            records.append({"abi": abi, "dependency": dependency.name, "licenses": licenses,
                "top_cmake_sha256": hashlib.sha256(cmake.read_bytes()).hexdigest() if cmake.is_file() else None,
                "license_collection_status": "KNOWN_NOTICE_FILES_CAPTURED" if licenses else "NO_KNOWN_NOTICE_FOUND_REVIEW_REQUIRED"})
    if not records:
        raise ValueError("No actual dependencies found")
    body = "\n".join(notices)
    if len(body.encode("utf-8")) > 4 * 1024 * 1024:
        raise ValueError("Notice inventory too large")
    output.mkdir(parents=True, exist_ok=True)
    (output / "runtime-notices.txt").write_text(body, encoding="utf-8")
    report = {"scope": "Actual source dependency inputs; root and explicitly mapped nested notices only, not full license clearance",
        "sherpa_commit": "5ce3d6d93a5f4fe11657bf11a6bf3a022eeef22f", "tts": "OFF",
        "toolchain": "Android NDK 27.2.12479018; toolchain/stdlib notices require separate review",
        "dependencies": records, "notices_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest()}
    (output / "runtime-dependencies.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(inventory(args.source, args.output), indent=2))
