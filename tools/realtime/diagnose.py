"""Read-only, serial-targeted baseline. Does not read conversations or clear logcat/data."""
import argparse
import datetime
import json
import subprocess
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--adb', required=True)
    p.add_argument('--serial', required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    commands = [
        ['get-state'],
        ['shell', 'getprop', 'ro.product.model'],
        ['shell', 'getprop', 'ro.build.version.sdk'],
        ['shell', 'getprop', 'ro.product.cpu.abi'],
        ['shell', 'getconf', 'PAGE_SIZE'],
        ['shell', 'dumpsys', 'battery'],
        ['shell', 'dumpsys', 'thermalservice'],
        ['shell', 'df', '-h', '/data'],
        ['shell', 'cat', '/proc/meminfo'],
        ['shell', 'settings', 'get', 'global', 'airplane_mode_on'],
        ['shell', 'settings', 'get', 'global', 'wifi_on'],
        ['shell', 'settings', 'get', 'global', 'bluetooth_on'],
        ['shell', 'ps', '-A', '-o', 'PID,NAME'],
    ]
    for package in ['ru.neurostenographer.app', 'ru.neurostenographer.app.c2candidate']:
        commands += [
            ['shell', 'dumpsys', 'package', package],
            ['shell', 'dumpsys', 'activity', 'services', package],
            ['shell', 'dumpsys', 'meminfo', package],
            ['shell', 'pm', 'path', package],
            ['shell', 'ls', '-l', f'/sdcard/Android/data/{package}/files'],
        ]
    result = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'scope': 'READ_ONLY_DEVICE_BASELINE', 'commands': []}
    for cmd in commands:
        r = subprocess.run([a.adb, '-s', a.serial, *cmd], capture_output=True,
                           encoding='utf-8', errors='replace', timeout=30)
        out = (r.stdout + r.stderr).replace(a.serial, '[REDACTED_SERIAL]')
        if cmd == ['shell', 'ps', '-A', '-o', 'PID,NAME']:
            out = '\n'.join(x for x in out.splitlines() if 'neurostenographer' in x or 'PID' in x)
        result['commands'].append({'argv': cmd, 'exit': r.returncode, 'output': out})
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(a.out)
    for c in result['commands']:
        if c['argv'][1:3] != ['dumpsys', 'package']:
            print(c['argv'], c['exit'], c['output'][:900])


if __name__ == '__main__':
    main()
