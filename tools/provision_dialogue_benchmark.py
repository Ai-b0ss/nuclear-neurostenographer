"""Prepare a tiny licensed ACTED/COMPOSED Russian evaluation, not a real-dialogue corpus.

No model calls or package installs. Audio stays ignored. References come solely
from the pinned external test.csv, never from recognition output. Clip extents
are NOT speech/word boundaries; no DER reference is created.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import wave
from provision_asr import ROOT, download

LOCK = json.loads((ROOT / "tools/fixtures/dialogs-ru-smoke-lock.json").read_text())


def compose(source, output, lock=LOCK):
    for pin in [lock["license"], lock["metadata"]]:
        if hashlib.sha256((source / pin["path"]).read_bytes()).hexdigest() != pin["sha256"]:
            raise ValueError("Unrecognized metadata/license")
    rows = list(csv.DictReader(io.StringIO((source / "test.csv").read_text(encoding="utf-8")), delimiter="|"))
    ds = [row for row in rows if row["speaker_id"] == "D" and row["emotion"] == "neutral"]
    ms = [row for row in rows if row["speaker_id"] == "M" and row["emotion"] == "neutral"]
    selected = [ds[0], ms[0], ds[1]]
    if [r["audio_path"] for r in selected] != [c["path"] for c in lock["clips"]]:
        raise ValueError("Frozen selection policy disagrees with metadata")
    payload, segments, at = bytearray(), [], 0
    rate, gap = lock["sample_rate"], lock["gap_frames"]
    for index, (clip, row) in enumerate(zip(lock["clips"], selected)):
        data = (source / Path(clip["path"]).name).read_bytes()
        if hashlib.sha256(data).hexdigest() != clip["sha256"]:
            raise ValueError("Unrecognized source audio")
        with wave.open(io.BytesIO(data)) as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes(), wav.getcomptype()) != (
                    1, 2, rate, clip["frames"], "NONE"):
                raise ValueError("Unexpected WAV format/extent")
            pcm = wav.readframes(clip["frames"])
            if len(pcm) != clip["frames"] * 2:
                raise ValueError("Truncated source PCM")
        segments.append({"start_ms": at * 1000 // rate, "end_ms": (at + clip["frames"]) * 1000 // rate,
                         "speaker_id": clip["speaker"], "text": row["text"]})
        payload.extend(pcm)
        at += clip["frames"]
        if index + 1 < len(selected):
            payload.extend(bytes(gap * 2))
            at += gap
    output.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output / "aba.wav"), "wb") as wav:
        wav.setparams((1, 2, rate, at, "NONE", "not compressed"))
        wav.writeframes(payload)
    digest = hashlib.sha256((output / "aba.wav").read_bytes()).hexdigest()
    if digest != lock["composite_sha256"]:
        (output / "aba.wav").unlink()
        raise ValueError("Composite bytes disagree with frozen fixture")
    reference = {"schema_version": 1, "recording_id": "dialogs-test-neutral-D-M-D-composed-v1",
        "annotation_source": f"https://huggingface.co/datasets/{lock['repository']}/blob/{lock['revision']}/test.csv",
        "license": "Dialogs OpenRAIL; copy of full terms in LICENSE.md; recipients must comply with Section 2",
        "kind": "ACTED_COMPOSED_THREE_UTTERANCES_NOT_NATURAL_DIALOGUE",
        "audio_sha256": digest, "audio_duration_ms": at * 1000 // rate, "text_segments": segments,
        "reference_limits": "External scripted text not manually audited; clip extents are NOT speech/word boundaries. DER deliberately absent.",
        "selection_policy": lock["selection_policy"], "training_contamination": "UNVERIFIED"}
    (output / "reference.json").write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copyfile(source / "LICENSE.md", output / "LICENSE.md")
    provenance = {"source_lock": lock, "composite_sha256": digest, "source_frames": at,
        "preprocessing": "Unchanged source PCM concatenation with two 500-ms zero gaps, canonical mono PCM16 44.1-kHz WAV. App performs its own normal resampling.",
        "license_note": "Dataset and derivative references/hypotheses require attached license and Section 2 restrictions; application/model licensing is separate."}
    (output / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return reference


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / ".local/dialogue-benchmark")
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to((ROOT / ".local").resolve()):
        raise ValueError("Fixture output must remain inside ignored workspace .local")
    assets = ROOT / ".local/androidTestAssets/dialogs"
    # These are generator-owned outputs. Failed provisioning must not leave a
    # previous favorable hypothesis/score/reference available as current evidence.
    for directory in [args.output, assets]:
        for name in ["aba.wav", "reference.json", "provenance.json", "hypothesis.json", "scores.json", "invocation.json", "LICENSE.md"]:
            (directory / name).unlink(missing_ok=True)
    source = ROOT / ".local/dialogs-ru-source"
    base = f"https://huggingface.co/datasets/{LOCK['repository']}/resolve/{LOCK['revision']}/"
    for item in [LOCK["license"], LOCK["metadata"], *LOCK["clips"]]:
        download(base + item["path"], source / Path(item["path"]).name, item["sha256"])
    reference = compose(source, args.output)
    assets.mkdir(parents=True, exist_ok=True)
    # External answers remain on the scoring runner, outside the test APK.
    # Inference receives audio and the required license, never reference text/IDs.
    for name in ["aba.wav", "LICENSE.md"]:
        shutil.copyfile(args.output / name, assets / name)
    print(json.dumps({"kind": reference["kind"], "audio_sha256": reference["audio_sha256"],
                      "audio_duration_ms": reference["audio_duration_ms"], "der": "NO_REFERENCE"}))


if __name__ == "__main__":
    main()
