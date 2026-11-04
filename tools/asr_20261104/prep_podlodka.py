"""Extract Podlodka (bond005/podlodka_speech @4a91614) clips to 16 kHz mono WAV + SHA-256 manifest.
FINDING: published validation and test splits are byte-identical (20/20 WAV+ref SHA equal), so validation is DROPPED.
HOLDOUT = published test (episodes 132,275,292,306). DEV = train rows from episodes NOT in test (7,200,312,338,358) -> disjoint episodes.
Never tune on HOLDOUT.
Usage: python -I prep_podlodka.py <data_dir_with_parquet> <out_dir>
Human-transcribed podcast speech: independent of the project's synthetic/acted sets, but
single clip-level references only (no speaker labels), license unstated -> evaluation only, not redistributed."""
import hashlib, io, json, sys
from pathlib import Path
import numpy as np, pyarrow.parquet as pq, soundfile as sf

def resample(x, sr, to=16000):
    if sr == to: return x
    n = int(round(len(x) * to / sr))
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)

def main(src, out):
    src, out = Path(src), Path(out); out.mkdir(parents=True, exist_ok=True)
    man = {"dataset": "bond005/podlodka_speech", "revision": "4a9161485a70ea849ccaa54a72faa9bfc0a60627",
           "resample": "numpy linear interpolation to 16 kHz mono PCM16", "items": []}
    test_eps = {r["episode"] for r in pq.read_table(next(src.glob("test-*.parquet")), columns=["episode"]).to_pylist()}
    for split, group in (("train", "DEV"), ("test", "HOLDOUT")):
        t = pq.read_table(next(src.glob(f"{split}-*.parquet"))).to_pylist()
        if split == "train": t = [r for r in t if r["episode"] not in test_eps]
        for i, r in enumerate(t):
            x, sr = sf.read(io.BytesIO(r["audio"]["bytes"]), dtype="float32", always_2d=True)
            x = resample(x.mean(1), sr)
            wav = out / f"podlodka-{split}-{i:02d}.wav"
            sf.write(wav, x, 16000, subtype="PCM_16")
            ref = out / (wav.stem + ".ref.txt"); ref.write_text(r["transcription"], encoding="utf8")
            man["items"].append({"id": wav.stem, "group": group, "split": split, "episode": r["episode"],
                "duration_s": round(len(x) / 16000, 3), "wav": wav.name,
                "wav_sha256": hashlib.sha256(wav.read_bytes()).hexdigest(),
                "ref": ref.name, "ref_sha256": hashlib.sha256(ref.read_bytes()).hexdigest(),
                "kind": "HUMAN_TRANSCRIBED_PODCAST_SEGMENT"})
    (out / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf8")
    for g in ("DEV", "HOLDOUT"):
        it = [m for m in man["items"] if m["group"] == g]
        print(g, len(it), "clips", round(sum(m["duration_s"] for m in it)), "s")
main(*sys.argv[1:3])
