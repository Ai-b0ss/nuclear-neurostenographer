"""Copy frozen corpus recordings into the disposable test APK assets after checking their hashes.

Run after build_corpus.py. The report records whether the emulator receives the same bytes as the host benchmark.
The audio is never uploaded as an artifact.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

PLAN = [("acted-dmd", 3, 1), ("datahive-ru_000001", 1, 1), ("rubook-rec_0416-white0db", 2, 0), ("rubook-rec_0062", 1, 0), ("rubook-rec_0284", 1, 0),
        ("rubook-rec_0455", 1, 0), ("rubook-rec_0178", 1, 0), ("rubook-rec_0062-white10db", 1, 0), ("datahive-ru_000010", 1, 0), ("datahive-ru_000013", 1, 0),
        ("nonspeech-silence", 1, 0), ("nonspeech-whitenoise", 1, 0)]
LONG = ("long-ru_000010", 1, 0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--long-wav", type=Path)
    parser.add_argument("--long-manifest", type=Path)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    cases = {c["id"]: c for c in json.loads(args.manifest.read_text(encoding="utf-8"))["cases"]}
    out = args.assets / "nemotron-bench"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    check = {}
    args.report.mkdir(parents=True, exist_ok=True)
    for case_id, repeats, full in PLAN:
        source = args.corpus / f"{case_id}.wav"
        actual = hashlib.sha256(source.read_bytes()).hexdigest()
        check[case_id] = {"expected": cases[case_id]["audio_sha256"], "actual": actual, "match": actual == cases[case_id]["audio_sha256"]}
        # An MP3 decoded by another ffmpeg build can differ. Such a file gets its own interval reference from this
        # run, and the report says so. Anything else that differs stops the run.
        if not check[case_id]["match"]:
            if not case_id.startswith(("datahive-", "acted-")):
                raise SystemExit(f"Hash differs from the frozen manifest: {case_id}")
            reference = json.loads((args.corpus / f"{case_id}.ref.json").read_text(encoding="utf-8"))
            reference.pop("text_segments", None)
            (args.report / f"{case_id}.ref.json").write_text(json.dumps(reference), encoding="utf-8")
        shutil.copyfile(source, out / f"{case_id}.wav")
        rows.append(f"{case_id}\t{repeats}\t{full}\n")
    if args.long_wav:
        expected = json.loads(args.long_manifest.read_text(encoding="utf-8"))["cases"][0]["audio_sha256"]
        actual = hashlib.sha256(args.long_wav.read_bytes()).hexdigest()
        check[LONG[0]] = {"expected": expected, "actual": actual, "match": actual == expected}
        shutil.copyfile(args.long_wav, out / f"{LONG[0]}.wav")
        rows.append(f"{LONG[0]}\t{LONG[1]}\t{LONG[2]}\n")
    (out / "plan.tsv").write_text("".join(rows), encoding="utf-8", newline="\n")
    (args.report / "corpus-check.json").write_text(json.dumps(check, indent=1) + "\n", encoding="utf-8")
    print("prepared", len(rows), "hash matches", sum(v["match"] for v in check.values()))


if __name__ == "__main__":
    main()
