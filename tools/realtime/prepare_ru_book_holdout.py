"""Deterministic blind quality holdout: 2 recordings for each of 2, 3, 4 voices.

Select solely from the corpus manifest (no audio/RTTM or C2 predictions).
Try disjoint audiobook speakers from the three development recordings.
The selection, SHA-256 and experiment policy are frozen before labels are read.
"""
import hashlib
import json
import os
import subprocess
import tarfile
from collections import defaultdict
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[2]
MANIFEST=ROOT/'.local/ru-book-mix-manifest.jsonl'
OUT=ROOT/'.local/ru-book-mix-holdout'
BASE='https://huggingface.co/datasets/mexus/ru-book-mix-10h/resolve/main/'
DEV={'rec_0150','rec_0300','rec_0437'}
SEED='NN-C2-PREVIEW-FIRST-HOLDOUT-20261106-V1'
REQUIRED={2:2,3:2,4:2}

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(65536),b''):h.update(block)
    return h.hexdigest()

def select(entries):
    dev_voices={voice for r in entries if r['file_id'] in DEV for voice in r['speakers'].values()}
    choice=[]
    for n,cnt in REQUIRED.items():
        pool=[r for r in entries if r['n_speakers']==n and r['file_id'] not in DEV]
        independent=[r for r in pool if not (set(r['speakers'].values()) & dev_voices)]
        if len(independent)<cnt:
            print('WARNING: insufficient speaker-disjoint entries for',n)
            pool=pool
        else:pool=independent
        pool.sort(key=lambda r:hashlib.sha256((SEED+r['file_id']).encode()).hexdigest())
        choice.extend(pool[:cnt])
    if len(choice)!=sum(REQUIRED.values()):
        raise RuntimeError('Insufficient recordings')
    return choice

def main():
    rows=[json.loads(s) for s in MANIFEST.read_text(encoding='utf-8').splitlines() if s]
    selected=select(rows)
    dev_voices={voice for r in rows if r['file_id'] in DEV for voice in r['speakers'].values()}
    OUT.mkdir(parents=True,exist_ok=True)
    manifest=dict(seed=SEED,scope='RUSSIAN_AUDIOBOOK_SYNTHETIC_BLIND_HOLDOUT_NOT_HUMAN_CONVERSATION',
        dataset_url='https://huggingface.co/datasets/mexus/ru-book-mix-10h',
        source_license='CC-BY-4.0',selection_before_inference=True,
        excluded_dev=sorted(DEV),
        records=[dict(file_id=r['file_id'],shard=r['shard'],n_speakers=r['n_speakers'],
                overlap_stats=r['overlap_stats'],speaker_disjoint=not bool(set(r['speakers'].values()) & dev_voices)) for r in selected])
    path=OUT/'frozen-selection.json'
    encoded=json.dumps(manifest,indent=2,ensure_ascii=False)+'\n'
    if path.exists() and path.read_text(encoding='utf-8')!=encoded:
        raise RuntimeError('Refusing to alter frozen holdout selection')
    path.write_text(encoded,encoding='utf-8')
    print('FROZEN', [(r['file_id'],r['n_speakers']) for r in selected],flush=True)
    for shard in sorted({r['shard'] for r in selected}):
        names={r['file_id'] for r in selected if r['shard']==shard}
        wanted={n+'.'+x for n in names for x in ('flac','rttm','json')}
        missing={x for x in wanted if not (OUT/x).is_file()}
        if missing:
            print('STREAM',shard,'missing',len(missing),flush=True)
            with urlopen(BASE+shard,timeout=120) as response:
                with tarfile.open(fileobj=response,mode='r|') as tar:
                    got=set()
                    for member in tar:
                        base=Path(member.name).name
                        if base not in missing:continue
                        if not member.isfile() or member.size>15_000_000:
                            raise RuntimeError('Untrusted archive member '+base)
                        source=tar.extractfile(member)
                        if source is None:raise RuntimeError('Cannot read '+base)
                        part=OUT/(base+'.part')
                        with part.open('wb') as destination:
                            left=member.size
                            while left>0:
                                block=source.read(min(65536,left))
                                if not block:raise EOFError(base)
                                destination.write(block);left-=len(block)
                        os.replace(part,OUT/base)
                        got.add(base)
                        print('EXTRACT',base,member.size,flush=True)
                        if got==missing:break
                    if got!=missing:raise RuntimeError('Missing '+repr(missing-got))
    for record in selected:
        name=record['file_id']
        wav=OUT/(name+'.wav')
        if not wav.exists():
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-n',
                '-i',str(OUT/(name+'.flac')),'-ar','16000','-ac','1',
                '-c:a','pcm_s16le',str(wav)],check=True)
        print('AUDIO_READY',name,sha(wav),flush=True)
    print('HOLDOUT_READY',len(selected),flush=True)

if __name__=='__main__':main()
