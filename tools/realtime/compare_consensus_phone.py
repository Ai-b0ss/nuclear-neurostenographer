"""Audit device A/B results without copying user audio or exposing transcript text."""
from pathlib import Path
from hashlib import sha256
import json
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from score_transcript import words
from verify_transcript_exports import verify

BEFORE=ROOT/'docs/evidence/ru-book-phone-20261106'
AFTER=ROOT/'docs/evidence/consensus-phone-20261106'
CASES=[('rec_0150','rttm-2voice','consensus-2voice'),
       ('rec_0300','rttm-3voice-r2','consensus-3voice'),
       ('rec_0437','rttm-4voice','consensus-4voice')]

def read(folder,name):
    return json.loads((folder/name).read_text(encoding='utf-8'))

def token_hash(document):
    ordered=[w for row in document['segments'] for w in words(row['text'])]
    return len(ordered),sha256(' '.join(ordered).encode()).hexdigest()

def main():
    rows=[]
    for clip,b,c in CASES:
        old=BEFORE/b;new=AFTER/c
        oldrun=read(old,'run.json');newrun=read(new,'run.json')
        oldm=read(old,'metrics.json');newm=read(new,'metrics.json')
        oldscore=read(old,'independent-score.json')
        newscore=read(new,'independent-score.json')
        assert oldrun['status']==newrun['status']=='PASS'
        assert oldm['fixture_sha256']==newm['fixture_sha256']
        assert oldm['runtime_sha256']==newm['runtime_sha256']
        assert oldm['captured_wav_sha256']==newm['captured_wav_sha256']
        assert newrun['consensus_experimental'] is True
        assert newm['consensus_experimental'] is True
        assert oldscore['der']['status']==newscore['der']['status']=='SCORED'
        assert newscore['wer']['status']==newscore['cpwer']['status']=='NOT_SCORED'
        olddoc=read(old,'transcript.json');newdoc=read(new,'transcript.json')
        orig=token_hash(olddoc);cand=token_hash(newdoc)
        assert orig==cand,clip+' changed ASR word tokens'
        verify(new,'transcript')
        result=dict(clip=clip,baseline_run=b,candidate_run=c,
            audio_sha256=newm['fixture_sha256'],
            runtime_sha256=newm['runtime_sha256'],
            token_count=cand[0],normalized_token_sha256=cand[1],
            words_preserved=True,exports_consistent=True,
            speaker_count=len({s['speaker_id'] for s in newdoc['segments'] if s['speaker_id'] is not None}),
            before_der=oldscore['der']['rate'],after_der=newscore['der']['rate'],
            relative_der_improvement=(oldscore['der']['rate']-newscore['der']['rate'])/oldscore['der']['rate'],
            baseline_compute_rtf=oldm['compute_rtf'],experimental_compute_rtf=newm['compute_rtf'],
            experimental_finalization_ms=newm['finalization_ms'],
            experimental_disagreement_ms=newm['speaker_disagreement_ms'],
            experimental_offline_fill_ms=newm['speaker_offline_fill_ms'])
        rows.append(result)
        print(clip,'DER',round(result['before_der']*100,3),'->',round(result['after_der']*100,3),
            'tokens',cand[0],'PASS',flush=True)
    default=AFTER/'default-4voice'
    default_validation='NOT_RUN'
    if (default/'run.json').is_file():
        run=read(default,'run.json');metrics=read(default,'metrics.json')
        score=read(default,'independent-score.json')
        orig=read(BEFORE/'rttm-4voice','transcript.json')
        text=read(default,'transcript.json')
        assert run['status']=='PASS' and metrics['consensus_experimental'] is False
        assert token_hash(orig)==token_hash(text)
        assert metrics['fixture_sha256']==read(BEFORE/'rttm-4voice','metrics.json')['fixture_sha256']
        verify(default,'transcript')
        default_validation=dict(pass_status='PASS',before_der=read(BEFORE/'rttm-4voice','independent-score.json')['der']['rate'],
            after_der=score['der']['rate'],same_text=True,
            source=text['provenance']['speaker_source'])
    report=dict(scope='PHYSICAL_HONOR_ARM64_PACED_RTTM_SYNTHETIC_AUDIOBOOK',
        words_reference='NOT_SCORED_NO_WORD_GOLD',
        case_results=rows,default_mode_regression=default_validation,
        project_gate='EXPERIMENT_ONLY_NOT_PRODUCTION_READY',
        caveats=['Six recording host holdout relative DER improvement was only 2.18%, below 15% target',
                 'Device compute RTF above 1 on all three 60-second trials',
                 'No natural multi-speaker dialogue with independent word-time gold'])
    (AFTER/'ab-comparison.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('AUDIT_PASS',len(rows),'paired device recordings, default:',default_validation if isinstance(default_validation,str) else 'PASS')

if __name__=='__main__':main()
