"""Score externally annotated text; clip extents must never become fake DER truth."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from score_transcript import evaluate, validate_segments


def assess(reference, hypothesis):
    if "diarization" in reference:
        raise ValueError("This fixture has clip extents only, no independent speech boundaries")
    report = evaluate(reference, hypothesis)
    turns = validate_segments(hypothesis.get("diarization", []), reference["audio_duration_ms"])
    if any(type(turn.get("attribution_eligible")) is not bool for turn in turns):
        raise ValueError("Raw attribution eligibility must be boolean")
    # Report dominant eligible cluster per source clip for this narrow A-B-A
    # recurrence probe. This is not DER, calibrated confidence or personal ID.
    assignments = []
    for clip in reference["text_segments"]:
        weights = {}
        for turn in turns:
            if turn.get("attribution_eligible") and turn.get("speaker_id") is not None:
                overlap = max(0, min(clip["end_ms"], turn["end_ms"]) - max(clip["start_ms"], turn["start_ms"]))
                weights[turn["speaker_id"]] = weights.get(turn["speaker_id"], 0) + overlap
        positive = sorted(((v, k) for k, v in weights.items() if v > 0), reverse=True)
        assignments.append(positive[0][1] if positive and (len(positive) == 1 or positive[0][0] > positive[1][0]) else None)
    determined = len(assignments) == 3 and all(s is not None for s in assignments)
    report["recurrence_probe"] = {"method": "dominant eligible cluster per source clip; not speech-boundary truth",
        "hypothesis_clusters": assignments, "status": "PASS" if determined and assignments[0] == assignments[2] != assignments[1]
        else "FAIL" if determined else "UNDETERMINED"}
    report["evaluation_scope"] = "Three composed acted utterances from external test.csv; not natural conversation or a representative corpus benchmark"
    report["metric_availability"] = "PARTIAL_NO_DER_REFERENCE"
    report["quality_gate"] = "NO_COMPETITION_ACCURACY_THRESHOLD_DEFINED"
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    output = args.directory / "scores.json"
    try:
        rbytes, hbytes = [(args.directory / n).read_bytes() for n in ["reference.json", "hypothesis.json"]]
        invocation = json.loads((args.directory / "invocation.json").read_bytes())["id"]
        if not isinstance(invocation, str) or not re.fullmatch(r"[0-9a-f]{32}", invocation):
            raise ValueError("Invalid invocation identity")
        hypothesis = json.loads(hbytes)
        if not isinstance(hypothesis, dict) or hypothesis.get("benchmark_invocation") != invocation:
            raise ValueError("Device output is missing or belongs to a different invocation")
        report = assess(json.loads(rbytes), hypothesis)
        report["benchmark_invocation"] = invocation
        report["reference_sha256"] = hashlib.sha256(rbytes).hexdigest()
        report["hypothesis_sha256"] = hashlib.sha256(hbytes).hexdigest()
        code = 0 if report["wer"]["status"] == "SCORED" else 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        report, code = {"status": "ERROR", "reason": str(error)}, 1
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
