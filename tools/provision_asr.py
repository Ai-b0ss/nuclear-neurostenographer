"""Pinned public downloads only; no inference service, credentials or pip dependencies.

python tools/provision_asr.py          # AAR for build
python tools/provision_asr.py --model # also create .local/gigaam-v3.zip for phone
python tools/provision_asr.py --test-assets # model + public upstream test WAV
python tools/provision_asr.py --runtime-file PATH # select exact pinned no-TTS candidate
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
HF_REV = "32a4c7cc81809bd132e2d935ab99e9e6ab47fbec"
BASE = f"https://huggingface.co/csukuangfj/sherpa-onnx-nemo-ctc-giga-am-v3-russian-2025-12-16/resolve/{HF_REV}/"
FILES = {
    "model.int8.onnx": "f86ebfa0429ced91be6054fc344827e9c6c2572f3c318416cd974b06f66437ec",
    "tokens.txt": "17cc514451bcceac9c280068c71502f8448f99e9fb1456b8d0761651fd0392f2",
    "LICENSE": "f00de6715714c7a63d08639cdbfaa40224eefc407302614bd19f1a8b98c875aa",
}
NO_TTS_CANDIDATE_SHA256 = "771fda6a4abf845a6f84f48e05e887fdf159671beb88cbc9aae327806511c1c8"
NO_TTS_CANDIDATE_RUN = 41039830327


def sha256(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def download(url, path, digest):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and sha256(path) == digest:
        return
    temp = path.with_suffix(path.suffix + ".part")
    urllib.request.urlretrieve(url, temp)
    if sha256(temp) != digest:
        temp.unlink()
        raise ValueError(f"SHA-256 mismatch: {path.name}")
    temp.replace(path)
    print(f"VERIFIED {path.name} {digest}")


def select_runtime(candidate, destination):
    # Pin in reviewed source, never accept a checksum supplied beside an unknown
    # local binary. Failed selection must preserve the previous build runtime.
    if sha256(candidate) != NO_TTS_CANDIDATE_SHA256:
        raise ValueError("Not the pinned no-TTS candidate; previous runtime retained")
    download(candidate.resolve().as_uri(), destination, NO_TTS_CANDIDATE_SHA256)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", action="store_true")
    parser.add_argument("--test-assets", action="store_true")
    parser.add_argument("--runtime-file", type=Path,
                        help="Exact pinned no-TTS candidate from same-repo run 41039830327")
    args = parser.parse_args()
    runtime = ROOT / "app/libs/sherpa-onnx-1.12.20.aar"
    if args.runtime_file:
        select_runtime(args.runtime_file, runtime)
    else:
        download("https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.12.20/sherpa-onnx-1.12.20.aar",
                 runtime, "e3905b1258b577d8d374db798618602ceaaff5805cbf9b356ab25267cd98144d")
    if args.model or args.test_assets:
        for name, digest in FILES.items():
            download(BASE + name, ROOT / ".local/model" / name, digest)
        dest = ROOT / ".local/gigaam-v3.zip"
        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_STORED) as z:
            for name in FILES:
                z.write(ROOT / ".local/model" / name, name)
        print(f"OFFLINE MODEL ZIP: {dest}")
    if args.test_assets:
        assets = ROOT / ".local/androidTestAssets"
        assets.mkdir(exist_ok=True)
        # Keep large test assets and public audio out of Git.
        import shutil
        shutil.copyfile(dest, assets / "gigaam-v3.zip")
        download(BASE + "test_wavs/example.wav", assets / "example.wav",
                 "d8aaaa18a5098d7c6de0595ae7ac1e64cacd0d4022af3595213bdaf23be77e69")
        (ROOT / ".local/provenance.json").write_text(json.dumps(
            {"revision": HF_REV, "files": FILES, "fixture": BASE + "test_wavs/example.wav"}, indent=2))


if __name__ == "__main__":
    main()
