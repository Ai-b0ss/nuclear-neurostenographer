"""Reuse pinned existing JVM/ORT inputs; all generated files stay in this worktree."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT / 'docs/evidence/realtime-honor-20261105/host-native-c2')
    parser.add_argument('--fixture', type=Path, default=Path('C:/Users/user/Documents/nuclear-neurostenographer/.local/synthetic-ru/syn3-clean.wav'))
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--hour', action='store_true')
    parser.add_argument('--final-hour', action='store_true')
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit('Refusing to overwrite evidence: ' + str(args.out))
    harness = Path('K:/nn-bench/harness')
    jdk = Path('K:/nn-c2-android/.local/toolchain/jdk/jdk-17.0.21+9')
    java = str(jdk / 'bin/java.exe')
    ort = harness / 'onnxruntime-1.17.1.jar'
    if hashlib.sha256(ort.read_bytes()).hexdigest() != 'a4e57e18a04b6c1b5b0e2885af1d8557873d4ca04bfcebf79743966c4c8eb20f':
        raise SystemExit('Existing ORT jar pin mismatch')
    model = Path('K:/nn-c2-android/.local/nemotron')
    pins = {'model.int8.ir9.onnx': 'c465504c2f3a29242e1b3d894187ae5962be7320bed71a2ae203950285ee6025',
            'mel_filters.bin': 'bce5ec5f194a5913f6508cee5a85512e7bad2352db8fc28f5c6ff75af8b09137',
            'hann400.bin': 'c427e2029118cf789649e5a4d439b6115d0dd0cbf95dcd22f65e3c848add8c5b',
            'silence_embeds.bin': 'd4417b3c0eabdf7c47032fac2b5b5a7ee83d819a6ddda8fd8eaf74e2b5cc4ac7'}
    for name, digest in pins.items():
        if hashlib.sha256((model / name).read_bytes()).hexdigest() != digest:
            raise SystemExit('Existing C2 model pin mismatch: ' + name)
    target = ROOT / ('.local/realtime-host-' + args.out.name + '.jar')
    kotlin = harness / 'kotlin'
    cp = os.pathsep.join([str(kotlin / 'kotlin-stdlib.jar'), str(ort)])
    sources = list((ROOT / 'core/src/main/kotlin/ru/neurostenographer/core').glob('*.kt'))
    sources += list((ROOT / 'app/src/nemotron/java/ru/neurostenographer/core').glob('*.kt'))
    sources += [ROOT / 'tools/realtime/HostStreaming.kt']
    subprocess.run([java, '-cp', str(kotlin / '*'), 'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler', '-no-stdlib', '-no-reflect',
                    '-jvm-target', '17', '-classpath', cp, '-d', str(target), *map(str, sources)], check=True)
    out = args.out
    out.mkdir(parents=True)
    fixture = args.fixture
    (out / 'inputs.json').write_text(json.dumps({'scope': 'WINDOWS_NATIVE_C2_NOT_PHONE', 'model_pins': pins,
        'ort_jar_sha256': hashlib.sha256(ort.read_bytes()).hexdigest(), 'fixture_sha256': hashlib.sha256(fixture.read_bytes()).hexdigest(),
        'source_hashes': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}, indent=2), encoding='utf-8')
    tmp = ROOT / '.local/tmp/host-ort'; tmp.mkdir(exist_ok=True)
    subprocess.run([java, '-Xmx2g', '-Djava.io.tmpdir=' + str(tmp), '-cp', os.pathsep.join([str(target), cp]),
                    'ru.neurostenographer.tools.HostStreamingKt', str(model), str(fixture), str(out),
                    *(['final-hour'] if args.final_hour else ['hour'] if args.hour else ['diagnostic'] if args.diagnostic else [])], check=True)


if __name__ == '__main__':
    main()
