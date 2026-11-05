"""Bounded environment evidence; official task-local adb, no authentication changes."""
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from common import LOCAL, REPO, owned, sha, write_json

def command(args, timeout=40, env=None):
    try:
        r=subprocess.run(args,cwd=REPO,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
        return dict(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr)
    except Exception as e:
        return dict(error=type(e).__name__+': '+str(e))

def device_probe():
    # Official Google SDK repository checksum, checked BEFORE any executable runs.
    url='https://dl.google.com/android/repository/repository2-1.xml'
    with urllib.request.urlopen(url,timeout=60) as r:
        root=ET.fromstring(r.read())
    pkg=next(x for x in root.iter('remotePackage') if x.get('path')=='platform-tools')
    archive=next(x for x in pkg.iter('archive') if x.findtext('host-os')=='windows')
    complete=archive.find('complete'); filename=complete.findtext('url')
    checksum=complete.find('checksum'); expected=checksum.text.strip(); algorithm=checksum.get('type','sha1')
    sdk=owned(LOCAL/'android-sdk'); dest=sdk/'platform-tools.zip'
    if not dest.exists() or hashlib.new(algorithm,dest.read_bytes()).hexdigest()!=expected:
        with urllib.request.urlopen('https://dl.google.com/android/repository/'+filename,timeout=90) as r:
            dest.write_bytes(r.read())
    if hashlib.new(algorithm,dest.read_bytes()).hexdigest()!=expected:
        raise ValueError('Official platform-tools checksum mismatch')
    with zipfile.ZipFile(dest) as z:
        for name in z.namelist():
            path=(sdk/name).resolve()
            if not path.is_relative_to(sdk.resolve()): raise ValueError('Unsafe archive path')
        z.extractall(sdk)
    env=dict(os.environ,ANDROID_USER_HOME=str(owned(LOCAL/'android-user')),ANDROID_SDK_HOME=str(LOCAL/'android-user'))
    adb=str(sdk/'platform-tools/adb.exe')
    # Own server port to avoid killing/upgrading any unrelated server.
    devices=command([adb,'-P','5047','devices','-l'],env=env)
    report=dict(url='https://dl.google.com/android/repository/'+filename,official_checksum={algorithm:expected},sha256=sha(dest),
                adb_sha256=sha(adb),version=command([adb,'version'],env=env),devices=devices)
    # Only terminate this probe's own server, never default port5037.
    report['owned_server_cleanup']=command([adb,'-P','5047','kill-server'],env=env)
    return report

if __name__=='__main__':
    owned(LOCAL)
    try: disk=shutil.disk_usage(LOCAL)._asdict()
    except Exception as e: disk=dict(error=str(e))
    report=dict(platform=platform.platform(),cpu=platform.processor(),logical_cpu=os.cpu_count(),disk=disk,
                tools={n:shutil.which(n) for n in ['python','java','javac','adb','ffmpeg','gh','gradle','nvidia-smi']},
                git={name:command(['git',*args]) for name,args in {
                    'sha':['rev-parse','HEAD'],'branch':['branch','--show-current'],'status':['status','--short'],
                    'diff':['diff','--stat'],'worktrees':['worktree','list','--porcelain']}.items()},
                processes=command(['powershell','-NoProfile','-Command',"Get-Process | Where-Object {$_.ProcessName -match 'python|java|adb|codex|node|gradle|ffmpeg'} | Select-Object ProcessName,Id,CPU | ConvertTo-Json"]),
                github=command(['gh','api','repos/Ai-b0ss/nuclear-neurostenographer/issues/10','--jq','{number,state,title,body}']))
    try: report['android']=device_probe()
    except Exception as e: report['android']=dict(status='BLOCKED',reason=type(e).__name__+': '+str(e))
    report['privacy']='No process command lines, credentials, phone files or participant audio collected.'
    write_json(LOCAL/'preflight.json',report)
    print('preflight.json written; Android:',report['android'])
