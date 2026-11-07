"""Frame-level attribution of missed speech introduced by opt-in FAST45->72.

Reads independent public Veche annotation only AFTER reading the already-saved
C2 predictions. This is a diagnosis, not a classifier or a tuning input.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from error_atlas import audit

ROOT=Path(__file__).resolve().parents[2]
IN=ROOT/'.local/veche-eval/veche-3-auth-incident'
BASE=ROOT/'docs/evidence/veche-phone-20261106/veche3-consensus'
FAST=ROOT/'docs/evidence/late72-phone-20261106/late72-veche3'
REPEAT=ROOT/'docs/evidence/late72-phone-20261106/veche3-recheck'
OUT=ROOT/'docs/evidence/speed-regression-20261106'

def sha(path: Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def metric(folder:Path):
    return json.loads((folder/'metrics.json').read_text(encoding='utf-8'))

def turns_to_tsv(folder:Path,dest:Path):
    rows=metric(folder)['diarization_turns']
    dest.write_text(''.join(f"{r['start_ms']}\t{r['end_ms']}\t{r['speaker_id']}\n"
                            for r in rows if r['end_ms']>r['start_ms']),encoding='utf-8')
    return len(rows)

def deltas(base,after):
    before=base['per_reference'];candidate=after['per_reference']
    assert len(before)==len(candidate)
    changed=[]
    for b,a in zip(before,candidate):
        assert (b['reference_index'],b['speaker'],b['start_ms'],b['end_ms'])==(
            a['reference_index'],a['speaker'],a['start_ms'],a['end_ms'])
        if b['missed_ms'] != a['missed_ms']:
            changed.append(dict(reference_index=b['reference_index'],
                speaker=b['speaker'],start_ms=b['start_ms'],end_ms=b['end_ms'],
                baseline_missed_ms=b['missed_ms'],candidate_missed_ms=a['missed_ms'],
                delta_missed_ms=a['missed_ms']-b['missed_ms']))
    return sorted(changed,key=lambda r:-r['delta_missed_ms'])

def new_loss_intervals(base,after):
    b=base['frames'];a=after['frames']
    boundaries=sorted({v for row in b+a for v in (row['start_ms'],row['end_ms'])})
    i=j=0
    result=[]
    for start,end in zip(boundaries,boundaries[1:]):
        while i<len(b) and b[i]['end_ms']<=start:i+=1
        while j<len(a) and a[j]['end_ms']<=start:j+=1
        before=b[i] if i<len(b) and b[i]['start_ms']<=start<b[i]['end_ms'] else {}
        afterrow=a[j] if j<len(a) and a[j]['start_ms']<=start<a[j]['end_ms'] else {}
        extra=int(afterrow.get('miss_slots',0))-int(before.get('miss_slots',0))
        if extra<=0:continue
        region=dict(start_ms=start,end_ms=end,extra_missing_speaker_ms=(end-start)*extra,
                    reference=afterrow.get('reference',''),predicted=afterrow.get('predicted',''),
                    baseline_predicted=before.get('predicted',''),
                    dbfs=afterrow.get('dbfs'))
        if result and result[-1]['end_ms']==start and result[-1]['reference']==region['reference'] and (
                result[-1]['baseline_predicted'],result[-1]['predicted'])==(
                region['baseline_predicted'],region['predicted']):
            result[-1]['end_ms']=end
            result[-1]['extra_missing_speaker_ms']+=(end-start)*extra
            result[-1]['min_dbfs']=min(result[-1].get('min_dbfs',region['dbfs']),region['dbfs'])
            result[-1]['max_dbfs']=max(result[-1].get('max_dbfs',region['dbfs']),region['dbfs'])
        else:
            region['min_dbfs']=region['max_dbfs']=region['dbfs']
            result.append(region)
    return sorted(result,key=lambda row:-row['extra_missing_speaker_ms'])

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    wav=IN/'clip.wav'
    reference=IN/'reference.json'
    ref=json.loads(reference.read_text(encoding='utf-8'))
    metrics=[metric(x) for x in (BASE,FAST,REPEAT)]
    for m in metrics:
        assert m['fixture_sha256']==ref['audio_sha256']==sha(wav)
        assert m['runtime_sha256']==metrics[0]['runtime_sha256']
        assert m['captured_wav_sha256']==metrics[0]['captured_wav_sha256']
        assert m['finalization_state']=='COMPLETE' and m['state']=='COMPLETE'
    reports=[]
    for name,folder in (('baseline',BASE),('accelerated',FAST),('repeat',REPEAT)):
        tsv=OUT/(name+'.tsv')
        n=turns_to_tsv(folder,tsv)
        summary=audit(wav,reference,tsv,OUT/name)
        import csv
        frames=[]
        with (OUT/name/'frames.csv').open(encoding='utf-8',newline='') as stream:
            for row in csv.DictReader(stream):
                frames.append(dict(start_ms=int(row['start_ms']),end_ms=int(row['end_ms']),
                    miss_slots=int(row['miss_slots']),reference=row['reference'],
                    predicted=row['predicted'],dbfs=float(row['dbfs'])))
        reports.append(dict(turns=n,summary=summary,frames=frames))
    a,b,c=reports
    errors=lambda row:row['summary']['score']
    assert errors(b)['miss_ms']==errors(c)['miss_ms']==2308
    assert errors(a)['miss_ms']==2068
    assert errors(a)['confusion_ms']==errors(b)['confusion_ms']==0
    extra=new_loss_intervals(a,b)
    comparison=dict(scope='PUBLIC_SCRIPTED_RUSSIAN_HUMAN_VOICE_RTTM_DIFFERENTIAL',
        no_retraining_no_reference_in_inference=True,
        audio_sha256=sha(wav),reference_sha256=sha(reference),
        run_hashes={name:sha(folder/'metrics.json') for name,folder in (
            ('baseline',BASE),('accelerated',FAST),('repeat',REPEAT))},
        baseline=dict(score=errors(a),turns=a['turns']),
        accelerated=dict(score=errors(b),turns=b['turns']),
        repeated=dict(score=errors(c),turns=c['turns']),
        new_missed_regions=extra,
        per_reference_deltas=deltas(a['summary'],b['summary']),
        remarks=['Only energy is measured, not independently detected speech',
                 'No RTTM annotations were used to produce either model output',
                 'These are 10-ms RTTM scoring regions with +/-250 ms collar exclusions'])
    (OUT/'comparison.json').write_text(json.dumps(comparison,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('NEW_LOSS_REGIONS',len(extra),'TOP',extra[:8],flush=True)
    print('UTTERANCE_DIFF',comparison['per_reference_deltas'][:8],flush=True)
    print('ERROR_DIFFERENCE',errors(b)['miss_ms']-errors(a)['miss_ms'],flush=True)

if __name__=='__main__':main()
