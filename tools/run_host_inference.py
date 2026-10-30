"""Reproduce actual Kotlin/JNI host checks with pinned downloads (JDK 17 required).

No Android SDK/emulator or pip required. Windows AMD64 / Linux x64 only.
The overlap probe runs in a child JVM because v1.12.20 can crash natively.
Host results NEVER establish Android correctness. All audio/weights stay ignored.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import zipfile
from provision_asr import ROOT, download

MAVEN = "https://repo.maven.apache.org/maven2/"
COMPILER = {
    "kotlin-compiler-embeddable": ("org/jetbrains/kotlin/kotlin-compiler-embeddable/1.9.25/kotlin-compiler-embeddable-1.9.25.jar", "e39ee0b62f0ad79fd45e84334f34aaee99c7291f591ddf68e2cdcdd09b73a472"),
    "kotlin-stdlib": ("org/jetbrains/kotlin/kotlin-stdlib/1.9.25/kotlin-stdlib-1.9.25.jar", "f9cdcdbff1f5de85380ae526977e683726c2aa42db1ed6e6e50ae89e496e95fd"),
    "kotlin-script-runtime": ("org/jetbrains/kotlin/kotlin-script-runtime/1.9.25/kotlin-script-runtime-1.9.25.jar", "9933edd6677b6aac46d1b5effda1adee9063fbb04c746e78b403398158abaf47"),
    "kotlin-reflect": ("org/jetbrains/kotlin/kotlin-reflect/1.6.10/kotlin-reflect-1.6.10.jar", "3277ac102ae17aad10a55abec75ff5696c8d109790396434b496e75087854203"),
    "trove4j": ("org/jetbrains/intellij/deps/trove4j/1.0.20200330/trove4j-1.0.20200330.jar", "c5fd725bffab51846bf3c77db1383c60aaaebfe1b7fe2f00d23fe1b7df0a439d"),
    "annotations": ("org/jetbrains/annotations/13.0/annotations-13.0.jar", "ace2a10dc8e2d5fd34925ecac03e4988b2c0f851650c94b8cef49ba1bd111478"),
}
NATIVE = {
    "Windows": ("win-x64", "24d9fe53301fe0b5026fb1cb3877b54d1a47ed079f75819e83a99a9a9e41e55a"),
    "Linux": ("linux-x64", "baa839c265f37b6f7f1dafde6f1d8125b4c8422d7c4ae3ceef2c58bb6e084383"),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--java", default="java")
    parser.add_argument("--output", type=Path, default=ROOT / ".local/host-results")
    args = parser.parse_args()
    assert platform.machine().lower() in ("amd64", "x86_64")
    name, digest = NATIVE[platform.system()]
    subprocess.run([sys.executable, ROOT / "tools/provision_asr.py", "--test-assets", "--upstream-runtime"], check=True)
    subprocess.run([sys.executable, ROOT / "tools/provision_diarization.py", "--test-assets"], check=True)
    compiler = ROOT / ".local/kotlin"
    for jar, (url, checksum) in COMPILER.items():
        download(MAVEN + url, compiler / (jar + ".jar"), checksum)
    native = ROOT / ".local" / ("windows-jni" if name == "win-x64" else "linux-jni")
    download(f"https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.12.20/sherpa-onnx-native-lib-{name}-v1.12.20.jar",
             native / "native.jar", digest)
    with zipfile.ZipFile(native / "native.jar") as z:
        for entry in z.namelist():
            if entry.endswith((".so", ".dll")):
                (native / Path(entry).name).write_bytes(z.read(entry))
    host = ROOT / ".local/host-compile"
    host.mkdir(exist_ok=True)
    with zipfile.ZipFile(ROOT / "app/libs/sherpa-onnx-1.12.20.aar") as z:
        (host / "classes.jar").write_bytes(z.read("classes.jar"))
    # Class-loading placeholder only; no Android AssetManager API is called.
    stub = host / "AssetManager.kt"
    stub.write_text("package android.content.res\nclass AssetManager\n", encoding="utf-8")
    sources = list((ROOT / "core/src/main/kotlin/ru/neurostenographer/core").glob("*.kt"))
    sources += [ROOT / "app/src/main/java/ru/neurostenographer/app" / (n + ".kt") for n in ["OfflineAsr", "OfflineDiarization"]]
    sources += [ROOT / "tools" / (n + ".kt") for n in ["OfflineAsrJvmSmoke", "DiarizationJvmSmoke", "OfflineDialogueJvmSmoke", "OverlapJvmProbe"]]
    placeholder = host / "android-host-placeholder.jar"
    subprocess.run([args.java, "-cp", str(compiler / "*"), "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler",
                    "-no-stdlib", "-no-reflect", "-jvm-target", "17", "-classpath", compiler / "kotlin-stdlib.jar",
                    "-d", placeholder, stub], check=True)
    cp = os.pathsep.join(str(p) for p in [compiler / "kotlin-stdlib.jar", host / "classes.jar", placeholder])
    jar = host / "tests.jar"
    subprocess.run([args.java, "-cp", str(compiler / "*"), "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler",
                    "-no-stdlib", "-no-reflect", "-jvm-target", "17", "-classpath", cp, "-d", jar, *sources], check=True)
    args.output.mkdir(parents=True, exist_ok=True)
    fixture = ROOT / ".local/androidTestAssets"
    tasks = {
        "asr": ("OfflineAsrJvmSmoke", [ROOT / ".local/model", fixture / "example.wav"]),
        "diarization": ("DiarizationJvmSmoke", [ROOT / ".local/diarization", fixture / "four-speakers.wav"]),
        "dialogue": ("OfflineDialogueJvmSmoke", [ROOT / ".local/model", ROOT / ".local/diarization", fixture / "example.wav"]),
        "overlap": ("OverlapJvmProbe", [ROOT / ".local/diarization", fixture / "four-speakers.wav"]),
    }
    results = {}
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = str(native) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
    for task, (main_class, parameters) in tasks.items():
        output = args.output / (task + ".json")
        # Never retain an old PASS file when a new probe fails.
        if output.exists():
            output.unlink()
        command = [args.java, f"-Djava.library.path={native}", f"-XX:ErrorFile={args.output / 'hs_err_pid%p.log'}",
                   "-cp", str(jar) + os.pathsep + cp, f"ru.neurostenographer.tools.{main_class}Kt", *parameters, output]
        try:
            with (args.output / (task + ".log")).open("wb") as log:
                completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=env, timeout=300)
            results[task] = {"exit_code": completed.returncode, "status": "PASS" if completed.returncode == 0 else "FAIL_NATIVE_OR_ASSERTION"}
            if task == "overlap":
                raw_log = (args.output / (task + ".log")).read_bytes()
                results[task]["native_fatal_error"] = any(x in raw_log for x in [b"EXCEPTION_ACCESS_VIOLATION", b"SIGSEGV", b"SIGABRT"])
                results[task]["output_produced"] = output.exists()
        except subprocess.TimeoutExpired:
            results[task] = {"status": "TIMEOUT"}
        print(task, results[task], flush=True)
    summary = {"platform": platform.system() + " " + platform.machine(), "android": "NOT_RUN",
               "native_jar_sha256": digest, "checks": results,
               "overlap_note": "Native failure is a real blocker, never a PASS. Android worker containment requires device execution."}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    # Preserve all evidence; unexpected core inference failures still fail CI.
    return 0 if all(v["status"] == "PASS" for v in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
