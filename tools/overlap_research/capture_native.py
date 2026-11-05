"""Read only the current journal-owned worker's library maps, with ownership check."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from common import LOCAL,write_json

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--serial',required=True);a=ap.parse_args()
    d=json.loads((LOCAL/'phone-runs/state.json').read_text());r=d['remote']
    if not r.startswith('/data/local/tmp/nn_issue10_codex_20261105_'):raise ValueError('Not a task directory')
    cmd='pid=$(cat '+r+'/job.pid); line=$(tr "\\000" " " < /proc/$pid/cmdline); case "$line" in *'+r+'*ru.neurostenographer*|*ru.neurostenographer*'+r+'*) echo TASK_PID=$pid; grep onnxruntime /proc/$pid/maps ;; *) echo OWNERSHIP_NOT_CONFIRMED; exit 3 ;; esac'
    env=dict(os.environ,ANDROID_USER_HOME=str(LOCAL/'android-user'),ANDROID_SDK_HOME=str(LOCAL/'android-user'))
    p=subprocess.run([str(LOCAL/'android-sdk/platform-tools/adb.exe'),'-P','5047','-s',a.serial,'shell',cmd],env=env,capture_output=True,text=True)
    expected=[r+'/native/'+n for n in ('libonnxruntime.so','libonnxruntime4j_jni.so')]
    result=dict(task_key=d['runs'][-1]['key'],returncode=p.returncode,maps=p.stdout,stderr=p.stderr,
                verified_paths=p.returncode==0 and all(n in p.stdout for n in expected),scope='Only journal-owned live worker; verify mapped paths against pinned transferred native files')
    write_json(LOCAL/'native-loaded-maps.json',result);print(json.dumps(result,indent=2))
