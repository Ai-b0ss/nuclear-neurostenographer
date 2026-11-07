"""Export deidentified manual-enrollment host scores and fixture hashes."""
import argparse
import json
from pathlib import Path

from common import sha, write_json
from manual_manifest import KIND, validate

CANDIDATE = "VoxLock v2 INT8 + same pinned A3/C2 + mandatory manual 3s enrollment"


def _wer(rows, key):
    metrics = [row[key]["wer"] for row in rows]
    if any(metric.get("status") != "SCORED" for metric in metrics):
        return dict(status="NOT_SCORED", errors=None, reference_words=None, rate=None)
    errors = sum(metric["errors"] for metric in metrics)
    reference_words = sum(metric["reference_words"] for metric in metrics)
    return dict(status="SCORED", errors=errors, reference_words=reference_words,
                rate=errors / reference_words if reference_words else None)


def export(fixtures_path, run_path, score_output, fixture_output):
    fixtures_path = Path(fixtures_path).resolve()
    manifest = validate(fixtures_path)
    summary = json.loads(Path(run_path).read_text(encoding="utf-8"))
    if summary.get("status") != "COMPLETE":
        raise ValueError("Completed host summary required")
    if summary["protocol"].get("fixture_manifest_sha256") != sha(fixtures_path):
        raise ValueError("Run and adapted fixture manifest differ")
    if summary["protocol"].get("enrollment_mode") != "manual":
        raise ValueError("Automatic/fallback enrollment evidence is not accepted")
    rows = summary["rows"]
    if len(rows) != len(manifest["cases"]):
        raise ValueError("Not every fixture has a completed result")
    cases = [dict(id=case["id"], audio_sha256=case["audio_sha256"], reference_sha256=case["reference_sha256"],
                  enrollment_sha256=[item["sha256"] for item in case["enrollments"]])
             for case in manifest["cases"]]
    fixture_report = dict(schema_version=1, kind=KIND, status="HASH_VERIFIED", enrollment_mode="manual",
                          adapted_manifest_sha256=sha(fixtures_path), cases=cases)
    durations = {case["id"]: case["duration_ms"] for case in manifest["cases"]}
    total_duration = sum(durations.values())

    def weighted_rtf(key):
        return sum(row["host"][key] * durations[row["case"]] for row in rows) / total_duration

    report = dict(
        schema_version=1,
        status="HOST_COMPLETE_HONOR_NOT_RUN",
        candidate=dict(name=CANDIDATE, wer=_wer(rows, "candidate")),
        fixtures=dict(status="HASH_VERIFIED", adapted_manifest_sha256=sha(fixtures_path), cases=cases),
        baseline=dict(name="same pinned A3+C2", wer=_wer(rows, "baseline")),
        recovered_correct_words=sum(row["word_recovery"]["recovered_correct_words"] for row in rows),
        unknown_words_before=sum(row["baseline"]["unknown_words"] for row in rows),
        unknown_words_after=sum(row["candidate"]["unknown_words"] for row in rows),
        host=dict(status="MEASURED", rtf_status="MEASURED", baseline_rtf=weighted_rtf("baseline_wall_rtf"),
                  candidate_rtf=weighted_rtf("candidate_wall_rtf"), pss_status="NOT_MEASURED", pss=None),
        honor=dict(status="NOT_RUN", rtf_status="NOT_RUN", baseline_rtf=None, candidate_rtf=None,
                   pss_status="NOT_RUN", pss=None),
        decision="RESEARCH_ONLY_MANUAL_REVIEW_REQUIRED",
    )
    write_json(score_output, report)
    write_json(fixture_output, fixture_report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--score-output", type=Path, required=True)
    parser.add_argument("--fixture-output", type=Path, required=True)
    args = parser.parse_args()
    report = export(args.fixtures, args.run, args.score_output, args.fixture_output)
    print(json.dumps({"status": report["status"], "decision": report["decision"]}))


if __name__ == "__main__":
    main()
