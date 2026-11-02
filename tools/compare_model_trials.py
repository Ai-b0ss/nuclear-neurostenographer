"""Compare offline ASR/diarization trials without converting missing scores to wins.

Consumes JSON reports emitted by score_transcript.py, not raw audio or predictions.
No dependencies, model downloads, or access to private recordings are required.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
METRICS = ("wer", "cpwer", "der")


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(value, length=64):
    return isinstance(value, str) and bool((HEX64 if length == 64 else HEX40).fullmatch(value))


def load_score(path):
    result = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(result, dict) and result.get("schema_version") == 1, f"Invalid score: {path}")
    ref = result.get("reference")
    require(isinstance(ref, dict), f"Missing independent reference in {path}")
    require(ref.get("kind") not in ("AUTHORED_UNIT_TEST_NO_AUDIO", None), f"Not real evaluation data: {path}")
    require(isinstance(ref.get("recording_id"), str) and ref["recording_id"].strip(), "Missing recording_id")
    require(all(digest(result.get(k)) for k in ("reference_sha256", "hypothesis_sha256")), "Missing score input hashes")
    require(digest(ref.get("audio_sha256")), "Missing audio SHA-256")
    for metric in METRICS:
        value = result.get(metric)
        require(isinstance(value, dict) and value.get("status") in
                ("SCORED", "NOT_SCORED", "UNDEFINED_EMPTY_REFERENCE"), f"Invalid {metric} status")
        if value["status"] != "SCORED":
            continue
        denominator = value.get("reference_words" if metric != "der" else "reference_speaker_ms")
        numerator = (value.get("errors") if metric != "der" else
                     sum(value.get(k, -1) for k in ("miss_ms", "false_alarm_ms", "confusion_ms")))
        require(type(denominator) is int and denominator > 0 and type(numerator) is int and numerator >= 0,
                f"Invalid scored {metric} counts")
        rate = value.get("rate")
        require(type(rate) in (int, float) and math.isfinite(rate) and
                math.isclose(rate, numerator / denominator, rel_tol=1e-7, abs_tol=1e-9),
                f"Inconsistent scored {metric} rate")
        if metric == "der":
            require(type(value.get("collar_radius_ms")) is int and value["collar_radius_ms"] >= 0 and
                    type(value.get("skip_reference_overlap")) is bool, "Unspecified DER protocol")
    return result


def compare(manifest, base_dir):
    require(isinstance(manifest, dict) and manifest.get("schema_version") == 1, "Expected schema_version 1")
    trials = manifest.get("trials")
    require(isinstance(trials, list) and 2 <= len(trials) <= 8, "Need 2-8 model trials")
    names, expected, der_protocol, records = set(), None, set(), []
    for trial in trials:
        require(isinstance(trial, dict), "Trial must be an object")
        name = trial.get("name")
        require(isinstance(name, str) and 0 < len(name) <= 64 and name not in names, "Duplicate/invalid trial name")
        names.add(name)
        require(digest(trial.get("code_commit"), 40) and digest(trial.get("runtime_sha256")),
                f"{name}: pin code commit and runtime digest")
        environment = trial.get("environment")
        require(isinstance(environment, dict) and
                all(isinstance(environment.get(k), str) and environment[k].strip()
                    for k in ("platform", "device", "abi")), f"{name}: missing device details")
        scope = trial.get("timing_scope")
        require(isinstance(scope, str) and scope.strip(), f"{name}: missing timing scope")
        cases = trial.get("cases")
        require(isinstance(cases, list) and 1 <= len(cases) <= 200, f"{name}: invalid cases")
        seen, metrics, total_elapsed, total_audio = set(), {m: [0, 0, 0] for m in METRICS}, 0, 0
        for case in cases:
            require(isinstance(case, dict), f"{name}: case not object")
            file_name = case.get("score_file")
            require(isinstance(file_name, str) and file_name.endswith(".json"), "Invalid score_file")
            # Explicitly keep the evaluation self-contained within its manifest directory.
            path = (base_dir / file_name).resolve()
            require(path.is_relative_to(base_dir.resolve()), "Score path escapes manifest directory")
            score = load_score(path)
            ref = score["reference"]
            duration, elapsed = case.get("audio_duration_ms"), case.get("elapsed_ms")
            require(type(duration) is int and duration > 0 and type(elapsed) is int and elapsed > 0,
                    f"{name}: positive measured duration and elapsed_ms required")
            key = (ref["recording_id"], ref["audio_sha256"], score["reference_sha256"], duration)
            require(key not in seen, f"{name}: duplicated case {ref['recording_id']}")
            seen.add(key)
            total_audio += duration
            total_elapsed += elapsed
            for metric in METRICS:
                value = score[metric]
                if value["status"] == "SCORED":
                    denominator = value["reference_words" if metric != "der" else "reference_speaker_ms"]
                    numerator = (value["errors"] if metric != "der" else
                                 sum(value[k] for k in ("miss_ms", "false_alarm_ms", "confusion_ms")))
                    metrics[metric][0] += numerator
                    metrics[metric][1] += denominator
                    if metric == "der":
                        der_protocol.add((value["collar_radius_ms"], value["skip_reference_overlap"]))
                else:
                    metrics[metric][2] += 1
        require(expected is None or seen == expected, f"{name}: corpus/reference mismatch with first trial")
        expected = seen
        formatted = {}
        for metric, (errors, denominator, missing) in metrics.items():
            fully_scored = missing == 0 and denominator > 0
            formatted[metric] = {"status": "SCORED" if fully_scored else "NOT_SCORED",
                                 "rate": errors / denominator if fully_scored else None,
                                 "errors": errors if fully_scored else None,
                                 "reference_units": denominator if fully_scored else None,
                                 "unscored_cases": missing}
        records.append({"name": name, "code_commit": trial["code_commit"],
                        "runtime_sha256": trial["runtime_sha256"], "environment": environment,
                        "timing_scope": scope, "cases": len(cases), "metrics": formatted,
                        "measured_rtf": total_elapsed / total_audio})
    require(len(der_protocol) <= 1, "DER scores use different collar/overlap protocols")
    comparable_timing = all((x["environment"], x["timing_scope"]) ==
                            (records[0]["environment"], records[0]["timing_scope"]) for x in records)
    return {"schema_version": 1, "status": "COMPARABLE_INPUTS", "cases_per_trial": len(expected),
            "accuracy_protocol": {"same_audio_and_reference": True,
                                  "der_collar_and_overlap": list(der_protocol)[0] if der_protocol else None},
            "timing_comparable": comparable_timing,
            "timing_warning": None if comparable_timing else "Different hardware or timing scope: do not rank RTF",
            "trials": records,
            "limitations": "This checks reported evidence identity and arithmetic, not audio authenticity, "
                           "ground-truth independence, Android runtime behavior or statistical significance."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest_path = args.manifest.resolve()
        out = args.output.resolve()
        require(out != manifest_path, "Output must not overwrite manifest")
        source = args.manifest.read_bytes()
        report = compare(json.loads(source), args.manifest.resolve().parent)
        require(all(out != (args.manifest.resolve().parent / c["score_file"]).resolve()
                    for t in json.loads(source)["trials"] for c in t["cases"]),
                "Output must not overwrite score inputs")
        report["manifest_sha256"] = hashlib.sha256(source).hexdigest()
        code = 0 if all(t["metrics"][m]["status"] == "SCORED"
                        for t in report["trials"] for m in METRICS) else 2
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        report, code = {"status": "ERROR", "reason": str(exc)}, 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main())
