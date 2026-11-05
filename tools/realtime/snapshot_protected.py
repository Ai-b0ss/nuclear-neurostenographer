"""Read-only final APK/model-asset inventory. Does not enter protected app data."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BEFORE = {
    'ru.neurostenographer.app': '5ba1f0c5545f48f21a3eb1dcd9da869c5a234c0e2c8395d3fb610019754d3bb0',
    'ru.neurostenographer.app.c2candidate': 'fbe7f3cc2642519c5afe6ad1be39e4c593b816d7f342a2c8b9e04641fed667a8',
}


def main():
    p = argparse.ArgumentParser(); p.add_argument('--adb', required=True); p.add_argument('--serial', required=True)
    a = p.parse_args(); adb = [a.adb, '-s', a.serial]
    def call(*args):
        return subprocess.check_output([*adb, *args], timeout=90).decode('utf-8', 'replace')
    rows = []
    for package, before in BEFORE.items():
        path = call('shell', 'pm', 'path', package).strip().removeprefix('package:')
        if not re.fullmatch(r'/data/app/[A-Za-z0-9._=+/-]+/base\.apk', path):
            raise SystemExit('Unexpected APK path')
        after = call('shell', 'sha256sum', path).split()[0]
        metadata = '\n'.join(s.strip() for s in call('shell', 'dumpsys', 'package', package).splitlines()
                             if 'versionName=' in s or 'versionCode=' in s)
        listing = call('shell', 'unzip', '-l', path)
        assets = '\n'.join(s.strip() for s in listing.splitlines() if re.search(r'assets/.*(zip|onnx)$', s))
        rows.append({'package': package, 'before_sha256': before, 'after_sha256': after,
                     'apk_unchanged': after == before, 'version': metadata, 'bundled_model_asset_inventory': assets})
        if after != before:
            raise SystemExit('Protected APK changed; inspect without overwriting anything')
    own_path = call('shell', 'pm', 'path', 'ru.neurostenographer.app.realtime').strip().removeprefix('package:')
    backup = ROOT / '.local/tested-phone-v5.apk'
    subprocess.run([*adb, 'pull', own_path, str(backup)], check=True, timeout=180, capture_output=True)
    own_sha = hashlib.sha256(backup.read_bytes()).hexdigest()
    expected = json.loads((ROOT / 'docs/evidence/realtime-honor-20261105/app-apk.json').read_text(encoding='utf-8'))['sha256']
    if own_sha != expected:
        raise SystemExit('Installed test APK changed from recorded inference artifact')
    policy = call('shell', 'dumpsys', 'window', 'policy')
    lock = '\n'.join(s.strip() for s in policy.splitlines() if re.match(r'^\s*(showing|secure|mIsShowing)=', s))
    report = {'status': 'PASS', 'scope': 'PROTECTED_APK_IDENTITY_NOT_PRIVATE_SESSION_CONTENT', 'packages': rows,
              'tested_apk_backup_sha256': own_sha, 'tested_apk_backup': '.local/tested-phone-v5.apk',
              'keyguard': lock, 'battery': call('shell', 'dumpsys', 'battery'),
              'candidate_services': call('shell', 'dumpsys', 'activity', 'services', 'ru.neurostenographer.app.realtime')}
    (ROOT / 'docs/evidence/realtime-honor-20261105/preservation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Protected APKs unchanged; tested APK backed up:', own_sha)
    print(lock)


if __name__ == '__main__':
    main()
