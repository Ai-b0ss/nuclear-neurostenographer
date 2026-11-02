"""Human check of DataHive references. Audio and labels stay on the reviewer's machine, outside Git.

prepare: python manual_review.py prepare --root ROOT --out REVIEW_DIR
  Writes one stereo WAV per recording plus Audacity label tracks with the VAD turns as a starting point.
  The reviewer listens to each channel and corrects its labels, then saves them as caller.reviewed.txt and callee.reviewed.txt.
score:   python manual_review.py score --root ROOT --review REVIEW_DIR --results ROOT/results-v2 --reviewer NAME --evidence DIR
  Only reviewed files count. Results are written apart from the VAD pseudo-reference and keep the human label kind.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
from score_transcript import der  # noqa: E402

# Fixed before any review: the worst C2 file, a median one, a C0-only failure and three spread across speech balance.
SAMPLE = ("ru_000001", "ru_000017", "ru_000006", "ru_000010", "ru_000013", "ru_000014")
CHANNELS = ("caller", "callee")


def read_labels(path, duration):
    """Audacity label file: start, end, text in seconds. Rejects anything that cannot be a time interval."""
    turns = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("\\"):
            continue
        fields = line.split("\t")
        start, end = round(float(fields[0]) * 1000), round(float(fields[1]) * 1000)
        if not 0 <= start < end <= duration + 50:
            raise ValueError(f"{path}:{number}: invalid interval")
        turns.append((start, min(end, duration)))
    return turns


def reviewed_reference(folder, duration):
    """None until both channels have been reviewed: a half-checked file is not a human reference."""
    paths = [folder / f"{channel}.reviewed.txt" for channel in CHANNELS]
    if not all(p.is_file() for p in paths):
        return None
    turns = []
    for channel, path in zip(CHANNELS, paths):
        turns += [{"start_ms": a, "end_ms": b, "speaker_id": channel} for a, b in read_labels(path, duration)]
    return sorted(turns, key=lambda t: t["start_ms"])


def prepare(args):
    corpus = args.root / "data/corpus"
    for name in SAMPLE:
        folder = args.out / name
        folder.mkdir(parents=True, exist_ok=True)
        subprocess.run([args.ffmpeg, "-v", "error", "-y", "-ss", "30", "-t", "120", "-i", str(args.root / "data/raw/datahive" / f"{name}.mp3"),
                        "-ar", "16000", "-c:a", "pcm_s16le", str(folder / "stereo.wav")], check=True)
        reference = json.loads((corpus / f"datahive-{name}.ref.json").read_text(encoding="utf-8"))
        for channel in CHANNELS:
            lines = [f"{t['start_ms'] / 1000:.3f}\t{t['end_ms'] / 1000:.3f}\t{channel}\n" for t in reference["diarization"] if t["speaker_id"] == channel]
            (folder / f"{channel}.vad.txt").write_text("".join(lines), encoding="utf-8")
    (args.out / "INSTRUCTIONS.txt").write_text(
        "Open stereo.wav in Audacity, split the stereo track, import both *.vad.txt files as labels.\n"
        "Listen to the left channel (caller) and the right channel (callee) separately. Correct every label so it covers that person's speech.\n"
        "Merge pauses shorter than 0.3 s, and label breathing or noise as non-speech. Do not look at any model output.\n"
        "Export each label track as caller.reviewed.txt and callee.reviewed.txt into the recording's folder.\n"
        "Do not upload audio or labels with speech content. Interval files only, no text.\n", encoding="utf-8")
    print("prepared", args.out)


def score(args):
    corpus = args.root / "data/corpus"
    rows = []
    for name in SAMPLE:
        case_id = f"datahive-{name}"
        vad = json.loads((corpus / f"{case_id}.ref.json").read_text(encoding="utf-8"))
        duration = vad["audio_duration_ms"]
        human = reviewed_reference(args.review / name, duration)
        row = {"case": case_id, "status": "NOT_REVIEWED" if human is None else "HUMAN_REVIEWED"}
        if human is not None:
            row["reference_sha256"] = hashlib.sha256(json.dumps(human, sort_keys=True).encode()).hexdigest()
            row["systems"] = {}
            for system in ("C0", "C1", "C2"):
                lines = (args.results / system / f"{case_id}.tsv").read_text(encoding="ascii").splitlines()
                turns = []
                for line in lines:
                    a, b, c = line.split("\t")
                    turns.append({"start_ms": int(a), "end_ms": int(b), "speaker_id": None if int(c) < 0 else f"h{c}"})
                against_human = der(human, turns, duration, 250, False)
                against_vad = der(vad["diarization"], turns, duration, 250, False)
                row["systems"][system] = {"der_human_collar250": against_human["rate"], "der_vad_collar250": against_vad["rate"]}
        rows.append(row)
    done = sum(r["status"] == "HUMAN_REVIEWED" for r in rows)
    report = {"kind": "HUMAN_REVIEWED_INTERVALS" if done else "NOT_SCORED", "reviewer": args.reviewer, "reviewed_files": done, "sample": len(SAMPLE),
              "note": "Kept apart from VAD pseudo-reference results. Audio, labels and transcripts are not in Git.", "rows": rows}
    args.evidence.mkdir(parents=True, exist_ok=True)
    (args.evidence / "manual-review.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("kind", "reviewed_files", "sample")}))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--ffmpeg", default="ffmpeg")
    s = sub.add_parser("score")
    s.add_argument("--root", type=Path, required=True)
    s.add_argument("--review", type=Path, required=True)
    s.add_argument("--results", type=Path, required=True)
    s.add_argument("--reviewer", required=True)
    s.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    (prepare if args.command == "prepare" else score)(args)


if __name__ == "__main__":
    main()
