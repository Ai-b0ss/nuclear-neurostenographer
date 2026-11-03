"""Frozen corpus for C0 versus C2 on the same Russian 3-4 speaker recordings. Selection rules are fixed here, before any run.

python tools/c2_same_tracks/build_same_corpus.py --root ROOT --out-dir ROOT/data/same --manifest docs/evidence/c2-same-tracks/manifest.json

Sets:
  phone3   The three tracks Sonnet ran on the HONOR phone (ivkond shard 0 rows 25, 30, 35), rebuilt byte for byte from the
           public parquet: float samples * 32767 truncated to int16, 16 kHz mono WAV. The SHA-256 must equal the hashes
           in docs/evidence/physical-honor-dnn-lx9-2026-11-03/synthetic-3-4-speakers on feature/long-recordings.
  holdout  Every row with 3 or more speakers in ivkond shards 4, 5 and 6 (shards 0 and 1 are used for C0 threshold tuning
           on the main branch, so they are not a holdout), one row per distinct dialogue text (the dataset repeats a
           dialogue with other noise; the first row wins). Synthetic TTS voices, dataset labels.
  realmix  Real people: two natural DataHive calls (CC BY 4.0) whose caller and callee country pairs differ, so the four
           speakers are different people, spliced in 40 s blocks X1 Y1 X2 Y2 X3 Y3 from their frozen 30-150 s windows.
           The reference is the per-channel Silero VAD of each call after the energy gate of tools/c2_analysis
           (independent of C0 and C2, automatic, never listened to). No text, so WER/cpWER are NOT_SCORED.
           The splice joins two different telephone channels: each block change is also a channel change, which makes
           telling the two calls apart easier than telling speakers apart in one room.

DER on phone3 and holdout is NOT_SCORED: the dataset labels tile the whole file, silence included (see der_reference_problem
in tools/diar_bench/build_corpus.py). Their speaker labels are used for WER, cpWER, speaker count and A-B-A returns.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import wave

import numpy as np
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "c2_analysis"))

IVKOND = "ivkond/synthetic-speech-diarization-ru"
IVKOND_REVISION = "3fa8404cfde61d2e3a3369000ce771747821e844"
SHARDS = {0: "9b6bba30e9d02d875bf645f6cae997f7de6ebac32b326396066a676cc887abee",
          4: "e620a50c497ed598c1aaba408b99e2461a7c3ac0a9dae8c49360c320d1eafaae",
          5: "6fa6c6152aedac1cec8bd2ffc0e225e44eb511afb9c23d74714c9cfe35e0b21f",
          6: "dcbc49ca0f16b8f4cb2612ab41117d9fa82b5ad339f5d64d318c7c2c09bdeaeb"}
PHONE3 = {"syn3-clean": (25, "7b5d5f9c8d5a984d193c2a0e31afe5dc6e3c1fb068d9499d552f104c0a6c4ce9"),
          "syn3-brown": (30, "942bfdf41cb3df235768273a739a24b821f008ce5377f67362a783763bb05ca9"),
          "syn4-noise": (35, "939648072d210ef99b1d6b1866110997852a53239d63989b78cbb2b267a70d49")}
HOLDOUT_SHARDS = (4, 5, 6)
# Calls paired by country of the two phone numbers (metadata.jsonl); ru_000001 is left out for its broken reference.
REALMIX = [("ru_000002", "ru_000007"), ("ru_000005", "ru_000013"), ("ru_000015", "ru_000003"), ("ru_000006", "ru_000017")]
BLOCK_MS = 40000
RATE = 16000


def wav_bytes(samples):
    """The phone tracks' conversion: no rounding, plain truncation toward zero."""
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
    return out.getvalue()


def ivkond_case(case_id, row, shard, data, group):
    samples = np.asarray(row["audio"]["array"], dtype=np.float32)
    if row["audio"]["sampling_rate"] != RATE:
        raise SystemExit(f"{case_id}: unexpected rate {row['audio']['sampling_rate']}")
    audio = wav_bytes(samples)
    duration = round(len(samples) * 1000 / RATE)
    segments = [{"start_ms": min(round(s["start"] * 1000), duration - 1), "end_ms": min(round(s["end"] * 1000), duration),
                 "speaker_id": str(s["speaker_id"]), "text": s["text"]} for s in row["speakers"]]
    reference = {"schema_version": 1, "recording_id": case_id, "audio_sha256": hashlib.sha256(audio).hexdigest(),
                 "audio_duration_ms": duration,
                 "annotation_source": f"https://huggingface.co/datasets/{IVKOND}/tree/{IVKOND_REVISION} train-{shard:05d}-of-00030.parquet row {data}",
                 "license": "MIT (dataset card)", "kind": "SYNTHETIC_TTS_DIALOGUE",
                 "text_segments": segments,
                 "diarization": [{k: s[k] for k in ("start_ms", "end_ms", "speaker_id")} for s in segments],
                 "meta": {"num_speakers": row["num_speakers"], "difficulty": row["difficulty"], "has_overlaps": row["has_overlaps"],
                          "has_noise": row["has_noise"], "noise_type": row["noise_type"], "snr": row["snr"]}}
    case = {"id": case_id, "set": group, "source": f"{IVKOND}@{IVKOND_REVISION[:8]}:shard{shard}:{data}", "audio_sha256": reference["audio_sha256"],
            "duration_ms": duration, "speakers": len({s["speaker_id"] for s in segments}), "noise": row["noise_type"],
            "der": "NOT_SCORED: dataset labels tile the file, silence included", "text": True}
    return audio, reference, case


