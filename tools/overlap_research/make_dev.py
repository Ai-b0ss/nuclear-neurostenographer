"""Deterministic SYNTHETIC DEV mixtures from the existing licensed ACTED DEV clips.

No holdout clips are read. External scripts are utterance references, not manual
word alignment or speech activity: DER and overlap word recall stay NOT_SCORED.
"""
import argparse
import csv
import io
import json
import wave
from pathlib import Path
import numpy as np
from common import REPO, LOCAL, owned, sha, write_json

def read_wav(path):
    with wave.open(str(path)) as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError('Expected mono PCM16')
        rate = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(np.float32) / 32768
    if rate != 16000:
        n = len(x) * 16000 // rate
        x = np.interp(np.arange(n) * rate / 16000, np.arange(len(x)), x).astype(np.float32)
    return x

def write_wav(path, x):
    x = np.asarray(x)
    if x.ndim != 1 or not np.isfinite(x).all():
        raise ValueError('Invalid PCM')
    with wave.open(str(path), 'wb') as w:
        w.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        w.writeframes(np.rint(np.clip(x, -1, 32767/32768) * 32768).astype('<i2').tobytes())

def build(source, output):
    lock = json.loads((REPO / 'tools/fixtures/dialogs-ru-smoke-lock.json').read_text())
    for pin in [lock['license'], lock['metadata'], *lock['clips']]:
        if sha(source / Path(pin['path']).name) != pin['sha256']:
            raise ValueError('Source pin mismatch: ' + pin['path'])
    rows = list(csv.DictReader(io.StringIO((source / 'test.csv').read_text(encoding='utf-8')), delimiter='|'))
    clips = [read_wav(source / Path(c['path']).name) for c in lock['clips']]
    texts = [next(r['text'] for r in rows if r['audio_path'] == c['path']) for c in lock['clips']]
    output = owned(output)
    # Clean identity anchors then repeated M speech overlaps the final D utterance.
    a, b, a2 = clips
    starts = [0, len(a)+8000, len(a)+len(b)+16000]
    cases = []
    for name, entries in [('aba-clean', [(0, starts[0]), (1, starts[1]), (2, starts[2])]),
                          ('two-person-overlap', [(0, starts[0]), (1, starts[1]), (2, starts[2]), (1, starts[2]+32000)])]:
        total = max(at + len(clips[i]) for i, at in entries) + 8000
        stems = {s: np.zeros(total, np.float32) for s in ('D', 'M')}
        segments = []
        for i, at in entries:
            who = lock['clips'][i]['speaker']
            stems[who][at:at+len(clips[i])] += clips[i] * 0.45
            segments.append(dict(start_ms=at//16, end_ms=(at+len(clips[i]))//16, speaker_id=who, text=texts[i]))
        mix = sum(stems.values())
        wav = output / (name+'.wav')
        write_wav(wav, mix)
        ref = dict(schema_version=1, recording_id=name, audio_sha256=sha(wav), audio_duration_ms=total//16,
                   kind='SYNTHETIC_DEV_FROM_ACTED_SOURCES', split='DEV', annotation_source=lock['repository']+'@'+lock['revision']+'/test.csv',
                   license='Dialogs OpenRAIL; see local LICENSE.md; no redistribution of audio in Git', text_segments=segments,
                   reference_limits='Scripted utterances, not manually verified audible words or word times. No speech activity ground truth. Not natural overlap; not HOLDOUT.')
        write_json(output / (name+'.ref.json'), ref)
        stem_hashes = {}
        for who, x in stems.items():
            p = output / (name+'.source-'+who+'.wav')
            write_wav(p, x)
            stem_hashes[who] = sha(p)
        cases.append(dict(id=name, split='DEV', kind=ref['kind'], audio_sha256=sha(wav), reference_sha256=sha(output/(name+'.ref.json')),
                          duration_ms=total//16, source_stem_sha256=stem_hashes,
                          placements=[dict(source_index=i,start_sample=at) for i,at in entries],
                          enrollment_anchor_ms=[[s//16,(s+len(c))//16] for s,c in zip(starts[:2], clips[:2])],
                          word_reference='NOT_AVAILABLE', diarization_reference='NOT_AVAILABLE'))
    (output / 'LICENSE.md').write_bytes((source / 'LICENSE.md').read_bytes())
    manifest = dict(schema_version=1, scope='SYNTHETIC DEV ONLY; existing 4-clip holdout untouched', source_lock=lock,
                    mixture='mono16k; deterministic linear resampling; gain0.45 per stem, integer PCM rounding; no ASR-derived reference',
                    cases=cases)
    write_json(output / 'manifest.json', manifest)
    return manifest

if __name__ == '__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--source',type=Path,required=True); ap.add_argument('--out',type=Path,default=LOCAL/'dev')
    args=ap.parse_args(); print(json.dumps(build(args.source,args.out),ensure_ascii=False,indent=2))
