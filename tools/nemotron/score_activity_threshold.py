"""Score debug-only Android C2 activity-logit sweep against pinned manual/RTTM turns."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from score_transcript import der  # noqa: E402

CASES = {
    ("ami-meeting", "ES2004a-360-600"),
    ("ami-meeting", "IS1009a-360-600"),
    ("rubook-probe", "rec_0001"),
    ("rubook-probe", "rec_0275"),
}
THRESHOLDS = {0.0, -0.25, -0.5}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    runs = json.loads(args.evidence.read_text(encoding="utf-8-sig"))["runs"]
    if len(runs) != len(CASES) * len(THRESHOLDS):
        raise ValueError("Incomplete threshold sweep")
    seen = set()
    for run in runs:
        key = (run["suite"], run["case"])
        threshold = run["activity_threshold"]
        if key not in CASES or threshold not in THRESHOLDS or (key, threshold) in seen:
            raise ValueError("Unexpected or repeated run")
        seen.add((key, threshold))
        folder = ROOT / ".local/androidTestAssets" / run["suite"]
        wav = folder / (run["case"] + ".wav")
        ref = folder / (run["case"] + (".reference.json" if run["suite"] == "ami-meeting" else ".ref.json"))
        reference = json.loads(ref.read_text())
        digest = hashlib.sha256(wav.read_bytes()).hexdigest()
        duration = run["audio_ms"]
        if digest != run["audio_sha256"] or digest != reference["audio_sha256"] or \
                duration != reference["audio_duration_ms"]:
            raise ValueError("Audio/reference identity mismatch")
        turns = run["turns"]
        padded = [{"start_ms": max(0, t["start_ms"] - 150),
                   "end_ms": min(duration, t["end_ms"] + 150),
                   "speaker_id": t["speaker_id"]} for t in turns]
        raw_score = der(reference["diarization"], turns, duration, collar_ms=250)
        padded_score = der(reference["diarization"], padded, duration, collar_ms=250)
        print(run["case"], threshold,
              "raw DER", f"{raw_score['rate']:.3%}",
              "pad150 DER", f"{padded_score['rate']:.3%}",
              "speakers", len({t["speaker_id"] for t in turns}),
              "infer_ms", run["infer_ms"])


if __name__ == "__main__":
    main()
