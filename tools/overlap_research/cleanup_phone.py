"""Remove only the positively identified completed task directory and owned adb server."""
import argparse
import json
import os
import re
import shlex
import subprocess
from common import LOCAL,write_json

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--serial',required=True);a=p.parse_args()
    folder=LOCAL/'phone-runs';state=json.loads((folder/'state.json').read_text());remote=state['remote']
    if state['status']!='COMPLETE' or any(r['status']!='OK' for r in state['runs']):raise ValueError('Unfinished owned work; do not clean')
    if not re.fullmatch(r'/data/local/tmp/nn_issue10_codex_20261105_[0-9]+',remote):raise ValueError('Unsafe target')
    if state['serial_sha256']!=__import__('hashlib').sha256(a.serial.encode()).hexdigest():raise ValueError('Wrong device')
    env=dict(os.environ,ANDROID_USER_HOME=str(LOCAL/'android-user'),ANDROID_SDK_HOME=str(LOCAL/'android-user'))
    adb=[str(LOCAL/'android-sdk/platform-tools/adb.exe'),'-P','5047']
    def shell(command):return subprocess.run(adb+['-s',a.serial,'shell',command],env=env,capture_output=True,text=True,check=True,timeout=60).stdout
    resolved=shell('readlink -f '+shlex.quote(remote)).strip()
    expected=json.loads((folder/'inputs.json').read_text())['probe.jar']['sha256']
    if resolved!=remote or shell('sha256sum '+shlex.quote(remote+'/probe.jar')).split()[0]!=expected:raise ValueError('Ownership/content of cleanup target not confirmed')
    before=shell('settings get global airplane_mode_on; settings get global wifi_on; dumpsys battery')
    shell('rm -rf -- '+shlex.quote(remote))
    absent=shell('if [ ! -e '+shlex.quote(remote)+' ]; then echo REMOVED; else echo STILL_PRESENT; fi').strip()
    if absent!='REMOVED':raise ValueError('Cleanup not confirmed')
    state['remote_cleanup']='REMOVED_AFTER_ALL_EVIDENCE_COLLECTED';write_json(folder/'state.json',state)
    server=subprocess.run(adb+['kill-server'],env=env,capture_output=True,text=True,timeout=30)
    write_json(LOCAL/'phone-cleanup.json',dict(status='PASS',removed_directory=remote,original_probe_sha256=expected,
        resolved_path_verified=True,phone_state_before_cleanup=before,owned_server_port=5047,server_exit_code=server.returncode,
        scope='Only completed task directory removed; native/model/WAV sources and signed contest APK untouched; no default adb5037 action'))
    print('CLEANED exact task phone directory; owned adb5047 server stopped')
