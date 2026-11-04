"""Provision pinned 20-minute natural Russian call for Android cost-only tests.

No text or human RTTM reference exists for this recording; WER/cpWER/DER must
remain unscored. The output WAV stays ignored under .local.
"""

import argparse
import hashlib
from pathlib import Path
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / ".local/datahive/ru_000010.mp3"
OUTPUT = ROOT / ".local/androidTestAssets/nemotron-bench/natural-long-ru_000010.wav"
REVISION = "1120cd7533b16ba8dd7a7c07e6d316b74b60f72a"
MP3_SHA256 = "5561f59008a6df48f705217cccd0b7609a97dc22560d6d8a5698c368f5338415"
WAV_SHA256 = "e9933e55693151a6f2c5d0f34188348d62053b66a70d9dad0dd25ffd3a408df5"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    SOURCE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if not SOURCE.exists():
        url = ("https://huggingface.co/datasets/datahiveai/multilingual-conversations-sample/resolve/"
               f"{REVISION}/preview/ru_000010.mp3")
        with urllib.request.urlopen(url, timeout=120) as response, SOURCE.open("wb") as out:
            while block := response.read(1024 * 1024):
                out.write(block)
    assert sha256(SOURCE) == MP3_SHA256, "Unexpected source MP3"
    if not OUTPUT.exists() or sha256(OUTPUT) != WAV_SHA256:
        subprocess.run([args.ffmpeg, "-v", "error", "-y", "-t", "1200", "-i", str(SOURCE),
                        "-ar", "16000", "-ac", "1", "-bitexact", "-c:a", "pcm_s16le", str(OUTPUT)],
                       check=True)
    assert sha256(OUTPUT) == WAV_SHA256, "Output differs from pinned 20-minute WAV"
    print(OUTPUT, WAV_SHA256)


if __name__ == "__main__":
    main()
