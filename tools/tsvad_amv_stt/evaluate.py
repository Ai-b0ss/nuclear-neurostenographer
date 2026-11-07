import argparse
import hashlib
import json
from pathlib import Path


def _intervals(document, duration_ms):
    result = []
    for interval in document.get("diarization", []):
        start = interval["start_ms"]
        end = interval["end_ms"]
        speaker = interval["speaker_id"]
        if type(start) is not int or type(end) is not int:
            raise ValueError("Interval bounds must be integer milliseconds")
        if start < 0 or start >= end or end > duration_ms:
            raise ValueError("Interval is outside the recording or empty")
        if speaker is None:
            raise ValueError("Activity scoring requires known speaker IDs")
        result.append((start, end, speaker))
    return result


def _active(intervals, start, end):
    return {speaker for a, b, speaker in intervals if a < end and b > start}


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def score_activity(reference, hypothesis):
    if "manual" not in str(reference.get("annotation_source", "")).casefold():
        raise ValueError("Reference must explicitly declare a manual annotation_source")
    duration_ms = reference["audio_duration_ms"]
    if type(duration_ms) is not int or duration_ms <= 0:
        raise ValueError("audio_duration_ms must be a positive integer")
    if hypothesis.get("audio_duration_ms", duration_ms) != duration_ms:
        raise ValueError("Reference and hypothesis durations differ")
    ref = _intervals(reference, duration_ms)
    hyp = _intervals(hypothesis, duration_ms)
    points = sorted({0, duration_ms, *[x for a, b, _ in ref + hyp for x in (a, b)]})

    totals = {
        "reference_speech_ms": 0,
        "hypothesis_speech_ms": 0,
        "speech_both_ms": 0,
        "reference_overlap_ms": 0,
        "hypothesis_overlap_ms": 0,
        "overlap_both_ms": 0,
    }
    speakers = sorted({speaker for _, _, speaker in ref + hyp}, key=lambda speaker: (type(speaker).__name__, str(speaker)))
    per_speaker = {
        speaker: {"reference_ms": 0, "hypothesis_ms": 0, "both_ms": 0}
        for speaker in speakers
    }
    for start, end in zip(points, points[1:]):
        duration = end - start
        ref_active = _active(ref, start, end)
        hyp_active = _active(hyp, start, end)
        totals["reference_speech_ms"] += duration * bool(ref_active)
        totals["hypothesis_speech_ms"] += duration * bool(hyp_active)
        totals["speech_both_ms"] += duration * bool(ref_active and hyp_active)
        totals["reference_overlap_ms"] += duration * (len(ref_active) >= 2)
        totals["hypothesis_overlap_ms"] += duration * (len(hyp_active) >= 2)
        totals["overlap_both_ms"] += duration * (len(ref_active) >= 2 and len(hyp_active) >= 2)
        for speaker in speakers:
            in_ref = speaker in ref_active
            in_hyp = speaker in hyp_active
            per_speaker[speaker]["reference_ms"] += duration * in_ref
            per_speaker[speaker]["hypothesis_ms"] += duration * in_hyp
            per_speaker[speaker]["both_ms"] += duration * (in_ref and in_hyp)

    miss_ms = totals["reference_speech_ms"] - totals["speech_both_ms"]
    false_alarm_ms = totals["hypothesis_speech_ms"] - totals["speech_both_ms"]
    speaker_activity = []
    for speaker, counts in per_speaker.items():
        speaker_activity.append({
            "speaker_id": speaker,
            **counts,
            "miss_ms": counts["reference_ms"] - counts["both_ms"],
            "false_alarm_ms": counts["hypothesis_ms"] - counts["both_ms"],
            "recall": _ratio(counts["both_ms"], counts["reference_ms"]),
            "precision": _ratio(counts["both_ms"], counts["hypothesis_ms"]),
        })
    return {
        "status": "SCORED",
        "protocol": "exact interval boundaries; union speech; >=2 distinct speakers for overlap; literal speaker IDs",
        "audio_duration_ms": duration_ms,
        **totals,
        "miss_ms": miss_ms,
        "false_alarm_ms": false_alarm_ms,
        "speech_recall": _ratio(totals["speech_both_ms"], totals["reference_speech_ms"]),
        "speech_precision": _ratio(totals["speech_both_ms"], totals["hypothesis_speech_ms"]),
        "activity_error_rate": _ratio(miss_ms + false_alarm_ms, totals["reference_speech_ms"]),
        "overlap_recall": _ratio(totals["overlap_both_ms"], totals["reference_overlap_ms"]),
        "overlap_precision": _ratio(totals["overlap_both_ms"], totals["hypothesis_overlap_ms"]),
        "speaker_activity": speaker_activity,
    }


def evaluate_pair(reference, baseline, candidate):
    baseline_score = score_activity(reference, baseline)
    candidate_score = score_activity(reference, candidate)
    delta = {}
    for metric in ("activity_error_rate", "speech_recall", "speech_precision", "overlap_recall", "overlap_precision"):
        before = baseline_score[metric]
        after = candidate_score[metric]
        delta[metric] = after - before if before is not None and after is not None else None
    return {
        "schema_version": 1,
        "reference_sha256": hashlib.sha256(
            json.dumps(reference, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "baseline": baseline_score,
        "candidate": candidate_score,
        "candidate_minus_baseline": delta,
    }


def main():
    parser = argparse.ArgumentParser(description="Score AMV-STT interval activity against a common manual reference")
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    report = evaluate_pair(load(args.reference), load(args.baseline), load(args.candidate))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
