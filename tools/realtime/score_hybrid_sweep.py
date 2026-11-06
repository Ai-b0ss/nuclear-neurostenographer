"""Score optional FAST cache variants against frozen RTTM development examples.

Host-only RTF is NOT a phone speed claim.
C2 source accuracy/cost is evaluated AFTER writing its predictions to disk.
"""
import argparse, json, hashlib, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from score_transcript import der
from score_clip_run import clamp_reference

MODES=['fast-hybrid-45','fast-hybrid-60','fast-hybrid-72','fast-hybrid-90']

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--folder',type=Path,required=True)
    p.add_argument('--reference',type=Path,required=True)
    a=p.parse_args()
    ref=clamp_reference(json.loads(a.reference.read_text(encoding='utf-8')))
    params=json.loads((a.folder/'inputs.json').read_text(encoding='utf-8'))
    if params['fixture_sha256']!=ref['audio_sha256']:
        raise ValueError('Wrong WAV/reference SHA')
    result=[]
    for m in MODES:
        turns=[]
        for idx,line in enumerate((a.folder/(m+'.tsv')).read_text(encoding='utf-8').splitlines(),1):
            s,e,who=line.split('\t')
            s,e=int(s),min(int(e),ref['audio_duration_ms'])
            if not (0<=s<e and who):raise ValueError('invalid turn '+str(idx))
            turns.append(dict(start_ms=s,end_ms=e,speaker_id=who))
        score=der(ref['diarization'],turns,ref['audio_duration_ms'],250,False)
        profile=json.loads((a.folder/(m+'-cost.json')).read_text(encoding='utf-8'))
        result.append(dict(mode=m,der=score['rate'],miss_ms=score['miss_ms'],fa_ms=score['false_alarm_ms'],
            confusion_ms=score['confusion_ms'],speakers=len({t['speaker_id'] for t in turns}),
            host_compute_rtf=profile['compute_rtf'],host_cpu_ms=profile['cpu_ms'],
            wav_sha=ref['audio_sha256']))
        print(m,'DER',round(score['rate']*100,3),'HOST_RTF',round(profile['compute_rtf'],4),'speakers',result[-1]['speakers'],flush=True)
    (a.folder/'hybrid-scores.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
