"""Score Android C2 AMI evidence and a predeclared turn-padding candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from score_transcript import der  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("meeting", choices=("ES2004a", "IS1009a"))
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    folder = ROOT / ".local/androidTestAssets/ami-meeting"
    stem = f"{args.meeting}-360-600"
    ref = json.loads((folder / f"{stem}.reference.json").read_text())
    hyp = json.loads(args.evidence.read_text(encoding="utf-8-sig"))
    digest = hashlib.sha256((folder / f"{stem}.wav").read_bytes()).hexdigest()
    if digest != ref["audio_sha256"] or digest != hyp["audio_sha256"]:
        raise ValueError("Evidence and reference audio hash mismatch")
    duration = ref["audio_duration_ms"]
    if hyp["audio_duration_ms"] != duration or hyp["backend"] != "c2":
        raise ValueError("Unexpected Android evidence")
    print(stem, "C2 infer_ms", hyp["infer_ms"], "peak_total_pss_kib", hyp["peak_total_pss_kib"])
    for padding in (0, 150, 300):
        turns = [{"start_ms": max(0, t["start_ms"] - padding),
                  "end_ms": min(duration, t["end_ms"] + padding),
                  "speaker_id": t["speaker_id"]} for t in hyp["diarization"]]
        for skip_overlap in (False, True):
            score = der(ref["diarization"], turns, duration, collar_ms=250,
                        skip_overlap=skip_overlap)
            print("padding_ms", padding, "skip_overlap", skip_overlap,
                  "DER", f"{score['rate']:.3%}", "miss/FA/conf_ms",
                  score["miss_ms"], score["false_alarm_ms"], score["confusion_ms"],
                  "reference_speaker_ms", score["reference_speaker_ms"])


if __name__ == "__main__":
    main()
