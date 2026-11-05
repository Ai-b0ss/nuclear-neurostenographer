"""Deterministic 1/2-speaker and overlap probes derived only from existing MIT synthetic TTS.
These are development probes, not independent natural-dialogue accuracy evidence.
"""
import array
import hashlib
import json
from pathlib import Path
import sys
import wave

ROOT = Path(__file__).resolve().parents[2]


def main():
    source = Path('C:/Users/user/Documents/nuclear-neurostenographer/.local/synthetic-ru')
    ref = json.loads((source / 'syn3-clean.reference.json').read_text(encoding='utf-8'))
    original = source / 'syn3-clean.wav'
    if hashlib.sha256(original.read_bytes()).hexdigest() != ref['audio_sha256']:
        raise SystemExit('Original fixture/reference mismatch')
    with wave.open(str(original), 'rb') as f:
        if (f.getnchannels(), f.getsampwidth(), f.getframerate()) != (1, 2, 16000):
            raise SystemExit('Expected existing 16k PCM16 fixture')
        data = array.array('h', f.readframes(f.getnframes()))
    if sys.byteorder != 'little':
        data.byteswap()
    out = ROOT / '.local/realtime-fixtures'; out.mkdir(exist_ok=True)
    refs = ROOT / 'docs/evidence/realtime-honor-20261105/fixture-references'; refs.mkdir(exist_ok=True)

    def piece(index):
        turn = ref['text_segments'][index]
        return data[turn['start_ms'] * 16:min(turn['end_ms'] * 16, len(data))], turn

    def save(name, pcm, segments, recipe):
        path = out / (name + '.wav')
        with wave.open(str(path), 'wb') as w:
            w.setparams((1, 2, 16000, 0, 'NONE', 'not compressed')); w.writeframes(pcm.tobytes())
        document = dict(ref, recording_id=name, audio_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                        audio_duration_ms=len(pcm) // 16, text_segments=segments,
                        diarization=[{k: s[k] for k in ['start_ms', 'end_ms', 'speaker_id']} for s in segments],
                        kind='DERIVED_SYNTHETIC_TTS_DEVELOPMENT_PROBE', derivation=recipe,
                        source_audio_sha256=ref['audio_sha256'])
        (refs / (name + '.reference.json')).write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding='utf-8')
        print(name, len(pcm) / 16000, document['audio_sha256'])

    pcm, turn = piece(5)
    save('single', pcm, [dict(turn, start_ms=0, end_ms=len(pcm) // 16)], 'source turn 5 unchanged PCM')
    joined = array.array('h'); segments = []
    for index in [0, 1, 5]:
        part, turn = piece(index)
        start = len(joined) // 16
        joined.extend(part)
        segments.append(dict(turn, start_ms=start, end_ms=len(joined) // 16))
        joined.extend(array.array('h', [0]) * 8000)
    save('aba', joined, segments, 'source turns [0,1,5], each followed by 500ms zero PCM; speaker 1 returns')
    a, ta = piece(5); b, tb = piece(1); offset = 16000
    mixed = array.array('h', [0]) * max(len(a), offset + len(b))
    for i, n in enumerate(a):
        mixed[i] = int(n * 0.5)
    for i, n in enumerate(b):
        mixed[offset + i] += int(n * 0.5)
    save('overlap', mixed, [dict(ta, start_ms=0, end_ms=len(a) // 16), dict(tb, start_ms=1000, end_ms=1000 + len(b) // 16)],
         'source turn 5 at 0ms plus turn 1 at 1000ms, each PCM gain 0.5; coarse original TTS turn references')


if __name__ == '__main__':
    main()
