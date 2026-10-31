"""Small offline scorer, original stdlib implementation; no model/audio downloads.

Metrics follow WER / concatenated minimum-permutation WER and time-based DER.
Chunk text intervals are NEVER used as diarization ground truth or predictions.
See docs/BENCHMARKS.md for schema, conventions and intentional limitations.
"""
import argparse
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata

NORMALIZATION = "NFKC, lowercase, yo->ye, Unicode alphanumeric tokens; no number expansion"
MAX_SPEAKERS = 12


def words(text):
    if not isinstance(text, str):
        raise ValueError("Text must be a string")
    return re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", text).lower().replace("ё", "е"))


def edit_counts(reference, hypothesis):
    # Linear memory; ties prefer substitution, then deletion, then insertion.
    row = [(i, 0, 0, i) for i in range(len(hypothesis) + 1)]  # errors,S,D,I
    for i, r in enumerate(reference, 1):
        out = [(i, 0, i, 0)]
        for j, h in enumerate(hypothesis, 1):
            if r == h:
                out.append(row[j - 1])
            else:
                e, s, d, ins = row[j - 1]
                a = (e + 1, s + 1, d, ins)
                e, s, d, ins = row[j]
                b = (e + 1, s, d + 1, ins)
                e, s, d, ins = out[-1]
                c = (e + 1, s, d, ins + 1)
                out.append(min((a, b, c), key=lambda x: x[0]))
        row = out
    e, s, d, ins = row[-1]
    return {"errors": e, "substitutions": s, "deletions": d, "insertions": ins,
            "reference_words": len(reference), "rate": e / len(reference) if reference else None,
            "status": "SCORED" if reference else "UNDEFINED_EMPTY_REFERENCE"}


def assignment(cost):
    """Exact minimum-cost square assignment; bounded to avoid factorial work."""
    n = len(cost)
    if n > MAX_SPEAKERS or any(len(row) != n for row in cost):
        raise ValueError("Assignment requires square matrix with at most 12 speakers")

    @lru_cache(None)
    def solve(mask):
        i = mask.bit_count()
        if i == n:
            return 0, ()
        best = None
        for j in range(n):
            if not mask & (1 << j):
                rest, path = solve(mask | (1 << j))
                candidate = cost[i][j] + rest, (j,) + path
                if best is None or candidate < best:
                    best = candidate
        return best
    return solve(0)


def speaker(value, allow_unknown=False):
    if value is None and allow_unknown:
        return
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Speaker must be a nonempty string (reference cannot be unknown)")


def validate_segments(items, duration, text=False, reference=False):
    if not isinstance(items, list):
        raise ValueError("Segments must be a list")
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each segment must be an object")
        start, end = item["start_ms"], item["end_ms"]
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= duration:
            raise ValueError("Invalid integer millisecond interval")
        if "speaker_id" not in item:
            raise ValueError("Missing speaker_id; use null for unknown")
        speaker(item["speaker_id"], allow_unknown=not reference)
        if text:
            words(item["text"])
            if "attribution_reliable" in item and type(item["attribution_reliable"]) is not bool:
                raise ValueError("attribution_reliable must be a boolean")
    return sorted(items, key=lambda s: (s["start_ms"], s["end_ms"]))


def cpwer(reference, hypothesis):
    # Missing identity is not silently turned into a conveniently matched speaker.
    if any(words(s["text"]) and (s["speaker_id"] is None or
           s.get("attribution_reliable") is False) for s in hypothesis):
        return {"status": "NOT_SCORED", "reason": "Hypothesis contains unattributed words"}
    def group(segments):
        out = {}
        for segment in segments:
            tokens = words(segment["text"])
            if tokens:
                out.setdefault(segment["speaker_id"], []).extend(tokens)
        return out
    r, h = group(reference), group(hypothesis)
    rn, hn = sorted(r), sorted(h)
    n = max(len(rn), len(hn))
    rseq = [r[k] for k in rn] + [[] for _ in range(n - len(rn))]
    hseq = [h[k] for k in hn] + [[] for _ in range(n - len(hn))]
    stats = [[edit_counts(a, b) for b in hseq] for a in rseq]
    errors, path = assignment([[s["errors"] for s in row] for row in stats])
    total = sum(map(len, rseq))
    return {"status": "SCORED" if total else "UNDEFINED_EMPTY_REFERENCE",
            "errors": errors, "reference_words": total, "rate": errors / total if total else None,
            **{k: sum(stats[i][j][k] for i, j in enumerate(path))
               for k in ("substitutions", "deletions", "insertions")},
            "mapping": [{"reference": rn[i] if i < len(rn) else None,
                         "hypothesis": hn[j] if j < len(hn) else None} for i, j in enumerate(path)]}


