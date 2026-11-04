"""Score the local C0/C2 Android instrumentation evidence on pinned public WAVs.

Run after NemotronBenchmarkTest.sameRecordingsThroughBothBackends. Evidence and
references stay under ignored .local. C0/C2 compares backends, not C++/Kotlin speed.
"""
import argparse
import hashlib
import json
from pathlib import Path

from score_transcript import evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--case", action="append", nargs=3, metavar=("ID", "WAV", "REFERENCE"), required=True)
    parser.add_argument("--baseline-evidence", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text(encoding="utf-8-sig"))
    baseline = (json.loads(args.baseline_evidence.read_text(encoding="utf-8-sig"))
                if args.baseline_evidence else None)
    if evidence["device"]["physical_device"] is not False:
        raise ValueError("This report is specifically for emulator evidence")
    cases = {name: (Path(wav), Path(ref)) for name, wav, ref in args.case}
    if len(cases) != len(args.case):
        raise ValueError("Duplicate case")
    runs = evidence["runs"]
    if len(runs) != len(cases) * 2 or {(r["case"], r["backend"]) for r in runs} != {
        (case, backend) for case in cases for backend in ("c0", "c2")
    }:
        raise ValueError("Expected exactly one C0 and C2 run per case")
    baseline_runs = baseline["runs"] if baseline else []
    if baseline and ({(r["case"], r["backend"]) for r in baseline_runs} !=
                     {(r["case"], r["backend"]) for r in runs}):
        raise ValueError("Baseline cases/backends differ")
    summary = {"device": evidence["device"], "cases": []}
    for name, (wav, ref_path) in cases.items():
        reference = json.loads(ref_path.read_text(encoding="utf-8"))
        audio_sha = hashlib.sha256(wav.read_bytes()).hexdigest()
        if audio_sha != reference["audio_sha256"]:
            raise ValueError(f"{name}: WAV differs from pinned reference")
        row = {"case": name, "audio_sha256": audio_sha, "backends": {}}
        for backend in ("c0", "c2"):
            run = next(r for r in runs if r["case"] == name and r["backend"] == backend)
            if run["status"] != "OK" or run["audio_ms"] != reference["audio_duration_ms"]:
                raise ValueError(f"{name}/{backend}: failed or mismatched audio duration")
            transcript = run.get("transcript", {})
            segments = transcript.get("segments_text")
            if not isinstance(segments, list) or not transcript.get("exports_nonblank"):
                raise ValueError(f"{name}/{backend}: transcript or exports unavailable")
            hypothesis = {"audio_sha256": audio_sha, "audio_duration_ms": run["audio_ms"],
                          "segments": segments}
            if "diarization" in reference:
                hypothesis["diarization"] = [
                    {"start_ms": start, "end_ms": end,
                     "speaker_id": None if cluster < 0 else f"Speaker {cluster + 1}"}
                    for start, end, cluster in run["turns"]
                ]
            score = evaluate(reference, hypothesis)
            row["backends"][backend] = {
                "wer": score["wer"], "cpwer": score["cpwer"], "der": score["der"],
                "infer_ms": run["infer_ms"], "wall_ms": run["wall_ms"],
                "peak_total_pss_kib": run["peak_total_pss_kib"],
                "speaker_sequence": [segment["speaker_id"] for segment in segments],
            }
            if baseline:
                previous = next(r for r in baseline_runs if r["case"] == name and r["backend"] == backend)
                if previous["audio_ms"] != run["audio_ms"] or previous["status"] != "OK":
                    raise ValueError(f"{name}/{backend}: invalid baseline")
                row["backends"][backend]["baseline_parity"] = {
                    "turns_equal": run["turns"] == previous["turns"],
                    "segments_equal": segments == previous["transcript"]["segments_text"],
                }
        summary["cases"].append(row)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for row in summary["cases"]:
        for backend, result in row["backends"].items():
            der_text = (f"{result['der']['rate']:.2%}" if result['der']['status'] == "SCORED"
                        else result['der']['status'])
            print(f"{row['case']} {backend}: WER {result['wer']['errors']}/{result['wer']['reference_words']}, "
                  f"cpWER {result['cpwer'].get('errors')}/{result['cpwer'].get('reference_words')}, "
                  f"DER {der_text}, infer {result['infer_ms']} ms"
                  + (f", parity {result['baseline_parity']}" if baseline else ""))


if __name__ == "__main__":
    main()
