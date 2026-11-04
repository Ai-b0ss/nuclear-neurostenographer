"""Check ZIP and ARM64 ELF 16 KB alignment of an Android APK.

Example: python tools/check_android_native_pages.py --apk app/build/outputs/apk/debug/app-debug.apk
         --ndk C:/Users/Anon/AppData/Local/Android/Sdk/ndk/26.1.10909125
         --zipalign C:/Users/Anon/AppData/Local/Android/Sdk/build-tools/35.0.0/zipalign.exe
The gate fails if even one packaged ARM64 library is 4 KB aligned.
"""
import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", required=True, type=Path)
    parser.add_argument("--ndk", required=True, type=Path)
    parser.add_argument("--zipalign", required=True, type=Path)
    args = parser.parse_args()
    objdump = args.ndk / "toolchains/llvm/prebuilt/windows-x86_64/bin/llvm-objdump.exe"
    aligned_zip = subprocess.run([str(args.zipalign), "-c", "-P", "16", "4", str(args.apk)],
                                 capture_output=True).returncode == 0
    libraries = {}
    with ZipFile(args.apk) as apk, tempfile.TemporaryDirectory() as temporary:
        for name in sorted(n for n in apk.namelist() if n.startswith("lib/arm64-v8a/") and n.endswith(".so")):
            path = Path(temporary) / Path(name).name
            path.write_bytes(apk.read(name))
            result = subprocess.run([str(objdump), "-p", str(path)], capture_output=True, text=True, check=True)
            exponents = [int(value) for value in re.findall(r"^\s*LOAD\b[^\n]*\balign 2\*\*(\d+)",
                                                             result.stdout, re.MULTILINE)]
            if not exponents:
                raise ValueError(f"No ELF LOAD segments in {name}")
            libraries[name] = {"minimum_page_bytes": 1 << min(exponents), "pass": min(exponents) >= 14}
    report = {"zip_alignment_16kb": aligned_zip, "arm64_libraries": libraries,
              "pass": aligned_zip and bool(libraries) and all(item["pass"] for item in libraries.values())}
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
