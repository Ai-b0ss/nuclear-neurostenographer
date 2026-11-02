"""Score emulator evidence for C0 and C2 against the frozen references and the host outputs.

python tools/nemotron/score_android.py --evidence-json device.json --corpus ROOT/data/corpus --manifest corpus-manifest.json --host-results ROOT/results-v2 --out report.json
An emulator on a CI host is not a phone: speed and memory here do not transfer to ARM64.
"""
import argparse
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
from score_transcript import der  # noqa: E402


def as_turns(rows):
    return [{"start_ms": a, "end_ms": b, "speaker_id": None if c < 0 else f"h{c}"} for a, b, c in rows]


def read_tsv(path):
    return as_turns([tuple(map(int, line.split("\t"))) for line in Path(path).read_text(encoding="ascii").splitlines() if line.strip()])


def errors(d):
    return d["miss_ms"] + d["false_alarm_ms"] + d["confusion_ms"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-json", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--host-results", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.evidence_json.read_text(encoding="utf-8"))
    cases = {c["id"]: c for c in json.loads(args.manifest.read_text(encoding="utf-8"))["cases"]}
    rows, repeat = [], {}
    for run in data["runs"]:
        case, backend = run["case"], run["backend"]
        repeat.setdefault((case, backend), []).append(run.get("turns"))
        row = {k: run.get(k) for k in ("case", "backend", "attempt", "status", "audio_ms", "load_ms", "infer_ms", "wall_ms", "peak_app_pss_kib", "peak_worker_pss_kib", "peak_total_pss_kib", "transcript")}
        row["speakers"] = len({t[2] for t in run.get("turns", []) if t[2] >= 0})
        if case in cases and run["status"] == "OK":
            reference = json.loads((args.corpus / f"{case}.ref.json").read_text(encoding="utf-8")).get("diarization")
            turns = as_turns(run["turns"])
            duration = cases[case]["duration_ms"]
            if reference:
                d = der(reference, turns, duration, 250, False)
                row.update(der=d["rate"], errors=errors(d), reference_ms=d["reference_speaker_ms"])
            host = args.host_results / {"c0": "C0", "c2": "C2"}[backend] / f"{case}.tsv"
            if host.exists():
                between = der(read_tsv(host), turns, duration, 0, False)
                row["der_against_host"] = between["rate"]
                if reference:
                    row["host_der"] = der(reference, read_tsv(host), duration, 250, False)["rate"]
        rows.append(row)
    summary = {}
    for backend in ("c0", "c2"):
        first = [r for r in rows if r["backend"] == backend and r["attempt"] == 0]
        scored = [r for r in first if "der" in r]
        short = [r for r in first if r["case"] != "long-ru_000010"]
        long_run = next((r for r in first if r["case"] == "long-ru_000010"), None)
        speech = sum(r["reference_ms"] for r in scored)
        summary[backend] = {"runs": sum(r["backend"] == backend for r in rows), "failed": sum(r["backend"] == backend and r["status"] != "OK" for r in rows),
                            "scored_files": len(scored), "pooled_der_collar250": sum(r["errors"] for r in scored) / speech if speech else None,
                            "infer_rtf": sum(r["infer_ms"] for r in short) / sum(r["audio_ms"] for r in short),
                            "wall_rtf": sum(r["wall_ms"] for r in short) / sum(r["audio_ms"] for r in short),
                            "peak_total_pss_mib_short": max(r["peak_total_pss_kib"] for r in short) / 1024,
                            "peak_worker_pss_mib_short": max(r["peak_worker_pss_kib"] for r in short) / 1024,
                            "long_20min": None if not long_run else {"infer_rtf": long_run["infer_ms"] / long_run["audio_ms"], "wall_rtf": long_run["wall_ms"] / long_run["audio_ms"],
                                                                     "peak_total_pss_mib": long_run["peak_total_pss_kib"] / 1024, "peak_worker_pss_mib": long_run["peak_worker_pss_kib"] / 1024},
                            "max_der_against_host": max((r.get("der_against_host") or 0) for r in first)}
    deterministic = {f"{case}/{backend}": all(t == turns[0] for t in turns) for (case, backend), turns in repeat.items() if len(turns) > 1}
    report = {"scope": "x86_64 emulator on a CI host. Physical ARM64: NOT_RUN.", "device": data["device"], "summary": summary, "repeat_runs_identical": deterministic, "rows": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("device", "summary", "repeat_runs_identical")}, indent=1))
    for r in rows:
        if r["attempt"] == 0:
            print(r["case"], r["backend"], r["status"], "der", None if "der" not in r else round(100 * r["der"], 2), "host", None if "host_der" not in r else round(100 * r["host_der"], 2),
                  "vs_host", None if "der_against_host" not in r else round(100 * (r["der_against_host"] or 0), 2), "spk", r["speakers"], (r["transcript"] or {}).get("attributed_segments"), (r["transcript"] or {}).get("exports_nonblank"))


if __name__ == "__main__":
    main()
