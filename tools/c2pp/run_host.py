"""Compile tools/c2pp/DumpLogits.kt with the product C2 sources and run it on the selected WAVs (Windows host).

Reuses the pinned harness of tools/realtime/host.py (ORT 1.17.1 jar, Kotlin compiler, C2 int8 model) and checks pins.
"""
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARNESS = Path('K:/nn-bench/harness')
JAVA = Path('K:/nn-c2-android/.local/toolchain/jdk/jdk-17.0.21+9/bin/java.exe')
MODEL = Path('K:/nn-c2-android/.local/nemotron')
ORT_SHA = 'a4e57e18a04b6c1b5b0e2885af1d8557873d4ca04bfcebf79743966c4c8eb20f'
PINS = {'model.int8.ir9.onnx': 'c465504c2f3a29242e1b3d894187ae5962be7320bed71a2ae203950285ee6025',
        'mel_filters.bin': 'bce5ec5f194a5913f6508cee5a85512e7bad2352db8fc28f5c6ff75af8b09137',
        'hann400.bin': 'c427e2029118cf789649e5a4d439b6115d0dd0cbf95dcd22f65e3c848add8c5b',
        'silence_embeds.bin': 'd4417b3c0eabdf7c47032fac2b5b5a7ee83d819a6ddda8fd8eaf74e2b5cc4ac7'}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--wavs', type=Path, nargs='+', required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--work', type=Path, required=True, help='scratch dir for the compiled jar and JVM tmp')
    ap.add_argument('--params', type=Path)
    a = ap.parse_args()
    ort = HARNESS / 'onnxruntime-1.17.1.jar'
    if sha(ort) != ORT_SHA:
        raise SystemExit('ORT jar pin mismatch')
    for name, digest in PINS.items():
        if sha(MODEL / name) != digest:
            raise SystemExit('C2 model pin mismatch: ' + name)
    sources = sorted((ROOT / 'core/src/main/kotlin/ru/neurostenographer/core').glob('*.kt'))
    sources += sorted((ROOT / 'app/src/nemotron/java/ru/neurostenographer/core').glob('*.kt'))
    sources += [ROOT / 'tools/c2pp/DumpLogits.kt']
    kotlin = HARNESS / 'kotlin'
    cp = os.pathsep.join([str(kotlin / 'kotlin-stdlib.jar'), str(ort)])
    a.work.mkdir(parents=True, exist_ok=True)
    jar = a.work / 'c2pp-classes'
    subprocess.run([str(JAVA), '-cp', str(kotlin / '*'), 'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler', '-no-stdlib', '-no-reflect',
                    '-jvm-target', '17', '-classpath', cp, '-d', str(jar), *map(str, sources)], check=True)
    a.out.mkdir(parents=True, exist_ok=True)
    lst = a.work / 'wavs.txt'
    lst.write_text('\n'.join(str(w) for w in a.wavs), encoding='utf-8')
    (a.out / 'inputs.json').write_text(json.dumps(dict(scope='WINDOWS_HOST_C2_NOT_PHONE', model_pins=PINS, ort_jar_sha256=ORT_SHA,
        sources={str(p.relative_to(ROOT)): sha(p) for p in sources}, wavs={w.name: sha(w) for w in a.wavs}), indent=1), encoding='utf-8')
    tmp = a.work / 'tmp'; tmp.mkdir(exist_ok=True)
    subprocess.run([str(JAVA), '-Xmx2g', '-Djava.io.tmpdir=' + str(tmp), '-cp', os.pathsep.join([str(jar), cp]),
                    'ru.neurostenographer.tools.DumpLogitsKt', str(MODEL), str(a.out), str(lst),
                    *([str(a.params)] if a.params else [])], check=True)


if __name__ == '__main__':
    main()
