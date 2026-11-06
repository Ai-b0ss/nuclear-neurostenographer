"""Read/verify the latest *public test* transcript revision from an exact device.

Does not access private recordings or credentials. Run only for existing
instrumentation evidence whose own invocation label is checked against the
device session's metrics.json. SHA-256 covers version manifest and each file.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

PACKAGE='ru.neurostenographer.app.realtime'
PATTERN=re.compile(r'test-(?:syn3-clean|syn3-brown|syn4-noise|silence|overlap|aba|single|rec_0150|rec_0300|rec_0437|veche-2-one-to-one|veche-3-auth-incident)-[0-9a-f-]+$')

def sha(data: bytes)->str:
    return hashlib.sha256(data).hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--adb',type=Path,required=True)
    parser.add_argument('--serial',required=True)
    parser.add_argument('--evidence',type=Path,required=True)
    a=parser.parse_args()
    own=json.loads((a.evidence/'run.json').read_text(encoding='utf-8'))
    if own['status']!='PASS' or own['method'].split('#')[-1]!='importedRussianStreaming':
        raise SystemExit('Not a successful public synthetic/consented fixture test')
    argv=[str(a.adb),'-s',a.serial]
    def read(path:str)->bytes:
        process=subprocess.run(argv+['exec-out','run-as',PACKAGE,'cat',path],
            capture_output=True,timeout=60)
        if process.returncode!=0:
            raise RuntimeError('Cannot read expected own test export: '+path)
        return process.stdout
    tag=read('files/realtime-last-synthetic.txt').decode('utf-8').strip()
    if not PATTERN.fullmatch(tag):raise SystemExit('Unsafe/non-test session')
    src='files/realtime/'+tag
    metrics=json.loads(read(src+'/metrics.json'))
    if metrics['invocation']!=a.evidence.name:
        raise SystemExit('Current test session is not the requested evidence label')
    manifest_data=read(src+'/transcript-current.json')
    pointer=json.loads(manifest_data)
    rev=pointer['revision']
    if not isinstance(rev,int) or not 1<=rev<=9_999_999_999:raise RuntimeError('Invalid revision')
    if pointer['state']!='FINAL':raise RuntimeError('Test transcript did not finalize')
    base=src+'/transcript-versions/v'+f'{rev:010d}'
    snapshot=read(base+'/snapshot.json')
    if sha(snapshot)!=pointer['snapshot_sha256']:raise RuntimeError('Manifest hash mismatch')
    doc=json.loads(snapshot)
    if (doc['revision'],doc['state'],doc['audio_ms']) != (
        rev,pointer['state'],pointer['audio_ms']):raise RuntimeError('Manifest metadata mismatch')
    if doc['audio_ms']!=metrics['audio_ms']:raise RuntimeError('PCM duration mismatch')
    version_dir=a.evidence/'transcript-versioned'
    version_dir.mkdir(exist_ok=True)
    for ext in ('json','txt','srt'):
        name='transcript.'+ext
        version=read(base+'/'+name)
        if sha(version)!=doc[ext+'_sha256']:
            raise RuntimeError('Corrupted revision file '+name)
        exported=(a.evidence/name).read_bytes()
        if sha(version)!=sha(exported):
            raise RuntimeError('Legacy export differs from versioned authoritative file '+name)
        (version_dir/name).write_bytes(version)
    (a.evidence/'transcript-current.json').write_bytes(manifest_data)
    (version_dir/'snapshot.json').write_bytes(snapshot)
    report=dict(status='PASS',scope='PHYSICAL_ANDROID_ATOMIC_TRIPLE_EXPORT_VERIFIED',
        source=tag,revision=rev,state=doc['state'],audio_ms=doc['audio_ms'],
        manifest_sha256=sha(snapshot),
        consistency='THREE_FORMATS_AND_LEGACY_HASH_IDENTICAL')
    (a.evidence/'snapshot-verification.json').write_text(
        json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report),flush=True)

if __name__=='__main__':main()
