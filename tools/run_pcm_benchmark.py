"""Reproduce parser comparison to the source-only round-3 checkpoint, no SDK/models."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile
from provision_asr import ROOT, download
from run_host_inference import COMPILER, MAVEN

BASELINE_SHA256 = "50430a0a274eed6b360bf794bcb882130aabd5422af9a01486f77c05af6cc5ca"
SOURCE = "core/src/main/kotlin/ru/neurostenographer/core/PcmWav.kt"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--java", default="java")
    p.add_argument("--baseline-archive", type=Path, default=ROOT / ".local/round3-source.zip")
    p.add_argument("--output", type=Path, default=ROOT / ".local/pcm-benchmark.json")
    args = p.parse_args()
    with zipfile.ZipFile(args.baseline_archive) as archive:
        baseline = archive.read(SOURCE)
    if hashlib.sha256(baseline).hexdigest() != BASELINE_SHA256:
        raise ValueError("Unexpected baseline parser bytes")
    dest = ROOT / ".local/pcm-benchmark"
    dest.mkdir(parents=True, exist_ok=True)
    old = dest / "PcmWavBaseline.kt"
    old.write_text(baseline.decode("utf-8").replace("package ru.neurostenographer.core", "package ru.neurostenographer.baseline"), encoding="utf-8")
    compiler = ROOT / ".local/kotlin"
    for name, (url, checksum) in COMPILER.items():
        download(MAVEN + url, compiler / (name + ".jar"), checksum)
    jar = dest / "benchmark.jar"
    subprocess.run([args.java, "-cp", str(compiler / "*"), "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler",
                    "-no-stdlib", "-no-reflect", "-jvm-target", "17", "-classpath", compiler / "kotlin-stdlib.jar",
                    "-d", jar, ROOT / SOURCE, old, ROOT / "tools/PcmImportBenchmark.kt"], check=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        args.output.unlink()  # never retain a stale success if the new JVM fails
    subprocess.run([args.java, "-cp", str(jar) + os.pathsep + str(compiler / "kotlin-stdlib.jar"),
                    "ru.neurostenographer.tools.PcmImportBenchmarkKt", args.output], check=True, timeout=120)
    report = json.loads(args.output.read_text(encoding="utf-8"))
    report["baseline_source_sha256"] = BASELINE_SHA256
    report["streaming_source_sha256"] = hashlib.sha256((ROOT / SOURCE).read_bytes()).hexdigest()
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
