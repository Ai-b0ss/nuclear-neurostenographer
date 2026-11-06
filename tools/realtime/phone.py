"""Serial-targeted runner for the isolated .realtime app. No clear/uninstall/logcat -c.
Only explicitly selected public, licensed test exports and mic metadata may leave the phone.
"""
import argparse
import atexit
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import threading
import wave
from confirm_installer import confirm

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'ru.neurostenographer.app.realtime'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--adb', required=True)
    p.add_argument('--serial', required=True)
    p.add_argument('--out', type=Path, default=ROOT / 'docs/evidence/realtime-honor-20261105')
    sub = p.add_subparsers(dest='action', required=True)
    sub.add_parser('install')
    fixture = sub.add_parser('fixtures')
    fixture.add_argument('--baseline', type=Path, default=Path('C:/Users/user/Documents/nuclear-neurostenographer'))
    run = sub.add_parser('run')
    run.add_argument('--method', default='importedRussianStreaming')
    run.add_argument('--clip', default='syn3-clean')
    run.add_argument('--pause', choices=['300', '500'], default='500')
    run.add_argument('--fallback', action='store_true')
    run.add_argument('--consensus-experimental', action='store_true')
    run.add_argument('--chunk72-after-three-experimental', action='store_true')
    run.add_argument('--unpaced', action='store_true')
    run.add_argument('--label', required=True)
    run.add_argument('--mic-seconds', type=int, default=20)
    run.add_argument('--timeout-seconds', type=int, default=480)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    adb = [a.adb, '-s', a.serial]

    def call(*cmd, check=True, timeout=180):
        r = subprocess.run([*adb, *cmd], capture_output=True, timeout=timeout)
        if check and r.returncode:
            raise RuntimeError(r.stdout.decode('utf-8', 'replace') + r.stderr.decode('utf-8', 'replace'))
        return r

    if call('get-state').stdout.strip() != b'device':
        raise SystemExit('Exact target device unavailable')
    if a.action == 'install':
        for kind, apk in [('app', ROOT / 'app/build/outputs/apk/debug/app-debug.apk'),
                          ('test', ROOT / 'app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk')]:
            # Verify the application identity from actual APK bytes before any install.
            aapt = Path('K:/nn-c2-android/.local/toolchain/sdk/build-tools/35.0.0/aapt.exe')
            badging = subprocess.check_output([str(aapt), 'dump', 'badging', str(apk)], text=True, encoding='utf-8')
            expected = PACKAGE if kind == 'app' else PACKAGE + '.test'
            if f"package: name='{expected}'" not in badging or 'android.permission.INTERNET' in badging:
                raise SystemExit('Unexpected APK package/permission')
            digest = hashlib.sha256(apk.read_bytes()).hexdigest()
            size = apk.stat().st_size
            label = re.search(r"application-label:'([^']+)'", badging)
            label = label.group(1) if label else expected
            install = subprocess.Popen([*adb, 'install', '-r', str(apk)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            def approve():
                try:
                    confirm(adb, label, seconds=240)
                except Exception as exc:
                    if install.poll() is None:
                        print('Installer confirmation:', str(exc), flush=True)
            threading.Thread(target=approve, daemon=True).start()
            data, _ = install.communicate(timeout=300)
            text = data.decode('utf-8', 'replace')
            print(kind, text.strip(), flush=True)
            if 'Success' not in text:
                raise SystemExit('Install not confirmed')
            remote_path = call('shell', 'pm', 'path', expected).stdout.decode().strip().removeprefix('package:')
            remote_sha = call('shell', 'sha256sum', remote_path).stdout.decode().split()[0]
            if remote_sha != digest:
                raise SystemExit('Installed APK bytes differ from hashed build input')
            (a.out / f'{kind}-apk.json').write_text(json.dumps({'sha256': digest, 'installed_sha256': remote_sha,
                'bytes': size, 'package': expected, 'badging': badging}, ensure_ascii=False, indent=2), encoding='utf-8')
        call('shell', 'pm', 'grant', PACKAGE, 'android.permission.RECORD_AUDIO')
    elif a.action == 'fixtures':
        dest = f'/sdcard/Android/data/{PACKAGE}/files/realtime-fixtures'
        call('shell', 'mkdir', '-p', dest)
        manifest = []
        local = ROOT / '.local/realtime-fixtures'
        local.mkdir(exist_ok=True)
        sources = [a.baseline / f'.local/synthetic-ru/{name}.wav' for name in ['syn3-clean', 'syn3-brown', 'syn4-noise']]
        with wave.open(str(local / 'silence.wav'), 'wb') as w:
            w.setparams((1, 2, 16000, 0, 'NONE', 'not compressed')); w.writeframes(bytes(16000 * 2 * 8))
        sources.append(local / 'silence.wav')
        sources += [local / (name + '.wav') for name in ['single', 'aba', 'overlap'] if (local / (name + '.wav')).exists()]
        # Already-licensed acted two-voice A-B-A fixture, resample through existing bounded importer
        # only when the source is already 16k PCM. Avoid unrelated audio/private recordings.
        for src in sources:
            call('push', str(src), dest + '/' + src.name)
            digest = hashlib.sha256(src.read_bytes()).hexdigest()
            on_device = call('shell', 'sha256sum', dest + '/' + src.name).stdout.decode().split()[0]
            if digest != on_device:
                raise SystemExit('Fixture transfer hash mismatch')
            manifest.append({'name': src.stem, 'sha256': digest, 'bytes': src.stat().st_size,
                             'scope': 'AUTHORED_SILENCE' if src.stem == 'silence' else 'EXISTING_MIT_SYNTHETIC_RUSSIAN_FIXTURE'})
        (a.out / 'fixtures.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        print('Verified fixture hashes:', len(manifest))
    else:
        if not re.fullmatch(r'[a-zA-Z0-9_-]+', a.label):
            raise SystemExit('Unsafe label')
        folder = a.out / a.label
        if folder.exists():
            raise SystemExit('Evidence already exists; use a fresh label (no overwrites)')
        folder.mkdir()
        method = a.method if '.' in a.method else f'ru.neurostenographer.app.RealtimeDeviceTest#{a.method}'
        command = [*adb, 'shell', 'am', 'instrument', '-w', '-r', '-e', 'class', method,
                   '-e', 'invocation', a.label,
                   '-e', 'micSeconds', str(a.mic_seconds),
                   '-e', 'clip', a.clip, '-e', 'pause', a.pause, '-e', 'paced', str(not a.unpaced).lower(),
                   '-e', 'fallback', str(a.fallback).lower(), '-e', 'consensus', str(a.consensus_experimental).lower(),
                   '-e', 'chunk72', str(a.chunk72_after_three_experimental).lower(),
                   PACKAGE + '.test/androidx.test.runner.AndroidJUnitRunner']
        since = call('shell', 'date', '+%m-%d %H:%M:%S.000').stdout.decode().strip()
        initial_power = call('shell', 'dumpsys', 'power').stdout.decode('utf-8', 'replace')
        was_awake = 'mWakefulness=Awake' in initial_power
        switched_off = False
        restored_screen = False
        def restore_screen():
            if switched_off and was_awake and not restored_screen:
                try:
                    call('shell', 'input', 'keyevent', '224', check=False)
                except Exception:
                    pass
        atexit.register(restore_screen)
        started = time.monotonic()
        with (folder / 'instrumentation.txt').open('wb') as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            samples = []
            while process.poll() is None:
                battery = call('shell', 'dumpsys', 'battery', check=False).stdout.decode('utf-8', 'replace')
                # dumpsys meminfo asks ART to run a full GC and can perturb JNI loading badly.
                # Read only our UID's kernel counters, with no app Binder/GC side effect.
                pids = call('shell', 'pidof', PACKAGE, check=False).stdout.decode().split()
                mem = ''
                for pid in pids:
                    if pid.isdigit():
                        mem += call('shell', 'run-as', PACKAGE, 'cat', f'/proc/{pid}/smaps_rollup', check=False).stdout.decode('utf-8', 'replace')
                cpu = call('shell', 'ps', '-A', '-o', 'PID,PCY,TIME,NAME', check=False).stdout.decode('utf-8', 'replace')
                cpu = '\n'.join(x for x in cpu.splitlines() if PACKAGE in x)
                samples.append({'elapsed_s': round(time.monotonic() - started, 3), 'battery': battery, 'meminfo': mem, 'cpu': cpu})
                if a.method == 'foregroundMicrophoneScreenOff' and not switched_off:
                    services = call('shell', 'dumpsys', 'activity', 'services', PACKAGE, check=False).stdout.decode('utf-8', 'replace')
                    if 'isForeground=true' in services:
                        (folder / 'foreground-service.txt').write_text(services, encoding='utf-8')
                        call('shell', 'input', 'keyevent', '3')
                        call('shell', 'input', 'keyevent', '223')
                        switched_off = True
                (folder / 'monitor.json').write_text(json.dumps(samples, indent=2), encoding='utf-8')
                # Stop only our instrumentation on sustained unhealthy device conditions.
                temp = re.search(r'^\s*temperature:\s*(\d+)', battery, re.M)
                if temp and int(temp.group(1)) >= 460:
                    call('shell', 'am', 'force-stop', PACKAGE, check=False)
                    (folder / 'thermal-stop.txt').write_text('Own candidate stopped at battery >=46 C; test is not PASS.\n')
                    break
                if time.monotonic() - started > min(4200, a.timeout_seconds):
                    call('shell', 'am', 'force-stop', PACKAGE, check=False)
                    (folder / 'timeout.txt').write_text('Own candidate stopped at configured deadline.\n')
                    break
                time.sleep(5)
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.terminate(); process.wait()
        output = (folder / 'instrumentation.txt').read_text(encoding='utf-8', errors='replace')
        if switched_off and was_awake:
            call('shell', 'input', 'keyevent', '224')
            restored_screen = True
        passed = bool(re.search(r'OK \([1-9]\d* tests?\)', output)) and not any(x in output for x in ['FAILURES!!!', 'INSTRUMENTATION_FAILED', 'Process crashed'])
        if a.method == 'importedRussianStreaming':
            pointer = call('exec-out', 'run-as', PACKAGE, 'cat', 'files/realtime-last-synthetic.txt').stdout.decode().strip()
            if not re.fullmatch(r'test-(syn3-clean|syn3-brown|syn4-noise|silence|overlap|aba|single|rec_0150|rec_0300|rec_0437|veche-2-one-to-one|veche-3-auth-incident)-[0-9a-f-]+', pointer):
                raise SystemExit('Invalid synthetic pointer; no files read')
            for name in ['metrics.json', 'transcript.json', 'transcript.txt', 'transcript.srt']:
                data = call('exec-out', 'run-as', PACKAGE, 'cat', f'files/realtime/{pointer}/{name}').stdout
                if name.endswith('.json'):
                    try:
                        parsed = json.loads(data)
                    except (ValueError, UnicodeDecodeError):
                        if passed:
                            raise
                        (folder / (name + '.NOT_RUN.txt')).write_text('No valid JSON checkpoint at failed test completion.\n')
                        continue
                    if name == 'metrics.json' and parsed.get('invocation') != a.label:
                        raise SystemExit('Stale/mismatched device evidence invocation')
                if data.startswith(b'cat:'):
                    if passed:
                        raise SystemExit('Missing expected export')
                    continue
                (folder / name).write_bytes(data)
            if passed:
                # An atomic revision pointer is authoritative for cross-format consistency.
                manifest_data = call('exec-out', 'run-as', PACKAGE, 'cat',
                    f'files/realtime/{pointer}/transcript-current.json').stdout
                manifest = json.loads(manifest_data)
                revision = manifest['revision']
                if not isinstance(revision, int) or not 1 <= revision <= 9_999_999_999:
                    raise SystemExit('Invalid snapshot revision number')
                if manifest['state'] != 'FINAL':
                    raise SystemExit('Expected final published snapshot')
                version = f'v{revision:010d}'
                base = f'files/realtime/{pointer}/transcript-versions/{version}'
                snapshot_data = call('exec-out', 'run-as', PACKAGE, 'cat',
                    base + '/snapshot.json').stdout
                if hashlib.sha256(snapshot_data).hexdigest() != manifest['snapshot_sha256']:
                    raise SystemExit('Atomic transcript manifest hash mismatch')
                snapshot = json.loads(snapshot_data)
                if (snapshot['revision'], snapshot['state'], snapshot['audio_ms']) != (
                    revision, manifest['state'], manifest['audio_ms']):
                    raise SystemExit('Transcript pointer disagrees with version manifest')
                version_dir = folder / 'transcript-versioned'
                version_dir.mkdir()
                (folder / 'transcript-current.json').write_bytes(manifest_data)
                (version_dir / 'snapshot.json').write_bytes(snapshot_data)
                for fmt in ('json', 'txt', 'srt'):
                    filename = f'transcript.{fmt}'
                    payload = call('exec-out', 'run-as', PACKAGE, 'cat',
                        base + '/' + filename).stdout
                    expected = snapshot[f'{fmt}_sha256']
                    if hashlib.sha256(payload).hexdigest() != expected:
                        raise SystemExit(f'Hash mismatch in versioned transcript {fmt}')
                    if hashlib.sha256((folder / filename).read_bytes()).hexdigest() != expected:
                        raise SystemExit(f'Legacy export differs from authoritative snapshot: {fmt}')
                    (version_dir / filename).write_bytes(payload)
        for method_name, artifact in [('transcriptSnapshotCrashRecovery', 'realtime-snapshot-recovery.json'),
                                      ('hourJournalBounded', 'realtime-hour-journal.json'), ('c2OfflineParity', 'realtime-parity.json'), ('microphoneCaptureOnlyAndRestart', 'realtime-microphone.json'),
                                      ('cancellationRecoveryAndRestart', 'realtime-recovery.json'), ('foregroundMicrophoneScreenOff', 'realtime-microphone-screenoff.json'),
                                      ('damagedC2KeepsAsrAlive', 'realtime-c2-fallback.json')]:
            if a.method == method_name and passed:
                data = call('exec-out', 'run-as', PACKAGE, 'cat', 'files/' + artifact).stdout
                json.loads(data); (folder / artifact).write_bytes(data)
        # Read only our own log lines; never clear the system's logs or store other apps' text.
        logs = call('logcat', '-d', '-v', 'brief', '-T', since, check=False).stdout.decode('utf-8', 'replace')
        relevant = '\n'.join(line for line in logs.splitlines() if PACKAGE in line or 'RealtimeInference' in line)
        (folder / 'app-logcat.txt').write_text(relevant.replace(a.serial, '[REDACTED_SERIAL]'), encoding='utf-8')
        record = {'status': 'PASS' if passed else 'FAIL', 'method': method, 'clip': a.clip,
                  'pause': a.pause, 'fallback': a.fallback, 'consensus_experimental': a.consensus_experimental,
                  'chunk72_after_three_experimental': a.chunk72_after_three_experimental, 'paced': not a.unpaced, 'wall_s': round(time.monotonic() - started, 3),
                  'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'adb_exit': process.returncode}
        record.update(screen_switched_off=switched_off, screen_restored=switched_off and was_awake)
        (folder / 'run.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        print(json.dumps(record), flush=True)
        if not passed:
            print(output[-6000:]); raise SystemExit(1)


if __name__ == '__main__':
    main()
