"""Build four frozen acted Russian ASR holdouts from pinned source clips.

Run tools/provision_dialogue_benchmark.py first to fetch test.csv/license. Source
WAVs listed in the lock must be downloaded from its pinned dataset revision.
Outputs and licensed audio remain ignored under .local/.
"""

import csv
import hashlib
import io
import json
from pathlib import Path
import wave


ROOT = Path(__file__).resolve().parents[2]
LOCK = json.loads((ROOT / "tools/fixtures/dialogs-ru-asr-holdout-lock.json").read_text(encoding="utf-8"))
SOURCE = ROOT / ".local/dialogs-ru-source"
ASSETS = ROOT / ".local/androidTestAssets/asr-holdout"
REFS = ROOT / ".local/asr-independent-holdout"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert sha256(SOURCE / "test.csv") == LOCK["metadata_sha256"]
    assert sha256(SOURCE / "LICENSE.md") == LOCK["license_sha256"]
    rows = {row["audio_path"]: row for row in csv.DictReader(
        (SOURCE / "test.csv").open(encoding="utf-8"), delimiter="|")}
    assert len(LOCK["clips"]) == 12
    ASSETS.mkdir(parents=True, exist_ok=True)
    REFS.mkdir(parents=True, exist_ok=True)
    plan = []
    for group in range(4):
        clips = LOCK["clips"][group * 3:(group + 1) * 3]
        assert [c["speaker"] for c in clips] == list("DMS")
        pcm = bytearray()
        segments = []
        at = 0
        rate = LOCK["sample_rate"]
        for index, clip in enumerate(clips):
            source = SOURCE / Path(clip["path"]).name
            assert sha256(source) == clip["sha256"]
            row = rows[clip["path"]]
            assert row["speaker_id"] == clip["speaker"] and row["emotion"] == clip["emotion"]
            with wave.open(io.BytesIO(source.read_bytes())) as wav:
                assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(),
                        wav.getnframes(), wav.getcomptype()) == (1, 2, rate, clip["frames"], "NONE")
                samples = wav.readframes(clip["frames"])
            segments.append({"start_ms": at * 1000 // rate,
                             "end_ms": (at + clip["frames"]) * 1000 // rate,
                             "speaker_id": clip["speaker"], "text": row["text"]})
            pcm.extend(samples)
            at += clip["frames"]
            if index < 2:
                pcm.extend(bytes(LOCK["gap_frames"] * 2))
                at += LOCK["gap_frames"]
        case = f"acted-holdout-{group}"
        wav_path = ASSETS / f"{case}.wav"
        with wave.open(str(wav_path), "wb") as wav:
            wav.setparams((1, 2, rate, at, "NONE", "not compressed"))
            wav.writeframes(pcm)
        digest = sha256(wav_path)
        reference = {
            "schema_version": 1, "recording_id": case,
            "annotation_source": f"https://huggingface.co/datasets/{LOCK['repository']}/blob/{LOCK['revision']}/test.csv",
            "license": "Dialogs OpenRAIL; Section 2 restrictions apply",
            "kind": "ACTED_COMPOSED_THREE_UTTERANCES_NOT_NATURAL_DIALOGUE",
            "audio_sha256": digest, "audio_duration_ms": at * 1000 // rate,
            "text_segments": segments,
            "reference_limits": "Script text is not manually re-audited; clip extents are not speech boundaries; no DER.",
            "selection_policy": LOCK["selection_policy"],
            "training_contamination": "UNVERIFIED",
        }
        (REFS / f"{case}.ref.json").write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        plan.append(f"{case}\t1\t1\t1")
        print(case, digest, reference["audio_duration_ms"])
    (ASSETS / "plan.tsv").write_text("\n".join(plan) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
