"""Fetch three pinned RTTM test recordings from public CC-BY-4.0 corpus.

Streams tar shards and extracts only selected samples; does not cache shards.
Evaluation only. NEVER train or optimize on the final holdout clips.
https://huggingface.co/datasets/mexus/ru-book-mix-10h
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[2]
MANIFEST=ROOT/'.local/ru-book-mix-manifest.jsonl'
OUT=ROOT/'.local/ru-book-mix-eval'
RECORDINGS=['rec_0150','rec_0300','rec_0437']
DATASET='mexus/ru-book-mix-10h'
BASE='https://huggingface.co/datasets/'+DATASET+'/resolve/main/'

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(65536),b''): h.update(block)
    return h.hexdigest()

def main():
    if not MANIFEST.is_file(): raise SystemExit('Missing manifest')
    entries={r['file_id']:r for line in MANIFEST.read_text(encoding='utf-8').splitlines()
             if (r:=json.loads(line))['file_id'] in RECORDINGS}
    assert sorted(entries)==sorted(RECORDINGS)
    assert [entries[k]['n_speakers'] for k in RECORDINGS]==[2,3,4]
    OUT.mkdir(parents=True,exist_ok=True)
    wanted={name+'.'+ext for name in RECORDINGS for ext in ('flac','rttm','json')}
    for shard in sorted({entries[x]['shard'] for x in RECORDINGS}):
        selected={x for x in wanted if x.split('.')[0] in
                  {k for k,v in entries.items() if v['shard']==shard}}
        if all((OUT/x).exists() and (OUT/x).stat().st_size>0 for x in selected):
            print('REUSE',shard,flush=True);continue
        url=BASE+shard
        print('STREAM',url,'for',sorted(selected),flush=True)
        with urlopen(url,timeout=120) as response:
            with tarfile.open(fileobj=response,mode='r|') as tar:
                extracted=set()
                for member in tar:
                    basename=Path(member.name).name
                    if basename not in selected:
                        continue
                    if not member.isfile() or member.size>15_000_000:
                        raise ValueError('Invalid sample member '+basename)
                    f=tar.extractfile(member)
                    if f is None: raise ValueError('Cannot read '+basename)
                    part=OUT/(basename+'.part')
                    with part.open('wb') as dst:
                        remaining=member.size
                        while remaining:
                            data=f.read(min(65536,remaining))
                            if not data: raise EOFError(basename)
                            dst.write(data);remaining-=len(data)
                    os.replace(part,OUT/basename)
                    extracted.add(basename)
                    print('EXTRACT',basename,member.size,'bytes',flush=True)
                    if extracted==selected: break
                if extracted != selected: raise ValueError('Missing members '+repr(selected-extracted))
    report=dict(scope='PUBLIC_SYNTHETIC_AUDIOBOOK_EVAL_NOT_NATURAL_CONVERSATION',
        dataset_url='https://huggingface.co/datasets/'+DATASET,
        source_license='CC-BY-4.0',attribution='mexus; its5Q/biggest-ru-book; bilguun/musan-noise',
        records=[])
    for name in RECORDINGS:
        flac=OUT/(name+'.flac')
        wav=OUT/(name+'.wav')
        if not wav.exists():
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-n','-i',str(flac),
                '-ac','1','-ar','16000','-c:a','pcm_s16le',str(wav)],check=True)
        rttm=OUT/(name+'.rttm')
        rows=[line.split() for line in rttm.read_text().splitlines() if line.strip()]
        if len({row[7] for row in rows})!=entries[name]['n_speakers']:
            raise ValueError('RTTM distinct speakers mismatch for '+name)
        report['records'].append(dict(name=name,shard=entries[name]['shard'],
            speakers=entries[name]['n_speakers'],wav_sha256=sha(wav),
            flac_sha256=sha(flac),rttm_sha256=sha(rttm),
            overlap=entries[name]['overlap_stats']))
    (OUT/'selection.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('READY',json.dumps(report['records'],ensure_ascii=False),flush=True)

if __name__=='__main__': main()
