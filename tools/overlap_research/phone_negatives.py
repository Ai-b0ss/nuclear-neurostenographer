"""Bounded owned-process cancellation/invalid enrollment/recovery, not Binder lifecycle."""
import argparse
import json
import os
import re
import shlex
import subprocess
import time
from common import LOCAL,write_json,sha
from make_dev import read_wav,write_wav

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--serial',required=True);a=ap.parse_args()
    folder=LOCAL/'phone-runs';state=json.loads((folder/'state.json').read_text());remote=state['remote']
    if state['status']!='COMPLETE':raise ValueError('Finish current performance/quality work first')
    if not re.fullmatch(r'/data/local/tmp/nn_issue10_codex_20261105_[0-9]+',remote):raise ValueError('Unsafe task directory')
    if state['serial_sha256']!=__import__('hashlib').sha256(a.serial.encode()).hexdigest():raise ValueError('Wrong device')
    env=dict(os.environ,ANDROID_USER_HOME=str(LOCAL/'android-user'),ANDROID_SDK_HOME=str(LOCAL/'android-user'))
    prefix=[str(LOCAL/'android-sdk/platform-tools/adb.exe'),'-P','5047','-s',a.serial]
    def adb(args,timeout=60,check=True):
        r=subprocess.run(prefix+args,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
        if check and r.returncode:raise RuntimeError(r.stderr+r.stdout)
        return r
    def shell(command,**kwargs):return adb(['shell',command],**kwargs)
    if shell('settings get global airplane_mode_on').stdout.strip()!='1':raise ValueError('Offline condition changed')
    short=folder/'short-enrollment.wav';write_wav(short,read_wav(LOCAL/'host-provided-v2/two-person-overlap.enroll-0.wav')[:-1])
    adb(['push',str(short),remote+'/short-enrollment.wav'])
    if shell('sha256sum '+remote+'/short-enrollment.wav').stdout.split()[0]!=sha(short):raise ValueError('Negative fixture transfer mismatch')
    def command(cls,args):
        return 'export CLASSPATH='+remote+'/probe.jar LD_LIBRARY_PATH='+remote+'/native; '+' '.join(shlex.quote(x) for x in ['app_process','-Djava.library.path='+remote+'/native','-Dresearch.words=false',remote,cls,*args])
    probe='ru.neurostenographer.research.VoxLockProbe'
    bad=command(probe,[remote+'/vox',remote+'/mix.wav',remote+'/short-enrollment.wav',remote+'/invalid-enroll-out.wav',remote+'/invalid-enroll.meta.json'])
    bad+=' & pid=$!; echo $pid > '+remote+'/invalid-enroll.pid; wait $pid; exit $?'
    invalid=shell(bad,check=False)
    bad_pid=int(shell('cat '+remote+'/invalid-enroll.pid').stdout.strip())
    filtered=shell('logcat -d --pid='+str(bad_pid)+' -v brief',check=False)
    invalid_log=invalid.stdout+invalid.stderr+filtered.stdout+filtered.stderr
    invalid_record=dict(status='EXPECTED_REJECTION' if invalid.returncode!=0 and 'Enrollment must be48000 samples' in invalid_log else 'UNVERIFIED_REJECTION',
        exit_code=invalid.returncode,pid=bad_pid,log=invalid_log,logcat_scope='Only task-created invalid-enrollment PID; no clearing/global log export')
    write_json(LOCAL/'phone-invalid-enrollment.json',invalid_record)
    if invalid_record['status']!='EXPECTED_REJECTION':raise ValueError('Invalid enrollment was not explicitly rejected; raw evidence retained')
    tag='cancel-probe-'+str(time.time_ns())
    journal=dict(scope='Standalone task process only; not application Binder/UI lifecycle',status='UNKNOWN_OUTCOME',tag=tag,
                 invalid_enrollment=invalid_record)
    path=LOCAL/'phone-negatives.json';write_json(path,journal)
    cmd=command(probe,[remote+'/vox',remote+'/mix.wav',remote+'/enroll0.wav',remote+'/'+tag+'.wav',remote+'/'+tag+'.meta.json'])
    cmd+=' & pid=$!; echo $pid > '+remote+'/'+tag+'.pid; wait $pid; exit $?'
    p=subprocess.Popen(prefix+['shell',cmd],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    time.sleep(8)
    pid=int(shell('cat '+remote+'/'+tag+'.pid').stdout.strip())
    line=shell('tr "\\000" " " < /proc/'+str(pid)+'/cmdline').stdout
    if remote not in line or tag not in line or probe not in line:raise ValueError('Cancellation ownership not confirmed; leave journal unknown')
    maps=shell('grep onnxruntime /proc/'+str(pid)+'/maps').stdout
    if remote+'/native/libonnxruntime.so' not in maps:raise ValueError('Native runtime not mapped; cannot claim native cancellation')
    shell('kill -TERM '+str(pid))
    stdout,stderr=p.communicate(timeout=30)
    if p.returncode not in (143,-15):raise ValueError('Unexpected cancellation exit:'+str(p.returncode))
    alive=shell('kill -0 '+str(pid),check=False).returncode==0
    if alive:raise ValueError('Cancelled worker still exists; do not dispatch recovery')
    journal['cancellation']=dict(status='CONFIRMED_TERMINATED',exit_code=p.returncode,native_loaded=True,pid_disappeared=True,log=(stdout+stderr).decode('utf-8','replace'))
    journal['status']='CANCELLED_RECOVERY_PENDING';write_json(path,journal)
    key='post-cancel-baseline'
    r=shell(command('ru.neurostenographer.tools.OverlapHostKt',['asr',remote+'/a3',remote+'/mix.wav',remote+'/r0.tsv',remote+'/'+key+'.json',remote+'/'+key+'.meta.json']),timeout=180)
    for name in (key+'.json',key+'.meta.json'):adb(['pull',remote+'/'+name,str(folder/name)])
    before=json.loads((folder/'r0-baseline.json').read_text(encoding='utf-8'));after=json.loads((folder/(key+'.json')).read_text(encoding='utf-8'))
    same=[s['text'] for s in before['segments']]==[s['text'] for s in after['segments']]
    if not same:raise ValueError('Recovery text differs; investigate before claiming PASS')
    journal['recovery']=dict(status='PASS',baseline_text_equal=True,transcript_sha256=sha(folder/(key+'.json')),
                             meta=json.loads((folder/(key+'.meta.json')).read_text()))
    journal['status']='PASS';write_json(path,journal)
    print('PASS invalid enrollment + owned native-process cancellation + A3 recovery')
