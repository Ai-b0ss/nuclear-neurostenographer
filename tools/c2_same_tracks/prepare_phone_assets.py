"""Test APK assets for C0 versus C2 on the HONOR phone: the same files as the host run, hash-checked, plus a frozen plan.

python tools/c2_same_tracks/prepare_phone_assets.py --root ROOT --manifest docs/evidence/c2-same-tracks/manifest.json \
    --assets .local/androidTestAssets --report device-evidence/phone-assets.json
Plan rows: case, repeats, full path (ASR + exports), public text (transcript text may leave the device).
Fixed before any phone run: the three phone tracks twice (repeat stability), the first two holdout ids of each shard,
two real-call mixes, the acted D-M-D clip (needed by the damaged-model test) and the first 20 minutes of ru_000010
(cancellation test and the 20-minute speed and memory gate). Text is public only for the synthetic MIT tracks.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

PHONE3 = ("syn3-clean", "syn3-brown", "syn4-noise")
REALMIX = ("realmix-02-07", "realmix-05-13")
LONG_SHA256 = "e9933e55693151a6f2c5d0f34188348d62053b66a70d9dad0dd25ffd3a408df5"
ACTED_SHA256 = "9294f7fc91b96c73b02148922030bbf2a3a740a1bb920ccbf2a5b243d0316c87"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plan_rows(cases):
    holdout = {}
    for case in sorted((c for c in cases if c["set"] == "holdout"), key=lambda c: c["id"]):
        holdout.setdefault(case["id"].split("-")[1], []).append(case["id"])
    rows = [(c, 2, 1, 1) for c in PHONE3]
    rows += [(c, 1, 1, 1) for shard in sorted(holdout) for c in holdout[shard][:2]]
    rows += [(c, 1, 0, 0) for c in REALMIX]
    rows += [("acted-dmd", 1, 0, 0), ("long-ru_000010", 1, 0, 0)]
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    cases = {c["id"]: c for c in json.loads(args.manifest.read_text(encoding="utf-8"))["cases"]}
    out = args.assets / "nemotron-bench"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    rows = plan_rows(cases.values())
    report = {"plan": [list(r) for r in rows], "files": {}}
    for case_id, *_ in rows:
        target = out / f"{case_id}.wav"
        if case_id in cases:
            source = args.root / "data/same" / f"{case_id}.wav"
            expected = cases[case_id]["audio_sha256"]
        elif case_id == "acted-dmd":
            source, expected = args.root / "data/corpus/acted-dmd.wav", ACTED_SHA256
        else:
            source, expected = args.root / "long-ru_000010.wav", LONG_SHA256
            if not source.exists():
                subprocess.run([args.ffmpeg, "-v", "error", "-y", "-t", "1200", "-i", str(args.root / "data/raw/datahive/ru_000010.mp3"),
                                "-ar", "16000", "-ac", "1", "-bitexact", "-c:a", "pcm_s16le", str(source)], check=True)
        actual = sha(source)
        # Only the long file may differ (another ffmpeg decodes the MP3 slightly differently); it is used for speed and memory only.
        if actual != expected and case_id != "long-ru_000010":
            raise SystemExit(f"{case_id}: hash {actual} is not {expected}")
        shutil.copyfile(source, target)
        report["files"][case_id] = {"sha256": actual, "matches_frozen": actual == expected}
    (out / "plan.tsv").write_text("".join("\t".join(map(str, r)) + "\n" for r in rows), encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
