"""Score frozen Android C0/C2 turns against independent Russian generator RTTM."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from score_transcript import der  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--split", choices=("development", "holdout"), default="development")
    args = parser.parse_args()
    folder = ROOT / ".local/androidTestAssets/rubook-probe"
    lock = json.loads((folder / "lock.json").read_text(encoding="utf-8"))
    expected = {row["id"]: row for row in lock["cases"] if row["split"] == args.split}
    runs = json.loads(args.evidence.read_text(encoding="utf-8-sig"))["runs"]
    assert len(runs) == len(expected) * 2
    assert {(r["case"], r["backend"]) for r in runs} == {
        (case, backend) for case in expected for backend in ("c0", "c2")}
    totals = {backend: {"errors": 0, "pad200_errors": 0, "reference": 0,
                        "model_ms": 0, "speakers_correct": 0}
              for backend in ("c0", "c2")}
    for run in runs:
        case = run["case"]
        wav = folder / f"{case}.wav"
        ref_file = folder / f"{case}.ref.json"
        assert hashlib.sha256(wav.read_bytes()).hexdigest() == run["audio_sha256"] == expected[case]["audio_sha256"]
        assert hashlib.sha256(ref_file.read_bytes()).hexdigest() == expected[case]["reference_sha256"]
        reference = json.loads(ref_file.read_text(encoding="utf-8"))
        assert reference["audio_sha256"] == run["audio_sha256"]
        assert reference["audio_duration_ms"] == run["audio_ms"] == 60000
        turns = [{"start_ms": t["start_ms"], "end_ms": t["end_ms"],
                  "speaker_id": f"h{t['speaker_id']}"} for t in run["turns"]]
        score = der(reference["diarization"], turns, 60000, collar_ms=250, skip_overlap=False)
        errors = score["miss_ms"] + score["false_alarm_ms"] + score["confusion_ms"]
        padded = [{**turn, "start_ms": max(0, turn["start_ms"] - 200),
                   "end_ms": min(60000, turn["end_ms"] + 200)} for turn in turns]
        padded_score = der(reference["diarization"], padded, 60000, collar_ms=250, skip_overlap=False)
        padded_errors = padded_score["miss_ms"] + padded_score["false_alarm_ms"] + padded_score["confusion_ms"]
        backend = run["backend"]
        t = totals[backend]
        t["errors"] += errors
        t["pad200_errors"] += padded_errors
        t["reference"] += score["reference_speaker_ms"]
        t["model_ms"] += run["load_ms"] + run["infer_ms"]
        t["speakers_correct"] += run["speaker_count"] == expected[case]["n_speakers"]
        print(case, backend, "DER", f"{score['rate']:.3%}",
              "DER_pad200", f"{padded_score['rate']:.3%}",
              "miss/FA/conf", score["miss_ms"], score["false_alarm_ms"], score["confusion_ms"],
              "speakers", run["speaker_count"], "/", expected[case]["n_speakers"],
              "model_load_plus_infer_ms", run["load_ms"] + run["infer_ms"])
    for backend, t in totals.items():
        print("TOTAL", backend, "DER", f"{t['errors'] / t['reference']:.3%}",
              "DER_pad200", f"{t['pad200_errors'] / t['reference']:.3%}",
              "speaker_count_correct", f"{t['speakers_correct']}/{len(expected)}",
              "model_load_plus_infer_ms", t["model_ms"])


if __name__ == "__main__":
    main()
