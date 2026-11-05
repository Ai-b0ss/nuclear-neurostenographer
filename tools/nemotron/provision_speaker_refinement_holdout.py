"""Freeze four unused acted Russian dialogues before speaker-refinement validation.

Source: pinned Dialogs test metadata and WAVs. Audio/reference stay ignored in
.local. `--freeze` is a one-time operation before any model inference on these
clips; normal runs verify the committed lock exactly.
"""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import wave


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / ".local/dialogs-ru-source"
ASSETS = ROOT / ".local/androidTestAssets/speaker-refinement-holdout"
REFS = ROOT / ".local/speaker-refinement-holdout-refs"
LOCK_PATH = ROOT / "tools/fixtures/dialogs-ru-speaker-refinement-holdout-lock.json"
EXCLUSION_LOCKS = ("dialogs-ru-smoke-lock.json", "dialogs-ru-disjoint-holdout-lock.json",
                   "dialogs-ru-asr-holdout-lock.json", "dialogs-ru-window-merge-holdout-lock.json")
SEED = "c2-speaker-refinement-holdout-v1"
# All selected source WAVs returned HTTP 200 during preflight, before inference.
RANKS = {"D": [0, 1, 2, 3], "M": [0, 1, 2, 3], "S": [0, 1, 3, 5]}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    if args.freeze and LOCK_PATH.exists():
        raise ValueError("Lock already exists; refusing to replace frozen selection")
    original = json.loads((ROOT / "tools/fixtures/dialogs-ru-asr-holdout-lock.json").read_text(encoding="utf-8"))
    metadata = (SOURCE / "test.csv").read_bytes()
    license_bytes = (SOURCE / "LICENSE.md").read_bytes()
    assert sha(metadata) == original["metadata_sha256"]
    assert sha(license_bytes) == original["license_sha256"]
    rows = list(csv.DictReader(io.StringIO(metadata.decode("utf-8")), delimiter="|"))
    by_path = {r["audio_path"]: r for r in rows}
    excluded = set()
    for name in EXCLUSION_LOCKS:
        lock = json.loads((ROOT / "tools/fixtures" / name).read_text(encoding="utf-8"))
        excluded.update(c["path"] for c in lock["clips"])
    picks = {}
    for speaker in "DMS":
        eligible = [r for r in rows if r["speaker_id"] == speaker and
                    r["audio_path"] not in excluded and r["emotion"] not in ("poem", "sgorogovrki") and
                    3 <= float(r["duration"]) <= 12]
        eligible.sort(key=lambda r: sha(f"{SEED}:{r['audio_path']}".encode()))
        picks[speaker] = [eligible[i] for i in RANKS[speaker]]
        assert len(picks[speaker]) == 4
    ASSETS.mkdir(parents=True, exist_ok=True)
    REFS.mkdir(parents=True, exist_ok=True)
    result = {"repository": original["repository"], "revision": original["revision"],
              "metadata_sha256": original["metadata_sha256"],
              "license_sha256": original["license_sha256"],
              "selection_seed": SEED, "selection_ranks": RANKS,
              "sample_rate": 44100, "gap_frames": 22050,
              "clips": [], "cases": []}
    base_url = f"https://huggingface.co/datasets/{original['repository']}/resolve/{original['revision']}/"
    for group in range(4):
        pcm = bytearray()
        segments = []
        at = 0
        for index, speaker in enumerate("DMS"):
            row = picks[speaker][group]
            path = row["audio_path"]
            source = SOURCE / Path(path).name
            if not source.exists():
                source.write_bytes(urllib.request.urlopen(base_url + path, timeout=120).read())
            data = source.read_bytes()
            with wave.open(io.BytesIO(data)) as wav:
                assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) == \
                    (1, 2, result["sample_rate"], "NONE")
                frames = wav.getnframes()
                audio = wav.readframes(frames)
            assert len(audio) == frames * 2
            result["clips"].append({"path": path, "speaker": speaker,
                                    "emotion": row["emotion"], "frames": frames,
                                    "sha256": sha(data)})
            segments.append({"start_ms": at * 1000 // 44100,
                             "end_ms": (at + frames) * 1000 // 44100,
                             "speaker_id": speaker, "text": row["text"]})
            pcm.extend(audio)
            at += frames
            if index < 2:
                pcm.extend(bytes(result["gap_frames"] * 2))
                at += result["gap_frames"]
        case = f"speaker-holdout-{group}"
        wav_path = ASSETS / f"{case}.wav"
        with wave.open(str(wav_path), "wb") as wav:
            wav.setparams((1, 2, 44100, at, "NONE", "not compressed"))
            wav.writeframes(pcm)
        digest = sha(wav_path.read_bytes())
        reference = {"schema_version": 1, "recording_id": case,
                     "annotation_source": f"https://huggingface.co/datasets/{original['repository']}/blob/{original['revision']}/test.csv",
                     "license": "Dialogs OpenRAIL; Section 2 restrictions apply",
                     "kind": "ACTED_COMPOSED_THREE_UTTERANCES_NOT_NATURAL_DIALOGUE",
                     "audio_sha256": digest, "audio_duration_ms": at * 1000 // 44100,
                     "text_segments": segments,
                     "reference_limits": "Script text not manually re-audited; clip extents are not DER speech boundaries"}
        ref_path = REFS / f"{case}.ref.json"
        ref_path.write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result["cases"].append({"id": case, "audio_sha256": digest,
                                "reference_sha256": sha(ref_path.read_bytes())})
    if args.freeze:
        LOCK_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        assert result == json.loads(LOCK_PATH.read_text(encoding="utf-8")), "Holdout differs from frozen lock"
    (ASSETS / "plan.tsv").write_text("".join(f"{case['id']}\t1\t1\t1\n" for case in result["cases"]),
                                     encoding="utf-8")
    print(json.dumps({"cases": result["cases"], "source": result["repository"]}, indent=2))


if __name__ == "__main__":
    main()
