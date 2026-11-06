"""Fixed, reference-blind candidate check on six frozen RTTM recordings.

Only a single preselected candidate ('preview-first') is compared against
the existing production offline-final C2. No parameter or source modification
is allowed in the holdout after the selection has been frozen.
"""
import hashlib
import json
import subprocess
import sys
import wave
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from score_transcript import der
from speaker_consensus import load,fuse,dump

DATA=ROOT/'.local/ru-book-mix-holdout'
OUT=ROOT/'docs/evidence/consensus-holdout-20261106'
CODE=ROOT/'tools/realtime/speaker_consensus.py'
SOURCE_SHA='817d2ae79a0a1a6c83dc7dbfbdcbae4b7d73a7a9b68fc2e5c3e594fda3f04730'

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(65536),b''):h.update(block)
    return h.hexdigest()

def reference_for(name,n):
    wav=DATA/(name+'.wav')
    with wave.open(str(wav),'rb') as f:
        if (f.getnchannels(),f.getsampwidth(),f.getframerate())!=(1,2,16000):
            raise ValueError('Bad audio type')
        dur=f.getnframes()*1000//f.getframerate()
    turns=[]
    for i,line in enumerate((DATA/(name+'.rttm')).read_text(encoding='utf-8').splitlines(),1):
        fields=line.split()
        if not fields:continue
        if len(fields)<9 or fields[0]!='SPEAKER':
            raise ValueError(f'Unexpected RTTM row {i}')
        start=round(float(fields[3])*1000)
        end=min(dur,round((float(fields[3])+float(fields[4]))*1000))
        if end>start: turns.append(dict(start_ms=start,end_ms=end,speaker_id=fields[7]))
    if len({r['speaker_id'] for r in turns})!=n:raise ValueError('Speaker mismatch')
    return dur,turns

def score(ref,turns,duration):
    hyp=[dict(start_ms=a,end_ms=min(duration,b),speaker_id=str(s))
         for a,b,s in turns if a<duration and min(duration,b)>a]
    return dict(predicted_speakers=len({x['speaker_id'] for x in hyp}),
                der=der(ref,hyp,duration,250,False))

def main():
    selection_file=DATA/'frozen-selection.json'
    sel=json.loads(selection_file.read_text(encoding='utf-8'))
    if sha(CODE)!=SOURCE_SHA:
        raise SystemExit('Fusion source changed after holdout was chosen')
    if sel['seed']!='NN-C2-PREVIEW-FIRST-HOLDOUT-20261106-V1' or len(sel['records'])!=6:
        raise SystemExit('Holdout selection is not the frozen cohort')
    OUT.mkdir(parents=True,exist_ok=True)
    rows=[]
    for chosen in sel['records']:
        name=chosen['file_id']
        n=chosen['n_speakers']
        if not chosen['speaker_disjoint']:
            print('WARNING overlap with development voices:',name,flush=True)
        folder=OUT/name
        # This is run independently, with no reference input whatsoever.
        if not (folder/'revised-fast.tsv').is_file():
            if folder.exists():
                raise RuntimeError('Partial case: inspect before modifying '+name)
            print('HOST',name,n,'voices',flush=True)
            subprocess.run([sys.executable,'-X','utf8',str(ROOT/'tools/realtime/host.py'),
                '--quality-only','--fixture',str(DATA/(name+'.wav')),
                '--out',str(folder)],cwd=ROOT,check=True)
        pins=json.loads((folder/'inputs.json').read_text(encoding='utf-8'))
        if pins['fixture_sha256']!=sha(DATA/(name+'.wav')):
            raise ValueError('Audio hash mismatch for '+name)
        preview=load(folder/'revised-fast.tsv')
        final=load(folder/'incremental-offline.tsv')
        fused,info=fuse(final,preview,'preview-first')
        dump(fused,folder/'preview-first.tsv')
        (folder/'fusion-metadata.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        # Only now load the reference; no tuning/hyperparameters based on it.
        duration,ref=reference_for(name,n)
        scored={key:score(ref,turns,duration) for key,turns in
                [('original-fast',load(folder/'fast.tsv')),
                 ('revised-fast',preview),('production-final',final),('preview-first-candidate',fused)]}
        report=dict(recording=name,speakers=n,selection_sha256=sha(selection_file),
            candidate_source_sha256=sha(CODE),
            fixture_sha256=sha(DATA/(name+'.wav')),
            rttm_sha256=sha(DATA/(name+'.rttm')),
            flac_sha256=sha(DATA/(name+'.flac')),
            collar_radius_ms=250,scope='HOST_ONLY_RUSSIAN_AUDIOBOOK_SYNTHETIC_RTTM_HOLDOUT',
            wer='NOT_SCORED_NO_TEXT_REFERENCE',
            results=scored,policy='PREVIEW_FIRST_WITH_FINAL_FILL')
        (folder/'holdout-score.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        rows.append(report)
        print('SCORE',name,
              {k:round(v['der']['rate']*100,3) for k,v in scored.items()},flush=True)
    before=sum(x['results']['production-final']['der']['miss_ms']+
               x['results']['production-final']['der']['false_alarm_ms']+
               x['results']['production-final']['der']['confusion_ms'] for x in rows)
    after=sum(x['results']['preview-first-candidate']['der']['miss_ms']+
              x['results']['preview-first-candidate']['der']['false_alarm_ms']+
              x['results']['preview-first-candidate']['der']['confusion_ms'] for x in rows)
    ref_time=sum(x['results']['production-final']['der']['reference_speaker_ms'] for x in rows)
    deterioration=[(x['recording'],
        (x['results']['preview-first-candidate']['der']['rate']-
         x['results']['production-final']['der']['rate'])*100) for x in rows]
    gate=(after<before and all(delta<=2 for _,delta in deterioration) and all(
        r['results']['preview-first-candidate']['predicted_speakers']==r['speakers'] for r in rows))
    aggregate=dict(status='GO_FOR_ANDROID_EXPERIMENT_ONLY' if gate else 'NO_GO',
        total_reference_speaker_ms=ref_time,production_errors_ms=before,candidate_errors_ms=after,
        production_der=before/ref_time,candidate_der=after/ref_time,
        relative_error_reduction=(before-after)/before if before else None,
        max_per_file_der_deterioration_pp=max(x[1] for x in deterioration),
        all_speaker_counts_match=all(r['results']['preview-first-candidate']['predicted_speakers']==r['speakers'] for r in rows),
        held_out=6,blinded_candidate_source_sha256=SOURCE_SHA)
    (OUT/'comparison.json').write_text(json.dumps(dict(summary=aggregate,records=rows),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('GATE',json.dumps(aggregate,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
