"""One-shot frozen speed candidate check on six audiobook RTTM files.

This selection was previously used for consensus evaluation. It was not used
to select FAST chunk size in the present speed investigation. It is not a
pristine holdout from every previous project experiment.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from score_transcript import der
from speaker_consensus import load
from evaluate_ru_book_holdout import reference_for

SRC=ROOT/'.local/ru-book-mix-holdout'
OUT=ROOT/'docs/evidence/speed-holdout-20261106'
SOURCE=ROOT/'tools/realtime/HostStreaming.kt'
POLICY='FAST_FIRST_3_CHUNKS_45_THEN_CHUNK72_EXACT_INDEPENDENT_SIX_RECORDINGS'
SEED='NN-C2-PREVIEW-FIRST-HOLDOUT-20261106-V1'
MODES=('fast-late-baseline','fast-late-72-3')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    cohort=json.loads((SRC/'frozen-selection.json').read_text(encoding='utf-8'))
    assert len(cohort['records'])==6 and cohort['seed']==SEED
    candidates=cohort['records']
    assert sorted([r['n_speakers'] for r in candidates])==[2,2,3,3,4,4]
    if any(not item['speaker_disjoint'] for item in candidates):
        raise AssertionError('Expected disjoint holdout speaker IDs')
    pin=sha(SOURCE)
    OUT.mkdir(parents=True,exist_ok=True)
    rows=[]
    for rec in candidates:
        name=rec['file_id'];n=rec['n_speakers']
        folder=OUT/name
        wav=SRC/(name+'.wav');gold=SRC/(name+'.rttm')
        if not folder.exists():
            subprocess.run([sys.executable,'-X','utf8',str(ROOT/'tools/realtime/host.py'),
                '--late-holdout','--fixture',str(wav),'--out',str(folder)],cwd=ROOT,check=True)
        if sha(SOURCE)!=pin:raise RuntimeError('Inference source changed during benchmark')
        inp=json.loads((folder/'inputs.json').read_text(encoding='utf-8'))
        assert inp['fixture_sha256']==sha(wav)
        duration,reference=reference_for(name,n)
        scores={}
        for mode in MODES:
            turns=load(folder/(mode+'.tsv'))
            hyp=[dict(start_ms=a,end_ms=min(b,duration),speaker_id=str(s)) for a,b,s in turns
                 if a<duration and b>a and min(b,duration)>a]
            d=der(reference,hyp,duration,250,False)
            cost=json.loads((folder/(mode+'-cost.json')).read_text(encoding='utf-8'))
            scores[mode]=dict(der=d['rate'],miss_ms=d['miss_ms'],
                confusion_ms=d['confusion_ms'],false_alarm_ms=d['false_alarm_ms'],
                reference_speaker_ms=d['reference_speaker_ms'],
                speakers=len(set(x['speaker_id'] for x in hyp)),
                host_compute_rtf=cost['compute_rtf'],host_cpu_ms=cost['cpu_ms'])
        row=dict(id=name,voices=n,wav_sha256=sha(wav),rttm_sha256=sha(gold),scores=scores)
        rows.append(row)
        print(name,'DER',round(scores[MODES[0]]['der']*100,3),'->',
              round(scores[MODES[1]]['der']*100,3),
              'host RTF',round(scores[MODES[0]]['host_compute_rtf'],4),'->',
              round(scores[MODES[1]]['host_compute_rtf'],4),flush=True)
    def errors(which):
        return sum(row['scores'][which]['miss_ms']+row['scores'][which]['confusion_ms']+
                   row['scores'][which]['false_alarm_ms'] for row in rows)
    ref_ms=sum(row['scores'][MODES[0]]['reference_speaker_ms'] for row in rows)
    old=errors(MODES[0]);new=errors(MODES[1])
    ratios=[row['scores'][MODES[1]]['host_compute_rtf']/row['scores'][MODES[0]]['host_compute_rtf'] for row in rows]
    deltas=[(row['scores'][MODES[1]]['der']-row['scores'][MODES[0]]['der'])*100 for row in rows]
    gate=(new/ref_ms<=old/ref_ms+0.002 and max(deltas)<=0.5 and
        max(ratios)<0.8 and all(row['scores'][MODES[1]]['speakers']==row['voices'] for row in rows))
    result=dict(scope='HOST_ONLY_FROZEN_SPEED_CANDIDATE_ON_PREVIOUS_CONSENSUS_HOLDOUT',
        selection_sha256=sha(SRC/'frozen-selection.json'),source_sha256=pin,
        policy=POLICY,cohort=rows,
        summary=dict(holdout_count=len(rows),reference_speaker_ms=ref_ms,
            baseline_der=old/ref_ms,candidate_der=new/ref_ms,
            average_host_speedup_pct=(1-sum(ratios)/len(ratios))*100,
            worst_der_regression_pp=max(deltas),max_host_rtf_ratio=max(ratios),
            gate='GO_FOR_DEVICE_EXPERIMENT' if gate else 'NO_GO'),
        notes=['Host-only synthetic audiobook data; cannot establish Android energy or latency',
               'Selection had already been used in consensus project, not untouched project holdout',
               'Synthetic mixing does not simulate spontaneous conversational diarization'])
    (OUT/'comparison.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('HOLDOUT_RESULT',json.dumps(result['summary']),flush=True)
if __name__=='__main__':main()
