"""Hash-bound real DataHive overlap fixtures with mandatory manual enrollment."""
import argparse
import json
from pathlib import Path
import re
import sys
import wave

import numpy as np

from common import LOCAL, owned, sha, write_json

KIND = "REAL_DATAHIVE_MANUAL_OVERLAP"
ENROLLMENT_SAMPLES = 48000
RATE = 16000


def read_pcm16_mono(path):
    with wave.open(str(path), "rb") as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) != (1, 2, RATE):
            raise ValueError(f"{path}: mono PCM16 16 kHz required")
        samples = np.frombuffer(stream.readframes(stream.getnframes()), "<i2").astype(np.float32) / 32768
    if not np.isfinite(samples).all():
        raise ValueError(f"{path}: non-finite PCM")
    return samples


def _digest(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"{label}: lowercase SHA-256 required")
    return value


def _file(root, value, label):
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label}: path required")
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    if not path.is_file():
        raise ValueError(f"{label}: file not found: {path}")
    return path.resolve()


def _check_hash(path, expected, label):
    _digest(expected, label)
    if sha(path) != expected:
        raise ValueError(f"{label}: SHA-256 mismatch")


def _reference(path, case_id, audio_sha256, duration_ms):
    from metrics import overlap_spans
    from score_transcript import validate_segments, words

    reference = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(reference, dict) or reference.get("schema_version") != 1:
        raise ValueError(f"{case_id}: reference schema_version=1 required")
    if reference.get("kind") != KIND:
        raise ValueError(f"{case_id}: real manual DataHive reference required; synthetic references are forbidden")
    if reference.get("recording_id") != case_id:
        raise ValueError(f"{case_id}: reference recording_id mismatch")
    if reference.get("audio_sha256") != audio_sha256 or reference.get("audio_duration_ms") != duration_ms:
        raise ValueError(f"{case_id}: reference is not bound to the exact audio")
    if not all(isinstance(reference.get(key), str) and reference[key].strip() for key in ("annotation_source", "license")):
        raise ValueError(f"{case_id}: annotation_source and license required")
    text = reference.get("text_segments")
    turns = reference.get("diarization")
    validate_segments(text, duration_ms, text=True, reference=True)
    validate_segments(turns, duration_ms, reference=True)
    if not text or any(len(words(segment["text"])) != 1 for segment in text):
        raise ValueError(f"{case_id}: one manually timed normalized word per text segment required")
    if not overlap_spans(turns):
        raise ValueError(f"{case_id}: manual reference contains no speaker overlap")
    return reference


def _case(raw, root):
    if not isinstance(raw, dict):
        raise ValueError("Each fixture case must be an object")
    case_id = raw.get("id")
    if not isinstance(case_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", case_id):
        raise ValueError("Case id must be a safe lowercase identifier")
    audio = _file(root, raw.get("audio_path"), f"{case_id}.audio_path")
    audio_sha256 = raw.get("audio_sha256")
    _check_hash(audio, audio_sha256, f"{case_id}.audio_sha256")
    samples = read_pcm16_mono(audio)
    if not samples.size:
        raise ValueError(f"{case_id}: empty audio")
    duration_ms = len(samples) // (RATE // 1000)
    reference_path = _file(root, raw.get("reference_path"), f"{case_id}.reference_path")
    reference_sha256 = raw.get("reference_sha256")
    _check_hash(reference_path, reference_sha256, f"{case_id}.reference_sha256")
    reference = _reference(reference_path, case_id, audio_sha256, duration_ms)
    enrollments = raw.get("enrollments")
    if not isinstance(enrollments, list) or len(enrollments) != 2:
        raise ValueError(f"{case_id}: exactly two manual enrollments required; no fallback exists")
    speakers = {segment["speaker_id"] for segment in reference["text_segments"]}
    result = []
    for index, enrollment in enumerate(enrollments):
        label = f"{case_id}.enrollments[{index}]"
        if not isinstance(enrollment, dict) or enrollment.get("selection") != "manual":
            raise ValueError(f"{label}: selection=manual required")
        speaker_id = enrollment.get("speaker_id")
        if speaker_id not in speakers:
            raise ValueError(f"{label}: speaker_id is absent from the manual reference")
        wav = _file(root, enrollment.get("wav_path"), f"{label}.wav_path")
        digest = enrollment.get("sha256")
        _check_hash(wav, digest, f"{label}.sha256")
        sample = read_pcm16_mono(wav)
        if len(sample) != ENROLLMENT_SAMPLES:
            raise ValueError(f"{label}: exactly 48000 samples (3 s) required; padding/truncation forbidden")
        rms = float(np.sqrt(np.mean(sample**2)))
        if rms < 1e-4 or np.max(np.abs(sample)) >= 0.99:
            raise ValueError(f"{label}: silent or clipped enrollment rejected")
        result.append(dict(speaker_id=speaker_id, selection="manual", wav_path=str(wav), sha256=digest,
                           samples=len(sample), rms=rms))
    if len({item["speaker_id"] for item in result}) != 2:
        raise ValueError(f"{case_id}: enrollment speaker identities must be distinct")
    if len({item["sha256"] for item in result}) != 2:
        raise ValueError(f"{case_id}: identical enrollment audio for two speakers rejected")
    return dict(id=case_id, audio_path=str(audio), audio_sha256=audio_sha256, duration_ms=duration_ms,
                reference_path=str(reference_path), reference_sha256=reference_sha256, enrollments=result)


def _root(manifest):
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("Manifest schema_version=1 required")
    if manifest.get("kind") != KIND or manifest.get("enrollment_mode") != "manual":
        raise ValueError("Real DataHive manifest with enrollment_mode=manual required")
    if not isinstance(manifest.get("cases"), list) or not manifest["cases"]:
        raise ValueError("At least one real overlap case required")


def validate(manifest_path):
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _root(manifest)
    cases = [_case(case, manifest_path.parent) for case in manifest["cases"]]
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Duplicate case id")
    return dict(schema_version=1, kind=KIND, enrollment_mode="manual",
                enrollment_samples=ENROLLMENT_SAMPLES, cases=cases)


def adapt(manifest_path, output):
    manifest_path = Path(manifest_path).resolve()
    normalized = validate(manifest_path)
    normalized["source_manifest_sha256"] = sha(manifest_path)
    output = Path(output)
    if (output / "manifest.json").exists():
        raise ValueError("Adapted fixture manifest already exists; use a new output directory")
    output = owned(output)
    write_json(output / "manifest.json", normalized)
    return normalized


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=LOCAL / "manual-real")
    args = parser.parse_args()
    normalized = adapt(args.manifest, args.out)
    print(json.dumps({"status": "VALIDATED_MANUAL_ENROLLMENT", "cases": len(normalized["cases"]),
                      "output": str(Path(args.out) / "manifest.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
