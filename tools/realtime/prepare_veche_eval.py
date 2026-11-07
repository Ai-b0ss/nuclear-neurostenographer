"""Prepare two bounded public human-voiced Russian meetings for anonymous ASR/DER evaluation.

Source: artem-tish/veche-bench (CC-BY-4.0); scripted voluntary reading,
NOT spontaneous conversation. Never ingest speaker names, demographic fields,
biometric profiles or identities into exported benchmark results.
Download only two small medium-overlap files, not the 955-MB dataset.
"""
import csv
import hashlib
import json
import urllib.request
import wave
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
LOCAL=ROOT/'.local/veche-eval'
OUT=ROOT/'docs/evidence/veche-eval-20261106'
BASE='https://huggingface.co/datasets/artem-tish/veche-bench/resolve/main/data_medium/'
CASES=['2-one-to-one','3-auth-incident']

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as stream:
        for part in iter(lambda:stream.read(65536),b''):h.update(part)
    return h.hexdigest()

def download(url,target,limit):
    if target.is_file() and target.stat().st_size>100:
        print('REUSE',target.name,target.stat().st_size,flush=True)
        return
    target.parent.mkdir(parents=True,exist_ok=True)
    tmp=target.with_suffix(target.suffix+'.part')
    if tmp.exists():raise RuntimeError('Existing partial file; inspect '+str(tmp))
    print('DOWNLOAD',url,flush=True)
    total=0
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Neurostenographer-Eval/1.0'}),timeout=120) as response:
        with tmp.open('wb') as f:
            while True:
                chunk=response.read(65536)
                if not chunk:break
                total+=len(chunk)
                if total>limit:raise RuntimeError('Dataset resource exceeds size limit')
                f.write(chunk)
    if total<100:raise RuntimeError('Truncated or empty resource')
    tmp.rename(target)
    print('SAVED',target.name,total,sha(target),flush=True)

def main():
    LOCAL.mkdir(parents=True,exist_ok=True)
    OUT.mkdir(parents=True,exist_ok=True)
    inventory=[]
    for name in CASES:
        source=LOCAL/name
        source.mkdir(exist_ok=True)
        for ext,limit in [('csv',1_000_000),('wav',15_000_000)]:
            path=source/(name+'.'+ext)
            download(BASE+name+'/'+name+'.'+ext,path,limit)
        with (source/(name+'.csv')).open(encoding='utf-8-sig',newline='') as f:
            rows=list(csv.DictReader(f))
        assert rows and {'speaker_id','start','end','text'}<=set(rows[0])
        # Only anonymous cluster slots, not names, genders or role identities.
        turns=[]
        for item in rows:
            start=round(float(item['start'])*1000)
            end=round(float(item['end'])*1000)
            if not(0<=start<end):raise ValueError('Invalid CSV time')
            turns.append(dict(start_ms=start,end_ms=end,
                speaker_id='speaker_'+str(int(item['speaker_id'])),
                text=item['text'].strip()))
        with wave.open(str(source/(name+'.wav')),'rb') as w:
            if (w.getnchannels(),w.getsampwidth(),w.getframerate())!=(1,2,16000):
                raise ValueError('Unsupported WAV format for '+name)
            total_frames=w.getnframes()
            duration=total_frames//16
            # Find complete speech-unit boundary near 60s, not inside a turn.
            end_candidates=sorted(set(t['end_ms'] for t in turns if 40000<=t['end_ms']<=90000))
            boundaries=[e for e in end_candidates
                if not any(t['start_ms']<e<t['end_ms'] for t in turns)]
            if not boundaries:raise ValueError('No safe sentence break in 40-90s for '+name)
            stop=min(boundaries,key=lambda x:(abs(x-60000),x))
            if stop>duration:raise ValueError('Reference extends beyond audio')
            clip_frames=min(total_frames,stop*16)
            # End at a complete utterance plus up to 100ms silence. Do not include partial words.
            effective_ms=clip_frames//16
            clipped=[r for r in turns if r['start_ms']<effective_ms and r['end_ms']<=effective_ms]
            if any(r['start_ms']<effective_ms<r['end_ms'] for r in turns):
                raise ValueError('Truncated reference turn; reject unsafe clip')
            w.rewind()
            pcm=w.readframes(clip_frames)
        case=LOCAL/('veche-'+name)
        case.mkdir(exist_ok=True)
        wav=case/'clip.wav'
        with wave.open(str(wav),'wb') as out:
            out.setparams((1,2,16000,0,'NONE','not compressed'))
            out.writeframes(pcm)
        ref=dict(schema_version=1,recording_id='veche-'+name,
            audio_duration_ms=effective_ms,audio_sha256=sha(wav),
            annotation_source='artem-tish/veche-bench data_medium human-scripted CSV',
            license='CC-BY-4.0',
            kind='SCRIPTED_HUMAN_RUSSIAN_MEETING_WITH_OVERLAP_NOT_SPONTANEOUS',
            diarization=[{k:t[k] for k in ('start_ms','end_ms','speaker_id')} for t in clipped],
            text_segments=clipped)
        (case/'reference.json').write_text(json.dumps(ref,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        record=dict(case=name,clip_name='veche-'+name,
            clip_duration_ms=effective_ms,speakers=len({r['speaker_id'] for r in clipped}),
            utterances=len(clipped),
            ref_sha256=sha(case/'reference.json'),
            wav_sha256=sha(wav),
            source_wav_sha256=sha(source/(name+'.wav')),
            source_csv_sha256=sha(source/(name+'.csv')),
            dataset_url='https://huggingface.co/datasets/artem-tish/veche-bench',
            license='CC-BY-4.0',
            scope='HUMAN_VOLUNTEERS_READING_PREPARED_SCRIPTS_NOT_SPONTANEOUS')
        inventory.append(record)
        print('PREPARED',name,record['speakers'],'speakers',effective_ms,'ms',
            len(clipped),'utterances',flush=True)
    (OUT/'source-manifest.json').write_text(json.dumps(inventory,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('READY',len(inventory),'files')

if __name__=='__main__':main()
