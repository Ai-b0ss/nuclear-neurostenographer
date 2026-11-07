"""Enhance one PCM WAV using a manual three-second enrollment and pinned ONNX models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import numpy as np

from adapter import (
    AdapterError,
    DEFAULT_MODEL_DIR,
    ENROLLMENT_SECONDS,
    LOCK,
    VoiceFilterLite,
    prepare_enrollment,
    prepare_mixture,
    read_wav,
    resample_16k,
    sha256,
    write_wav_atomic,
)


def enhance_files(
    enrollment_path: Path,
    input_path: Path,
    output_path: Path,
    model_dir: Path = DEFAULT_MODEL_DIR,
    threads: int = 1,
    max_duration_seconds: float = 600.0,
) -> dict:
    started = time.perf_counter()
    enrollment_path = Path(enrollment_path)
    input_path = Path(input_path)
    output_path = Path(output_path)
    if output_path.resolve() in {enrollment_path.resolve(), input_path.resolve()}:
        raise AdapterError("Output WAV must not overwrite enrollment or mixture input")
    enrollment_audio = read_wav(enrollment_path, max_duration_seconds)
    mixture_audio = read_wav(input_path, max_duration_seconds)
    enrollment = prepare_enrollment(
        resample_16k(enrollment_audio.samples, enrollment_audio.sample_rate), ENROLLMENT_SECONDS
    )
    mixture = prepare_mixture(resample_16k(mixture_audio.samples, mixture_audio.sample_rate))
    load_started = time.perf_counter()
    engine = VoiceFilterLite(model_dir, threads=threads)
    load_seconds = time.perf_counter() - load_started
    inference_started = time.perf_counter()
    enhanced = engine.enhance(enrollment, mixture)
    inference_seconds = time.perf_counter() - inference_started
    write_result = write_wav_atomic(output_path, enhanced)
    wall_seconds = time.perf_counter() - started
    audio_seconds = mixture.size / 16000.0
    return {
        "status": "OK",
        "mode": "offline_research_synthetic_or_manual_input",
        "upstream_commit": LOCK["upstream"]["commit"],
        "implementation": "independent_adapter",
        "models": engine.models,
        "enrollment": {
            "path": str(enrollment_path),
            "sha256": sha256(enrollment_path),
            "source_sample_rate": enrollment_audio.sample_rate,
            "source_duration_seconds": enrollment_audio.duration_seconds,
            "used_duration_seconds": ENROLLMENT_SECONDS,
        },
        "input": {
            "path": str(input_path),
            "sha256": sha256(input_path),
            "source_sample_rate": mixture_audio.sample_rate,
            "source_channels": mixture_audio.source_channels,
            "source_duration_seconds": mixture_audio.duration_seconds,
            "processed_duration_seconds": audio_seconds,
        },
        "output": {
            "path": str(output_path),
            "sample_rate": 16000,
            "channels": 1,
            "pcm_bits": 16,
            "frames": int(enhanced.size),
            "duration_seconds": audio_seconds,
            "rms": float(np.sqrt(np.mean(np.square(enhanced, dtype=np.float64)))),
            **write_result,
        },
        "timing": {
            "model_load_seconds": load_seconds,
            "inference_seconds": inference_seconds,
            "wall_seconds": wall_seconds,
            "inference_rtf": inference_seconds / audio_seconds,
            "wall_rtf": wall_seconds / audio_seconds,
        },
        "threads": threads,
        "quality_wer_status": "NOT_RUN",
        "pss_status": "NOT_RUN",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enrollment", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path, help="Mixture PCM WAV")
    parser.add_argument("--output", required=True, type=Path, help="Enhanced 16 kHz mono PCM16 WAV")
    parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--max-duration-seconds", type=float, default=600.0)
    parser.add_argument("--report", type=Path, help="Optional actual-run JSON report")
    args = parser.parse_args()
    try:
        report = enhance_files(
            args.enrollment,
            args.input,
            args.output,
            args.models_dir,
            args.threads,
            args.max_duration_seconds,
        )
    except (AdapterError, OSError, RuntimeError) as error:
        raise SystemExit(f"INFERENCE FAILED: {error}") from error
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
