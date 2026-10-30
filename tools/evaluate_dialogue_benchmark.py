"""Score externally annotated text; clip extents must never become fake DER truth."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from score_transcript import evaluate, validate_segments


def validate_turns(raw, audio_ms):
    turns = validate_segments(raw, audio_ms)
    for turn in turns:
        if type(turn.get("attribution_eligible")) is not bool:
            raise ValueError("Raw attribution eligibility must be boolean")
        if turn["attribution_eligible"] and turn["speaker_id"] is None:
            raise ValueError("Eligible speech requires an inferred speaker")
    return turns


def recurrence(reference, raw):
    turns = validate_turns(raw, reference["audio_duration_ms"])
    # Dominant eligible cluster per externally annotated source clip. This is
    # NOT true speech-boundary scoring or diarization error rate.
    assignments = []
    for clip in reference["text_segments"]:
        weights = {}
        for turn in turns:
            if turn["attribution_eligible"] and turn["speaker_id"] is not None:
                overlap = max(0, min(clip["end_ms"], turn["end_ms"]) -
                              max(clip["start_ms"], turn["start_ms"]))
                weights[turn["speaker_id"]] = weights.get(turn["speaker_id"], 0) + overlap
        positive = sorted(((v, k) for k, v in weights.items() if v > 0), reverse=True)
        assignments.append(positive[0][1] if positive and
                           (len(positive) == 1 or positive[0][0] > positive[1][0]) else None)
    determined = len(assignments) == 3 and all(s is not None for s in assignments)
    return {"method": "dominant eligible cluster per source clip; not speech-boundary truth",
            "hypothesis_clusters": assignments,
            "status": "PASS" if determined and assignments[0] == assignments[2] != assignments[1]
            else "FAIL" if determined else "UNDETERMINED"}


def assess(reference, hypothesis):
    if "diarization" in reference:
        raise ValueError("This fixture has clip extents only, no independent speech boundaries")
    report = evaluate(reference, hypothesis)
    report["recurrence_probe"] = recurrence(reference, hypothesis.get("diarization", []))
    # This deliberately does NOT use word-level ASR output to choose a threshold.
    # Preserve the untouched production baseline and the externally frozen fixture.
    sweep = hypothesis.get("clustering_sweep")
    if sweep is not None:
        expected = [0.5, 0.65, 0.8, 0.9]
        if not isinstance(sweep, list) or len(sweep) != len(expected):
            raise ValueError("Speaker threshold sweep must contain exactly four experiments")
        outcomes = []
        for trial, threshold in zip(sweep, expected):
            if not isinstance(trial, dict):
                raise ValueError("Malformed speaker threshold trial")
            value = trial.get("threshold")
            if type(value) not in (int, float) or not abs(value - threshold) < 1e-5:
                raise ValueError("Unrecognized or reordered clustering threshold")
            duration = trial.get("process_ms")
            if type(duration) is not int or duration < 0:
                raise ValueError("Invalid clustering experiment duration")
            turns = trial.get("diarization")
            if not isinstance(turns, list):
                raise ValueError("Missing clustering experiment diarization")
            validated = validate_turns(turns, reference["audio_duration_ms"])
            outcome = recurrence(reference, validated)
            outcomes.append({"threshold": threshold, "recurrence_probe": outcome,
                "eligible_speaker_count": len({t["speaker_id"] for t in validated
                    if t["attribution_eligible"] and t["speaker_id"] is not None}),
                "unknown_turns": sum(not t["attribution_eligible"] for t in validated),
                "process_ms": duration})
        # The last experiment must be the exact production .9 result. A mismatch
        # would silently compare different recordings/inference runs.
        if sweep[-1]["diarization"] != hypothesis.get("diarization"):
            raise ValueError("Production baseline differs from threshold sweep")
        if outcomes[-1]["recurrence_probe"] != report["recurrence_probe"]:
            raise ValueError("Baseline speaker recurrence is inconsistent")
        report["clustering_sweep"] = outcomes
        report["clustering_experiment_status"] = "EXPERIMENT_ONLY_NO_AUTO_SELECTION"
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
