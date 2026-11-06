"""Evaluate reference-blind fusion on frozen dev fixtures (reference read AFTER fusion).

The external RTTM files have now been inspected and are DEVELOPMENT examples,
not an independent holdout for a subsequent fusion candidate.
No Android production switch is changed here.
"""
import json,hashlib,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from score_transcript import der
from score_clip_run import clamp_reference
from speaker_consensus import load,fuse,dump

ROOT=Path(__file__).resolve().parents[2]
SYN=Path('C:/Users/user/Documents/nuclear-neurostenographer/.local/synthetic-ru')
REFS=ROOT/'docs/evidence/realtime-honor-20261105/fixture-references'
DERIVED=ROOT/'docs/evidence/architecture-20261106/references'
DATA=ROOT/'docs/evidence/architecture-20261106'
NEW=ROOT/'docs/evidence/ru-book-eval-20261106'
OUT=ROOT/'docs/evidence/consensus-dev-20261106'

CASES=[
    ('syn3',DATA/'syn3',SYN/'syn3-clean.reference.json'),
    ('syn4',DATA/'syn4',SYN/'syn4-noise.reference.json'),
    ('aba',DATA/'aba',REFS/'aba.reference.json'),
    ('overlap',DATA/'overlap',REFS/'overlap.reference.json'),
    ('abab',DATA/'abab',DERIVED/'abab.reference.json'),
    ('return-pause',DATA/'return-pause',DERIVED/'return-pause.reference.json'),
    ('short-tail',DATA/'short-tail',DERIVED/'short-tail.reference.json'),
    ('rttm-2',NEW/'rec_0150',NEW/'rec_0150/reference.json'),
    ('rttm-3',NEW/'rec_0300',NEW/'rec_0300/reference.json'),
    ('rttm-4',NEW/'rec_0437',NEW/'rec_0437/reference.json'),
]

def main():
    report=[]
    for name,source,reference_path in CASES:
        preview=load(source/'revised-fast.tsv')
        final=load(source/'incremental-offline.tsv')
        target=OUT/name
        # No gold/reference exists in this function or its inputs.
        options={}
        for policy in ('preview-first','final-first','union'):
            turns,stats=fuse(final,preview,policy)
            dump(turns,target/(policy+'.tsv'))
            options[policy]=dict(turns=turns,stats=stats)
        # Evaluate only after predictions are already saved.
        ref=clamp_reference(json.loads(reference_path.read_text(encoding='utf-8')))
        results={}
        for label,turns in [('preview',preview),('final',final)]+[
                (k,v['turns']) for k,v in options.items()]:
            hyp=[dict(start_ms=a,end_ms=min(b,ref['audio_duration_ms']),speaker_id=str(s))
                 for a,b,s in turns if a<ref['audio_duration_ms']]
            score=der(ref['diarization'],hyp,ref['audio_duration_ms'],250,False)
            results[label]=dict(speakers=len({r['speaker_id'] for r in hyp}),der=score)
        for policy,v in options.items():
            (target/(policy+'.json')).write_text(json.dumps(v['stats'],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        results['reference_speakers']=len({r['speaker_id'] for r in ref['diarization']})
        (target/'scores.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        report.append(dict(fixture=name,source_preview_sha256=hashlib.sha256((source/'revised-fast.tsv').read_bytes()).hexdigest(),
            source_final_sha256=hashlib.sha256((source/'incremental-offline.tsv').read_bytes()).hexdigest(),
            reference_sha256=hashlib.sha256(reference_path.read_bytes()).hexdigest(),
            scores={k:round(v['der']['rate']*100,3) for k,v in results.items() if isinstance(v,dict)}))
        print(name,report[-1]['scores'],flush=True)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'summary.json').write_text(json.dumps(dict(scope='DEV_ONLY_NOT_INDEPENDENT_HOLDOUT',
        policy='Reference-blind permutation temporal consensus 10ms/TSV intervals',
        cases=report),indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('COMPLETE',len(report),'dev fixtures')

if __name__=='__main__':main()
