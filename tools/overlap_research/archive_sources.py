"""Reconcile measured source hashes to actual files or the engineering checkpoint."""
import hashlib
import json
from pathlib import Path
import subprocess
from common import REPO,LOCAL,owned,write_json

if __name__=='__main__':
    source=REPO/'tools/overlap_research'
    protocol=json.loads((LOCAL/'host-provided-v2/protocol.json').read_text())
    snapshot=owned(LOCAL/'source-snapshots/host-v2');rows=[]
    for name,want in protocol['source_hashes'].items():
        path=source/name
        candidates=[('worktree',path.read_bytes())]
        r=subprocess.run(['git','show','1d9fdda:tools/overlap_research/'+name],cwd=REPO,capture_output=True)
        if r.returncode==0:candidates.append(('1d9fdda',r.stdout))
        match=next(((ref,blob) for ref,blob in candidates if hashlib.sha256(blob).hexdigest()==want),None)
        if match is None:raise ValueError('Measured source not reconciled: '+name)
        ref,blob=match;(snapshot/name).write_bytes(blob);rows.append(dict(file=name,sha256=want,source=ref))
    phone=json.loads((LOCAL/'phone/build.json').read_text());phone_rows=[]
    for name,key in [('OverlapHost.kt','kotlin_source_sha256'),('VoxLockProbe.java','java_source_sha256')]:
        r=subprocess.run(['git','show','1d9fdda:tools/overlap_research/'+name],cwd=REPO,capture_output=True,check=True)
        if hashlib.sha256(r.stdout).hexdigest()!=phone[key]:raise ValueError('Phone source checkpoint mismatch')
        phone_rows.append(dict(file=name,sha256=phone[key],source='1d9fdda'))
    write_json(LOCAL/'source-reconciliation.json',dict(host=rows,phone=phone_rows,status='ALL_MEASURED_SOURCE_HASHES_RECONCILED',
        note='worktree entries must match final committed files; earlier instrumentation variants are pinned to1d9fdda, and all measured source bytes are saved locally.'))
    print('RECONCILED',len(rows),'host sources and2 phone sources')