def der(reference, hypothesis, duration, collar_ms=0, skip_overlap=False):
    if type(collar_ms) is not int or collar_ms < 0:
        raise ValueError("collar_ms must be a nonnegative integer radius")
    reference = validate_segments(reference, duration, reference=True)
    hypothesis = validate_segments(hypothesis, duration)
    collars = [(max(0, s[k] - collar_ms), min(duration, s[k] + collar_ms))
               for s in reference for k in ("start_ms", "end_ms") if collar_ms]
    boundaries = {0, duration}
    for s in reference + hypothesis:
        boundaries.update((s["start_ms"], s["end_ms"]))
    for start, end in collars:
        boundaries.update((start, end))
    points = sorted(boundaries)
    regions = []
    for start, end in zip(points, points[1:]):
        if any(a <= start < b for a, b in collars):
            continue
        r = {s["speaker_id"] for s in reference if s["start_ms"] <= start < s["end_ms"]}
        h = {s["speaker_id"] for s in hypothesis if s["start_ms"] <= start < s["end_ms"]}
        if not (skip_overlap and len(r) > 1):
            regions.append((end - start, r, h))
    rn = sorted({s["speaker_id"] for s in reference})
    hn = sorted({s["speaker_id"] for s in hypothesis if s["speaker_id"] is not None})
    n = max(len(rn), len(hn))
    cost = [[-sum(dt for dt, r, h in regions if i < len(rn) and j < len(hn)
                 and rn[i] in r and hn[j] in h) for j in range(n)] for i in range(n)]
    _, path = assignment(cost)
    mapping = {hn[j]: rn[i] for i, j in enumerate(path) if i < len(rn) and j < len(hn)}
    miss = fa = confusion = ref_ms = scored_ms = 0
    for dt, r, h in regions:
        correct = sum(1 for who in h if who in mapping and mapping[who] in r)
        miss += dt * max(len(r) - len(h), 0)
        fa += dt * max(len(h) - len(r), 0)
        confusion += dt * (min(len(r), len(h)) - correct)
        ref_ms += dt * len(r)
        scored_ms += dt
    return {"status": "SCORED" if ref_ms else "UNDEFINED_EMPTY_REFERENCE",
            "rate": (miss + fa + confusion) / ref_ms if ref_ms else None,
            "miss_ms": miss, "false_alarm_ms": fa, "confusion_ms": confusion,
            "reference_speaker_ms": ref_ms, "scored_wall_ms": scored_ms,
            "collar_radius_ms": collar_ms, "skip_reference_overlap": skip_overlap,
            "hypothesis_to_reference": mapping}


def evaluate(reference, hypothesis, collar_ms=0, skip_overlap=False):
    if not isinstance(hypothesis, dict):
        raise ValueError("Hypothesis must be a JSON object")
    if reference is not None and not isinstance(reference, dict):
        raise ValueError("Reference must be a JSON object")
    if type(collar_ms) is not int or collar_ms < 0 or type(skip_overlap) is not bool:
        raise ValueError("Invalid scoring options")
    not_scored = {"status": "NOT_SCORED", "reason": "No independent reference supplied"}
    report = {"schema_version": 1, "normalization": NORMALIZATION,
              "wer": dict(not_scored), "cpwer": dict(not_scored), "der": dict(not_scored)}
    if reference is None:
        return report
    if reference.get("schema_version") != 1 or not all(reference.get(k) for k in
            ("recording_id", "annotation_source", "license", "kind")):
        raise ValueError("Reference requires version, recording_id, annotation_source, license, kind")
    if not re.fullmatch(r"[0-9a-f]{64}", reference.get("audio_sha256", "")):
        raise ValueError("Reference requires audio SHA-256")
    duration = reference["audio_duration_ms"]
    if (type(duration) is not int or duration <= 0 or
            type(hypothesis.get("audio_duration_ms")) is not int or hypothesis["audio_duration_ms"] != duration):
        raise ValueError("Missing or mismatched audio duration")
    if hypothesis.get("audio_sha256") != reference["audio_sha256"]:
        raise ValueError("Hypothesis must identify the same audio SHA-256")
    report["reference"] = {k: reference[k] for k in ("recording_id", "annotation_source", "license", "kind", "audio_sha256")}
    hyp = validate_segments(hypothesis["segments"], duration, text=True)
    if "text_segments" in reference:
        ref = validate_segments(reference["text_segments"], duration, text=True, reference=True)
        report["wer"] = edit_counts(words(" ".join(s["text"] for s in ref)), words(" ".join(s["text"] for s in hyp)))
        report["wer"]["ordering"] = "segment start then end; overlap may make sequence WER ambiguous"
        report["cpwer"] = cpwer(ref, hyp)
    else:
        for k in ("wer", "cpwer"):
            report[k] = {"status": "NOT_SCORED", "reason": "No reference text_segments"}
    if "diarization" in reference and "diarization" in hypothesis:
        report["der"] = der(reference["diarization"], hypothesis["diarization"], duration, collar_ms, skip_overlap)
    else:
        report["der"] = {"status": "NOT_SCORED", "reason": "Independent reference and raw hypothesis diarization required; ASR chunk times are not speech boundaries"}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--hypothesis", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--collar-ms", type=int, default=0)
    parser.add_argument("--skip-overlap", action="store_true")
    args = parser.parse_args()
    if args.output.resolve() in [p.resolve() for p in (args.reference, args.hypothesis) if p]:
        parser.error("Output must not overwrite an input")
    try:
        hbytes = args.hypothesis.read_bytes()
        rbytes = args.reference.read_bytes() if args.reference else None
        reference = json.loads(rbytes) if rbytes is not None else None
        if rbytes is not None and not isinstance(reference, dict):
            raise ValueError("Reference file must contain a JSON object")
        report = evaluate(reference, json.loads(hbytes), args.collar_ms, args.skip_overlap)
        report["hypothesis_sha256"] = hashlib.sha256(hbytes).hexdigest()
        report["reference_sha256"] = hashlib.sha256(rbytes).hexdigest() if rbytes is not None else None
        code = 0 if all(report[k]["status"] == "SCORED" for k in ("wer", "cpwer", "der")) else 2
    except (ValueError, KeyError, TypeError, OSError) as e:
        report, code = {"status": "ERROR", "reason": str(e)}, 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "exit_code": code}))
    return code


if __name__ == "__main__":
    sys.exit(main())
