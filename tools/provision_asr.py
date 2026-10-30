"""Pinned public downloads only; no inference service, credentials or pip dependencies.

python tools/provision_asr.py          # verified no-TTS AAR (GitHub CLI if not cached)
python tools/provision_asr.py --model # also create .local/gigaam-v3.zip for phone
python tools/provision_asr.py --test-assets # model + public upstream test WAV
python tools/provision_asr.py --runtime-file PATH # select exact pinned no-TTS candidate
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
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
LOCK = dict(line.split("=", 1) for line in
            (ROOT / "tools/runtime/runtime.properties").read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#"))
NO_TTS_CANDIDATE_SHA256 = LOCK["sha256"]
NO_TTS_CANDIDATE_RUN = int(LOCK["run_id"])


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


def provision_runtime(destination, cache=None):
    if destination.is_file() and sha256(destination) == NO_TTS_CANDIDATE_SHA256:
        return
    cache = cache or ROOT / ".local/runtime-cache"
    cache.mkdir(parents=True, exist_ok=True)
    cached = cache / LOCK["filename"]
    if cached.is_file() and sha256(cached) == NO_TTS_CANDIDATE_SHA256:
        select_runtime(cached, destination)
        return
    # No token lookup or settings changes. gh uses the caller's existing login
    # (or the Actions job's ephemeral token). Expiry/auth/network errors fail
    # explicitly, never fall back to the GPL/TTS upstream runtime.
    with tempfile.TemporaryDirectory(dir=cache) as temporary:
        try:
            subprocess.run(["gh", "run", "download", str(NO_TTS_CANDIDATE_RUN),
                "--repo", LOCK["repository"], "--name", LOCK["artifact"], "--dir", temporary],
                check=True, timeout=120, capture_output=True)
        except (OSError, subprocess.SubprocessError) as error:
            raise RuntimeError("Pinned no-TTS artifact unavailable. Use existing gh authentication or "
                "supply --runtime-file with the exact pinned AAR. No upstream fallback was selected.") from error
        downloaded = Path(temporary) / LOCK["filename"]
        select_runtime(downloaded, destination)
        # Cache only after full validation; no untrusted checksum sidecar is used.
        select_runtime(downloaded, cached)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", action="store_true")
    parser.add_argument("--test-assets", action="store_true")
    runtime_args = parser.add_mutually_exclusive_group()
    runtime_args.add_argument("--runtime-file", type=Path, help="Exact pinned no-TTS AAR")
    runtime_args.add_argument("--upstream-runtime", action="store_true",
                              help="Explicit GPL/TTS baseline for regression only, not distribution")
    args = parser.parse_args()
    runtime = ROOT / "app/libs/sherpa-onnx-1.12.20.aar"
    if args.runtime_file:
        select_runtime(args.runtime_file, runtime)
    elif args.upstream_runtime:
        download("https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.12.20/sherpa-onnx-1.12.20.aar",
                 runtime, LOCK["upstream_sha256"])
    else:
        provision_runtime(runtime)
    selection = {"sha256": sha256(runtime), "upstream_regression": args.upstream_runtime,
                 "repository": LOCK["repository"], "native_build_run": NO_TTS_CANDIDATE_RUN if not args.upstream_runtime else None}
    (ROOT / ".local").mkdir(exist_ok=True)
    (ROOT / ".local/runtime-selection.json").write_text(json.dumps(selection, indent=2) + "\n", encoding="utf-8")
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
            {"revision": HF_REV, "files": FILES, "fixture": BASE + "test_wavs/example.wav",
             "runtime": selection}, indent=2))


if __name__ == "__main__":
    main()
