"""Actual ARM64 regression of repaired error handling, separate DEX/version evidence."""
import argparse
import json
import os
import re
import shlex
import subprocess
import numpy as np
from common import LOCAL,sha,write_json
from make_dev import write_wav,read_wav

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--serial',required=True);a=p.parse_args()
    state=json.loads((LOCAL/'phone-runs/state.json').read_text());r=state['remote']
    if state['status']!='COMPLETE' or not re.fullmatch(r'/data/local/tmp/nn_issue10_codex_20261105_[0-9]+',r):raise ValueError('Unresolved/wrong task state')
    if state['serial_sha256']!=__import__('hashlib').sha256(a.serial.encode()).hexdigest():raise ValueError('Wrong device')
    env=dict(os.environ,ANDROID_USER_HOME=str(LOCAL/'android-user'),ANDROID_SDK_HOME=str(LOCAL/'android-user'))
    adb=[str(LOCAL/'android-sdk/platform-tools/adb.exe'),'-P','5047','-s',a.serial]
    def run(args,check=True):return subprocess.run(adb+args,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180,check=check)
    folder=LOCAL/'phone-v2';dex=folder/'probe-dex.jar';build=json.loads((folder/'build.json').read_text())
    if sha(dex)!=build['dex_sha256']:raise ValueError('New DEX pin mismatch')
    run(['push',str(dex),r+'/probe-handled.jar'])
    if run(['shell','sha256sum '+r+'/probe-handled.jar']).stdout.split()[0]!=sha(dex):raise ValueError('New DEX transfer mismatch')
    silent=folder/'silence1600.wav';write_wav(silent,np.zeros(1600,np.float32));run(['push',str(silent),r+'/guard-silence.wav'])
    rows=[]
    for label,mix,enroll in [('invalid',r+'/mix.wav',r+'/short-enrollment.wav'),('valid-silence',r+'/guard-silence.wav',r+'/enroll0.wav')]:
        args=['app_process','-Djava.library.path='+r+'/native',r,'ru.neurostenographer.research.VoxLockProbe',r+'/vox',mix,enroll,r+'/guard-'+label+'.wav',r+'/guard-'+label+'.meta.json']
        command='export CLASSPATH='+r+'/probe-handled.jar LD_LIBRARY_PATH='+r+'/native; '+' '.join(map(shlex.quote,args))
        result=run(['shell',command],check=False)
        run(['pull',r+'/guard-'+label+'.meta.json',str(folder/(label+'.meta.json'))])
        meta=json.loads((folder/(label+'.meta.json')).read_text());row=dict(label=label,exit_code=result.returncode,meta=meta,stdout=result.stdout,stderr=result.stderr)
        if label=='invalid':
            if result.returncode!=2 or meta.get('status')!='INVALID_INPUT':raise ValueError('Handled rejection regression')
        else:
            if result.returncode or meta.get('status')!='OK' or meta.get('samples')!=1600:raise ValueError('Valid inference regression')
            run(['pull',r+'/guard-valid-silence.wav',str(folder/'valid-silence.wav')]);x=read_wav(folder/'valid-silence.wav')
            if len(x)!=1600 or not np.isfinite(x).all() or np.max(np.abs(x))!=0:raise ValueError('Silence output changed')
        rows.append(row)
    write_json(LOCAL/'input-guard-regression.json',dict(status='PASS',scope='Separate repaired DEX; original5-repeat DEX unchanged. Actual ARM64 handled invalid input and valid silence inference.',
        new_dex_sha256=sha(dex),rows=rows,build=build))
    print('PASS ARM64 INVALID_INPUT exit2 + valid silence inference exit0')
