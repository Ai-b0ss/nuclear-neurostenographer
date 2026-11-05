"""Freeze an independent, single-speaker Golos farfield WER sample.

The tar and extracted audio/text remain in ignored .local. Selection is made
from metadata and a fixed seed before any inference; the committed lock pins
the source archive, each source item, and the converted WAV/reference.
"""

import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import wave


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / ".local/golos-farfield-test.tar"
ASSETS = ROOT / ".local/androidTestAssets/golos-farfield"
REFS = ROOT / ".local/golos-farfield-refs"
LOCK = ROOT / "tools/fixtures/golos-farfield-android-lock.json"
SOURCE_SHA256 = "f0a587ea242d22c3e1bfacfd08ecb6fd822bcee199811c2154b5bca883b7ec3b"
REVISION = "931f5c412a8045e0b03b9e5584072f0810c41dcc"
SEED = "golos-farfield-android-wer-v1"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    if args.freeze and LOCK.exists():
        raise ValueError("Refusing to replace frozen selection")
    assert sha(SOURCE.read_bytes()) == SOURCE_SHA256
    with tarfile.open(SOURCE) as archive:
        members = {m.name: m for m in archive.getmembers()}
        metadata = [json.load(archive.extractfile(m)) for m in members.values()
                    if m.name.endswith(".json")]
        assert len(metadata) == 1916
        bins = ((2.0, 3.0), (3.0, 4.0), (4.0, 8.0))
        picks = []
        for low, high in bins:
            eligible = [row for row in metadata if low <= row["duration"] < high
                        and len(row["text"].split()) >= 3
                        and f'{row["id"]}.opus' in members]
            eligible.sort(key=lambda row: sha(f'{SEED}:{row["id"]}'.encode()))
            assert len(eligible) >= 10
            picks.extend(eligible[:10])
        ASSETS.mkdir(parents=True, exist_ok=True)
        REFS.mkdir(parents=True, exist_ok=True)
        cases = []
        for index, row in enumerate(picks):
            source_name = f'{row["id"]}.opus'
            opus = archive.extractfile(members[source_name]).read()
            pcm = subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
                 "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1"],
                input=opus, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout
            out = io.BytesIO()
            with wave.open(out, "wb") as writer:
                writer.setparams((1, 2, 16000, len(pcm) // 2, "NONE", "not compressed"))
                writer.writeframes(pcm)
            converted = out.getvalue()
            case_id = f"golos-farfield-{index:02d}"
            wav = ASSETS / f"{case_id}.wav"
            wav.write_bytes(converted)
            ref = REFS / f"{case_id}.json"
            ref.write_text(json.dumps({"id": row["id"], "text": row["text"],
                                       "duration": row["duration"]}, ensure_ascii=False,
                                      indent=2) + "\n", encoding="utf-8")
            cases.append({"id": case_id, "source_id": row["id"],
                          "source_opus_sha256": sha(opus), "wav_sha256": sha(converted),
                          "reference_sha256": sha(ref.read_bytes()),
                          "duration": row["duration"]})
    result = {"dataset": "Golos farfield test (OpenSLR SLR114)",
              "mirror": "Sh1man/golos_opus", "revision": REVISION,
              "archive": "farfield/test/test-00000.tar", "archive_sha256": SOURCE_SHA256,
              "selection_seed": SEED, "duration_bins_seconds": [[2, 3], [3, 4], [4, 8]],
              "cases_per_bin": 10, "cases": cases,
              "metric": "WER only; no multi-speaker or timing ground truth"}
    if args.freeze:
        LOCK.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        assert result == json.loads(LOCK.read_text(encoding="utf-8"))
    (ASSETS / "plan.tsv").write_text("".join(f'{c["id"]}\t1\t1\t1\n' for c in cases),
                                      encoding="utf-8")
    print(f"Frozen {len(cases)} cases, {sum(c['duration'] for c in cases):.1f} seconds")


if __name__ == "__main__":
    main()
