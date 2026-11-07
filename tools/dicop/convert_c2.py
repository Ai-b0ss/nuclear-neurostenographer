"""Convert frozen C2 references or turns into the official DiCoP RTTM/audio layout.

Reference (oracle diarization):
python tools/dicop/convert_c2.py --manifest docs/evidence/c2-same-tracks/manifest.json \
    --corpus ROOT/data/same --mode reference --output ROOT/dicop/reference

C2 diarization:
python tools/dicop/convert_c2.py --manifest docs/evidence/c2-same-tracks/manifest.json \
    --corpus ROOT/data/same --mode c2 --turns ROOT/results-same/C2 --output ROOT/dicop/c2

Only stdlib file conversion and WAV validation are performed. No DiCoP checkout, checkpoint,
model download, training or inference is needed. Unknown C2 cluster -1 is excluded and counted.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import wave

from contract import checkpoint_contract, upstream_contract

SAFE_TOKEN = re.compile(r"^[A-Za-z0-9_.~-]+$")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rttm_escape(value):
    """Percent-encode one whitespace-delimited RTTM token as UTF-8."""
    value = str(value)
    if not value:
        raise ValueError("RTTM tokens must not be empty")
    if SAFE_TOKEN.fullmatch(value):
        return value
    return "".join(
        character if re.fullmatch(r"[A-Za-z0-9_.~-]", character) else "".join(
            f"%{byte:02X}" for byte in character.encode("utf-8")
        )
        for character in value
    )


def validate_intervals(turns, duration_ms):
    if not isinstance(duration_ms, int) or isinstance(duration_ms, bool) or duration_ms <= 0:
        raise ValueError("audio_duration_ms must be a positive integer")
    validated = []
    for index, turn in enumerate(turns):
        try:
            start, end, speaker = turn["start_ms"], turn["end_ms"], turn["speaker_id"]
        except (KeyError, TypeError) as exc:
            raise ValueError(f"turn {index}: start_ms, end_ms and speaker_id are required") from exc
        if any(not isinstance(value, int) or isinstance(value, bool) for value in (start, end)):
            raise ValueError(f"turn {index}: interval bounds must be integer milliseconds")
        if start < 0 or end <= start or end > duration_ms:
            raise ValueError(f"turn {index}: invalid interval [{start}, {end}) for duration {duration_ms}")
        if speaker is None or not str(speaker):
            raise ValueError(f"turn {index}: speaker_id must not be empty")
        validated.append({"start_ms": start, "end_ms": end, "speaker_id": str(speaker)})
    return sorted(
        validated, key=lambda turn: (turn["start_ms"], turn["end_ms"], turn["speaker_id"])
    )


def rttm_text(session_id, turns):
    session = rttm_escape(session_id)
    return "".join(
        f"SPEAKER {session} 1 {turn['start_ms'] / 1000:.3f} "
        f"{(turn['end_ms'] - turn['start_ms']) / 1000:.3f} <NA> <NA> "
        f"{rttm_escape(turn['speaker_id'])} <NA> <NA>\n"
        for turn in turns
    )


def read_c2_turns(path, duration_ms):
    turns = []
    unknown = 0
    for line_number, line in enumerate(Path(path).read_text(encoding="ascii").splitlines(), 1):
        if not line.strip():
            continue
        try:
            start, end, cluster = line.split("\t")
            start, end, cluster = int(start), int(end), int(cluster)
        except ValueError as exc:
            raise ValueError(f"{path}:{line_number}: expected start_ms<TAB>end_ms<TAB>cluster") from exc
        if cluster < 0:
            unknown += 1
            continue
        turns.append({"start_ms": start, "end_ms": end, "speaker_id": f"h{cluster}"})
    return validate_intervals(turns, duration_ms), unknown


def read_reference(path, case_id):
    reference = json.loads(Path(path).read_text(encoding="utf-8"))
    if reference.get("recording_id") != case_id:
        raise ValueError(f"{path}: recording_id does not match case {case_id}")
    duration = reference.get("audio_duration_ms")
    turns = validate_intervals(reference.get("diarization", []), duration)
    if not turns:
        raise ValueError(f"{path}: no diarization turns")
    return reference, turns


def validate_wav(path, expected_sha256, expected_duration_ms):
    actual_sha = sha256(path)
    if actual_sha != expected_sha256:
        raise ValueError(f"{path}: audio SHA-256 does not match the frozen manifest")
    with wave.open(str(path), "rb") as audio:
        properties = (audio.getframerate(), audio.getnchannels(), audio.getsampwidth())
        duration = round(audio.getnframes() * 1000 / audio.getframerate())
    if properties != (16000, 1, 2):
        raise ValueError(f"{path}: expected 16 kHz mono PCM16 WAV, got {properties}")
    if duration != expected_duration_ms:
        raise ValueError(f"{path}: WAV duration {duration} ms != reference {expected_duration_ms} ms")
    return actual_sha


def convert(manifest_path, corpus, output, mode="reference", turns_dir=None):
    if mode not in ("reference", "c2"):
        raise ValueError("mode must be reference or c2")
    if mode == "c2" and turns_dir is None:
        raise ValueError("--turns is required in c2 mode")
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    corpus, output = Path(corpus), Path(output)
    rows = []
    for case in sorted(manifest["cases"], key=lambda item: item["id"]):
        case_id = case["id"]
        source_audio = corpus / f"{case_id}.wav"
        reference, reference_turns = read_reference(corpus / f"{case_id}.ref.json", case_id)
        if reference.get("audio_sha256") != case["audio_sha256"]:
            raise ValueError(f"{case_id}: reference and manifest audio hashes differ")
        audio_sha = validate_wav(source_audio, case["audio_sha256"], reference["audio_duration_ms"])
        if mode == "reference":
            turns, unknown = reference_turns, 0
            turns_source = f"{case_id}.ref.json#diarization"
        else:
            turns_path = Path(turns_dir) / f"{case_id}.tsv"
            turns, unknown = read_c2_turns(turns_path, reference["audio_duration_ms"])
            turns_source = str(turns_path)
        if not turns:
            raise ValueError(f"{case_id}: no usable turns after unknown clusters are excluded")
        session = rttm_escape(case_id)
        audio_dir, rttm_dir = output / "audio", output / "rttm"
        audio_dir.mkdir(parents=True, exist_ok=True)
        rttm_dir.mkdir(parents=True, exist_ok=True)
        target_audio = audio_dir / f"{session}.wav"
        shutil.copyfile(source_audio, target_audio)
        rttm_path = rttm_dir / f"{session}.rttm"
        rttm_path.write_text(rttm_text(case_id, turns), encoding="ascii", newline="\n")
        rows.append({
            "case_id": case_id,
            "session_id": session,
            "turns_source": turns_source,
            "turns": len(turns),
            "unknown_turns_excluded": unknown,
            "audio": f"audio/{session}.wav",
            "audio_sha256": audio_sha,
            "rttm": f"rttm/{session}.rttm",
            "rttm_sha256": sha256(rttm_path),
        })
    result = {
        "schema_version": 1,
        "status": "READY_FOR_INFERENCE_LAYOUT",
        "mode": mode,
        "upstream": upstream_contract(),
        "checkpoint": checkpoint_contract(),
        "audio_layout": "audio/{session}.wav",
        "rttm_layout": "rttm/{session}.rttm",
        "infer_command": "python infer.py --rttm rttm --audio-dir audio --output hyp.stm --checkpoint LOCAL_RUSSIAN_PROVEN_CHECKPOINT",
        "cases": rows,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "fixture-manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--mode", choices=("reference", "c2"), default="reference")
    parser.add_argument("--turns", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = convert(args.manifest, args.corpus, args.output, args.mode, args.turns)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, wave.Error) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(f"Prepared {len(result['cases'])} sessions in {args.output}; inference NOT_RUN")


if __name__ == "__main__":
    main()
