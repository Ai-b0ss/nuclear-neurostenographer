"""Explain one two-channel DataHive result from intervals only: how clusters map onto the real channels.

Automatic diagnosis, not a human reference. It reveals whether a cluster splits one channel, or mixes both.
"""
import argparse
import json
from pathlib import Path


def turns(path):
    rows = [line.split("\t") for line in Path(path).read_text(encoding="ascii").splitlines() if line.strip()]
    return [(int(a), int(b), int(c)) for a, b, c in rows]


def overlap(a, b, x, y):
    return max(0, min(b, y) - max(a, x))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--results", default="results-v2")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = {"scope": "Intervals only; automatic, not a human reference", "cases": {}}
    for case in args.cases.split(","):
        reference = json.loads((args.root / "data/corpus" / f"{case}.ref.json").read_text(encoding="utf-8"))["diarization"]
        speakers = sorted({t["speaker_id"] for t in reference})
        entry = {"reference_speech_ms": {s: sum(t["end_ms"] - t["start_ms"] for t in reference if t["speaker_id"] == s) for s in speakers}}
        for system in ("C0", "C2"):
            table = {}
            for a, b, c in turns(args.root / args.results / system / f"{case}.tsv"):
                row = table.setdefault(str(c), {s: 0 for s in speakers} | {"total_ms": 0, "first_ms": a})
                row["total_ms"] += b - a
                row["first_ms"] = min(row["first_ms"], a)
                for t in reference:
                    row[t["speaker_id"]] += overlap(a, b, t["start_ms"], t["end_ms"])
            entry[system] = table
        report["cases"][case] = entry
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
