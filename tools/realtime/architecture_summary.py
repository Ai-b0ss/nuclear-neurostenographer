"""Summarize artifacts without filling missing tests or claiming natural-dialogue accuracy."""
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
sys.path.insert(0,str(ROOT/'tools/realtime'))
from analyze import analyze
from score_transcript import words
from verify_transcript_exports import verify

BASE=ROOT/'docs/evidence/architecture-20261106'
SYN=Path('C:/Users/user/Documents/nuclear-neurostenographer/.local/synthetic-ru')
DERIVED=ROOT/'docs/evidence/realtime-honor-20261105/fixture-references'


def stability(reference, turns):
    voices={}
    for r in reference.get('diarization', []):
        scores={}
        for h in turns:
            overlap=max(0,min(r['end_ms'],h['end_ms'])-max(r['start_ms'],h['start_ms']))
            scores[h['speaker_id']]=scores.get(h['speaker_id'],0)+overlap
        dominant=max(scores,key=scores.get) if scores and max(scores.values())>0 else None
        voices.setdefault(r['speaker_id'],[]).append(dominant)
    return dict(dominant_ids_by_reference_voice=voices,
        reference_voices_with_multiple_dominant_ids=sum(len(set(v)-{None})>1 for v in voices.values()),
        missing_reference_turns=sum(x is None for v in voices.values() for x in v),
        scope='COARSE_REFERENCE_TURN_DOMINANCE_NOT_FRAME_ACCURACY')

def matched_word_attribution(reference, segments, mapping):
    refs=reference.get('text_segments', [])
    if any(a['speaker_id']!=b['speaker_id'] and max(a['start_ms'],b['start_ms'])<min(a['end_ms'],b['end_ms'])
           for i,a in enumerate(refs) for b in refs[i+1:]):
        return dict(status='NOT_SCORED',reason='Overlapping reference word order is ambiguous')
    r=[(w,t['speaker_id']) for t in sorted(refs,key=lambda t:t['start_ms']) for w in words(t['text'])]
    h=[(w,t['speaker_id']) for t in segments for w in words(t['text'])]
    if not r: return dict(status='NOT_SCORED',reason='No text reference')
    dp=[[0]*(len(h)+1) for _ in range(len(r)+1)]
    for i in range(len(r)+1): dp[i][0]=i
    for j in range(len(h)+1): dp[0][j]=j
    for i in range(1,len(r)+1):
        for j in range(1,len(h)+1):
            dp[i][j]=min(dp[i-1][j-1]+(r[i-1][0]!=h[j-1][0]),dp[i-1][j]+1,dp[i][j-1]+1)
    i,j=len(r),len(h); matched=wrong=unknown=0
    while i or j:
        if i and j and dp[i][j]==dp[i-1][j-1]+(r[i-1][0]!=h[j-1][0]):
            if r[i-1][0]==h[j-1][0]:
                matched+=1
                if h[j-1][1] is None: unknown+=1
                elif mapping.get(h[j-1][1])!=r[i-1][1]: wrong+=1
            i-=1; j-=1
        elif i and dp[i][j]==dp[i-1][j]+1: i-=1
        else: j-=1
    return dict(status='SCORED',exact_lexical_matches=matched,wrong_speaker=wrong,unknown_speaker=unknown,
        scope='LEXICAL_DP_MATCHES_ONLY_GLOBAL_DER_ID_MAPPING_NO_WORD_TIME_GOLD',
        errors_including_unknown=wrong+unknown,rate=(wrong+unknown)/matched if matched else None)

def main():
    host=[]
    for folder in sorted(BASE.iterdir()):
        if not (folder/'scores.json').exists(): continue
        data=json.loads((folder/'scores.json').read_text())['results']
        host.append(dict(fixture=folder.name, baseline=data['fast'], live=data['revised-fast'], final=data['incremental-offline']))
    phone=[]; checks=[]
    for group in ['phone-baseline','phone-new','phone-final','phone-verified']:
        for folder in sorted((BASE/group).iterdir()):
            if not folder.is_dir() or not (folder/'run.json').exists(): continue
            run=json.loads((folder/'run.json').read_text())
            checks.append(dict(group=group, run=folder.name, **run))
            if not (folder/'metrics.json').exists(): continue
            metrics=json.loads((folder/'metrics.json').read_text())
            ref=SYN if metrics['clip'].startswith('syn') else DERIVED
            row=analyze(folder,ref)
            row['group']=group
            reference=ref/(metrics['clip']+'.reference.json')
            if reference.exists(): row['identity_stability']=stability(json.loads(reference.read_text(encoding='utf-8')),metrics['diarization_turns'])
            row.update({k:metrics.get(k) for k in ['finalization_ms','finalization_state','revised_frames']})
            segments=json.loads((folder/'transcript.json').read_text(encoding='utf-8'))['segments']
            if reference.exists() and row.get('der',{}).get('hypothesis_to_reference'):
                row['matched_word_attribution']=matched_word_attribution(json.loads(reference.read_text(encoding='utf-8')),segments,row['der']['hypothesis_to_reference'])
            row['words']=sum(len(s['text'].split()) for s in segments)
            row['unknown_words']=sum(len(s['text'].split()) for s in segments if s['speaker_id'] is None)
            row['overlap_segments']=sum(s['overlapping_speech'] for s in segments)
            if segments:
                try: verify(folder,'transcript'); row['export_consistency']='PASS'
                except Exception as exc: row['export_consistency']='FAIL: '+str(exc)
            else: row['export_consistency']='EMPTY_SILENCE'
            phone.append(row)
    report=dict(scope='SYNTHETIC_TTS_AND_AUTHORED_TESTS_NOT_NATURAL_CONVERSATION_GOLD',host=host,phone=phone,instrumentation=checks)
    (BASE/'comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('host fixtures',len(host),'phone inference runs',len(phone),'instrumentation',len(checks))
    for r in phone:
        print(r['group'],r['run'],r['speakers'],r['unknown_words'],r.get('der',{}).get('rate'),r['export_consistency'])

if __name__=='__main__': main()
