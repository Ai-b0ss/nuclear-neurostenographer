"""Feed the per-recording score reports into tools/compare_model_trials.py (PR #11), once per corpus group."""
import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
RUNTIME = {"C0": "24d9fe53301fe0b5026fb1cb3877b54d1a47ed079f75819e83a99a9a9e41e55a",
           "C1": "f4338e05a0d1913f387321d2b56bd1cb4985990e3288ce7149e755ea789929bf",
           "C2": "17fd04215d655d2feee413a44f96e57d4ebd96cdd9cdbdf8c26da266e08bc835"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    args = parser.parse_args()
    cases = json.loads((args.evidence / "corpus-manifest.json").read_text(encoding="utf-8"))["cases"]
    runs = json.loads((args.evidence / "runs.json").read_text(encoding="utf-8"))
    outcome = {}
    for group in ("rubook", "datahive", "acted", "ivkond"):
        members = [c for c in cases if c["group"] == group]
        trials = []
        for system in ("C0", "C1", "C2"):
            trial_cases = [{"score_file": str(args.root / f"results/{system}/scores/{c['id']}/collar250_overlap.json"),
                            "audio_duration_ms": c["duration_ms"], "elapsed_ms": runs[f"{system}/{c['id']}"]["inference"]["process_ms"]} for c in members]
            trials.append({"name": system, "code_commit": args.code_commit, "runtime_sha256": RUNTIME[system],
                           "environment": {"platform": "windows-host", "device": platform.processor() or "x86-64 host", "abi": "x86_64"},
                           "timing_scope": "diarization process_ms, 2 threads, model load excluded", "cases": trial_cases})
        manifest = args.root / f"comparison-{group}.json"
        manifest.write_text(json.dumps({"schema_version": 1, "trials": trials}, indent=1), encoding="utf-8")
        out = args.evidence / f"comparison-{group}.json"
        done = subprocess.run([sys.executable, str(REPO / "tools/compare_model_trials.py"), "--manifest", str(manifest), "--output", str(out)], capture_output=True, text=True)
        outcome[group] = done.returncode
        print(group, "exit", done.returncode, done.stdout.strip()[:200], done.stderr.strip()[:300])
    print(outcome)


if __name__ == "__main__":
    main()
