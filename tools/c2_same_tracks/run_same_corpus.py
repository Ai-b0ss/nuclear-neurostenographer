"""Run C0 and C2 on the frozen same-recordings corpus through the app's own code, then score both the same way.

python tools/c2_same_tracks/run_same_corpus.py --root ROOT --java JAVA17 --corpus ROOT/data/same \
    --manifest docs/evidence/c2-same-tracks/manifest.json --results ROOT/results-same --evidence docs/evidence/c2-same-tracks

Per case and system, sequentially, one JVM each (so the wall time includes JVM start and model load, like the app's worker):
  C0  production OfflineDiarization (pyannote + ERes2Net, threshold 0.8) via tools/diar_bench/DiarBench.kt, sherpa-onnx 1.12.20
  C2  the prototype's Kotlin NemotronDiarization (INT8, ONNX Runtime 1.17.1) via tools/nemotron/NemotronHostBench.kt
  ASR the production OfflineAsr (GigaAM v3 CTC) with each system's turns, the same canonicalize/speechWindows path as the app
No parameter is chosen here: C0 keeps 0.8, C2 keeps its pinned defaults. Scoring is in score_same_corpus.py.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "diar_bench"))
from run_bench import run_measured  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--java", required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--nemotron", type=Path, default=Path(__file__).resolve().parents[2] / ".local/nemotron", help="Folder from tools/provision_nemotron.py")
    parser.add_argument("--only", help="Comma separated case ids")
    args = parser.parse_args()
    harness = args.root / "harness"
    kotlin = harness / "kotlin"
    c0_classpath = (harness / "classpath.txt").read_text(encoding="utf-8")
    c2_classpath = ";".join(str(p) for p in (harness / "nemotron-host.jar", kotlin / "kotlin-stdlib.jar", harness / "classes.jar",
                                              harness / "placeholder.jar", harness / "onnxruntime-1.17.1.jar"))
    native = harness / "native"
    jvm = [args.java, f"-Djava.library.path={native}", "-Xmx4g"]
    models = args.root / "data/models"
    nemotron = args.nemotron
    if not (nemotron / "CHANGES.txt").is_file():
        raise SystemExit(f"Missing {nemotron}: install it with tools/provision_nemotron.py")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    records_path = args.evidence / "runs.json"
    records = json.loads(records_path.read_text(encoding="utf-8")) if records_path.exists() else {}
    environment = {"c0_runtime": "sherpa-onnx 1.12.20 JNI, ONNX Runtime 1.17.1, 2 threads, threshold 0.8",
                   "c2_runtime": "ONNX Runtime Java 1.17.1, 2 threads, model.int8.onnx patched to IR 9",
                   "asr": "GigaAM v3 CTC int8 via sherpa-onnx 1.12.20, 2 threads",
                   "nemotron_changes_sha256": sha(nemotron / "CHANGES.txt"),
                   "jars": {p.name: sha(p) for p in (harness / "bench.jar", harness / "classes.jar", harness / "nemotron-host.jar") if p.exists()},
                   "memory": "peak working set of the JVM process tree, Windows host; not phone PSS"}
    only = set(args.only.split(",")) if args.only else None
    for case in manifest["cases"]:
        if only and case["id"] not in only:
            continue
        wav = args.corpus / f"{case['id']}.wav"
        if sha(wav) != case["audio_sha256"]:
            raise SystemExit(f"Hash mismatch: {wav}")
        for system in ("C0", "C2"):
            out = args.results / system
            out.mkdir(parents=True, exist_ok=True)
            turns, meta = out / f"{case['id']}.tsv", out / f"{case['id']}.meta.json"
            key = f"{system}/{case['id']}"
            if key in records and records[key].get("audio_sha256") == case["audio_sha256"] and turns.exists() and sha(turns) == records[key].get("turns_sha256"):
                continue
            for stale in (turns, meta):
                stale.unlink(missing_ok=True)
            if system == "C0":
                command = [*jvm, f"-XX:ErrorFile={out}/hs_err_%p.log", "-cp", c0_classpath, "ru.neurostenographer.tools.DiarBenchKt",
                           "c0", str(models / "c0"), str(wav), str(turns), str(meta)]
            else:
                listing = out / f"{case['id']}.list"
                listing.write_text(f"{wav}\t{turns}\t{meta}\n", encoding="utf-8")
                command = [*jvm, f"-XX:ErrorFile={out}/hs_err_%p.log", "-cp", c2_classpath, "ru.neurostenographer.tools.NemotronHostBenchKt",
                           str(nemotron), str(listing)]
            record = run_measured(command, out / f"{case['id']}.log")
            if record["status"] == "OK" and not (turns.exists() and meta.exists()):
                record["status"] = "FAIL_NO_OUTPUT"
            record["audio_sha256"] = case["audio_sha256"]
            if meta.exists():
                record["inference"] = json.loads(meta.read_text(encoding="utf-8"))
            if turns.exists():
                record["turns_sha256"] = sha(turns)
            if case["text"] and record["status"] == "OK":
                transcript, asr_meta = out / f"{case['id']}.transcript.json", out / f"{case['id']}.asrmeta.json"
                transcript.unlink(missing_ok=True)
                asr = run_measured([*jvm, "-cp", c0_classpath, "ru.neurostenographer.tools.DiarBenchKt", "asr", str(models / "asr"),
                                    str(wav), str(turns), str(transcript), str(asr_meta)], out / f"{case['id']}.asr.log")
                if asr["status"] == "OK" and not transcript.exists():
                    asr["status"] = "FAIL_NO_OUTPUT"
                if asr_meta.exists():
                    asr["inference"] = json.loads(asr_meta.read_text(encoding="utf-8"))
                if transcript.exists():
                    asr["transcript_sha256"] = sha(transcript)
                record["asr"] = asr
            records[key] = record
            print(key, record["status"], record["wall_ms"], record["peak_working_set_mib"], record.get("asr", {}).get("status"), flush=True)
            records_path.parent.mkdir(parents=True, exist_ok=True)
            records_path.write_text(json.dumps(records, indent=1) + "\n", encoding="utf-8")
    (args.evidence / "environment.json").write_text(json.dumps(environment, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
