"""A0 (GigaAM v3 CTC) vs A3 (GigaAM v3 e2e RNNT, opset-fixed) on the frozen same-recordings corpus, through the app's own
OfflineAsr, on the SAME C2 speaker turns (results-same/C2/*.tsv). Only the ASR differs, so DER is identical by construction
(it depends on the turns only) and is not recomputed here; WER / cpWER / cpWER-U use score_same_corpus.measure unchanged.

python -I tools/asr_20261104/run_a3_same_corpus.py --root K:/nn-bench --java JAVA17 --a0 K:/nn-bench/data/models/asr \
    --a3 K:/nn-asr-phone/mfix/A3 --out K:/nn-bench/results-a3 --evidence docs/evidence/asr-20261104/same-corpus-a3

Builds harness/bench-asr.jar from the current sources (core + OfflineAsr + AsrModelSpec + InferenceThreads + DiarBench) with a
BuildConfig stub whose ASR_A3 comes from -DasrA3; the earlier bench.jar is left untouched.
"""
import argparse, hashlib, json, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools")); sys.path.insert(0, str(REPO / "tools/c2_same_tracks"))
from score_same_corpus import measure, load_reference, read_turns, bootstrap  # noqa: E402

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def build(root, java):
    h = root / "harness"; kotlin = h / "kotlin"; jar = h / "bench-asr.jar"
    stub = h / "BuildConfigStub.kt"
    stub.write_text('package ru.neurostenographer.app\nobject BuildConfig { val ASR_A3: Boolean = System.getProperty("asrA3") == "true" }\n', encoding="utf-8")
    app = REPO / "app/src/main/java/ru/neurostenographer/app"
    src = sorted((REPO / "core/src/main/kotlin/ru/neurostenographer/core").glob("*.kt"))
    src += [app / f"{n}.kt" for n in ("OfflineAsr", "OfflineDiarization", "AsrModelSpec", "InferenceThreads")]
    src += [REPO / "tools/diar_bench/DiarBench.kt", stub]
    cp = ";".join(map(str, [kotlin / "kotlin-stdlib.jar", h / "classes.jar", h / "placeholder.jar"]))
    subprocess.run([java, "-cp", str(kotlin / "*"), "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler", "-no-stdlib", "-no-reflect",
                    "-jvm-target", "17", "-classpath", cp, "-d", str(jar), *map(str, src)], check=True)
    return f"{jar};{cp}", h / "native"

def main():
    ap = argparse.ArgumentParser()
    for a in ("--root", "--a0", "--a3", "--out", "--evidence"): ap.add_argument(a, type=Path, required=True)
    ap.add_argument("--java", required=True)
    ap.add_argument("--manifest", type=Path, default=REPO / "docs/evidence/c2-same-tracks/manifest.json")
    args = ap.parse_args()
    corpus, turns_dir = args.root / "data/same", args.root / "results-same/C2"
    classpath, native = build(args.root, args.java)
    cases = [c for c in json.loads(args.manifest.read_text(encoding="utf-8"))["cases"] if c["text"]]
    rows, runs = [], {}
    for system, model, flag in (("A0", args.a0, "false"), ("A3", args.a3, "true")):
        out = args.out / system; out.mkdir(parents=True, exist_ok=True)
        for case in cases:
            wav, tsv = corpus / f"{case['id']}.wav", turns_dir / f"{case['id']}.tsv"
            assert sha(wav) == case["audio_sha256"], wav
            tr, meta = out / f"{case['id']}.transcript.json", out / f"{case['id']}.asrmeta.json"
            t0 = time.monotonic()
            r = subprocess.run([args.java, f"-Djava.library.path={native}", f"-DasrA3={flag}", "-Xmx4g", "-cp", classpath,
                                "ru.neurostenographer.tools.DiarBenchKt", "asr", str(model), str(wav), str(tsv), str(tr), str(meta)],
                               capture_output=True, text=True)
            status = "OK" if r.returncode == 0 and tr.exists() else f"FAIL rc={r.returncode} {r.stderr[-300:]}"
            runs[f"{system}/{case['id']}"] = dict(status=status, wall_s=round(time.monotonic() - t0, 1), turns_sha256=sha(tsv),
                                                   meta=json.loads(meta.read_text()) if meta.exists() else None)
            segs = json.loads(tr.read_text(encoding="utf-8"))["segments"] if status == "OK" else None
            row = dict(case=case["id"], set=case["set"], system=system, status=status)
            if segs is not None:
                row.update(measure(case, load_reference(corpus, case), read_turns(tsv), segs))
            rows.append(row); print(system, case["id"], status[:60], row.get("wer", {}).get("errors"), row.get("cpwer", {}).get("errors"), flush=True)
    def agg(sys_, set_=None, key="wer"):
        R = [r for r in rows if r["system"] == sys_ and (set_ is None or r["set"] == set_) and r.get(key, {}).get("status") == "SCORED"]
        e, n = sum(r[key]["errors"] for r in R), sum(r[key]["reference_words"] for r in R)
        return dict(errors=e, words=n, rate=round(e / n, 4) if n else None, cases=len(R))
    summary = {}
    for s in (None, "holdout", "phone3"):
        name = s or "all"
        summary[name] = {sys_: {k: agg(sys_, s, k) for k in ("wer", "cpwer", "cpwer_u")} for sys_ in ("A0", "A3")}
        for k in ("wer", "cpwer_u"):
            pairs = []
            for c in cases:
                if s and c["set"] != s: continue
                a = next(r for r in rows if r["system"] == "A0" and r["case"] == c["id"]); b = next(r for r in rows if r["system"] == "A3" and r["case"] == c["id"])
                if a.get(k, {}).get("status") == b.get(k, {}).get("status") == "SCORED":
                    pairs.append((a[k]["errors"], b[k]["errors"], a[k]["reference_words"]))  # (A0, A3, words): CI of A3 - A0
            summary[name][f"bootstrap_{k}_A3_minus_A0"] = bootstrap(pairs) if pairs else None
    args.evidence.mkdir(parents=True, exist_ok=True)
    (args.evidence / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    (args.evidence / "runs.json").write_text(json.dumps(runs, indent=1), encoding="utf-8")
    (args.evidence / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))

if __name__ == "__main__":
    main()
