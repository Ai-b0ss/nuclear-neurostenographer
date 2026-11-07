"""Evaluate anonymous scripted human Russian meetings end-to-end on a real phone.

Assess WER, cpWER (only if attributable), DER with 250-ms collar,
identical PCM and model hash, export consistency, token preservation.
Ground-truth text stays in .local, only numeric scores in committed evidence.
"""
import json
import hashlib
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from score_transcript import words
from verify_transcript_exports import verify
from analyze import analyze

DATA=ROOT/'.local/veche-eval'
PHONE=ROOT/'docs/evidence/veche-phone-20261106'
OUT=ROOT/'docs/evidence/veche-eval-20261106'
CASES=[('2-one-to-one','veche2-default','veche2-consensus'),
       ('3-auth-incident','veche3-default','veche3-consensus')]

def load(path):
    return json.loads(path.read_text(encoding='utf-8'))

def digest(document):
    tokens=[t for s in document['segments'] for t in words(s['text'])]
    return len(tokens),hashlib.sha256(' '.join(tokens).encode()).hexdigest()

def main():
    # The only fixture references used are explicit, anonymized copied gold.
    for name,_,_ in CASES:
        source=DATA/('veche-'+name)/'reference.json'
        dest=DATA/('veche-'+name+'.reference.json')
        data=source.read_bytes()
        if dest.is_file() and dest.read_bytes()!=data:
            raise RuntimeError('Reference drift '+name)
        dest.write_bytes(data)
    outcomes=[]
    for name,baseline,candidate in CASES:
        b=PHONE/baseline
        e=PHONE/candidate
        if not e.joinpath('run.json').exists() or not b.joinpath('run.json').exists():
            print(name,'NOT_YET_RUN',flush=True);continue
        for path in (b,e):
            run=load(path/'run.json')
            if run['status']!='PASS':raise RuntimeError('Device failure '+str(path))
            score_path=path/'independent-score.json'
            analyzed=analyze(path,DATA)
            if not score_path.is_file():raise RuntimeError('Independent scoring absent '+str(path))
            if analyzed.get('der',{}).get('status')!='SCORED':
                raise RuntimeError('DER not scored '+str(path))
            verify(path,'transcript')
        bm=load(b/'metrics.json')
        em=load(e/'metrics.json')
        bd=load(b/'transcript.json')
        ed=load(e/'transcript.json')
        s1=load(b/'independent-score.json')
        s2=load(e/'independent-score.json')
        assert bm['fixture_sha256']==em['fixture_sha256']
        assert bm['captured_wav_sha256']==em['captured_wav_sha256']
        assert bm['runtime_sha256']==em['runtime_sha256']
        assert bm['consensus_experimental'] is False
        assert em['consensus_experimental'] is True
        assert digest(bd)==digest(ed), 'Token sequence changed '+name
        n=len({t['speaker_id'] for t in ed['segments'] if t['speaker_id'] is not None})
        reference=load(DATA/('veche-'+name)/'reference.json')
        expected=len({x['speaker_id'] for x in reference['diarization']})
        if n!=expected:print('SPEAKER COUNT FAILED',name,n,expected,flush=True)
        row=dict(clip='veche-'+name,source='PUBLIC_VOLUNTEERS_READING_SCRIPTED_RUSSIAN_MEETING',
            audio_sha256=bm['fixture_sha256'],
            reference_sha256=hashlib.sha256((DATA/('veche-'+name)/'reference.json').read_bytes()).hexdigest(),
            speakers_ref=expected,speakers_final=n,
            tokens=digest(bd)[0],tokens_identical=True,
            old_der=s1['der'],new_der=s2['der'],
            old_wer=s1['wer'],new_wer=s2['wer'],
            old_cpwer=s1['cpwer'],new_cpwer=s2['cpwer'],
            old_compute_rtf=bm['compute_rtf'],new_compute_rtf=em['compute_rtf'],
            memory_sampled_pss_kb=em['sampled_pss_kb'],
            experimental_disagreement_ms=em['speaker_disagreement_ms'],
            experimental_fill_ms=em['speaker_offline_fill_ms'],
            notes='RTTM derived from human CSV utterance timestamps; no word-level acoustic alignment gold')
        outcomes.append(row)
        print('SCORED',name,
            'DER',round(s1['der']['rate']*100,2),'->',round(s2['der']['rate']*100,2),
            'WER',round(s1['wer']['rate']*100,2) if s1['wer']['rate'] is not None else None,
            'cpWER',s1['cpwer'].get('status'),s2['cpwer'].get('status'),
            'voices',n,'tokens',row['tokens'],flush=True)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'device-comparison.json').write_text(json.dumps(outcomes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('COMPARISON',len(outcomes),'records',flush=True)
if __name__=='__main__':main()
