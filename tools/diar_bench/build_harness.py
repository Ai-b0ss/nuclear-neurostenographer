"""Compile DiarBench.kt against the production Kotlin sources and pinned sherpa-onnx 1.12.20.

python tools/diar_bench/build_harness.py --root K:/nn-bench --java JAVA17 [--assets EXISTING_LOCAL]
Every file is verified by the pins already used in tools/run_host_inference.py.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
from provision_asr import LOCK, download  # noqa: E402
from run_host_inference import COMPILER, MAVEN, NATIVE  # noqa: E402

AAR_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.12.20/sherpa-onnx-1.12.20.aar"


def fetch(url, dest, digest, assets):
    if assets and assets.is_file() and hashlib.sha256(assets.read_bytes()).hexdigest() == digest:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(assets, dest)
    download(url, dest, digest)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--java", default="java")
    parser.add_argument("--assets", type=Path, help="Optional existing .local folder; hashes are still checked")
    args = parser.parse_args()
    out = args.root / "harness"
    kotlin = out / "kotlin"
    for jar, (url, digest) in COMPILER.items():
        fetch(MAVEN + url, kotlin / f"{jar}.jar", digest, args.assets / "kotlin" / f"{jar}.jar" if args.assets else None)
    name, digest = NATIVE["Windows"]
    native = out / "native"
    fetch(f"https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.12.20/sherpa-onnx-native-lib-{name}-v1.12.20.jar",
          native / "native.jar", digest, args.assets / "windows-jni/native.jar" if args.assets else None)
    with zipfile.ZipFile(native / "native.jar") as z:
        for entry in z.namelist():
            if entry.endswith(".dll"):
                (native / Path(entry).name).write_bytes(z.read(entry))
    aar = out / "sherpa-onnx-1.12.20.aar"
    fetch(AAR_URL, aar, LOCK["upstream_sha256"], args.assets / "sherpa-onnx-1.12.20.aar" if args.assets else None)
    with zipfile.ZipFile(aar) as z:
        (out / "classes.jar").write_bytes(z.read("classes.jar"))
    stub = out / "AssetManager.kt"
    stub.write_text("package android.content.res\nclass AssetManager\n", encoding="utf-8")
    compiler = [args.java, "-cp", str(kotlin / "*"), "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler",
                "-no-stdlib", "-no-reflect", "-jvm-target", "17"]
    placeholder = out / "placeholder.jar"
    subprocess.run([*compiler, "-classpath", str(kotlin / "kotlin-stdlib.jar"), "-d", str(placeholder), str(stub)], check=True)
    classpath = ";".join(map(str, [kotlin / "kotlin-stdlib.jar", out / "classes.jar", placeholder]))
    sources = list((REPO / "core/src/main/kotlin/ru/neurostenographer/core").glob("*.kt"))
    sources += [REPO / "app/src/main/java/ru/neurostenographer/app" / f"{n}.kt" for n in ("OfflineAsr", "OfflineDiarization")]
    sources += [REPO / "tools/diar_bench/DiarBench.kt"]
    subprocess.run([*compiler, "-classpath", classpath, "-d", str(out / "bench.jar"), *map(str, sources)], check=True)
    (out / "classpath.txt").write_text(f"{out / 'bench.jar'};{classpath}", encoding="utf-8")
    print("BUILT", out / "bench.jar")


if __name__ == "__main__":
    main()
