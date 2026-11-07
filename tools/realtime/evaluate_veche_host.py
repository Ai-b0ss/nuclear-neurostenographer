"""Reference-blind host C2 evaluation on human scripted Russian meeting fragments.

Gold comes from anonymized CSV speaker intervals. No speaker identification,
voice profiling or attempt to infer participants' actual identities.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from score_transcript import der
from speaker_consensus import load,fuse,dump

CASES=['2-one-to-one','3-auth-incident']
DATA=ROOT/'.local/veche-eval'
OUT=ROOT/'docs/evidence/veche-eval-20261106'

def hash_(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def score(turns,ref):
    duration=ref['audio_duration_ms']
    hypothesis=[dict(start_ms=a,end_ms=min(b,duration),speaker_id=str(s))
                for a,b,s in turns if a<duration and min(b,duration)>a]
    return dict(speakers=len({r['speaker_id'] for r in hypothesis}),
                der=der(ref['diarization'],hypothesis,duration,250,False))

def main():
    outcomes=[]
    for name in CASES:
        src=DATA/('veche-'+name)
        ref=json.loads((src/'reference.json').read_text(encoding='utf-8'))
        out=OUT/('host-'+str(2 if name.startswith('2-') else 3))
        if not (out/'parity.json').is_file():raise RuntimeError('Missing host C2 inference '+name)
        inputs=json.loads((out/'inputs.json').read_text(encoding='utf-8'))
        if inputs['fixture_sha256']!=ref['audio_sha256']:
            raise RuntimeError('Fixture hash mismatch '+name)
        preview=load(out/'revised-fast.tsv')
        final=load(out/'incremental-offline.tsv')
        fused,metadata=fuse(final,preview,'preview-first')
        dump(fused,out/'preview-first.tsv')
        (out/'speaker-consensus.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
        scores={k:score(turns,ref) for k,turns in
            [('fast',load(out/'fast.tsv')),('preview',preview),
             ('final',final),('preview-first',fused)]}
        (out/'veche-scores.json').write_text(json.dumps(scores,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        row=dict(clip='veche-'+name,source_sha256=ref['audio_sha256'],
            reference_sha256=hash_(src/'reference.json'),
            diarization_gold='HUMAN_SCRIPTED_MEETING_CSV_TIMINGS',
            cpwer_wer='NOT_RUN_C2_ONLY',
            results=scores)
        outcomes.append(row)
        print(name,{k:round(v['der']['rate']*100,3) for k,v in scores.items()},
            'speakers',{k:v['speakers'] for k,v in scores.items()},flush=True)
    (OUT/'host-comparison.json').write_text(json.dumps(outcomes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
