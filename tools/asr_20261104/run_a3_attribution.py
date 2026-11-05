"""A3 through the app's own OfflineAsr on the frozen same-recordings corpus and the SAME C2 turns (results-same/C2/*.tsv),
scored like rescore_a3_digits.py (digits spelled out in the hypothesis, then score_same_corpus.measure unchanged).
Used to compare two builds of the ASR path, e.g. main (windows cut at every diarization boundary, chunk attribution)
against word-timestamp attribution. --src picks the source tree to build from (default: this checkout); --base points at
an earlier --out of this script and adds paired bootstrap CIs (this run minus base, by recording).

python -I tools/asr_20261104/run_a3_attribution.py --root K:/nn-bench --java JAVA17 --model K:/nn-bench/data/models/a3-opsetfix \
    --out K:/nn-bench/results-a3w/new --base K:/nn-bench/results-a3w/main
"""
import argparse, hashlib, json, re, subprocess, sys, time
from pathlib import Path
from num2words import num2words

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools")); sys.path.insert(0, str(REPO / "tools/c2_same_tracks"))
from score_same_corpus import measure, load_reference, read_turns, bootstrap  # noqa: E402

KEYS = ("wer", "cpwer", "cpwer_u")

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def spell(text):
    text = re.sub(r"(?<=\d)[ \u00a0](?=\d{3}\b)", "", text)
    return re.sub(r"\d+", lambda m: " " + num2words(int(m.group()), lang="ru") + " ", text)

def build(root, java, src, out):
    h = root / "harness"; kotlin = h / "kotlin"; jar = out / "bench-asr.jar"
    stub = out / "BuildConfigStub.kt"
    stub.write_text('package ru.neurostenographer.app\nobject BuildConfig { val ASR_A3: Boolean = true }\n', encoding="utf-8")
    app = src / "app/src/main/java/ru/neurostenographer/app"
    files = sorted((src / "core/src/main/kotlin/ru/neurostenographer/core").glob("*.kt"))
    files += [app / f"{n}.kt" for n in ("OfflineAsr", "OfflineDiarization", "AsrModelSpec", "InferenceThreads")]
    files += [src / "tools/diar_bench/DiarBench.kt", stub]
    cp = ";".join(map(str, [kotlin / "kotlin-stdlib.jar", h / "classes.jar", h / "placeholder.jar"]))
    subprocess.run([java, "-cp", str(kotlin / "*"), "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler", "-no-stdlib", "-no-reflect", "-nowarn",
                    "-jvm-target", "17", "-classpath", cp, "-d", str(jar), *map(str, files)], check=True)
    return f"{jar};{cp}", h / "native"

def main():
    ap = argparse.ArgumentParser()
    for a in ("--root", "--model", "--out"): ap.add_argument(a, type=Path, required=True)
    ap.add_argument("--java", required=True)
    ap.add_argument("--src", type=Path, default=REPO)
    ap.add_argument("--base", type=Path)
    ap.add_argument("--manifest", type=Path, default=REPO / "docs/evidence/c2-same-tracks/manifest.json")
    args = ap.parse_args()
    corpus, turns_dir = args.root / "data/same", args.root / "results-same/C2"
    args.out.mkdir(parents=True, exist_ok=True)
    classpath, native = build(args.root, args.java, args.src, args.out)
    cases = [c for c in json.loads(args.manifest.read_text(encoding="utf-8"))["cases"] if c["text"]]
    rows, runs = [], {}
    for case in cases:
        wav, tsv = corpus / f"{case['id']}.wav", turns_dir / f"{case['id']}.tsv"
        assert sha(wav) == case["audio_sha256"], wav
        tr, meta = args.out / f"{case['id']}.transcript.json", args.out / f"{case['id']}.asrmeta.json"
        t0 = time.monotonic()
        r = subprocess.run([args.java, f"-Djava.library.path={native}", "-Xmx4g", "-cp", classpath,
                            "ru.neurostenographer.tools.DiarBenchKt", "asr", str(args.model), str(wav), str(tsv), str(tr), str(meta)],
                           capture_output=True, text=True)
        ok = r.returncode == 0 and tr.exists()
        runs[case["id"]] = dict(status="OK" if ok else f"FAIL rc={r.returncode} {r.stderr[-300:]}", wall_s=round(time.monotonic() - t0, 1),
                                meta=json.loads(meta.read_text()) if meta.exists() else None)
        if not ok: sys.exit(f"{case['id']}: {runs[case['id']]['status']}")
        segs = [dict(s, text=spell(s["text"])) for s in json.loads(tr.read_text(encoding="utf-8"))["segments"]]
        row = dict(case=case["id"], set=case["set"], **measure(case, load_reference(corpus, case), read_turns(tsv), segs))
        rows.append(row); print(case["id"], *(row[k].get("errors") for k in KEYS), row["unattributed_words"], flush=True)
    base = {r["case"]: r for r in json.loads((args.base / "rows.json").read_text(encoding="utf-8"))} if args.base else {}
    summary = {}
    for name in ("all", "holdout", "phone3"):
        sel = [r for r in rows if name == "all" or r["set"] == name]
        s = summary[name] = {"unattributed_words": sum(r["unattributed_words"] for r in sel)}
        for k in KEYS:
            R = [r for r in sel if r[k].get("status") == "SCORED"]
            e, n = sum(r[k]["errors"] for r in R), sum(r[k]["reference_words"] for r in R)
            s[k] = dict(errors=e, words=n, rate=round(e / n, 4) if n else None, cases=len(R))
            if base:
                pairs = [(base[r["case"]][k]["errors"], r[k]["errors"], r[k]["reference_words"]) for r in sel
                         if r[k].get("status") == "SCORED" and base[r["case"]][k].get("status") == "SCORED"]
                s[f"{k}_paired"] = dict(cases=len(pairs), base_errors=sum(p[0] for p in pairs), errors=sum(p[1] for p in pairs),
                                        words=sum(p[2] for p in pairs), ci95_minus_base=bootstrap(pairs) if len(pairs) > 1 else None)
    (args.out / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    (args.out / "runs.json").write_text(json.dumps(runs, indent=1), encoding="utf-8")
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))

if __name__ == "__main__":
    main()
