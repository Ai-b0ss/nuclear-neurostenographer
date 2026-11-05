"""Issue #10 task-owned I/O. No private audio is uploaded by these tools."""
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request

REPO = Path(__file__).resolve().parents[2]
LOCAL = REPO / '.local/issue10'

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def write_json(path, value, *, line_ending='\n'):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload=(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').replace('\n',line_ending)
    temporary=path.with_name(path.name+'.'+str(os.getpid())+'.'+str(time.time_ns())+'.tmp')
    with temporary.open('wb') as stream:
        stream.write(payload.encode('utf-8'));stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)

def owned(path):
    path = Path(path).resolve()
    if not path.is_relative_to(LOCAL.resolve()):
        raise ValueError('Output must remain in task-owned .local/issue10')
    path.mkdir(parents=True, exist_ok=True)
    return path

def fetch(url, destination, digest):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and sha(destination) == digest:
        return
    temporary = destination.with_suffix(destination.suffix + '.partial')
    with urllib.request.urlopen(url, timeout=90) as r, temporary.open('wb') as f:
        while block := r.read(1024 * 1024):
            f.write(block)
    if sha(temporary) != digest:
        raise ValueError('Download hash mismatch: ' + url)
    temporary.replace(destination)
