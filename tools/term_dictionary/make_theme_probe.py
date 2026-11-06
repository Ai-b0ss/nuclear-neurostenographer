"""gTTS (online, Russian voice; public sentences only, no private audio) -> 16 kHz mono WAV of docs/evidence/term-dictionary-20261107/probe-sentences.txt,
1 s of silence between sentences. Run A3 over all.wav with tools/diar_bench/DiarBench.kt asr (one turn over the whole file).
  python -X utf8 tools/term_dictionary/make_theme_probe.py <dir with sentences.txt>   (needs gTTS and ffmpeg)"""
import sys, subprocess
from pathlib import Path
from gtts import gTTS
d = Path(sys.argv[1]); lines = [l.strip() for l in (d / 'sentences.txt').read_text(encoding='utf-8').splitlines() if l.strip()]
parts = []
for i, s in enumerate(lines):
    mp3 = d / f'{i:02d}.mp3'
    if not mp3.exists(): gTTS(s, lang='ru').save(str(mp3))
    parts.append(mp3)
lst = d / 'concat.txt'
# 1 s of silence between sentences
sil = d / 'sil.wav'
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=16000:cl=mono', '-t', '1', str(sil)], check=True)
wavs = []
for p in parts:
    w = p.with_suffix('.wav'); subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(p), '-ar', '16000', '-ac', '1', '-sample_fmt', 's16', str(w)], check=True); wavs += [w, sil]
lst.write_text(''.join(f"file '{w.as_posix()}'\n" for w in wavs), encoding='utf-8')
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', str(lst), '-ar', '16000', '-ac', '1', '-sample_fmt', 's16', str(d / 'all.wav')], check=True)
print(len(lines), 'sentences')
