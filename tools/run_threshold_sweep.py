"""Compile and run ThresholdSweepJvm on this PC (needs `python tools/run_host_inference.py` once for the jars).

  python tools/run_threshold_sweep.py --thresholds 0.7,0.8,0.9 --wavs DIR --output out.jsonl [--model .local/diarization]

Host JNI only; results say nothing about Android correctness and are not a release gate.
"""
import argparse
import os
import platform
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--thresholds", required=True)
    parser.add_argument("--wavs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=ROOT / ".local/diarization")
    parser.add_argument("--java", default=str(next((ROOT / ".local/java17").glob("*/bin/java.exe"), "java")))
    args = parser.parse_args()
    compiler, host = ROOT / ".local/kotlin", ROOT / ".local/host-compile"
    native = ROOT / ".local" / ("windows-jni" if platform.system() == "Windows" else "linux-jni")
    sources = list((ROOT / "core/src/main/kotlin/ru/neurostenographer/core").glob("*.kt"))
    sources += [ROOT / "app/src/main/java/ru/neurostenographer/app" / (n + ".kt") for n in ["OfflineDiarization", "InferenceThreads"]]
    sources += [ROOT / "tools/ThresholdSweepJvm.kt"]
    cp = os.pathsep.join(str(p) for p in [compiler / "kotlin-stdlib.jar", host / "classes.jar", host / "android-host-placeholder.jar"])
    # One jar per run: parallel runs must not overwrite a jar another JVM has open.
    jar = host / f"sweep-{os.getpid()}.jar"
    subprocess.run([args.java, "-cp", str(compiler / "*"), "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler", "-no-stdlib", "-no-reflect",
                    "-jvm-target", "17", "-classpath", cp, "-d", str(jar), *map(str, sources)], check=True)
    env = dict(os.environ, LD_LIBRARY_PATH=str(native) + os.pathsep + os.environ.get("LD_LIBRARY_PATH", ""))
    subprocess.run([args.java, f"-Djava.library.path={native}", "-cp", os.pathsep.join([str(jar), cp]),
                    "ru.neurostenographer.tools.ThresholdSweepJvmKt", str(args.model), args.thresholds, str(args.output), str(args.wavs)],
                   check=True, env=env)


if __name__ == "__main__":
    main()
