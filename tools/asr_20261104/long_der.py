"""DER of the C2 turns on the 20-minute file long-ru_000010 (DataHive ru_000010.mp3, seconds 0-1200) against a reference built
the same way as the datahive corpus: Silero VAD on each of the two call channels (caller/callee). AUTOMATIC, NOT HUMAN.
The ASR model does not enter DER, so this number holds for A0+C2 and A3+C2 alike.

python -I long_der.py --data K:/nn-bench/data --wav K:/nn-bench/data/corpus-long/long-ru_000010.wav \
    --turns K:/nn-bench/results-v2-long1/C2/long-ru_000010.tsv [--turns ...] --ffmpeg ffmpeg --out OUT.json
"""
import argparse, hashlib, json, sys, wave
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools")); sys.path.insert(0, str(REPO / "tools/diar_bench")); sys.path.insert(0, str(REPO / "tools/c2_same_tracks"))
from build_corpus import Silero, segments_from_probs, decode, VAD  # noqa: E402
from score_same_corpus import der  # noqa: E402
from score_bench import read_turns  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--data", type=Path, required=True); ap.add_argument("--wav", type=Path, required=True)
ap.add_argument("--turns", type=Path, action="append", required=True); ap.add_argument("--ffmpeg", default="ffmpeg")
ap.add_argument("--out", type=Path, required=True)
a = ap.parse_args()
mp3 = a.data / "raw/datahive/ru_000010.mp3"
channels = decode(a.ffmpeg, mp3, 2, 0, 1200)
mono = decode(a.ffmpeg, mp3, 1, 0, 1200)
with wave.open(str(a.wav)) as w:
    pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
n = min(len(pcm), len(mono)); alignment_corr = float(np.corrcoef(pcm[:n], mono[:n])[0, 1])
duration = round(len(pcm) * 1000 / 16000)
silero = Silero(a.data / "models/silero/silero_vad.onnx")
reference = []
for i, label in enumerate(("caller", "callee")):
    probs, frame_ms = silero.probabilities(channels[:, i].copy())
    reference += [{"start_ms": s, "end_ms": e, "speaker_id": label} for s, e in segments_from_probs(probs, frame_ms, duration)]
reference.sort(key=lambda t: t["start_ms"])
out = dict(recording="long-ru_000010", wav_sha256=hashlib.sha256(a.wav.read_bytes()).hexdigest(), duration_ms=duration,
           reference=f"Silero VAD per channel {VAD}; AUTOMATIC, NOT HUMAN", wav_vs_mp3_mono_corr=round(alignment_corr, 4),
           channel_corr=round(float(np.corrcoef(channels[:, 0], channels[:, 1])[0, 1]), 4),
           reference_speech_ms={l: sum(t["end_ms"] - t["start_ms"] for t in reference if t["speaker_id"] == l) for l in ("caller", "callee")},
           runs={})
for t in a.turns:
    turns = read_turns(t)
    hyp = [{"start_ms": s, "end_ms": e, "speaker_id": f"h{c}"} for s, e, c in turns if c >= 0]
    row = {}
    for collar in (0, 250):
        d = der(reference, hyp, duration, collar, False)
        row[f"collar_{collar}"] = {"rate": round(d["rate"], 4), **{k: d[k] for k in ("miss_ms", "false_alarm_ms", "confusion_ms", "reference_speaker_ms")}}
    row["clusters"] = len({c for _, _, c in turns if c >= 0}); row["unknown_turns"] = sum(c < 0 for _, _, c in turns)
    out["runs"][str(t)] = row
a.out.write_text(json.dumps(out, indent=1), encoding="utf-8"); print(json.dumps(out, indent=1))
