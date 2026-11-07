"""Independent A/B control of opt-in C2 chunk acceleration on physical ARM64."""
from pathlib import Path
import json,hashlib,sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from score_transcript import words
from verify_transcript_exports import verify

BEFORE=ROOT/'docs/evidence/consensus-phone-20261106'
AFTER=ROOT/'docs/evidence/late72-phone-20261106'
PAIRS=[
    ('rec_0437','consensus-4voice','late72-4voice'),
    ('rec_0300','consensus-3voice','late72-3voice'),
    ('rec_0150','consensus-2voice','late72-2voice'),
    ('veche-2-one-to-one',None,'late72-veche2'),
    ('veche-3-auth-incident',None,'late72-veche3')
]

def data(folder,name):
    return json.loads((folder/name).read_text(encoding='utf-8'))
def digest(document):
    normalized=[word for segment in document['segments'] for word in words(segment['text'])]
    return len(normalized),hashlib.sha256(' '.join(normalized).encode()).hexdigest()

def main():
    results=[]
    for clip,ref,candidate in PAIRS:
        new=AFTER/candidate
        if not (new/'run.json').exists():
            print('NOT_RUN',candidate)
            continue
        old=(BEFORE/ref if ref else ROOT/'docs/evidence/veche-phone-20261106'/(
            'veche2-consensus' if clip=='veche-2-one-to-one' else 'veche3-consensus'))
        if not (old/'run.json').exists():
            print('BASELINE_NOT_RUN',clip)
            continue
        before=data(old,'metrics.json');after=data(new,'metrics.json')
        olddoc=data(old,'transcript.json');newdoc=data(new,'transcript.json')
        oldrun=data(old,'run.json');newrun=data(new,'run.json')
        assert oldrun['status']==newrun['status']=='PASS'
        assert before['fixture_sha256']==after['fixture_sha256']
        assert before['runtime_sha256']==after['runtime_sha256']
        assert before['captured_wav_sha256']==after['captured_wav_sha256']
        assert not before.get('c2_chunk72_after3_experimental',False)
        assert after['c2_chunk72_after3_experimental']
        assert after['consensus_experimental']
        assert len(after['diarization_steps'])<len(before['diarization_steps'])
        assert all(x['chunk']==45 for x in after['diarization_steps'][:3])
        assert any(x['chunk']==72 for x in after['diarization_steps'][3:])
        assert after['finalization_state']==before['finalization_state']=='COMPLETE'
        original=digest(olddoc);newtext=digest(newdoc)
        assert original==newtext, 'A3 text mismatch on '+clip
        verify(new,'transcript')
        oldscore=data(old,'independent-score.json');newscore=data(new,'independent-score.json')
        assert oldscore['der']['status']==newscore['der']['status']=='SCORED'
        assert oldscore['wer']['status']==newscore['wer']['status'] or clip.startswith('veche')
        result=dict(clip=clip,baseline=old.name,experiment=new.name,
            wav_sha256=after['fixture_sha256'],token_count=newtext[0],
            tokens_sha256=newtext[1],voice_count=len({x['speaker_id'] for x in newdoc['segments'] if x['speaker_id']}),
            der_before=oldscore['der']['rate'],der_after=newscore['der']['rate'],
            compute_rtf_before=before['compute_rtf'],compute_rtf_after=after['compute_rtf'],
            c2_ms_before=before['c2_ms'],c2_ms_after=after['c2_ms'],
            first_diar_step_ms_before=before['diarization_steps'][0]['at_ms'],
            first_diar_step_ms_after=after['diarization_steps'][0]['at_ms'],
            asr_ms_before=before['asr_ms'],asr_ms_after=after['asr_ms'],
            finalization_ms_before=before['finalization_ms'],
            finalization_ms_after=after['finalization_ms'],
            words_preserved=True,exports_consistent=True)
        results.append(result)
        print('SCORED',clip,'DER',round(result['der_before']*100,3),'->',round(result['der_after']*100,3),
            'RTF',round(result['compute_rtf_before'],3),'->',round(result['compute_rtf_after'],3),
            'words',result['token_count'],flush=True)
    # A separate run with BOTH experimental switches off is an essential regression gate.
    off=AFTER/'late72-default-off-4voice'
    off_result={'status':'NOT_RUN'}
    if (off/'run.json').is_file():
        old=ROOT/'docs/evidence/consensus-phone-20261106/default-4voice'
        assert data(off,'run.json')['status']=='PASS'
        baseline=data(old,'metrics.json'); now=data(off,'metrics.json')
        assert now['fixture_sha256']==baseline['fixture_sha256']
        assert now['captured_wav_sha256']==baseline['captured_wav_sha256']
        assert now['runtime_sha256']==baseline['runtime_sha256']
        assert now['c2_chunk72_after3_experimental'] is False
        assert now['consensus_experimental'] is False
        assert now['finalization_state']=='COMPLETE'
        assert all(x['chunk']==45 for x in now['diarization_steps'])
        orig=data(old,'independent-score.json')['der']
        after=data(off,'independent-score.json')['der']
        assert orig['rate']==after['rate'] and orig['miss_ms']==after['miss_ms'] and orig['confusion_ms']==after['confusion_ms']
        assert digest(data(old,'transcript.json'))==digest(data(off,'transcript.json'))
        assert 'global-offline-final' in data(off,'transcript.json')['provenance']['speaker_source']
        verify(off,'transcript')
        off_result=dict(status='PASS',baseline=old.name,experiment=off.name,
                        der=after['rate'],words_preserved=True,default_mode_unchanged=True,
                        compute_rtf=now['compute_rtf'])
    # Independent repeat of the exact clip + pinned model after a quality regression.
    repeat_path=AFTER/'veche3-recheck'
    repeat={'status':'NOT_RUN'}
    if (repeat_path/'run.json').is_file():
        original_path=AFTER/'late72-veche3'
        original=data(original_path,'metrics.json')
        another=data(repeat_path,'metrics.json')
        assert data(repeat_path,'run.json')['status']=='PASS'
        for field in ('fixture_sha256','runtime_sha256','captured_wav_sha256'):
            assert original[field]==another[field],field
        assert another['consensus_experimental'] and another['c2_chunk72_after3_experimental']
        assert len(another['diarization_steps'])==len(original['diarization_steps'])
        assert digest(data(repeat_path,'transcript.json'))==digest(data(original_path,'transcript.json'))
        refder=data(original_path,'independent-score.json')['der']
        der2=data(repeat_path,'independent-score.json')['der']
        assert refder['rate']==der2['rate']
        assert refder['miss_ms']==der2['miss_ms']
        verify(repeat_path,'transcript')
        repeat=dict(status='PASS',clip='veche-3-auth-incident',
            repeated_der=der2['rate'],repeated_miss_ms=der2['miss_ms'],
            repeated_rtf=another['compute_rtf'],same_fixture_runtime_tokens_and_der=True)
    all_under_one=all(row['compute_rtf_after']<1 for row in results)
    max_der_regression_pp=max(((row['der_after']-row['der_before'])*100 for row in results),default=None)
    # Quality gate forbids default rollout when *any* human-speech
    # recording has a repeatable absolute DER deterioration >0.2 pp.
    quality_ok=all((row['der_after']-row['der_before'])*100<=0.2
                   for row in results if row['clip'].startswith('veche'))
    gate=dict(quality_gate='PASS' if quality_ok else 'FAIL',
        performance_gate='PASS' if len(results)==5 and all_under_one else 'INCOMPLETE_OR_FAIL',
        max_case_der_deterioration_pp=max_der_regression_pp,
        production_rollout='NO_GO_KEEP_EXPERIMENTAL')
    report=dict(scope='PHYSICAL_HONOR_PACED_16K_OFFLINE_EXPERIMENTAL_CHUNK72_AFTER3',cases=results,
        repeatability_control=repeat,gate=gate,
        default_mode_regression=off_result,
        control='default unchanged; preview first three chunks 45, later chunks 72',
        target_rtf_max=1.0,
        wer_status='NOT_SCORED_FOR_RTTM_BOOK_MIX',
        production_rollout='DISABLED_BY_DEFAULT')
    (AFTER/'ab-comparison.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('COMPARED',len(results),'cases',flush=True)

if __name__=='__main__':main()
