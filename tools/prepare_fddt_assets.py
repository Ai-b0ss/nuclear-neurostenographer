#!/usr/bin/env python3
"""Copy and independently verify Ruzanna's FDDT ONNX files into local Gradle assets.

Usage:
  python tools/prepare_fddt_assets.py --archive "/path/to/fddt_rnnt 2.zip"
  python tools/prepare_fddt_assets.py --verify-only

No network access or arbitrary archive extraction. Supports Windows, Linux, macOS.
"""
import argparse
import hashlib
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ZIP_SHA256 = "e3459a89aba3b80a1df1ddb20550bf308ee1ab517252c58af8956a7622950097"
FILES = {
    "encoder_fddt.int8.onnx": (320122758, "98d9a0480416e61434b1edbca18491fcb0593ad27eb6e628cf687011c4921140"),
    "decoder.onnx": (4599970, "75d61a4e5b1bfeaa667360bef042f284c43ca0a4e310de5de3377e6b48ac7835"),
    "joint.onnx": (2712926, "8f007db342af76c7355912ab0611d66aaafa4d74df035ca0016ed622e4344fc7"),
    "tokens.txt": (13354, "39abae20e692998290c574e606f11a9edef2902a1995463fcff63d1490cf22b7"),
}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def verified(path, expected_size, expected_hash):
    return path.is_file() and path.stat().st_size == expected_size and digest(path) == expected_hash


def prepare(archive, dest, verify_only=False):
    if verify_only:
        for name, (size, sha) in FILES.items():
            if not verified(dest / name, size, sha):
                raise ValueError("Missing or corrupted model: " + name)
            print("PASS", name)
        return

    if archive is None:
        raise ValueError("--archive is required unless --verify-only is selected")
    if not archive.is_file():
        raise FileNotFoundError(str(archive))
    if digest(archive) != ZIP_SHA256:
        raise ValueError("Archive SHA256 mismatch: expected unmodified fddt_rnnt 2.zip")
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for name, (size, sha) in FILES.items():
            target = dest / name
            if verified(target, size, sha):
                print("VERIFIED_ALREADY", name)
                continue
            entry = z.getinfo("fddt_rnnt/onnx/" + name)
            if entry.file_size != size:
                raise ValueError("Archive entry size mismatch: " + name)
            fd, tmpname = tempfile.mkstemp(prefix="." + name + ".", suffix=".partial", dir=dest)
            os.close(fd)
            tmp = Path(tmpname)
            try:
                with z.open(entry) as source, tmp.open("wb") as output:
                    while True:
                        block = source.read(1024 * 1024)
                        if not block:
                            break
                        output.write(block)
                if not verified(tmp, size, sha):
                    raise ValueError("Archive entry SHA256 mismatch: " + name)
                os.replace(tmp, target)
                print("VERIFIED_EXTRACTED", name)
            finally:
                tmp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="Exact original fddt_rnnt 2.zip")
    parser.add_argument("--dest", type=Path, default=Path(__file__).resolve().parents[1] / ".local" / "fddtAssets")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    try:
        prepare(args.archive, args.dest, args.verify_only)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as e:
        print("ERROR:", str(e), file=sys.stderr)
        return 1
    print("FDDT ASSETS READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
