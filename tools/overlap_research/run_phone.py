"""Task-owned ARM64 app_process feasibility, sequential workers, no contest APK changes.

Requires owner-authorized adb access. Uses port5047. Phone artifacts remain under
one newly created /data/local/tmp/nn_issue10_* directory; no app data/log clearing.
On a timeout leave UNKNOWN_OUTCOME and reconcile the owned PID before any retry.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import time
from common import LOCAL,REPO,owned,sha,write_json

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--serial',required=True);ap.add_argument('--a3',type=Path,required=True);ap.add_argument('--c2',type=Path,required=True)
    ap.add_argument('--repeats',type=int,default=5);ap.add_argument('--setup-only',action='store_true');ap.add_argument('--probe-only',action='store_true');a=ap.parse_args()
    if not 1<=a.repeats<=10:raise ValueError('Bounded repeats1..10 required')
    out=owned(LOCAL/'phone-runs');adb=str(LOCAL/'android-sdk/platform-tools/adb.exe')
    env=dict(os.environ,ANDROID_USER_HOME=str(LOCAL/'android-user'),ANDROID_SDK_HOME=str(LOCAL/'android-user'))
    prefix=[adb,'-P','5047','-s',a.serial]
    def run(args,timeout=120,check=True):
        r=subprocess.run(prefix+list(args),env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
        if check and r.returncode:raise RuntimeError(r.stderr+r.stdout)
        return r
    def shell(text,**kwargs):return run(['shell',text],**kwargs)
    state_path=out/'state.json'
    if state_path.exists():state=json.loads(state_path.read_text())
    else:
        remote='/data/local/tmp/nn_issue10_codex_20261105_'+str(int(time.time()))
        shell('mkdir '+remote)
        state=dict(remote=remote,status='CREATED',serial_sha256=__import__('hashlib').sha256(a.serial.encode()).hexdigest(),runs=[])
        write_json(state_path,state)
    remote=state['remote']
    if not remote.startswith('/data/local/tmp/nn_issue10_codex_20261105_'):raise ValueError('Unsafe task directory')
    # Never infer a timed-out device operation failed. Refuse dispatch until reconciled.
    if state['status']=='UNKNOWN_OUTCOME':
        r=shell('cat '+remote+'/job.rc',check=False)
        if r.returncode:raise RuntimeError('UNKNOWN_OUTCOME: owned job still unresolved; inspect task PID before retry')
        raise RuntimeError('Previous job exit now known: '+r.stdout.strip()+'; preserve evidence and explicitly reconcile state')
    baseline_files={p.name:p for p in a.a3.glob('*') if p.suffix in ('.onnx','.txt')}
    c2_names=['model.int8.ir9.onnx','mel_filters.bin','hann400.bin','silence_embeds.bin','LICENSE','NOTICE','CHANGES.txt']
    mappings={'probe.jar':LOCAL/'phone/probe-dex.jar','mix.wav':LOCAL/'dev/two-person-overlap.wav',
              'enroll0.wav':LOCAL/'host-provided-v1/two-person-overlap.enroll-0.wav','enroll1.wav':LOCAL/'host-provided-v1/two-person-overlap.enroll-1.wav',
              'vox/enroll.onnx':LOCAL/'voxlock/enroll.onnx','vox/chunk_int8.onnx':LOCAL/'voxlock/chunk_int8.onnx'}
    mappings.update({'native/'+p.name:p for p in (LOCAL/'phone/native').glob('*.so')})
    mappings.update({'a3/'+n:p for n,p in baseline_files.items()});mappings.update({'c2/'+n:a.c2/n for n in c2_names})
    if state['status']=='CREATED':
        write_json(out/'device-before.json',dict(info=shell('getprop ro.product.model; getprop ro.product.cpu.abi; getprop ro.build.version.release; getconf PAGESIZE; settings get global airplane_mode_on; settings get global wifi_on; settings get global mobile_data; dumpsys battery; df /data/local/tmp').stdout))
        shell('mkdir '+remote+'/native '+remote+'/a3 '+remote+'/c2 '+remote+'/vox')
        checks={}
        for relative,path in mappings.items():
            digest=sha(path);run(['push',str(path),remote+'/'+relative],timeout=300)
            actual=shell('sha256sum '+remote+'/'+relative).stdout.split()[0]
            if actual!=digest:raise ValueError('Phone transfer hash mismatch:'+relative)
            checks[relative]=dict(sha256=digest,bytes=path.stat().st_size)
        write_json(out/'inputs.json',checks);state['status']='STAGED';write_json(state_path,state)
    if a.setup_only:print('STAGED task-owned probe');return
    if shell('settings get global airplane_mode_on').stdout.strip()!='1':raise RuntimeError('Phone is not in airplane mode; do not silently change owner settings')
    def job(key,cls,args,outputs):
        if any(r['key']==key and r['status']=='OK' for r in state['runs']):return
        cmd=' '.join(shlex.quote(str(x)) for x in ['app_process','-Djava.library.path='+remote+'/native','-Dresearch.words=false',remote,cls,*args])
        command='export CLASSPATH='+remote+'/probe.jar LD_LIBRARY_PATH='+remote+'/native; '+cmd+' > '+remote+'/'+key+'.log 2>&1 & pid=$!; echo $pid > '+remote+'/job.pid; wait $pid; rc=$?; echo $rc > '+remote+'/job.rc; exit $rc'
        shell('rm -f '+remote+'/job.rc '+remote+'/job.pid') # exact task-owned status files only
        start=time.perf_counter();p=subprocess.Popen(prefix+['shell',command],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        samples=[];record=dict(key=key,status='RUNNING',outputs=outputs)
        state['runs'].append(record);state['status']='UNKNOWN_OUTCOME';write_json(state_path,state)
        # Sampling itself adds overhead; compare all task workers with this same protocol.
        while p.poll() is None:
            if time.perf_counter()-start>1200:
                record['status']='UNKNOWN_OUTCOME';write_json(state_path,state);raise RuntimeError('Owned device job timeout; left journal for reconciliation')
            r=shell('pid=$(cat '+remote+'/job.pid 2>/dev/null); if [ -n "$pid" ]; then dumpsys meminfo "$pid"; fi',check=False)
            import re
            match=re.search(r'TOTAL PSS:\s*(\d+)',r.stdout) or re.search(r'^\s*TOTAL\s+(\d+)',r.stdout,re.M)
            if match:samples.append(dict(elapsed_s=time.perf_counter()-start,total_pss_kib=int(match.group(1))))
            time.sleep(1)
        stdout,stderr=p.communicate();record.update(status='OK' if p.returncode==0 else 'FAIL',exit_code=p.returncode,wall_s=time.perf_counter()-start,
                 sampled_peak_total_task_pss_kib=max((s['total_pss_kib'] for s in samples),default=None),pss_samples=samples,
                 measurement='1s requested sampling plus adb overhead; one task-owned worker at a time; sampled estimate, not true peak',transport_stdout=stdout.decode('utf-8','replace'),transport_stderr=stderr.decode('utf-8','replace'))
        for name in [key+'.log',*outputs]:
            run(['pull',remote+'/'+name,str(out/name)],check=False)
        if record['status']=='OK' and not all((out/n).is_file() for n in outputs):record['status']='FAIL_MISSING_OUTPUT'
        record['output_sha256']={n:sha(out/n) for n in outputs if (out/n).exists()}
        meta=next((out/n for n in outputs if n.endswith('.meta.json')),None)
        if meta and meta.exists():record['inference']=json.loads(meta.read_text())
        record['battery']=shell('dumpsys battery').stdout
        state['status']='STAGED';write_json(state_path,state)
        print(key,record['status'],round(record['wall_s'],2),record['sampled_peak_total_task_pss_kib'],flush=True)
        if record['status']!='OK':raise RuntimeError('Device probe failed; inspect task log '+key)
    cls='ru.neurostenographer.tools.OverlapHostKt';vcls='ru.neurostenographer.research.VoxLockProbe'
    for i in range(a.repeats):
        if not a.probe_only:
            job('r'+str(i)+'-c2',cls,['c2',remote+'/c2',remote+'/mix.wav',remote+'/r'+str(i)+'.tsv',remote+'/r'+str(i)+'-c2.meta.json'],['r'+str(i)+'.tsv','r'+str(i)+'-c2.meta.json'])
            job('r'+str(i)+'-baseline',cls,['asr',remote+'/a3',remote+'/mix.wav',remote+'/r'+str(i)+'.tsv',remote+'/r'+str(i)+'-baseline.json',remote+'/r'+str(i)+'-baseline.meta.json'],['r'+str(i)+'-baseline.json','r'+str(i)+'-baseline.meta.json'])
        for target in range(2):
            key='r'+str(i)+'-target'+str(target)
            job(key,vcls,[remote+'/vox',remote+'/mix.wav',remote+'/enroll'+str(target)+'.wav',remote+'/'+key+'.wav',remote+'/'+key+'.meta.json'],[key+'.wav',key+'.meta.json'])
            if not a.probe_only:
                job(key+'-asr',cls,['asr',remote+'/a3',remote+'/'+key+'.wav',remote+'/r'+str(i)+'.tsv',remote+'/'+key+'.json',remote+'/'+key+'-asr.meta.json'],[key+'.json',key+'-asr.meta.json'])
    state['status']='COMPLETE';write_json(state_path,state)
    write_json(out/'device-after.json',dict(info=shell('settings get global airplane_mode_on; dumpsys battery').stdout))
    print('PHONE FEASIBILITY COMPLETE',flush=True)

if __name__=='__main__':main()
