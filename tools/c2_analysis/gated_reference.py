"""Energy-gated DataHive reference: removes VAD-labelled frames whose own channel is practically silent.

Defect found on ru_000001: the per-channel Silero reference labels frames at about -86 dBFS (62% below -60 dBFS) as speech.
The gate is fixed before scoring and not tuned on any model: a labelled frame stays speech only if its own channel is
above GATE_ABSOLUTE_DBFS and at least GATE_ABOVE_FLOOR_DB above that channel's 10th-percentile level. It only removes
labels; speech the VAD missed is not added, so a remaining false alarm can still be reference error.

python tools/c2_analysis/gated_reference.py --root ROOT --out docs/evidence/nemotron-android/gated-reference.json
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analyze_datahive import level_db, stereo, turns_tsv  # noqa: E402
from score_transcript import der  # noqa: E402

GATE_ABSOLUTE_DBFS = -60.0
GATE_ABOVE_FLOOR_DB = 15.0
MIN_TURN_MS = 250
MERGE_GAP_MS = 200
LABELS = ("caller", "callee")


def gate(turns, levels, duration):
    """Turns with silent frames removed, short pieces dropped and close pieces merged, as in the original VAD rules."""
    out = []
    for index, label in enumerate(LABELS):
        level = levels[index]
        threshold = max(GATE_ABSOLUTE_DBFS, float(np.percentile(level, 10)) + GATE_ABOVE_FLOOR_DB)
        keep = np.zeros(len(level), dtype=bool)
        for t in turns:
            if t["speaker_id"] == label:
                keep[t["start_ms"] // 20:t["end_ms"] // 20] = True
        keep &= level > threshold
        pieces, start = [], None
        for i, on in enumerate(np.append(keep, False)):
            if on and start is None:
                start = i
            elif not on and start is not None:
                pieces.append([start * 20, i * 20])
                start = None
        merged = []
        for a, b in pieces:
            if merged and a - merged[-1][1] <= MERGE_GAP_MS:
                merged[-1][1] = b
            else:
                merged.append([a, b])
        out += [{"start_ms": a, "end_ms": min(b, duration), "speaker_id": label} for a, b in merged if b - a >= MIN_TURN_MS]
    return sorted(out, key=lambda t: t["start_ms"])


def errors(d):
    return d["miss_ms"] + d["false_alarm_ms"] + d["confusion_ms"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    corpus = args.root / "data/corpus"
    names = sorted(p.name.removesuffix(".ref.json") for p in corpus.glob("datahive-*.ref.json"))
    rows, pooled = [], {s: {"vad": [0, 0], "gated": [0, 0]} for s in ("C0", "C1", "C2")}
    for case in names:
        reference = json.loads((corpus / f"{case}.ref.json").read_text(encoding="utf-8"))
        duration = reference["audio_duration_ms"]
        channels = stereo(args.ffmpeg, args.root / "data/raw/datahive" / f"{case.removeprefix('datahive-')}.mp3")
        count = duration // 20
        levels = [level_db(channels[:, i])[:count] for i in range(2)]
        gated = gate(reference["diarization"], levels, duration)
        before = sum(t["end_ms"] - t["start_ms"] for t in reference["diarization"])
        after = sum(t["end_ms"] - t["start_ms"] for t in gated)
        row = {"case": case, "vad_label_ms": before, "gated_label_ms": after, "removed_share": round(1 - after / before, 3) if before else None,
               "gated_reference_sha256": hashlib.sha256(json.dumps(gated, sort_keys=True).encode()).hexdigest()}
        for system in ("C0", "C1", "C2"):
            hypothesis = turns_tsv(args.root / "results-v2" / system / f"{case}.tsv")
            a, b = der(reference["diarization"], hypothesis, duration, 250, False), der(gated, hypothesis, duration, 250, False)
            row[system] = {"der_vad": round(a["rate"], 4), "der_gated": round(b["rate"], 4),
                           "gated_components_ms": {k: b[k] for k in ("miss_ms", "false_alarm_ms", "confusion_ms")}}
            pooled[system]["vad"][0] += errors(a)
            pooled[system]["vad"][1] += a["reference_speaker_ms"]
            pooled[system]["gated"][0] += errors(b)
            pooled[system]["gated"][1] += b["reference_speaker_ms"]
        rows.append(row)
        print(case, row["removed_share"], {s: (row[s]["der_vad"], row[s]["der_gated"]) for s in ("C0", "C2")}, flush=True)
    summary = {s: {k: round(v[0] / v[1], 4) for k, v in pooled[s].items()} for s in pooled}
    report = {"scope": "Automatic reference repair; no human listening. Collar 250 ms, overlap scored.",
              "gate": {"absolute_dbfs": GATE_ABSOLUTE_DBFS, "above_channel_floor_db": GATE_ABOVE_FLOOR_DB, "min_turn_ms": MIN_TURN_MS, "merge_gap_ms": MERGE_GAP_MS},
              "pooled_der": summary, "recordings": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
