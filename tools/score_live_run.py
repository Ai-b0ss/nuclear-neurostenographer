"""Score a live read-aloud run against tools/fixtures/live-dialogue-script-ru.json.

  python tools/score_live_run.py --export transcript.json --audio-sha256 HEX --out-dir DIR

`--export` is the JSON the app saved (pulled with phone_kit.py exports); the audio is NOT needed
here: its SHA-256 can be computed on the phone (`run-as ... sha256sum`) so the recording never leaves
the device. The script builds the reference and hypothesis files for tools/score_transcript.py and runs it.
Reports WER, cpWER and the speaker mapping; DER stays NOT_SCORED (no independent speech boundaries).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/fixtures/live-dialogue-script-ru.json"


def build(export, script, audio_sha256):
    """Return (reference, hypothesis) dicts in the scorer's schema. Reference times only order the text."""
    duration = export["audio_duration_ms"]
    turns = script["turns"]
    step = max(1, duration // len(turns))
    reference = {
        "schema_version": 1, "recording_id": script["recording_id"], "audio_sha256": audio_sha256,
        "audio_duration_ms": duration, "annotation_source": script["annotation_source"],
        "license": script["license"], "kind": "ACTED_READ_ALOUD_LIVE",
        "text_segments": [{"start_ms": i * step, "end_ms": min(duration, (i + 1) * step) if i + 1 < len(turns) else duration,
                           "speaker_id": t["speaker_id"], "text": t["text"]} for i, t in enumerate(turns)],
    }
    hypothesis = {
        "schema_version": 1, "recording_id": script["recording_id"], "audio_sha256": audio_sha256,
        "audio_duration_ms": duration,
        "segments": [{k: s[k] for k in ("start_ms", "end_ms", "speaker_id", "text")} for s in export["segments"]],
    }
    return reference, hypothesis


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--audio-sha256", required=True)
    parser.add_argument("--script", type=Path, default=SCRIPT, help="reference script (default: the project script)")
    parser.add_argument("--out-dir", type=Path, default=Path("live-score"))
    args = parser.parse_args()
    script = json.loads(args.script.read_text(encoding="utf-8"))
    export = json.loads(args.export.read_text(encoding="utf-8"))
    reference, hypothesis = build(export, script, args.audio_sha256)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "reference.json").write_text(json.dumps(reference, ensure_ascii=False, indent=1), encoding="utf-8")
    (args.out_dir / "hypothesis.json").write_text(json.dumps(hypothesis, ensure_ascii=False, indent=1), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "tools/score_transcript.py"), "--reference", str(args.out_dir / "reference.json"),
                    "--hypothesis", str(args.out_dir / "hypothesis.json"), "--output", str(args.out_dir / "score.json"),
                    "--collar-ms", "0"], capture_output=True)
    score = json.loads((args.out_dir / "score.json").read_text(encoding="utf-8"))
    print("WER", score["wer"]["errors"], "/", score["wer"]["reference_words"], score["wer"].get("rate"))
    print("cpWER", score["cpwer"]["errors"], "/", score["cpwer"]["reference_words"], score["cpwer"].get("rate"),
          score["cpwer"].get("mapping"))
    print("DER", score["der"]["status"])


if __name__ == "__main__":
    main()
