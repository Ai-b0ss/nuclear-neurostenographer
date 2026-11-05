"""Check actual published artifact bytes, new-file boundaries, and local Markdown links."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
from common import REPO,LOCAL,sha,write_json

def git(*args):return subprocess.run(['git',*args],cwd=REPO,capture_output=True,check=True).stdout

if __name__=='__main__':
    folder=REPO/'docs/evidence/issue10-codex-20261105';manifest=json.loads((folder/'evidence-manifest.json').read_text())
    for name,record in manifest['files'].items():
        p=folder/name
        if sha(p)!=record['sha256'] or p.stat().st_size!=record['bytes']:raise ValueError('Evidence changed:'+name)
    raw=json.loads((folder/'raw-output-manifest.json').read_text())
    for row in raw['files']:
        p=REPO/row['path']
        if sha(p)!=row['sha256'] or p.stat().st_size!=row['bytes']:raise ValueError('Raw output changed:'+row['path'])
    paths=set(git('diff','--name-only','a10dd3954a1a53aaf749f7ef7696bf6446cc42f4').decode().splitlines())
    paths.update(git('ls-files','--others','--exclude-standard').decode().splitlines())
    forbidden={'.wav','.mp3','.mp4','.m4a','.flac','.ogg','.onnx','.pt','.safetensors','.aar','.apk','.jar','.key','.p12','.jks','.keystore'}
    secret=re.compile(rb'(?:ghp|gho)_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}|sk-[A-Za-z0-9_-]{25,}|-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----')
    for name in paths:
        p=REPO/name
        if not p.is_file():continue
        if name.startswith(('.local/','.git/','app/','core/')) or p.suffix.lower() in forbidden:raise ValueError('Forbidden delivery path:'+name)
        data=p.read_bytes()
        if len(data)>1024*1024 or b'\x00' in data or secret.search(data):raise ValueError('Large/binary/secret-like delivery content:'+name)
        if p.suffix=='.md':
            for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',data.decode('utf-8')):
                if target.startswith(('http:','https:','#','mailto:')):continue
                clean=target.split('#')[0].strip('<>')
                if clean and not (p.parent/clean).exists():raise ValueError('Broken local link:'+name+' -> '+target)
    if git('diff','a10dd3954a1a53aaf749f7ef7696bf6446cc42f4','--','app','core','build.gradle.kts','settings.gradle.kts').strip():raise ValueError('Production files changed')
    write_json(LOCAL/'delivery-audit.json',dict(status='PASS',evidence_files_verified=len(manifest['files']),raw_artifacts_verified=len(raw['files']),
        changed_files_checked=len(paths),scope='New/research changes only; high-precision credential markers/binary/size/forbidden extensions; production files unchanged; local links resolve. Not a universal secret-detection certification.'))
    print('DELIVERY PASS:',len(manifest['files']),'evidence hashes;',len(raw['files']),'raw hashes;',len(paths),'changed paths')
