"""Score the JSON export of one phone run against a reference file in the scorer's schema.

  python tools/score_clip_run.py --reference REF.json --export PHONE.json --out-dir DIR

The reference end times are clamped to the audio duration (the public synthetic dataset rounds its last
segment a few milliseconds past the end). The hypothesis is the app's exported segments; DER stays
NOT_SCORED because the export has no raw speech turns (chunk times are never used as diarization).
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def clamp_reference(reference):
    duration = reference["audio_duration_ms"]
    fixed = json.loads(json.dumps(reference))
    for key in ("text_segments", "diarization"):
        for segment in fixed.get(key, []):
            segment["end_ms"] = min(segment["end_ms"], duration)
            segment["start_ms"] = min(segment["start_ms"], segment["end_ms"] - 1)
    return fixed


def hypothesis_from_export(export, reference, audio=None):
    digest=reference['audio_sha256']
    if audio is not None:
        with Path(audio).open('rb') as stream:
            digest=hashlib.file_digest(stream,'sha256').hexdigest()
        if digest!=reference['audio_sha256']:
            raise ValueError('Actual WAV hash differs from reference')
    if export.get('audio_sha256',digest)!=digest:
        raise ValueError('Export audio hash differs from reference/actual WAV')
    return {"schema_version": 1, "recording_id": reference["recording_id"], "audio_sha256": digest,
            "audio_identity_verification": "WAV_HASH_VERIFIED" if audio is not None else "REFERENCE_ASSOCIATION_ONLY_NOT_INDEPENDENTLY_VERIFIED",
            "audio_duration_ms": export["audio_duration_ms"],
            "segments": [{k: s[k] for k in ("start_ms", "end_ms", "speaker_id", "text", "attribution_reliable") if k in s} for s in export["segments"]]}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--audio", type=Path, help="Original WAV for independently verified audio identity")
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem=args.export.stem
    # A new invalid run must never leave a previous favorable score as current.
    (args.out_dir/f'{stem}.score.json').write_text(json.dumps({'status':'ERROR','reason':'EVALUATION_NOT_COMPLETED'}),encoding='utf-8')
    reference = clamp_reference(json.loads(args.reference.read_text(encoding="utf-8")))
    export = json.loads(args.export.read_text(encoding="utf-8"))
    if export["audio_duration_ms"] != reference["audio_duration_ms"]:
        sys.exit(f"Duration mismatch: export {export['audio_duration_ms']} ms, reference {reference['audio_duration_ms']} ms")
    (args.out_dir / f"{stem}.reference.json").write_text(json.dumps(reference, ensure_ascii=False, indent=1), encoding="utf-8")
    hypothesis = hypothesis_from_export(export, reference, args.audio)
    (args.out_dir / f"{stem}.hypothesis.json").write_text(json.dumps(hypothesis, ensure_ascii=False, indent=1), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "tools/score_transcript.py"), "--reference", str(args.out_dir / f"{stem}.reference.json"),
                    "--hypothesis", str(args.out_dir / f"{stem}.hypothesis.json"), "--output", str(args.out_dir / f"{stem}.score.json"),
                    "--collar-ms", "0"], capture_output=True)
    score = json.loads((args.out_dir / f"{stem}.score.json").read_text(encoding="utf-8"))
    if "wer" not in score:
        sys.exit("Scoring failed: " + json.dumps(score, ensure_ascii=False))
    speakers = sorted({s["speaker_id"] for s in export["segments"] if s["speaker_id"] is not None})
    unknown = sum(1 for s in export["segments"] if s["speaker_id"] is None)
    print(json.dumps({"clip": stem, "reference_speakers": len({s['speaker_id'] for s in reference['text_segments']}),
                      "app_speakers": len(speakers), "unknown_speaker_segments": unknown, "segments": len(export["segments"]),
                      "wer": f"{score['wer']['errors']}/{score['wer']['reference_words']}", "wer_rate": round(score["wer"]["rate"], 4),
                      "cpwer": f"{score['cpwer'].get('errors')}/{score['cpwer'].get('reference_words')}",
                      "cpwer_rate": round(score["cpwer"]["rate"], 4) if score["cpwer"].get("rate") is not None else None,
                      "mapping": score["cpwer"].get("mapping"), "der": score["der"]["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
