"""Run bounded relevant regressions and retain real logs, including failures."""
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from common import REPO,LOCAL,owned,write_json,sha

if __name__=='__main__':
    out=owned(LOCAL/'verification'/('attempt-'+str(time.time_ns())))
    suites=[('overlap','tools/overlap_research/test_overlap.py',False),('overlap-optimized','tools/overlap_research/test_overlap.py',True),
            ('same-corpus','tools/c2_same_tracks/test_same_tracks.py',False),('scorer','tools/test_score_transcript.py',False),
            ('phone-score','tools/test_score_clip_run.py',False),
            ('evidence','tools/test_android_evidence.py',False),('evidence-optimized','tools/test_android_evidence.py',True),
            ('runtime-identity','tools/test_runtime_identity.py',False),('runtime-identity-optimized','tools/test_runtime_identity.py',True),
            ('worker-collector','tools/test_android_workflow.py',False),('checkpoint-privacy','tools/test_create_checkpoint.py',False)]
    suites += [('exports-'+kind,'tools/test_transcript_exports.py',False) for kind in ('plain','named','edited')]
    rows=[]
    for name,path,opt in suites:
        args=[sys.executable,'-B']+(['-O'] if opt else [])+[str(REPO/path)]
        if name.startswith('exports-'):
            # Core source harness writes these samples with production serializers.
            args+=[str(REPO/'build/export-samples'/name.removeprefix('exports-'))]
        r=subprocess.run(args,cwd=REPO,capture_output=True,timeout=180)
        log=out/(name+'.log');log.write_bytes(r.stdout+r.stderr)
        text=(r.stdout+r.stderr).decode('utf-8','replace');count=re.search(r'Ran (\d+) tests?',text)
        skip=re.search(r'skipped=(\d+)',text)
        row=dict(suite=name,status='PASS_WITH_SKIP' if r.returncode==0 and skip else 'PASS' if r.returncode==0 else 'FAIL',returncode=r.returncode,tests=int(count.group(1)) if count else None,skipped=int(skip.group(1)) if skip else 0,
                 command=['python',*['-B'],*(['-O'] if opt else []),path]+(['build/export-samples/'+name.removeprefix('exports-')] if name.startswith('exports-') else []),log_sha256=sha(log))
        rows.append(row);print(name,row['status'],row['tests'],flush=True)
    write_json(out/'summary.json',dict(python=sys.version,rows=rows,all_pass=all(r['returncode']==0 for r in rows)))
    write_json(LOCAL/'verification/latest.json',dict(path=str(out.relative_to(REPO)),summary_sha256=sha(out/'summary.json')))
    sys.exit(0 if all(r['returncode']==0 for r in rows) else 1)
