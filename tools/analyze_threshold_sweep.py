"""Summarize a threshold sweep from tools/run_threshold_sweep.py against the dataset annotations.

  python tools/analyze_threshold_sweep.py --sweep out.jsonl --refs DIR [--output summary.json]

Per threshold: how often the number of speakers is exactly right, mean absolute count error, how many
tracks were over-/under-split, and the speaker-confusion share of the reference speech time (from
tools/score_transcript.py, which gives the mapping-optimal DER pieces). Miss time is not compared across
thresholds because the synthetic annotation includes the pauses inside turns. Host runs only.
"""
import argparse
import collections
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def count_speakers(turns):
    return len({t["speaker_id"] for t in turns if t["speaker_id"] is not None})


def confusion_share(reference, turns, work):
    sha = hashlib.sha256(reference["name"].encode()).hexdigest()  # identity only; audio is not read by the scorer
    ref = {"schema_version": 1, "recording_id": reference["name"], "audio_sha256": sha,
           "audio_duration_ms": reference["duration_ms"], "annotation_source": "synthetic dataset annotation",
           "license": "MIT", "kind": "SYNTHETIC", "text_segments": [], "diarization": reference["diarization"]}
    hyp = {"schema_version": 1, "recording_id": reference["name"], "audio_sha256": sha,
           "audio_duration_ms": reference["duration_ms"], "segments": [],
           "diarization": [t for t in turns if t["speaker_id"] is not None]}
    (work / "r.json").write_text(json.dumps(ref), encoding="utf-8")
    (work / "h.json").write_text(json.dumps(hyp), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "tools/score_transcript.py"), "--reference", str(work / "r.json"),
                    "--hypothesis", str(work / "h.json"), "--output", str(work / "s.json"), "--collar-ms", "0"],
                   capture_output=True)
    der = json.loads((work / "s.json").read_text(encoding="utf-8")).get("der", {})
    if der.get("status") != "SCORED" or not der.get("reference_speaker_ms"):
        return None
    return der["confusion_ms"] / der["reference_speaker_ms"]


def summarize(rows, refs, work):
    by_threshold = collections.defaultdict(list)
    for row in rows:
        ref = refs[Path(row["file"]).stem]
        n = ref["num_speakers"]
        found = count_speakers(row["turns"])
        by_threshold[row["threshold"]].append({"n": n, "found": found, "confusion": confusion_share(ref, row["turns"], work)})
    summary = {}
    for threshold, items in sorted(by_threshold.items()):
        entry = {"tracks": len(items), "exact": round(sum(i["found"] == i["n"] for i in items) / len(items), 3),
                 "mean_abs_error": round(sum(abs(i["found"] - i["n"]) for i in items) / len(items), 3),
                 "over": sum(i["found"] > i["n"] for i in items), "under": sum(i["found"] < i["n"] for i in items)}
        conf = [i["confusion"] for i in items if i["confusion"] is not None]
        entry["mean_confusion_share"] = round(sum(conf) / len(conf), 4) if conf else None
        for n in sorted({i["n"] for i in items}):
            group = [i for i in items if i["n"] == n]
            entry[f"n{n}"] = {"tracks": len(group), "exact": sum(i["found"] == n for i in group),
                              "over": sum(i["found"] > n for i in group), "under": sum(i["found"] < n for i in group)}
        summary[str(threshold)] = entry
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sweep", type=Path, required=True)
    parser.add_argument("--refs", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.sweep.read_text(encoding="utf-8").splitlines() if line.strip()]
    refs = {p.name[:-len(".ref.json")]: json.loads(p.read_text(encoding="utf-8")) for p in args.refs.glob("*.ref.json")}
    with tempfile.TemporaryDirectory() as tmp:
        summary = summarize(rows, refs, Path(tmp))
    text = json.dumps(summary, indent=1, ensure_ascii=False)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
