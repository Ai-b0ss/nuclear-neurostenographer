"""Package source/build evidence only; never weights, signing keys or audio."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/evidence/realtime-honor-20261105'


def main():
    for src, name in [('.local/build-realtime-11.log', 'final-build.txt'), ('.local/build-product-regression.log', 'product-regression-build.txt'),
                      ('.local/host-realtime.log', 'host-native-build-run.txt'), ('app/build/reports/lint-results-debug.txt', 'lint-debug.txt'),
                      ('app/build/reports/lint-results-release.txt', 'lint-product.txt')]:
        shutil.copyfile(ROOT / src, OUT / name)
    sources = []
    for folder in ['app/src/realtime', 'app/src/realtimeTest', 'tools/realtime']:
        sources += [p for p in (ROOT / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    sources += [ROOT / p for p in ['app/build.gradle.kts', 'core/build.gradle.kts',
        'app/src/main/java/ru/neurostenographer/app/MainActivity.kt', 'app/src/main/java/ru/neurostenographer/app/TranscriptionViewModel.kt',
        'app/src/nemotron/java/ru/neurostenographer/core/NemotronDiarizer.kt', 'app/src/nemotron/java/ru/neurostenographer/core/NemotronStreaming.kt',
        'core/src/main/kotlin/ru/neurostenographer/core/RealtimeCore.kt', 'core/src/main/kotlin/ru/neurostenographer/core/RealtimeTranscript.kt',
        'core/src/main/kotlin/ru/neurostenographer/core/Pcm16WavWriter.kt', 'core/src/main/kotlin/ru/neurostenographer/core/QuietCuts.kt',
        'core/src/test/kotlin/ru/neurostenographer/core/RealtimeCoreTest.kt', 'core/src/test/kotlin/ru/neurostenographer/core/Pcm16WavWriterTest.kt',
        'core/src/test/kotlin/ru/neurostenographer/core/TranscriptCoreTest.kt']]
    manifest = {'scope': 'SOURCE_AND_LOCAL_BUILD_CHECKPOINT',
        'base': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
        'source_sha256': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(sources))},
        'git_normalized_blob_sha1': {p.relative_to(ROOT).as_posix(): subprocess.check_output(
            ['git', 'hash-object', '--path', p.relative_to(ROOT).as_posix(), str(p)], cwd=ROOT, text=True).strip()
            for p in sorted(set(sources))},
        'line_endings': 'source_sha256 hashes this materialized Windows worktree; git_normalized_blob_sha1 identifies source across Git EOL normalization; device evidence is -text'}
    (OUT / 'source-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Source hashes:', len(manifest['source_sha256']))


if __name__ == '__main__':
    main()
