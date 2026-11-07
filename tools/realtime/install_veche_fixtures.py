"""Install two public, licensed, scripted human speech fragments on test package only."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
LOCAL=ROOT/'.local/veche-eval'
PACKAGE='ru.neurostenographer.app.realtime'
OUT=ROOT/'docs/evidence/veche-eval-20261106'
RECORDS=['2-one-to-one','3-auth-incident']

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--adb',type=Path,required=True)
    p.add_argument('--serial',required=True)
    a=p.parse_args()
    adb=[str(a.adb),'-s',a.serial]
    def call(*args):
        return subprocess.check_output(adb+list(args),text=True,encoding='utf-8',stderr=subprocess.STDOUT)
    if call('get-state').strip()!='device':raise RuntimeError('Selected device unavailable')
    if PACKAGE not in call('shell','pm','list','packages',PACKAGE):raise RuntimeError('Wrong test package')
    target='/sdcard/Android/data/'+PACKAGE+'/files/realtime-fixtures'
    call('shell','mkdir','-p',target)
    records=[]
    for name in RECORDS:
        case=LOCAL/('veche-'+name)
        wav=case/'clip.wav'
        ref=json.loads((case/'reference.json').read_text(encoding='utf-8'))
        remote=target+'/veche-'+name+'.wav'
        call('push',str(wav),remote)
        actual=call('shell','sha256sum',remote).split()[0]
        if ref['audio_sha256']!=actual:
            raise RuntimeError('Remote synthetic benchmark bytes mismatch')
        records.append(dict(name='veche-'+name,audio_sha256=actual,
            human_scripted=True,speakers=len({r['speaker_id'] for r in ref['diarization']})))
        print('VERIFIED PUBLIC BENCHMARK',name,actual,flush=True)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'device-fixtures.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