def realmix_case(root, first, second, ffmpeg):
    from analyze_datahive import level_db, stereo
    from gated_reference import gate
    import soundfile as sf
    corpus = root / "data/corpus"
    parts, labels = {}, {}
    for call in (first, second):
        reference = json.loads((corpus / f"datahive-{call}.ref.json").read_text(encoding="utf-8"))
        mono, rate = sf.read(corpus / f"datahive-{call}.wav", dtype="int16")
        if rate != RATE or len(mono) != reference["audio_duration_ms"] * RATE // 1000:
            raise SystemExit(f"{call}: unexpected corpus audio")
        channels = stereo(ffmpeg, root / "data/raw/datahive" / f"{call}.mp3")
        count = reference["audio_duration_ms"] // 20
        levels = [level_db(channels[:, i])[:count] for i in range(2)]
        parts[call] = mono
        labels[call] = gate(reference["diarization"], levels, reference["audio_duration_ms"])
    pieces, turns, offset = [], [], 0
    for block in range(3):
        for call in (first, second):
            a, b = block * BLOCK_MS, (block + 1) * BLOCK_MS
            pieces.append(parts[call][a * RATE // 1000:b * RATE // 1000])
            for t in labels[call]:
                s, e = max(t["start_ms"], a), min(t["end_ms"], b)
                if e - s >= 250:
                    turns.append({"start_ms": offset + s - a, "end_ms": offset + e - a, "speaker_id": f"{call}-{t['speaker_id']}"})
            offset += BLOCK_MS
    samples = np.concatenate(pieces)
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(samples.astype("<i2").tobytes())
    audio = out.getvalue()
    case_id = f"realmix-{first[-2:]}-{second[-2:]}"
    turns.sort(key=lambda t: (t["start_ms"], t["speaker_id"]))
    reference = {"schema_version": 1, "recording_id": case_id, "audio_sha256": hashlib.sha256(audio).hexdigest(),
                 "audio_duration_ms": offset,
                 "annotation_source": f"datahiveai/russian-conversations-sample {first}+{second}, 30-150 s windows spliced in 40 s blocks; "
                                      "per-channel Silero VAD gated by channel energy; no human check",
                 "license": "CC BY 4.0 (DataHive)", "kind": "REAL_CALLS_SPLICED_CHANNEL_VAD", "diarization": turns}
    case = {"id": case_id, "set": "realmix", "source": f"datahive:{first}+{second}", "audio_sha256": reference["audio_sha256"],
            "duration_ms": offset, "speakers": len({t["speaker_id"] for t in turns}), "noise": "real phone calls",
            "der": "SCORED against the gated channel reference", "text": False}
    return audio, reference, case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    raw = args.root / "data/raw/ivkond"
    for shard, digest in SHARDS.items():
        if hashlib.sha256((raw / f"shard{shard}.parquet").read_bytes()).hexdigest() != digest:
            raise SystemExit(f"shard {shard} hash mismatch")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    built = []
    shard0 = pq.read_table(raw / "shard0.parquet")
    for name, (index, digest) in PHONE3.items():
        built.append(ivkond_case(name, shard0.slice(index, 1).to_pylist()[0], 0, index, "phone3"))
        if built[-1][1]["audio_sha256"] != digest:
            raise SystemExit(f"{name}: rebuilt audio differs from the phone track")
    seen = set()
    for shard in HOLDOUT_SHARDS:
        table = pq.read_table(raw / f"shard{shard}.parquet")
        meta = table.select(["num_speakers", "speakers"]).to_pylist()
        for index, row in enumerate(meta):
            if row["num_speakers"] < 3:
                continue
            text = tuple(s["text"] for s in row["speakers"])
            if text in seen:
                continue
            seen.add(text)
            built.append(ivkond_case(f"hold-s{shard}-r{index:02d}", table.slice(index, 1).to_pylist()[0], shard, index, "holdout"))
    for first, second in REALMIX:
        built.append(realmix_case(args.root, first, second, args.ffmpeg))
    cases = []
    for audio, reference, case in built:
        (args.out_dir / f"{case['id']}.wav").write_bytes(audio)
        text = json.dumps(reference, ensure_ascii=False, indent=1) + "\n"
        (args.out_dir / f"{case['id']}.ref.json").write_text(text, encoding="utf-8")
        case["reference_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cases.append(case)
        print(case["id"], case["speakers"], case["duration_ms"], case["audio_sha256"][:12], flush=True)
    manifest = {"rules": __doc__.strip(), "ivkond_revision": IVKOND_REVISION, "shard_sha256": SHARDS, "cases": cases}
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
