"""Score the phone evidence of NemotronBenchmarkTest with exactly the host measures, and compare each run with the host.

python tools/c2_same_tracks/score_phone_run.py --evidence-json DIR/nemotron-evidence.json --corpus ROOT/data/same \
    --manifest docs/evidence/c2-same-tracks/manifest.json --host-results ROOT/results-same --out DIR/score.json
Host agreement: DER of the phone turns against the host turns of the same system and file (collar 0), and whether the
speaker count is the same. Phone memory is the summed PSS of the app and the :diarization worker, not a host working set.
"""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from score_same_corpus import der, load_reference, measure, read_turns, summary  # noqa: E402

LONG = "long-ru_000010"


def as_dicts(turns):
    return [{"start_ms": a, "end_ms": b, "speaker_id": f"h{c}"} for a, b, c in turns if c >= 0]


def score(evidence, cases, corpus, host_results):
    rows, repeats = [], {}
    for run in evidence["runs"]:
        system = run["backend"].upper()
        row = {"case": run["case"], "system": system, "attempt": run.get("attempt", 0), "status": run["status"], "audio_ms": run["audio_ms"],
               "wall_ms": run.get("wall_ms"), "infer_ms": run.get("infer_ms"), "load_ms": run.get("load_ms"),
               "peak_mib": round(run["peak_total_pss_kib"] / 1024, 1), "rtf": round(run["infer_ms"] / run["audio_ms"], 4) if run.get("infer_ms") else None}
        turns = [tuple(t) for t in run.get("turns", [])]
        if run["status"] == "OK":
            repeats.setdefault(f"{run['case']}/{system}", []).append(turns)
        case = cases.get(run["case"])
        if case and run["status"] == "OK" and row["attempt"] == 0:
            reference = load_reference(corpus, case)
            segments = run.get("transcript", {}).get("segments_text")
            row.update(set=case["set"], ref_speakers=case["speakers"], noise=case["noise"], duration_ms=run["audio_ms"])
            row.update(measure(case, reference, turns, segments))
            host = host_results / system / f"{case['id']}.tsv"
            if host.exists():
                host_turns = read_turns(host)
                agreement = der(as_dicts(host_turns), as_dicts(turns), run["audio_ms"], 0, False)
                row["host_agreement"] = {"der_phone_vs_host": round(agreement["rate"], 4) if agreement["rate"] is not None else None,
                                         "same_speaker_count": len({c for *_, c in host_turns if c >= 0}) == row["hyp_speakers"]}
        elif case:
            row["set"] = case["set"]
        rows.append(row)
    scored = [r for r in rows if r.get("set") and r["attempt"] == 0]
    report = {"scope": "Physical phone run of the same files as the host comparison",
              "device": evidence.get("device"),
              "summary": {name: summary(scored, name) for name in ("phone3", "holdout", "realmix")},
              "failed_runs": sum(r["status"] != "OK" for r in rows),
              "repeat_runs_identical": {k: all(v == runs[0] for v in runs[1:]) for k, runs in repeats.items() if len(runs) > 1},
              "long": {r["system"]: {k: r[k] for k in ("status", "wall_ms", "infer_ms", "audio_ms", "peak_mib", "rtf")} for r in rows if r["case"] == LONG and r["attempt"] == 0},
              "rows": rows}
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-json", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--host-results", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    cases = {c["id"]: c for c in json.loads(args.manifest.read_text(encoding="utf-8"))["cases"]}
    report = score(json.loads(args.evidence_json.read_text(encoding="utf-8")), cases, args.corpus, args.host_results)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("device", "summary", "failed_runs", "repeat_runs_identical", "long")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
