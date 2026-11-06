"""Inspect the bundled realtime debug artifact; no installation or network."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from check_apk import runtime_identity


def main():
    apk = ROOT / 'app/build/outputs/apk/debug/app-debug.apk'
    aapt = Path('K:/nn-c2-android/.local/toolchain/sdk/build-tools/35.0.0/aapt.exe')
    manifest = subprocess.check_output([str(aapt), 'dump', 'xmltree', str(apk), 'AndroidManifest.xml'], text=True, encoding='utf-8')
    badging = subprocess.check_output([str(aapt), 'dump', 'badging', str(apk)], text=True, encoding='utf-8')
    if "package: name='ru.neurostenographer.app.realtime'" not in badging or 'android.permission.INTERNET' in manifest:
        raise SystemExit('Unsafe/unexpected package or permissions')
    assets = {}
    with zipfile.ZipFile(apk) as z:
        for name in ['gigaam-v3-e2e-rnnt.zip', 'nemotron.zip', 'silero_vad.onnx']:
            data = z.read('assets/' + name)
            digest = hashlib.sha256(data).hexdigest()
            expected = ROOT / ('.local/realtimeAssets' if name == 'silero_vad.onnx' else '.local/productAssets') / name
            if digest != hashlib.sha256(expected.read_bytes()).hexdigest():
                raise SystemExit('Bundled asset bytes mismatch: ' + name)
            assets[name] = {'bytes': len(data), 'sha256': digest}
        if 'assets/silero-LICENSE.txt' not in z.namelist():
            raise SystemExit('Missing Silero license')
        if any(x.lower().endswith(('.wav', '.mp3', '.flac', '.ogg')) for x in z.namelist()):
            raise SystemExit('Unexpected audio in product APK')
    identity = runtime_identity(apk, ROOT / 'app/libs/sherpa-onnx-1.12.20.aar')
    report = {'status': 'PASS', 'scope': 'STATIC_PACKAGING_NOT_PHONE_EXECUTION', 'apk_sha256': hashlib.sha256(apk.read_bytes()).hexdigest(),
              'apk_bytes': apk.stat().st_size, 'bundled_assets': assets, 'runtime_identity': identity,
              'manifest': manifest, 'badging': badging, 'phone_installation_of_this_final_artifact': 'NOT_RUN_SECURE_KEYGUARD'}
    out = ROOT / 'docs/evidence/realtime-honor-20261105/final-apk.json'
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(report['status'], report['apk_sha256'], report['apk_bytes'])


if __name__ == '__main__':
    main()
