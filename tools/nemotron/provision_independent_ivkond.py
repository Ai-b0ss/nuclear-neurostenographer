"""Freeze four external Russian dialogue cases with dataset speaker/turn labels.

The pinned Parquet is downloaded separately. Audio and derived references stay
under .local; only selection and validation code belongs in Git.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import soundfile as sf

REVISION = "3fa8404cfde61d2e3a3369000ce771747821e844"
PARQUET_SHA256 = "9b6bba30e9d02d875bf645f6cae997f7de6ebac32b326396066a676cc887abee"
SOURCE = ("https://huggingface.co/datasets/ivkond/synthetic-speech-diarization-ru/"
          f"blob/{REVISION}/train-00000-of-00030.parquet")
SEED = "c2-independent-v1"
SCENARIOS = ((2, False, "ivkond-2clean"), (2, True, "ivkond-2overlap"),
             (3, True, "ivkond-3overlap"), (4, True, "ivkond-4overlap"))


def digest(path):
    with Path(path).open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def turn_label_audit(turns, audio):
    """Measure whether coarse turn extents can serve as speech boundaries."""
    frame = 320
    n = len(audio) // frame
    if not n:
        return {"coverage": 0.0, "silent_labelled": 1.0, "der_usable": False}
    rms = np.sqrt(np.mean(audio[:n * frame].reshape(n, frame) ** 2, axis=1) + 1e-12)
    active = rms > max(1e-3, 0.1 * np.percentile(rms, 95))
    labelled = np.zeros(n, dtype=bool)
    for turn in turns:
        labelled[turn["start_ms"] // 20:turn["end_ms"] // 20] = True
    coverage = float(labelled.mean())
    silent = float((labelled & ~active).sum() / max(int(labelled.sum()), 1))
    # Long utterance/turn extents may include pauses. The old 96% coverage
    # condition admitted a 94.9%-covered case with 43.5% silent labelled time.
    # Such labels can support text/speaker scoring, but not a defensible DER.
    return {"coverage": coverage, "silent_labelled": silent,
            "der_usable": coverage >= 0.05 and not (coverage >= 0.75 and silent > 0.33)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", required=True, type=Path)
    parser.add_argument("--assets", required=True, type=Path)
    parser.add_argument("--references", required=True, type=Path)
    args = parser.parse_args()
    if digest(args.parquet) != PARQUET_SHA256:
        raise ValueError("Pinned ivkond shard SHA-256 mismatch")
    metadata = pq.read_table(args.parquet, columns=["duration", "num_speakers", "has_overlaps"]).to_pylist()
    chosen = []
    for count, overlap, case_id in SCENARIOS:
        eligible = [index for index, row in enumerate(metadata)
                    if row["num_speakers"] == count and row["has_overlaps"] is overlap
                    and row["duration"] <= 90]
        if not eligible:
            raise ValueError(f"No eligible {case_id} rows")
        index = min(eligible, key=lambda i: hashlib.sha256(f"{SEED}|{i}".encode()).hexdigest())
        chosen.append((index, case_id))
    table = pq.read_table(args.parquet, columns=["audio", "sampling_rate", "speakers",
                                                     "duration", "num_speakers", "has_overlaps"])
    args.assets.mkdir(parents=True, exist_ok=True)
    args.references.mkdir(parents=True, exist_ok=True)
    manifest = {"revision": REVISION, "source_sha256": PARQUET_SHA256,
                "selection": "first SHA-256(c2-independent-v1|row) per scenario, duration <= 90 s",
                "cases": []}
    for index, case_id in chosen:
        row = table.take(pa.array([index])).to_pylist()[0]
        if row["sampling_rate"] != 16000:
            raise ValueError(f"{case_id}: unexpected sample rate")
        cell = row["audio"]
        audio = np.asarray(cell["array"], dtype=np.float32) if cell.get("array") is not None else None
        if audio is None or audio.ndim != 1 or not np.isfinite(audio).all():
            raise ValueError(f"{case_id}: invalid mono audio")
        wav = args.assets / f"{case_id}.wav"
        sf.write(wav, np.clip(audio, -1, 1), 16000, subtype="PCM_16")
        duration = len(audio) * 1000 // 16000  # match PcmAudio.durationMs
        texts = []
        for segment in row["speakers"]:
            start = round(segment["start"] * 1000)
            end = min(round(segment["end"] * 1000), duration)
            if not 0 <= start < end <= duration:
                raise ValueError(f"{case_id}: invalid dataset turn")
            texts.append({"start_ms": start, "end_ms": end,
                          "speaker_id": f"s{segment['speaker_id']}", "text": segment["text"]})
        turns = [{key: segment[key] for key in ("start_ms", "end_ms", "speaker_id")}
                 for segment in texts]
        reference = {"schema_version": 1, "recording_id": case_id,
                     "annotation_source": f"{SOURCE}#row-{index}",
                     "license": "MIT per dataset card; synthetic voice origin not independently audited",
                     "kind": "SYNTHETIC_DATASET_TURN_LABELS",
                     "audio_sha256": digest(wav), "audio_duration_ms": duration,
                     "text_segments": texts,
                     "reference_limits": "Dataset turn extents, not manually audited word/speech boundaries; training contamination unverified"}
        audit = turn_label_audit(turns, audio)
        if audit["der_usable"]:
            reference["diarization"] = turns
        ref_path = args.references / f"{case_id}.ref.json"
        ref_path.write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest["cases"].append({"id": case_id, "row": index, "speakers": row["num_speakers"],
                                  "has_overlaps": row["has_overlaps"], "duration_ms": duration,
                                  "audio_sha256": reference["audio_sha256"],
                                  "reference_sha256": digest(ref_path),
                                  "der_reference_accepted": "diarization" in reference,
                                  "turn_label_audit": audit})
    (args.references / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest["cases"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
