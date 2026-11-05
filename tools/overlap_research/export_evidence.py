"""Publish only deidentified metrics/provenance, never task audio/model/participant text."""
import argparse
import json
from pathlib import Path
import subprocess
from common import REPO,LOCAL,sha,write_json

OUT=REPO/'docs/evidence/issue10-codex-20261105'

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def export(allow_partial=False):
    OUT.mkdir(parents=True,exist_ok=True)
    exported=[]
    def save(name,value):write_json(OUT/name,value);exported.append(name)
    for local,name in [('host-provided-v2/summary.json','host-provided.json'),('host-strict-v2/summary.json','host-strict-c2.json'),
                       ('runtime-negatives.json','runtime-negatives.json'),('arm64-static.json','native-static.json'),
                       ('probe-host-parity.json','jvm-waveform-parity.json'),('phone-waveform-parity.json','arm64-waveform-parity.json'),
                       ('graphs.json','onnx-graphs.json'),('provider-audit.json','provider-audit.json'),('python-packages.json','python-packages.json'),
                       ('fixture-rebuild.json','fixture-rebuild.json'),('fallback-verification.json','fallback-verification.json'),
                       ('native-loaded-maps.json','native-loaded-maps.json'),('baseline/provenance.json','baseline-rebuild.json'),
                       ('public-audit.json','other-candidates.json'),('hardware.json','hardware.json'),('dev/manifest.json','fixture-manifest.json')]:
        save(name,read(LOCAL/local))
    provenance=read(LOCAL/'provenance.json');save('model-runtime-provenance.json',provenance)
    phone=read(LOCAL/'phone-runs/summary.json')
    if not allow_partial and (phone['status']!='COMPLETE' or phone['complete_paired_repeats']<5):
        raise ValueError('Physical repeats incomplete; refusing final favorable evidence')
    save('phone-summary.json',phone)
    save('phone-build.json',read(LOCAL/'phone/build.json'))
    save('phone-inputs.json',read(LOCAL/'phone-runs/inputs.json'))
    # Preserve actual per-stage metadata/hashes while retaining detailed sample traces locally.
    state=read(LOCAL/'phone-runs/state.json')
    save('phone-stage-runs.json',dict(scope='Actual device observations, task-only worker; PID sample traces retained under ignored .local',
        status=state['status'],remote_directory=state['remote'],measured_code_checkpoint='1d9fdda',
        runs=[{k:v for k,v in r.items() if k not in ('pss_samples','transport_stdout','transport_stderr')} for r in state['runs']]))
    latest=read(LOCAL/'verification/latest.json');verification=read(REPO/latest['path']/'summary.json')
    if not verification['all_pass']:raise ValueError('Regression gate is red')
    save('regressions.json',verification)
    live=read(LOCAL/'github-live.json')
    issue=live['issue10']['issue'];related=[]
    for r in live['related']:
        payload=r.get('issue',r)
        related.append({k:payload.get(k) for k in ('url','issue_number','number','state','merged','head_sha','merge_commit_sha') if k in payload})
    save('github-status.json',dict(issue10={k:issue[k] for k in ('url','issue_number','state','title')},related=related,
                                  cli='gh API404; authenticated connector read succeeded; git ls-remote succeeded outside sandbox, no auth changes'))
    # Raw source output hashes without embedding audio or reference/hypothesis words.
    raw=[]
    for sub in ('host-strict-v2','host-provided-v2','phone-runs'):
        for p in sorted((LOCAL/sub).glob('*')):
            if p.is_file() and p.suffix in ('.wav','.json','.tsv','.log'):
                raw.append(dict(path=p.relative_to(REPO).as_posix(),sha256=sha(p),bytes=p.stat().st_size,
                    kind='LOCAL_ONLY_AUDIO' if p.suffix=='.wav' else 'LOCAL_ONLY_RAW_OUTPUT'))
    save('raw-output-manifest.json',dict(scope='Paths/hash/size only; no audio, transcribed words, weights, credentials or private phone files published',files=raw))
    save('evidence-manifest.json',dict(status='PARTIAL' if allow_partial else 'COMPLETE_ARTIFACT_EXPORT_NOT_ISSUE_CLOSURE',
         base_sha='a10dd3954a1a53aaf749f7ef7696bf6446cc42f4',branch='research/issue10-codex-20261105',
         files={n:dict(sha256=sha(OUT/n),bytes=(OUT/n).stat().st_size) for n in exported},
         limitations=['SYNTHETIC DEV only; natural manually annotated Russian overlap missing','Identity verifier and real app lifecycle gates still open','16KB ORT Java alignment fails','No paid APIs, no issue publication/closure, no main/release changes']))
    print('EXPORTED',len(exported)+1,'deidentified evidence artifacts')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--allow-partial',action='store_true');a=p.parse_args();export(a.allow_partial)
