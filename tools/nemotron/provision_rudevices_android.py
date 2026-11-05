"""Freeze the complete 47-record tail shard of SOVA RuDevices for Android WER.

The third-party mirror supplies a test split, but SOVA did not define an
official train/test split. This is a conversational-speech probe, not a
multi-speaker or training-disjoint benchmark. WAV/text remain ignored.
"""

import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import wave
import io


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / ".local/rudevices-test-tail.tar"
ASSETS = ROOT / ".local/androidTestAssets/rudevices-tail"
REFS = ROOT / ".local/rudevices-tail-refs"
LOCK = ROOT / "tools/fixtures/rudevices-tail-android-lock.json"
ARCHIVE_SHA256 = "4a37760aba6ec72d55d0911bd2941510ef3fbdf368bfed012ba42debb2a1cfcc"
REVISION = "3d5a8ee75616a47d339c9c9a7f84fc75c0e93d43"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    if args.freeze and LOCK.exists():
        raise ValueError("Refusing to replace frozen selection")
    assert sha(SOURCE.read_bytes()) == ARCHIVE_SHA256
    ASSETS.mkdir(parents=True, exist_ok=True)
    REFS.mkdir(parents=True, exist_ok=True)
    with tarfile.open(SOURCE) as archive:
        members = {m.name: m for m in archive.getmembers()}
        rows = [json.load(archive.extractfile(m)) for m in members.values()
                if m.name.endswith(".json")]
        assert len(rows) == 47
        assert len({row["id"] for row in rows}) == len(rows)
        rows.sort(key=lambda row: row["id"])
        cases = []
        for index, row in enumerate(rows):
            wav_bytes = archive.extractfile(members[f'{row["id"]}.wav']).read()
            with wave.open(io.BytesIO(wav_bytes)) as reader:
                assert (reader.getnchannels(), reader.getsampwidth(),
                        reader.getframerate(), reader.getcomptype()) == (1, 2, 16000, "NONE")
            name = f"rudevices-{index:02d}"
            (ASSETS / f"{name}.wav").write_bytes(wav_bytes)
            reference = REFS / f"{name}.json"
            reference.write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
            cases.append({"id": name, "source_id": row["id"],
                          "wav_sha256": sha(wav_bytes),
                          "reference_sha256": sha(reference.read_bytes()),
                          "duration": row["duration"]})
    lock = {"dataset": "SOVA RuDevices live Russian speech",
            "mirror": "Sh1man/rudevices", "revision": REVISION,
            "archive": "rudevices_audio_records/test/test-00001.tar",
            "archive_sha256": ARCHIVE_SHA256, "selection": "all 47 records in tail shard",
            "split_caveat": "SOVA authors did not define an official test split",
            "metric": "WER only; no speaker/timing labels", "cases": cases}
    if args.freeze:
        LOCK.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        assert lock == json.loads(LOCK.read_text(encoding="utf-8"))
    (ASSETS / "plan.tsv").write_text("".join(f'{c["id"]}\t1\t1\t1\n' for c in cases),
                                      encoding="utf-8")
    print(f"Frozen {len(cases)} cases, {sum(c['duration'] for c in cases):.1f} seconds")


if __name__ == "__main__":
    main()
