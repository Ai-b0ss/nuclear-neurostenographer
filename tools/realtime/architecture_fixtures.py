"""Frozen structural probes from existing synthetic Russian speech; no natural-dialogue claim."""
import array
import hashlib
import json
from pathlib import Path
import wave

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path('C:/Users/user/Documents/nuclear-neurostenographer/.local/synthetic-ru')
OUT = ROOT / '.local/realtime-fixtures'
REFS = ROOT / 'docs/evidence/architecture-20261106/references'


def main():
    ref = json.loads((SOURCE / 'syn3-clean.reference.json').read_text(encoding='utf-8'))
    source = SOURCE / 'syn3-clean.wav'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == ref['audio_sha256']
    with wave.open(str(source), 'rb') as f:
        assert f.getparams()[:3] == (1, 2, 16000)
        pcm = array.array('h', f.readframes(f.getnframes()))
    OUT.mkdir(exist_ok=True); REFS.mkdir(parents=True, exist_ok=True)
    for name, indices, gap, limit in [('abab', [0, 1, 5, 1], 500, None),
            ('return-pause', [0, 1, 5], 20000, None), ('short-tail', [0, 1, 5, 1], 300, 700)]:
        audio = array.array('h'); turns = []
        for idx in indices:
            t = ref['text_segments'][idx]
            length = t['end_ms'] - t['start_ms'] if limit is None else limit
            part = pcm[t['start_ms'] * 16:(t['start_ms'] + length) * 16]
            start = len(audio) // 16; audio.extend(part)
            turns.append(dict(start_ms=start, end_ms=len(audio)//16, speaker_id=t['speaker_id']))
            audio.extend(array.array('h', [0]) * (gap * 16))
        audio.extend(array.array('h', [0]) * 127)  # non-frame-aligned EOF
        file = OUT / (name + '.wav')
        with wave.open(str(file), 'wb') as f:
            f.setparams((1, 2, 16000, 0, 'NONE', 'not compressed')); f.writeframes(audio.tobytes())
        document = dict(schema_version=1, recording_id=name, audio_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
            audio_duration_ms=len(audio)//16, diarization=turns,
            kind='DERIVED_SYNTHETIC_COARSE_INTERVALS_NO_WORD_GOLD', source_sha256=ref['audio_sha256'],
            recipe=dict(indices=indices, gap_ms=gap, clip_ms=limit, tail_samples=127))
        (REFS / (name + '.reference.json')).write_text(json.dumps(document, indent=2), encoding='utf-8')
        print(name, len(audio)/16000)


if __name__ == '__main__':
    main()
