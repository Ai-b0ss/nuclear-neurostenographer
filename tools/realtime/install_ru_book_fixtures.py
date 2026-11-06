"""Install evaluation-only audio on the explicitly selected test APK's external dir."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from evaluate_ru_book_mix import DATA, NAMES, rttm_reference

PACKAGE='ru.neurostenographer.app.realtime'
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--adb',type=Path,required=True)
    parser.add_argument('--serial',required=True)
    args=parser.parse_args()
    base=[str(args.adb),'-s',args.serial]
    def run(*cmd):
        return subprocess.check_output([*base,*cmd],stderr=subprocess.STDOUT,text=True,encoding='utf-8')
    assert run('get-state').strip()=='device'
    if PACKAGE not in run('shell','pm','list','packages',PACKAGE):
        raise RuntimeError('Test package is not installed')
    dest=f'/sdcard/Android/data/{PACKAGE}/files/realtime-fixtures'
    run('shell','mkdir','-p',dest)
    selection=json.loads((DATA/'selection.json').read_text(encoding='utf-8'))
    meta={r['name']:r for r in selection['records']}
    for name in NAMES:
        ref=rttm_reference(name,meta[name]['speakers'])
        src=DATA/(name+'.wav')
        destination=dest+'/'+src.name
        print(run('push',str(src),destination).strip(),flush=True)
        digest=run('shell','sha256sum',destination).split()[0]
        if digest != ref['audio_sha256']:
            raise RuntimeError('Remote audio hash mismatch: '+name)
        (DATA/(name+'.reference.json')).write_text(
            json.dumps(ref,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('VERIFIED',name,meta[name]['speakers'],digest,flush=True)

if __name__=='__main__':main()
