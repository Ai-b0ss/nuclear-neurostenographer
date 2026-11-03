"""Robustness checks around the main C0/C1 table; they do not replace it.

1. C0 threshold sweep on the same recordings. It may flatter C0 because it is tuned on the test data.
2. DataHive DER against a second reference: per-channel energy VAD instead of Silero.
3. DER parity of tools/score_transcript.py with pyannote.metrics.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
from pyannote.core import Annotation, Segment
from pyannote.metrics.diarization import DiarizationErrorRate

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
from score_transcript import der  # noqa: E402


def read_turns(path):
    rows = [line.split("\t") for line in path.read_text(encoding="ascii").splitlines() if line.strip()]
    return [{"start_ms": int(a), "end_ms": int(b), "speaker_id": None if int(c) < 0 else f"h{c}"} for a, b, c in rows]


def pooled(cases, folder, corpus, collar=250, reference_override=None):
    totals = dict(miss_ms=0, false_alarm_ms=0, confusion_ms=0, reference_speaker_ms=0)
    exact = count_error = n = 0
    for case in cases:
        path = folder / f"{case['id']}.tsv"
        if not path.exists():
            continue
        turns = read_turns(path)
        reference = (reference_override or {}).get(case["id"]) or json.loads((corpus / f"{case['id']}.ref.json").read_text(encoding="utf-8"))["diarization"]
        result = der(reference, turns, case["duration_ms"], collar, False)
        for key in totals:
            totals[key] += result[key]
        speakers = len({t["speaker_id"] for t in turns if t["speaker_id"]})
        exact += speakers == case["speakers"]
        count_error += abs(speakers - case["speakers"])
        n += 1
    errors = totals["miss_ms"] + totals["false_alarm_ms"] + totals["confusion_ms"]
    denominator = totals["reference_speaker_ms"] or 1
    return {"files": n, "der_percent": round(100 * errors / denominator, 2), "confusion_percent": round(100 * totals["confusion_ms"] / denominator, 2),
            "exact_speaker_count": exact, "mean_abs_count_error": round(count_error / max(n, 1), 2)}


def energy_reference(raw, name, ffmpeg, duration):
    data = subprocess.run([ffmpeg, "-v", "error", "-ss", "30", "-t", "120", "-i", str(raw / name), "-ar", "16000", "-f", "f32le", "-"],
                          capture_output=True, check=True).stdout
    stereo = np.frombuffer(data, dtype=np.float32).reshape(-1, 2)
    turns = []
    frame = 320
    for index, label in enumerate(("caller", "callee")):
        x = stereo[:, index]
        count = len(x) // frame
        rms = np.sqrt(np.mean(x[:count * frame].reshape(count, frame) ** 2, axis=1) + 1e-12)
        db = 20 * np.log10(rms + 1e-9)
        active = db > max(np.percentile(db, 95) - 30, np.percentile(db, 10) + 10)
        start = last = None
        for i, on in enumerate(active):
            if on:
                start = i if start is None else start
                last = i
            elif start is not None and i - last > 15:
                if (last - start) >= 12:
                    turns.append({"start_ms": start * 20, "end_ms": min((last + 1) * 20, duration), "speaker_id": label})
                start = None
        if start is not None and (last - start) >= 12:
            turns.append({"start_ms": start * 20, "end_ms": min((last + 1) * 20, duration), "speaker_id": label})
    return turns


def annotation(turns):
    result = Annotation()
    for i, t in enumerate(turns):
        result[Segment(t["start_ms"] / 1000, t["end_ms"] / 1000), i] = t["speaker_id"] or f"unk{i}"
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--thresholds", default="085,090,095")
    args = parser.parse_args()
    corpus = args.root / "data/corpus"
    cases = json.loads((args.evidence / "corpus-manifest.json").read_text(encoding="utf-8"))["cases"]
    groups = {"datahive": [c for c in cases if c["group"] == "datahive"], "rubook": [c for c in cases if c["group"] == "rubook"]}
    report = {"threshold_sweep": {}, "note": "Sweep uses the test recordings, so it can only flatter C0"}
    for group, members in groups.items():
        rows = {"C0 t=0.80 (production)": pooled(members, args.root / "results/C0", corpus)}
        for tag in args.thresholds.split(","):
            rows[f"C0 t=0.{tag[1:]}"] = pooled(members, args.root / f"results-t{tag}/C0", corpus)
        rows["C1 fp32"] = pooled(members, args.root / "results/C1", corpus)
        rows["C2 int8"] = pooled(members, args.root / "results/C2", corpus)
        report["threshold_sweep"][group] = rows
    alt = {c["id"]: energy_reference(args.root / "data/raw/datahive", c["id"].removeprefix("datahive-") + ".mp3", args.ffmpeg, c["duration_ms"]) for c in groups["datahive"]}
    report["datahive_energy_reference"] = {s: pooled(groups["datahive"], args.root / f"results/{s}", corpus, reference_override=alt) for s in ("C0", "C1", "C2")}
    parity = []
    for case in groups["datahive"][:5] + groups["rubook"][:5]:
        reference = json.loads((corpus / f"{case['id']}.ref.json").read_text(encoding="utf-8"))["diarization"]
        turns = [t for t in read_turns(args.root / f"results/C2/{case['id']}.tsv")]
        ours = der(reference, turns, case["duration_ms"], 0, False)["rate"]
        theirs = DiarizationErrorRate(collar=0.0, skip_overlap=False)(annotation(reference), annotation(turns))
        parity.append({"case": case["id"], "score_transcript": round(ours, 5), "pyannote_metrics": round(float(theirs), 5)})
    report["der_parity_collar0"] = {"max_abs_difference": max(abs(p["score_transcript"] - p["pyannote_metrics"]) for p in parity), "cases": parity}
    (args.evidence / "sensitivity.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
