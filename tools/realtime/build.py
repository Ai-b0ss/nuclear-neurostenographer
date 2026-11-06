"""Offline isolated build using the existing trusted toolchain (no downloads)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--toolchain', type=Path, default=Path('K:/nn-c2-android/.local/toolchain'))
    p.add_argument('--baseline', type=Path, default=Path('C:/Users/user/Documents/nuclear-neurostenographer'))
    p.add_argument('--variant', choices=['realtime', 'product', 'ordinary'], default='realtime')
    p.add_argument('tasks', nargs='*', default=[':core:runCoreTests', ':app:assembleDebug', ':app:assembleDebugAndroidTest'])
    a = p.parse_args()
    local = ROOT / '.local'
    local.mkdir(exist_ok=True)
    cache = local / 'gradle-home'
    if not (cache / '.copied').exists():
        # Python's extended Windows paths avoid MAX_PATH for Maven artifact names.
        source = '\\\\?\\' + str((a.toolchain / 'gradle-home').resolve()) if os.name == 'nt' else str(a.toolchain / 'gradle-home')
        target = '\\\\?\\' + str(cache.resolve()) if os.name == 'nt' else str(cache)
        shutil.copytree(source, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns('*.lock', 'daemon', '*.log'))
        (cache / '.copied').touch()
    (ROOT / 'app/libs').mkdir(exist_ok=True)
    aar = a.baseline / 'app/libs/sherpa-onnx-1.12.20.aar'
    if hashlib.sha256(aar.read_bytes()).hexdigest() != '771fda6a4abf845a6f84f48e05e887fdf159671beb88cbc9aae327806511c1c8':
        raise SystemExit('Trusted runtime AAR pin mismatch')
    shutil.copy2(aar, ROOT / 'app/libs' / aar.name)
    for name in ['gigaam-v3-e2e-rnnt.zip', 'nemotron.zip']:
        dest = local / 'productAssets' / name
        dest.parent.mkdir(exist_ok=True)
        if not dest.exists():
            shutil.copy2(a.baseline / '.local/productAssets' / name, dest)
    sdk = a.toolchain / 'sdk'
    (ROOT / 'local.properties').write_text('sdk.dir=' + sdk.as_posix().replace(':', '\\:') + '\n', encoding='utf-8')
    jdk = a.toolchain / 'jdk/jdk-17.0.21+9'
    env = dict(os.environ, JAVA_HOME=str(jdk), ANDROID_HOME=str(sdk), GRADLE_USER_HOME=str(cache),
               ANDROID_USER_HOME=str(local / 'android-user'), TEMP=str(local / 'tmp'), TMP=str(local / 'tmp'))
    (local / 'tmp').mkdir(exist_ok=True)
    # Workspace-owned key: no access to the production signing key.
    key = local / 'realtime-debug.jks'
    if not key.exists():
        subprocess.run([str(jdk / 'bin/keytool.exe'), '-genkeypair', '-keystore', str(key), '-storepass', 'android',
                        '-alias', 'androiddebugkey', '-keypass', 'android', '-dname', 'CN=Realtime Test',
                        '-keyalg', 'RSA', '-validity', '3650'], check=True, env=env)
    flags = ['-PnemotronProduct=true', '-PasrA3=true'] if a.variant != 'ordinary' else []
    if a.variant == 'realtime':
        flags += ['-Prealtime=true']
    cmd = [str(a.toolchain / 'gradle/gradle-8.9/bin/gradle.bat'), '--no-daemon', '--offline', '--console=plain',
           *flags, '-PlocalDebugStore=.local/realtime-debug.jks', *a.tasks]
    print('Building ' + a.variant + ' APK, offline', flush=True)
    result = subprocess.run(cmd, cwd=ROOT, env=env)
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
