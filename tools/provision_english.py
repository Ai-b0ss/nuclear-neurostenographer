"""Prepare the pinned, offline Whisper Tiny bundle. Weights are never committed.

python tools/provision_english.py --model-dir .local/english/sherpa-onnx-whisper-tiny
Omit --model-dir to download the three pinned files from the upstream converter.
"""
import argparse
import hashlib
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REVISION = "65176e2deb88badc814a94058666cadccc29b61c"
BASE = f"https://huggingface.co/csukuangfj/sherpa-onnx-whisper-tiny/resolve/{REVISION}/"
PINS = {
    "tiny-encoder.int8.onnx": ("d24fb083ae3b1041fc24e97971d60e280c9342201fbb67b0ab428a8b4a51a434", 12937772),
    "tiny-decoder.int8.onnx": ("d2fece8dd42771f1df975c6c0445770d0c292bf7547c2cae04a6c0cc57540925", 89855401),
    "tiny-tokens.txt": ("b34b360dbb493e781e479794586d661700670d65564001f23024971d1f2fa126", 816730),
}


def verify(path, digest, size):
    if path.stat().st_size != size:
        raise ValueError(f"Wrong size: {path.name}")
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != digest:
        raise ValueError(f"SHA-256 mismatch: {path.name}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path)
    args = parser.parse_args()
    directory = args.model_dir or ROOT / ".local/english-download"
    directory.mkdir(parents=True, exist_ok=True)
    for name, (digest, size) in PINS.items():
        target = directory / name
        if args.model_dir is None and not target.exists():
            stage = target.with_suffix(target.suffix + ".part")
            try:
                with urllib.request.urlopen(BASE + name, timeout=60) as src, stage.open("wb") as dst:
                    total = 0
                    while chunk := src.read(1024 * 1024):
                        total += len(chunk)
                        if total > size:
                            raise ValueError(f"Oversized download: {name}")
                        dst.write(chunk)
                verify(stage, digest, size)
                stage.replace(target)
            finally:
                stage.unlink(missing_ok=True)
        verify(target, digest, size)
    output = ROOT / ".local/englishAssets/whisper-tiny.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = output.with_suffix(".zip.part")
    try:
        with zipfile.ZipFile(stage, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
            for name in PINS:
                archive.write(directory / name, name)
        stage.replace(output)
    finally:
        stage.unlink(missing_ok=True)
    print(f"Prepared {output}; {output.stat().st_size} bytes; all SHA-256 pins verified")


if __name__ == "__main__":
    main()
