"""Run the Kotlin C2 port on the host with ONNX Runtime 1.17.1 and compare it with the Python C2 outputs.

python tools/nemotron/run_host_parity.py --root ROOT --java JAVA17 --evidence DIR --python-results ROOT/results-v2/C2
Host evidence for the port only. It says nothing about an Android device.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
from score_transcript import der  # noqa: E402

ORT_JAR = "https://repo1.maven.org/maven2/com/microsoft/onnxruntime/onnxruntime/1.17.1/onnxruntime-1.17.1.jar"
ORT_SHA256 = "a4e57e18a04b6c1b5b0e2885af1d8557873d4ca04bfcebf79743966c4c8eb20f"


def turns(path):
    rows = [line.split("\t") for line in Path(path).read_text(encoding="ascii").splitlines() if line.strip()]
    return [{"start_ms": int(a), "end_ms": int(b), "speaker_id": None if int(c) < 0 else f"h{c}"} for a, b, c in rows]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--java", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--python-results", type=Path, required=True)
    args = parser.parse_args()
    harness = args.root / "harness"
    jar = harness / "onnxruntime-1.17.1.jar"
    if not jar.is_file() or hashlib.sha256(jar.read_bytes()).hexdigest() != ORT_SHA256:
        urllib.request.urlretrieve(ORT_JAR, jar)
    if hashlib.sha256(jar.read_bytes()).hexdigest() != ORT_SHA256:
        raise SystemExit("ONNX Runtime jar hash mismatch")
    kotlin = harness / "kotlin"
    base = [str(kotlin / "kotlin-stdlib.jar"), str(harness / "classes.jar"), str(harness / "placeholder.jar"), str(jar)]
    sources = [str(p) for p in (REPO / "core/src/main/kotlin/ru/neurostenographer/core").glob("*.kt")]
    sources += [str(REPO / "app/src/main/java/ru/neurostenographer/app/OfflineDiarization.kt"), str(REPO / "app/src/main/java/ru/neurostenographer/app/InferenceThreads.kt"), str(REPO / "app/src/nemotron/java/ru/neurostenographer/app/NemotronDiarization.kt"), str(REPO / "app/src/nemotron/java/ru/neurostenographer/core/NemotronDiarizer.kt"),
                str(REPO / "tools/nemotron/NemotronHostBench.kt")]
    output = harness / "nemotron-host.jar"
    subprocess.run([args.java, "-cp", str(kotlin / "*"), "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler", "-no-stdlib", "-no-reflect", "-jvm-target", "17",
                    "-classpath", ";".join(base), "-d", str(output), *sources], check=True)
    cases = json.loads(args.manifest.read_text(encoding="utf-8"))["cases"]
    folder = args.root / "results-c3"
    folder.mkdir(exist_ok=True)
    jobs = args.root / "c3-jobs.tsv"
    jobs.write_text("".join(f"{args.root / 'data/corpus' / (c['id'] + '.wav')}\t{folder / (c['id'] + '.tsv')}\t{folder / (c['id'] + '.meta.json')}\n" for c in cases), encoding="utf-8")
    subprocess.run([args.java, "-Xmx4g", "-cp", ";".join([str(output), *base]), "ru.neurostenographer.tools.NemotronHostBenchKt",
                    str(REPO / ".local/nemotron"), str(jobs)], check=True)
    rows, identical = [], 0
    for c in cases:
        kotlin_path, python_path = folder / f"{c['id']}.tsv", args.python_results / f"{c['id']}.tsv"
        a, b = turns(python_path), turns(kotlin_path)
        same = python_path.read_bytes().replace(b"\r\n", b"\n") == kotlin_path.read_bytes().replace(b"\r\n", b"\n")
        identical += same
        between = der(a, b, c["duration_ms"], 0, False)
        meta = json.loads((folder / f"{c['id']}.meta.json").read_text(encoding="utf-8"))
        row = {"case": c["id"], "identical_turns": same, "der_against_python_c2": between["rate"], "infer_ms": meta["infer_ms"], "duration_ms": c["duration_ms"]}
        reference = json.loads((args.root / "data/corpus" / f"{c['id']}.ref.json").read_text(encoding="utf-8")).get("diarization")
        if reference:
            pa = der(reference, a, c["duration_ms"], 250, False)
            pb = der(reference, b, c["duration_ms"], 250, False)
            row.update(group=c["group"], python_errors=pa["miss_ms"] + pa["false_alarm_ms"] + pa["confusion_ms"],
                       kotlin_errors=pb["miss_ms"] + pb["false_alarm_ms"] + pb["confusion_ms"], reference_ms=pa["reference_speaker_ms"])
        rows.append(row)
    scored = [r for r in rows if "reference_ms" in r]
    speech = sum(r["reference_ms"] for r in scored)
    summary = {"scope": "Host JVM, ONNX Runtime 1.17.1, Kotlin mel and speaker cache. Not an Android result.", "cases": len(rows), "identical_turn_files": identical,
               "max_der_against_python_c2": max((r["der_against_python_c2"] or 0) for r in rows),
               "pooled_der_python_c2": sum(r["python_errors"] for r in scored) / speech, "pooled_der_kotlin": sum(r["kotlin_errors"] for r in scored) / speech,
               "infer_rtf": sum(r["infer_ms"] for r in rows) / sum(r["duration_ms"] for r in rows), "rows": rows}
    args.evidence.mkdir(parents=True, exist_ok=True)
    (args.evidence / "kotlin-host-parity.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print({k: v for k, v in summary.items() if k != "rows"})


if __name__ == "__main__":
    main()
