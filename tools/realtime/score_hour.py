"""One-hour periodic synthetic stress scores; never independent hour-long speech evidence."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from score_transcript import der
from architecture_summary import stability

base=ROOT/'docs/evidence/architecture-20261106'
ref=json.loads(Path('C:/Users/user/Documents/nuclear-neurostenographer/.local/synthetic-ru/syn3-clean.reference.json').read_text(encoding='utf-8'))
duration=3600000
period_samples=536119
reference=[]
for repeat in range((duration*16+period_samples-1)//period_samples):
    for t in ref['diarization']:
        start=repeat*period_samples//16+t['start_ms']
        end=min(duration,repeat*period_samples//16+t['end_ms'],(repeat+1)*period_samples//16)
        if end>start: reference.append(dict(start_ms=start,end_ms=end,speaker_id=t['speaker_id']))
results={}
for folder,name in [('hour','baseline-fast-60min'),('hour','revised-fast-60min'),('hour','final-offline-60min'),('hour-final','selected-final-60min')]:
    path=base/folder/(name+'.tsv')
    if not path.exists(): results[name]={'status':'NOT_COMPLETED'}; continue
    turns=[]
    for line in path.read_text().splitlines():
        start,end,speaker=line.split('\t')
        turns.append(dict(start_ms=int(start),end_ms=int(end),speaker_id=speaker))
    results[name]=dict(der=der(reference,turns,duration,250,False),identity=stability(dict(diarization=reference),turns),
        runtime=json.loads(path.with_suffix('.json').read_text()),cost=json.loads(path.with_name(name+'-cost.json').read_text()))
(base/'hour-comparison.json').write_text(json.dumps(dict(scope='PERIODIC_SYNTHETIC_NATIVE_WINDOWS_C2_ONE_HOUR_NOT_PHONE_NOT_ASR',results=results),indent=2))
for name,r in results.items(): print(name,r.get('der',{}).get('rate'),r.get('status'),r.get('runtime',{}).get('speakers'))
