"""Freeze four independent Russian RTTM fixtures for the Android C0/C2 probe.

Download the three pinned WebDataset shards into .local/ru-book-mix first.
Audio and labels remain in ignored .local; the committed selection predates inference.
"""

import hashlib
import io
import json
from pathlib import Path
import tarfile

import soundfile as sf


ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / ".local/ru-book-mix"
DEST = ROOT / ".local/androidTestAssets/rubook-probe"
REVISION = "18655c48833c5acfcd868a36eb38465712d15f1c"
CASES = (("rec_0000", "development"), ("rec_0055", "development"),
         ("rec_0275", "development"), ("rec_0437", "development"),
         ("rec_0001", "holdout"), ("rec_0056", "holdout"),
         ("rec_0274", "holdout"), ("rec_0438", "holdout"))


def main():
    manifest = {row["file_id"]: row for row in
                (json.loads(line) for line in (RAW / "manifest.jsonl").read_text().splitlines())}
    DEST.mkdir(parents=True, exist_ok=True)
    lock = {"source": "mexus/ru-book-mix-10h", "revision": REVISION,
            "license": "CC-BY-4.0", "cases": []}
    for case, split in CASES:
        meta = manifest[case]
        shard = RAW / Path(meta["shard"]).name
        with tarfile.open(shard) as archive:
            flac = archive.extractfile(f"{case}.flac").read()
            rttm = archive.extractfile(f"{case}.rttm").read().decode("utf-8")
        audio, rate = sf.read(io.BytesIO(flac), dtype="float32")
        assert rate == 16000 and audio.ndim == 1 and len(audio) == 960000
        wav = DEST / f"{case}.wav"
        sf.write(wav, audio, rate, subtype="PCM_16")
        digest = hashlib.sha256(wav.read_bytes()).hexdigest()
        turns = []
        for line in rttm.splitlines():
            fields = line.split()
            assert len(fields) >= 9 and fields[0] == "SPEAKER" and fields[1] == case
            start = round(float(fields[3]) * 1000)
            end = min(60000, round((float(fields[3]) + float(fields[4])) * 1000))
            if end > start:
                turns.append({"start_ms": start, "end_ms": end, "speaker_id": fields[7]})
        assert len({turn["speaker_id"] for turn in turns}) == meta["n_speakers"]
        reference = {"schema_version": 1, "recording_id": case,
                     "annotation_source": "Generator RTTM; independent of app output",
                     "license": "CC-BY-4.0", "kind": "synthetic audiobook mix",
                     "audio_sha256": digest, "audio_duration_ms": 60000,
                     "diarization": turns}
        (DEST / f"{case}.ref.json").write_text(json.dumps(reference, ensure_ascii=False), encoding="utf-8")
        lock["cases"].append({"id": case, "split": split, "shard": meta["shard"],
                              "n_speakers": meta["n_speakers"],
                              "overlap2": meta["overlap_stats"]["overlap2"],
                              "audio_sha256": digest,
                              "reference_sha256": hashlib.sha256((DEST / f"{case}.ref.json").read_bytes()).hexdigest()})
    (DEST / "lock.json").write_text(json.dumps(lock, indent=2), encoding="utf-8")
    pinned = json.loads((ROOT / "tools/fixtures/rubook-android-lock.json").read_text(encoding="utf-8"))
    assert lock == pinned, "Downloaded audio or labels differ from the committed lock"
    print(json.dumps(lock, indent=2))


if __name__ == "__main__":
    main()
