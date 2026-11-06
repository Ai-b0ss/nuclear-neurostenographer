"""Reproducible OFFLINE C2 evaluation on three disjoint test files with NIST RTTM.

Uses the public preselected rec_0150/0300/0437 (2/3/4 voices), not in training.
The original FLAC audio is under .local (never committed); reports refer to
pinned SHA-256 and contain independent RTTM labels. No ASR word gold exists.
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
DATA=ROOT/'.local/ru-book-mix-eval'
OUT=ROOT/'docs/evidence/ru-book-eval-20261106'
NAMES=['rec_0150','rec_0300','rec_0437']

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(65536),b''):h.update(b)
    return h.hexdigest()

def rttm_reference(name, expected):
    wav=DATA/(name+'.wav')
    rttm=DATA/(name+'.rttm')
    with wave.open(str(wav),'rb') as f:
        if (f.getframerate(),f.getnchannels(),f.getsampwidth()) != (16000,1,2):
            raise ValueError('Bad wav type')
        duration=f.getnframes()*1000//16000
    turns=[]
    for idx,line in enumerate(rttm.read_text(encoding='utf-8').splitlines(),1):
        fields=line.split()
        if not fields:continue
        if len(fields)<9 or fields[0] != 'SPEAKER':
            raise ValueError('Unexpected RTTM row '+str(idx))
        start=round(float(fields[3])*1000)
        end=min(duration,round((float(fields[3])+float(fields[4]))*1000))
        if end>start: turns.append(dict(start_ms=start,end_ms=end,speaker_id=fields[7]))
    if len(set(r['speaker_id'] for r in turns))!=expected:
        raise ValueError('Speaker count differs from manifest')
    return dict(schema_version=1,recording_id=name,audio_duration_ms=duration,
        audio_sha256=sha(wav),annotation_source='mexus/ru-book-mix-10h NIST RTTM',
        kind='SYNTHETIC_RUSSIAN_AUDIOBOOK_MIX_NOT_CONVERSATION',
        license='CC-BY-4.0',diarization=turns)

def main():
    selection=json.loads((DATA/'selection.json').read_text(encoding='utf-8'))
    meta={r['name']:r for r in selection['records']}
    OUT.mkdir(parents=True,exist_ok=True)
    reports=[]
    for name in NAMES:
        expected=meta[name]['speakers']
        reference=rttm_reference(name,expected)
        case=OUT/name
        if not case.exists():
            command=[sys.executable,'-X','utf8',str(ROOT/'tools/realtime/host.py'),
                     '--fixture',str(DATA/(name+'.wav')),'--out',str(case)]
            print('INFER',name,flush=True)
            subprocess.run(command,cwd=ROOT,check=True)
        if not (case/'inputs.json').is_file():
            raise ValueError('Missing native inference results')
        pins=json.loads((case/'inputs.json').read_text(encoding='utf-8'))
        if pins['fixture_sha256']!=reference['audio_sha256']:
            raise ValueError('Model fixture mismatch')
        (case/'reference.json').write_text(json.dumps(reference,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        command=[sys.executable,'-X','utf8',str(ROOT/'tools/realtime/score_host.py'),
                 str(case),str(case/'reference.json')]
        result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
        print('SCORE',name,result.returncode,result.stdout.strip(),flush=True)
        # score_host returns 1 when FAST speaker count fails, not a harness failure.
        if result.returncode not in (0,1) or not (case/'scores.json').is_file():
            raise RuntimeError(result.stdout+'\n'+result.stderr)
        scores=json.loads((case/'scores.json').read_text(encoding='utf-8'))['results']
        reports.append(dict(name=name,reference_speakers=expected,
            reference_rttm_sha256=meta[name]['rttm_sha256'],
            source_flac_sha256=meta[name]['flac_sha256'],
            audio_wav_sha256=reference['audio_sha256'],
            clip_duration_ms=reference['audio_duration_ms'],
            results={k:dict(speakers=v['speakers'],der=v['der']) for k,v in scores.items()
                if k in ('fast','revised-fast','incremental-offline')},
            scope='HOST_NATIVE_NEMOTRON_C2_RTTM_NOT_PHONE_NOT_NATURAL_CONVERSATION',
            wer='NOT_SCORED_NO_WORD_GOLD'))
    (OUT/'comparison.json').write_text(json.dumps(dict(dataset_url=selection['dataset_url'],
        license=selection['source_license'],attribution=selection['attribution'],
        evaluation_only=True,not_training=True,files=reports),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('COMPLETE',len(reports),'RTTM cases',flush=True)

if __name__=='__main__':main()
