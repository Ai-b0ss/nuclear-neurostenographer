"""Paired real-data A3+C2 / manual-enrollment VoxLock host experiment."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.request

import numpy as np

from common import LOCAL, owned, sha, write_json
from make_dev import write_wav
from manual_manifest import KIND, read_pcm16_mono, validate
from manual_metrics import word_recovery
from metrics import overlap_spans, score
from provision import PINS
from run_host import build_hybrid, read_turns, seal_hyp

A3_PINS = {
    "gigaam_v3_e2e_rnnt_encoder_int8.onnx": "75e93f387fa3cf5743e2b702dbc3108214b9769fdf4ae131f4e4c6d6087571ac",
    "gigaam_v3_e2e_rnnt_decoder.onnx": "781971998e6a355d6a714f6932a30eab295e7ba0d14fd7e0f78c83b87e811860",
    "gigaam_v3_e2e_rnnt_joint.onnx": "602ff7017a93311aad34df1437c8d7f49911353c13d6eae7a6ee7b041339465c",
    "gigaam_v3_e2e_rnnt_tokens.txt": "7ddf22514c42c531358182c81446a8159771e9921019f09ae743ea622d40221d",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True, help="Adapted manifest from manual_manifest.py")
    parser.add_argument("--java", type=Path, required=True)
    parser.add_argument("--a3", type=Path, required=True)
    parser.add_argument("--c2", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=LOCAL / "manual-host")
    args = parser.parse_args()
    fixtures_path = args.fixtures.resolve()
    manifest = validate(fixtures_path)
    if manifest["kind"] != KIND or manifest["enrollment_mode"] != "manual":
        raise ValueError("Manual real-data fixtures required")
    out = owned(args.out)
    tmp = owned(out / "tmp")
    if (out / "summary.json").exists():
        raise ValueError("Use a new output directory; previous evidence is immutable")
    harness = LOCAL / "harness"
    provenance = json.loads((LOCAL / "provenance.json").read_text(encoding="utf-8"))
    for name, digest in provenance["harness"].items():
        if sha(harness / name) != digest:
            raise ValueError("Harness dependency changed: " + name)
    for name, digest in A3_PINS.items():
        if sha(args.a3 / name) != digest:
            raise ValueError("A3 model pin mismatch: " + name)
    for name, (_, digest) in PINS.items():
        if sha(LOCAL / "voxlock" / name) != digest:
            raise ValueError("VoxLock pin mismatch: " + name)
    protocol = dict(
        split="SHARED REAL DATAHIVE OVERLAP; manual references; no synthetic rerun",
        candidate="VoxLock v2 INT8, threads1, two explicit manual 3s enrollments, no automatic enrollment or no-enrollment fallback",
        enrollment_mode="manual",
        fixture_manifest_sha256=sha(fixtures_path),
        a3=A3_PINS,
        host_jar=sha(harness / "overlap-host.jar"),
        source_hashes={path.name: sha(path) for path in Path(__file__).parent.glob("*")
                       if path.suffix in (".py", ".kt", ".java")},
        overlap="C2 detects splice regions; manual reference overlap is used only for scoring",
        identity="Recovered words remain null/unreliable; enrollment IDs never become verified output identities",
        host_scope="Production A3/C2 Kotlin with host JNI; full-clip extraction per target; PSS not measured",
    )
    write_json(out / "protocol.json", protocol)
    classpath = os.pathsep.join(str(harness / name) for name in
                                ["overlap-host.jar", "kotlin/kotlin-stdlib.jar", "classes.jar", "placeholder.jar",
                                 "onnxruntime-1.17.1.jar"])
    jvm = [str(args.java), "-Djava.io.tmpdir=" + str(tmp), "-Djava.library.path=" + str(harness / "native"),
           "-Xmx3g", "-XX:ErrorFile=" + str(out / "hs_err_%p.log"), "-cp", classpath,
           "ru.neurostenographer.tools.OverlapHostKt"]
    runs = []

    def java(mode, model, wav, turns_path, transcript=None):
        metadata = Path(str(transcript or turns_path) + ".meta.json")
        outputs = [turns_path, metadata] if transcript is None else [transcript, Path(str(transcript) + ".words.json"), metadata]
        for path in outputs:
            path.unlink(missing_ok=True)
        command = jvm + [mode, str(model), str(wav), str(turns_path)]
        if transcript is not None:
            command.append(str(transcript))
        command.append(str(metadata))
        started = time.perf_counter()
        result = subprocess.run(command, capture_output=True, timeout=900)
        log = out / (str(len(runs)) + ".jvm.log")
        log.write_bytes(result.stdout + result.stderr)
        record = dict(mode=mode, input_sha256=sha(wav), returncode=result.returncode,
                      wall_s=time.perf_counter() - started, log=log.name,
                      outputs={path.name: sha(path) for path in outputs if path.exists()})
        runs.append(record)
        write_json(out / "runs.json", runs)
        if result.returncode or not all(path.exists() for path in outputs):
            raise RuntimeError("JVM failure; see " + str(log))
        record["inference"] = json.loads(metadata.read_text(encoding="utf-8"))
        write_json(out / "runs.json", runs)
        return json.loads(transcript.read_text(encoding="utf-8")) if transcript else read_turns(turns_path)

    def denied(*args, **kwargs):
        raise RuntimeError("OFFLINE_TEST_NETWORK_DENIED")

    class NoNetwork(socket.socket):
        connect = denied
        connect_ex = denied

    socket.socket = NoNetwork
    socket.create_connection = denied
    urllib.request.urlopen = denied
    spec = importlib.util.spec_from_file_location("audited_voxlock", LOCAL / "voxlock/core.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    started = time.perf_counter()
    voxlock = module.VoxLock(model_dir=LOCAL / "voxlock", precision="int8", threads=1)
    load_s = time.perf_counter() - started
    from score_transcript import words

    rows = []
    for case in manifest["cases"]:
        name = case["id"]
        wav = Path(case["audio_path"])
        reference_path = Path(case["reference_path"])
        reference = json.loads(reference_path.read_text(encoding="utf-8"))
        samples = read_pcm16_mono(wav)
        turns_path = out / (name + ".c2.tsv")
        turns = java("c2", args.c2, wav, turns_path)
        baseline_wall_s = runs[-1]["wall_s"]
        baseline_path = out / (name + ".baseline.json")
        baseline = seal_hyp(java("asr", args.a3, wav, turns_path, baseline_path), wav, turns)
        baseline_wall_s += runs[-1]["wall_s"]
        write_json(baseline_path, baseline)
        baseline_words = json.loads(Path(str(baseline_path) + ".words.json").read_text(encoding="utf-8"))["segments"]
        app_tokens = [word for segment in baseline["segments"] for word in words(segment["text"])]
        word_tokens = [word for segment in baseline_words for word in words(segment["text"])]
        if app_tokens != word_tokens:
            raise ValueError("Sidecar word decode differs from production text")
        spans = overlap_spans(turns)
        row = dict(case=name, audio_sha256=case["audio_sha256"], baseline=score(reference, baseline),
                   c2_turns=turns, overlap_spans=spans,
                   enrollments=[{key: value for key, value in enrollment.items() if key != "wav_path"}
                                for enrollment in case["enrollments"]],
                   voxlock_load_s=load_s)
        target_words = {}
        stems = []
        candidate_wall_s = baseline_wall_s
        for index, enrollment in enumerate(case["enrollments"]):
            enrollment_samples = read_pcm16_mono(enrollment["wav_path"])
            started = time.perf_counter()
            cpu_started = time.process_time()
            extracted = voxlock.isolate(samples, sample=enrollment_samples)
            cpu_s = time.process_time() - cpu_started
            elapsed = time.perf_counter() - started
            candidate_wall_s += elapsed
            if len(extracted) != len(samples) or not np.isfinite(extracted).all():
                raise ValueError("Invalid extracted length/finiteness")
            target_wav = out / (name + ".target-" + str(index) + ".wav")
            write_wav(target_wav, extracted)
            stems.append(extracted)
            target_path = out / (name + ".target-" + str(index) + ".json")
            target = seal_hyp(java("asr", args.a3, target_wav, turns_path, target_path), wav, turns)
            candidate_wall_s += runs[-1]["wall_s"]
            write_json(target_path, target)
            sidecar = json.loads(Path(str(target_path) + ".words.json").read_text(encoding="utf-8"))["segments"]
            if [word for segment in target["segments"] for word in words(segment["text"])] != [
                    word for segment in sidecar for word in words(segment["text"])]:
                raise ValueError("Target sidecar differs from production text")
            target_words[enrollment["speaker_id"]] = sidecar
            target_reference = dict(reference, text_segments=[
                segment for segment in reference["text_segments"] if segment["speaker_id"] == enrollment["speaker_id"]])
            row["target_" + str(index)] = dict(
                speaker_id=enrollment["speaker_id"], enrollment_sha256=enrollment["sha256"], audio_sha256=sha(target_wav),
                samples=len(extracted), peak=float(np.max(np.abs(extracted))),
                clipped_samples=int(np.sum(np.abs(extracted) >= 1)), rms=float(np.sqrt(np.mean(extracted * extracted))),
                wall_s=elapsed, cpu_s=cpu_s, rtf=elapsed / (len(samples) / 16000),
                transcript=score(reference, target), target_only=score(target_reference, target))
        correlation = float(np.corrcoef(stems)[0, 1])
        row["target_correlation"] = correlation if np.isfinite(correlation) else None
        row["targets_duplicate_bytes"] = np.array_equal(stems[0], stems[1])
        candidate = dict(baseline, segments=build_hybrid(baseline_words, target_words, spans))
        candidate_path = out / (name + ".candidate.json")
        write_json(candidate_path, candidate)
        row["candidate"] = score(reference, candidate)
        row["word_recovery"] = word_recovery(reference, baseline_words, candidate["segments"])
        wrong_words = {case["enrollments"][0]["speaker_id"]: target_words[case["enrollments"][1]["speaker_id"]],
                       case["enrollments"][1]["speaker_id"]: target_words[case["enrollments"][0]["speaker_id"]]}
        wrong = dict(baseline, segments=build_hybrid(baseline_words, wrong_words, spans))
        row["wrong_enrollment_control"] = dict(status="EXECUTED_OPPOSITE_SPEAKER_ENROLLMENT", score=score(reference, wrong),
                                               limitation="Reuses executed opposite extraction; not an unseen-third-speaker test")
        duration_s = case["duration_ms"] / 1000
        row["host"] = dict(status="MEASURED", baseline_wall_rtf=baseline_wall_s / duration_s,
                           candidate_wall_rtf=candidate_wall_s / duration_s,
                           pss_status="NOT_MEASURED", scope="Outer process wall plus Python separator; model load reported separately")
        rows.append(row)
        write_json(out / "summary.json", dict(status="IN_PROGRESS", protocol=protocol, rows=rows, runs=runs))
    write_json(out / "summary.json", dict(status="COMPLETE", protocol=protocol, rows=rows, runs=runs,
                                          network="Python socket connects disabled during inference; JVM uses local files"))
    print("COMPLETED", out / "summary.json", flush=True)


if __name__ == "__main__":
    main()
