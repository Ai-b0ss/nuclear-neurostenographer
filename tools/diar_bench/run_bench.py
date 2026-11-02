"""Run C0 and C1 on every corpus case, sequentially, one child process per case and system.

python tools/diar_bench/run_bench.py --root ROOT --java JAVA17 --ort-python PY --manifest corpus-manifest.json --evidence DIR
Failures are recorded and kept: a crash or timeout never becomes a score. A stored run is reused only if its
fingerprint matches the current model, code, threshold, runtime and audio; otherwise it is run again.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import time

import psutil

from provenance import asr_config, digest_of, file_hash, run_fingerprint, system_config

TIMEOUT_S = 1800
TEXT_GROUPS = {"ivkond", "acted"}
SYSTEMS = {"C0": None, "C1": "model.onnx", "C2": "model.int8.onnx"}


def run_measured(command, log_path, cwd=None, timeout_s=TIMEOUT_S):
    started = time.perf_counter()
    peak = 0
    with open(log_path, "wb") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, cwd=cwd)
        watcher = psutil.Process(process.pid)
        timed_out = False
        while process.poll() is None:
            # A Windows venv python.exe is a launcher: the interpreter is its child, so measure the tree.
            try:
                family = [watcher, *watcher.children(recursive=True)]
                peak = max(peak, sum(getattr(p.memory_info(), "peak_wset", p.memory_info().rss) for p in family))
            except psutil.Error:
                pass
            if time.perf_counter() - started > timeout_s:
                for child in watcher.children(recursive=True):
                    child.kill()
                process.kill()
                timed_out = True
            time.sleep(0.05)
    log_bytes = Path(log_path).read_bytes()
    code = process.returncode
    status = "TIMEOUT" if timed_out else "OK" if code == 0 else "FAIL_NATIVE" if any(
        x in log_bytes for x in (b"EXCEPTION_ACCESS_VIOLATION", b"SIGSEGV", b"SIGABRT", b"A fatal error")) else "FAIL"
    return {"status": status, "exit_code": code, "wall_ms": round((time.perf_counter() - started) * 1000), "peak_working_set_mib": round(peak / 2 ** 20, 1)}


def is_current(record, fingerprint):
    return bool(record) and record.get("fingerprint") == fingerprint


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--java", required=True)
    parser.add_argument("--ort-python", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--results", default="results-v2", help="Folder under ROOT for raw outputs")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--only", help="Comma separated systems")
    parser.add_argument("--group", help="Comma separated groups")
    parser.add_argument("--runs-name", default="runs", help="Record file name inside --evidence")
    parser.add_argument("--c0-threshold", help="Sensitivity runs only; production stays 0.8")
    parser.add_argument("--corpus", type=Path, help="Audio folder if not data/corpus")
    args = parser.parse_args()
    corpus = args.corpus or args.root / "data/corpus"
    results_dir = args.root / args.results
    classpath = (args.root / "harness/classpath.txt").read_text(encoding="utf-8")
    jvm = [args.java, f"-Djava.library.path={args.root / 'harness/native'}", f"-XX:ErrorFile={results_dir}/hs_err_%p.log", "-Xmx4g", "-cp", classpath,
           "ru.neurostenographer.tools.DiarBenchKt"]
    models = args.root / "data/models"
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    systems = args.only.split(",") if args.only else list(SYSTEMS)
    groups = args.group.split(",") if args.group else None
    records_path = args.evidence / f"{args.runs_name}.json"
    records = json.loads(records_path.read_text(encoding="utf-8")) if records_path.exists() else {}
    ort_version = subprocess.run([args.ort_python, "-I", "-c", "import onnxruntime;print(onnxruntime.__version__)"], capture_output=True, text=True, check=True).stdout.strip()
    jni = {"sherpa_native_jar": file_hash(args.root / "harness/native/native.jar"), "onnxruntime": "1.17.1"}
    configs = {s: system_config(models, s, SYSTEMS, args.c0_threshold if s == "C0" else None, jni if s == "C0" else {"onnxruntime": ort_version}) for s in systems}
    asr = asr_config(models, jni)
    for case in manifest["cases"]:
        if groups and case["group"] not in groups:
            continue
        wav = corpus / f"{case['id']}.wav"
        if hashlib.sha256(wav.read_bytes()).hexdigest() != case["audio_sha256"]:
            raise SystemExit(f"Hash mismatch: {wav}")
        for system in systems:
            out = results_dir / system
            out.mkdir(parents=True, exist_ok=True)
            turns, meta, key = out / f"{case['id']}.tsv", out / f"{case['id']}.meta.json", f"{system}/{case['id']}"
            fingerprint = run_fingerprint(configs[system], case["audio_sha256"])
            if args.force or not is_current(records.get(key), fingerprint):
                for stale in (turns, meta):
                    stale.unlink(missing_ok=True)
                records.pop(key + "/asr", None)
                if system == "C0":
                    command = [*jvm, "c0", str(models / "c0"), str(wav), str(turns), str(meta)] + ([args.c0_threshold] if args.c0_threshold else [])
                else:
                    command = [args.ort_python, "-I", str(Path(__file__).with_name("run_c1.py")), str(models / "nemotron"), SYSTEMS[system], str(wav), str(turns), str(meta)]
                record = run_measured(command, out / f"{case['id']}.log")
                if record["status"] == "OK" and not (turns.exists() and meta.exists()):
                    record["status"] = "FAIL_NO_OUTPUT"
                if meta.exists():
                    record["inference"] = json.loads(meta.read_text(encoding="utf-8"))
                record["fingerprint"] = fingerprint
                if turns.exists():
                    record["turns_sha256"] = file_hash(turns)
                records[key] = record
                print(key, record["status"], record["wall_ms"], record["peak_working_set_mib"], flush=True)
            record = records[key]
            asr_key = key + "/asr"
            asr_fingerprint = digest_of({"asr": asr, "turns": record.get("turns_sha256"), "audio": case["audio_sha256"]})
            if case["group"] in TEXT_GROUPS and record["status"] == "OK" and (args.force or not is_current(records.get(asr_key), asr_fingerprint)):
                transcript, asr_meta = out / f"{case['id']}.transcript.json", out / f"{case['id']}.asrmeta.json"
                transcript.unlink(missing_ok=True)
                result = run_measured([*jvm, "asr", str(models / "asr"), str(wav), str(turns), str(transcript), str(asr_meta)], out / f"{case['id']}.asr.log")
                if result["status"] == "OK" and not transcript.exists():
                    result["status"] = "FAIL_NO_OUTPUT"
                if asr_meta.exists():
                    result["inference"] = json.loads(asr_meta.read_text(encoding="utf-8"))
                result["fingerprint"] = asr_fingerprint
                if transcript.exists():
                    result["transcript_sha256"] = file_hash(transcript)
                records[asr_key] = result
                print(asr_key, result["status"], result["wall_ms"], flush=True)
            records_path.parent.mkdir(parents=True, exist_ok=True)
            records_path.write_text(json.dumps(records, indent=1) + "\n", encoding="utf-8")
    environment = {"platform": platform.platform(), "machine": platform.machine(), "processor": platform.processor(),
                   "physical_arm64": "NOT_RUN", "threads": 2, "c1_c2_onnxruntime": ort_version, "c0_asr_onnxruntime": "1.17.1",
                   "configs": configs, "asr": asr}
    (args.evidence / "environment.json").write_text(json.dumps(environment, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
