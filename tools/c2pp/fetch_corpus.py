"""Stream the selected ru-book-mix shards and extract only selected FLAC/RTTM members; convert to 16 kHz mono WAV.

Shards are streamed, never cached. Output stays outside Git (audio is not committed).
"""
import argparse
import json
import subprocess
import tarfile
from pathlib import Path
from urllib.request import urlopen

BASE = 'https://huggingface.co/datasets/mexus/ru-book-mix-10h/resolve/main/'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--selection', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    sel = json.loads(a.selection.read_text(encoding='utf-8'))
    recs = sel['dev'] + sel['test']
    a.out.mkdir(parents=True, exist_ok=True)
    for shard in sorted({r['shard'] for r in recs}):
        wanted = {r['file_id'] + ext for r in recs if r['shard'] == shard for ext in ('.flac', '.rttm')}
        wanted = {w for w in wanted if not (a.out / w).exists()}
        if not wanted:
            print('REUSE', shard, flush=True); continue
        print('STREAM', shard, len(wanted), 'members', flush=True)
        with urlopen(BASE + shard, timeout=120) as resp, tarfile.open(fileobj=resp, mode='r|') as tar:
            for m in tar:
                name = Path(m.name).name
                if name not in wanted:
                    continue
                if not m.isfile() or m.size > 15_000_000:
                    raise ValueError('Invalid member ' + name)
                part = a.out / (name + '.part')
                part.write_bytes(tar.extractfile(m).read())
                part.replace(a.out / name)
                wanted.discard(name)
                if not wanted:
                    break
        if wanted:
            raise ValueError('Missing ' + repr(sorted(wanted)))
    for r in recs:
        wav = a.out / (r['file_id'] + '.wav')
        if not wav.exists():
            subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(a.out / (r['file_id'] + '.flac')),
                            '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(wav)], check=True)
    print('OK', len(recs), 'recordings in', a.out)


if __name__ == '__main__':
    main()
