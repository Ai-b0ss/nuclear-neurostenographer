"""Fingerprints that tie a stored run to its model, code, threshold, audio and reference.

A record whose fingerprint differs from the current one is stale: it is rerun or refused, never reused.
"""
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
C0_MODELS = ("c0/segmentation.onnx", "c0/embedding.onnx")
C1_SHARED = ("nemotron/preprocessor_core.onnx", "nemotron/constants.npz", "nemotron/diarize.py")
HARNESS_KOTLIN = ["tools/diar_bench/DiarBench.kt", "app/src/main/java/ru/neurostenographer/app/OfflineDiarization.kt",
                  "core/src/main/kotlin/ru/neurostenographer/core/DiarizationTimeline.kt"]
ASR_KOTLIN = ["app/src/main/java/ru/neurostenographer/app/OfflineAsr.kt", "core/src/main/kotlin/ru/neurostenographer/core/TranscriptCore.kt",
              "core/src/main/kotlin/ru/neurostenographer/core/QuietCuts.kt"]
_cache = {}


def file_hash(path):
    path = Path(path)
    key = (str(path), path.stat().st_mtime_ns, path.stat().st_size)
    if key not in _cache:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1 << 20):
                digest.update(chunk)
        _cache[key] = digest.hexdigest()
    return _cache[key]


def text_hash(path):
    """Line-ending independent, so a Git checkout does not make results look stale."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def digest_of(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def system_config(models_dir, system, c1_files, threshold, runtime):
    """Everything that can change a system's output, except the recording itself."""
    models_dir = Path(models_dir)
    if system == "C0":
        return {"system": system, "threshold": threshold or "0.8", "runtime": runtime,
                "models": {m: file_hash(models_dir / m) for m in C0_MODELS},
                "code": {c: text_hash(REPO / c) for c in HARNESS_KOTLIN}}
    return {"system": system, "threshold": "0.5", "runtime": runtime,
            "models": {m: file_hash(models_dir / m) for m in (*C1_SHARED, f"nemotron/{c1_files[system]}")},
            "code": {"tools/diar_bench/run_c1.py": text_hash(REPO / "tools/diar_bench/run_c1.py")}}


def asr_config(models_dir, runtime):
    models_dir = Path(models_dir)
    return {"models": {m: file_hash(models_dir / m) for m in ("asr/model.int8.onnx", "asr/tokens.txt")},
            "runtime": runtime, "code": {c: text_hash(REPO / c) for c in ASR_KOTLIN}}


def run_fingerprint(config, audio_sha256):
    return digest_of({"config": config, "audio_sha256": audio_sha256})
