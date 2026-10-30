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
    # Dominant eligible cluster per externally annotated source clip. Clip
    # extents are NOT manually annotated speech boundaries, so this is never DER.
    clips = reference["text_segments"]
    assignments = []
    for clip in clips:
        weights = {}
        for turn in turns:
            if turn["attribution_eligible"] and turn["speaker_id"] is not None:
                overlap = max(0, min(clip["end_ms"], turn["end_ms"]) -
                              max(clip["start_ms"], turn["start_ms"]))
                weights[turn["speaker_id"]] = weights.get(turn["speaker_id"], 0) + overlap
        positive = sorted(((v, k) for k, v in weights.items() if v > 0), reverse=True)
        assignments.append(positive[0][1] if positive and
                           (len(positive) == 1 or positive[0][0] > positive[1][0]) else None)
    truth = [clip["speaker_id"] for clip in clips]
    pairs = [(i, j) for i in range(len(truth)) for j in range(i + 1, len(truth))]
    same = [(i, j) for i, j in pairs if truth[i] == truth[j]]
    different = [(i, j) for i, j in pairs if truth[i] != truth[j]]
    # With no recurrence or no contrasting speaker, the probe is undefined.
    determined = bool(same and different) and all(x is not None for x in assignments)
    consistent = determined and all((assignments[i] == assignments[j]) ==
                                    (truth[i] == truth[j]) for i, j in pairs)
    return {"method": "pairwise clip-level speaker recurrence using eligible raw diarization; not DER",
            "hypothesis_clusters": assignments, "total_clips": len(clips),
            "same_speaker_pairs": len(same), "different_speaker_pairs": len(different),
            "status": "PASS" if consistent else "FAIL" if determined else "UNDETERMINED"}


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
        # Model-generated baseline must be exactly one trial, never a guessed
        # post-hoc "best" score. This also guards a later default change.
        baseline = hypothesis.get("production_clustering_threshold")
        if type(baseline) not in (int, float):
            raise ValueError("Missing production clustering threshold")
        indexes = [i for i, v in enumerate(expected) if abs(v - baseline) < 1e-5]
        if len(indexes) != 1:
            raise ValueError("Unknown production clustering threshold")
        selected = indexes[0]
        if sweep[selected]["diarization"] != hypothesis.get("diarization"):
            raise ValueError("Production baseline differs from threshold sweep")
        if outcomes[selected]["recurrence_probe"] != report["recurrence_probe"]:
            raise ValueError("Baseline speaker recurrence is inconsistent")
        report["production_clustering_threshold"] = expected[selected]
        report["clustering_sweep"] = outcomes
        report["clustering_experiment_status"] = "EXPERIMENT_ONLY_NO_AUTO_SELECTION"
    suite = reference.get("evaluation_suite", "development")
    if suite not in ("development", "holdout"):
        raise ValueError("Unknown evaluation suite")
    if hypothesis.get("benchmark_suite", "development") != suite:
        raise ValueError("Reference and device-output benchmark suites disagree")
    if suite == "holdout":
        if sweep is not None:
            raise ValueError("Holdout must not run an exploratory threshold sweep")
        if abs(hypothesis.get("production_clustering_threshold", -1) - 0.8) > 1e-5:
            raise ValueError("Holdout must use preregistered production threshold 0.8")
        if len(reference["text_segments"]) != 4:
            raise ValueError("Holdout must contain four pinned independent clips")
        report["evaluation_scope"] = "Four unused acted Russian clips, M-D-M-D, disjoint from 3-clip development probe; same dataset, no clean natural-dialogue DER"
        report["holdout_scope"] = "DISJOINT_AUDIO_SAME_DATASET_NONBLIND_TEST"
    else:
        report["evaluation_scope"] = "Three composed acted utterances from external test.csv; reused in threshold development, not held out"
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
