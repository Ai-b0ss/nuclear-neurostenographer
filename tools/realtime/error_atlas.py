"""Frame-accurate audit of diarization misses against *coarse* speaker reference.

This is not an independent speech detector. RMS estimates audible energy only,
and cannot establish human speech or repair incomplete reference boundaries.
No reference labels, threshold tuning or RMS features go into model inference.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import wave
from array import array
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from score_transcript import der
from score_clip_run import clamp_reference

FRAME_MS = 10
SAMPLE_RATE = 16000
LOW_DB = -45.0
HIGH_DB = -35.0


def read_wav(path: Path):
    with wave.open(str(path), "rb") as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, SAMPLE_RATE):
            raise ValueError("Expected 16kHz mono PCM16 WAV")
        samples = array("h")
        samples.frombytes(w.readframes(w.getnframes()))
        if sys.byteorder != "little":
            samples.byteswap()
    return samples


def energy_frames(samples):
    result = []
    for i in range(0, len(samples), 160):
        frame = samples[i:i + 160]
        rms = math.sqrt(sum(float(x) ** 2 for x in frame) / len(frame)) / 32768
        result.append(20 * math.log10(max(rms, 1e-10)))
    return result


def read_tsv(path: Path, duration: int):
    turns = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        s, e, who = line.split("\t")
        start, end = int(s), min(int(e), duration)
        if not 0 <= start < end <= duration or not who.strip():
            raise ValueError(f"Invalid turn row {i}")
        turns.append(dict(start_ms=start, end_ms=end, speaker_id=who))
    return turns


def scored_intervals(ref, hyp, duration, collar_ms, rms_db):
    collars = [(max(0, turn[k] - collar_ms), min(duration, turn[k] + collar_ms))
               for turn in ref for k in ("start_ms", "end_ms") if collar_ms]
    boundaries = {0, duration}
    for t in ref + hyp:
        boundaries.update((t["start_ms"], t["end_ms"]))
    for a, b in collars:
        boundaries.update((a, b))
    # Split also at audio frame boundaries to preserve exact millisecond accounting.
    boundaries.update(min(duration, t * FRAME_MS) for t in range(len(rms_db) + 1))
    for a, b in zip(sorted(boundaries), sorted(boundaries)[1:]):
        if a == b:
            continue
        excluded = any(x <= a < y for x, y in collars)
        r = {t["speaker_id"] for t in ref if t["start_ms"] <= a < t["end_ms"]}
        h = {t["speaker_id"] for t in hyp if t["start_ms"] <= a < t["end_ms"]}
        db = rms_db[min(a // FRAME_MS, len(rms_db) - 1)]
        yield a, b, excluded, r, h, db


def classify(ref, hyp, duration, collar_ms, rms_db, mapping):
    totals = dict(reference_ms=0, missed_ms=0, false_alarm_ms=0,
                  confusion_ms=0, scored_ms=0, excluded_ms=0,
                  missed_quiet45_ms=0, missed_quiet35_ms=0, missed_loud35_ms=0)
    events = []
    last = None
    for a, b, exclude, r, h, db in scored_intervals(ref, hyp, duration, collar_ms, rms_db):
        dt = b - a
        mapped = {mapping.get(who, "_unmapped_" + who) for who in h}
        correct = sum(1 for who in h if mapping.get(who) in r)
        miss = max(len(r) - len(h), 0)
        fa = max(len(h) - len(r), 0)
        confusion = min(len(r), len(h)) - correct
        if exclude:
            totals["excluded_ms"] += dt
            category = "COLLAR_UNSCORED"
        else:
            totals["scored_ms"] += dt
            totals["reference_ms"] += dt * len(r)
            totals["missed_ms"] += dt * miss
            totals["false_alarm_ms"] += dt * fa
            totals["confusion_ms"] += dt * confusion
            if miss:
                if db < LOW_DB:
                    totals["missed_quiet45_ms"] += dt * miss
                if db < HIGH_DB:
                    totals["missed_quiet35_ms"] += dt * miss
                else:
                    totals["missed_loud35_ms"] += dt * miss
                category = "REF_SPEAKER_MISSED_PCM_QUIET" if db < LOW_DB else "REF_SPEAKER_MISSED_PCM_ENERGETIC"
            elif confusion:
                category = "SPEAKER_CONFUSION"
            elif fa:
                category = "FALSE_ALARM"
            else:
                category = "NO_SCORING_ERROR"
        if exclude or r or h:
            event = dict(start_ms=a, end_ms=b, excluded=exclude,
                         reference="|".join(sorted(r)), predicted="|".join(sorted(h)),
                         predicted_mapped="|".join(sorted(mapped)), dbfs=round(db, 2),
                         category=category, miss_slots=0 if exclude else miss,
                         confusion_slots=0 if exclude else confusion)
            events.append(event)
    return totals, events


def per_reference(ref, events):
    report = []
    for index, turn in enumerate(ref):
        rows = [r for r in events if not r["excluded"] and
                r["start_ms"] < turn["end_ms"] and r["end_ms"] > turn["start_ms"]]
        scored = sum(min(r["end_ms"], turn["end_ms"]) - max(r["start_ms"], turn["start_ms"])
                     for r in rows)
        missed = sum((min(r["end_ms"], turn["end_ms"]) - max(r["start_ms"], turn["start_ms"]))
                     for r in rows if r["category"].startswith("REF_SPEAKER_MISSED"))
        missed_quiet = sum((min(r["end_ms"], turn["end_ms"]) - max(r["start_ms"], turn["start_ms"]))
                           for r in rows if r["category"] == "REF_SPEAKER_MISSED_PCM_QUIET")
        report.append(dict(reference_index=index, speaker=turn["speaker_id"],
                           start_ms=turn["start_ms"], end_ms=turn["end_ms"],
                           scored_ms=scored, missed_ms=missed,
                           missed_pcm_quiet45_ms=missed_quiet))
    return report


def audit(wav, reference_path, tsv, out):
    ref = clamp_reference(json.loads(reference_path.read_text(encoding="utf-8")))
    if hashlib.sha256(wav.read_bytes()).hexdigest() != ref["audio_sha256"]:
        raise ValueError("WAV/reference SHA-256 mismatch")
    samples = read_wav(wav)
    duration = ref["audio_duration_ms"]
    if abs(len(samples) / 16 - duration) > 1:
        raise ValueError("WAV/reference duration mismatch")
    reference = ref["diarization"]
    hypothesis = read_tsv(tsv, duration)
    score = der(reference, hypothesis, duration, 250, False)
    energies = energy_frames(samples)
    totals, events = classify(reference, hypothesis, duration, 250, energies, score["hypothesis_to_reference"])
    assert (totals["reference_ms"], totals["missed_ms"], totals["false_alarm_ms"], totals["confusion_ms"]) == (
        score["reference_speaker_ms"], score["miss_ms"], score["false_alarm_ms"], score["confusion_ms"]), (
        totals, score)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "frames.csv").open("w", newline="", encoding="utf-8") as f:
        fields = ["start_ms", "end_ms", "excluded", "reference", "predicted", "predicted_mapped",
                  "dbfs", "category", "miss_slots", "confusion_slots"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(events)
    summary = dict(source_audio_sha256=ref["audio_sha256"],
                   reference_sha256=hashlib.sha256(reference_path.read_bytes()).hexdigest(),
                   hypothesis_sha256=hashlib.sha256(tsv.read_bytes()).hexdigest(),
                   scope="COARSE_TTS_REFERENCE_PCM_ENERGY_ONLY_NOT_SPEECH_GOLD",
                   collar_radius_ms=250, threshold_dbfs=dict(quiet=LOW_DB, energetic=HIGH_DB),
                   score=score, totals=totals,
                   per_reference=per_reference(reference, events),
                   caveats=["PCM energy alone does not prove human speech, silence or voice identity.",
                            "Reference labels are coarse TTS clip intervals; high reference misses may be annotation artifacts.",
                            "Predicted turns reflect saved raw C2 output; ASR/VAD evidence is not inferred from them."])
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(label=tsv.stem, der=round(score["rate"], 5),
                          missed_ms=score["miss_ms"], quiet45_ms=totals["missed_quiet45_ms"],
                          quiet35_ms=totals["missed_quiet35_ms"],
                          loud35_ms=totals["missed_loud35_ms"]), ensure_ascii=False))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wav", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--turns", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    a = parser.parse_args()
    audit(a.wav, a.reference, a.turns, a.out)


if __name__ == "__main__":
    main()
