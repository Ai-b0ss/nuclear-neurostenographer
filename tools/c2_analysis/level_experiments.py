"""Does input level explain C2 errors on a call with one very quiet side? Diagnostic runs of the pinned C2 on the host.

python tools/c2_analysis/level_experiments.py --root ROOT --ort-python PY --cases ru_000001,ru_000002 --out FILE.json
Variants of the same 30-150 s window, all scored against the same VAD reference and the energy reference:
  mono      the frozen corpus file, (L + R) / 2
  peak      the mono file scaled so its peak is -1 dBFS (a global gain the app could apply)
  balanced  each channel scaled to the same speech RMS before mixing (needs two channels: diagnostic only)
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analyze_datahive import RATE, frames_of, run_c2, stereo  # noqa: E402
from diar_bench.sensitivity import energy_reference  # noqa: E402
from score_transcript import der  # noqa: E402


def variants(root, name, ffmpeg):
    corpus = root / "data/corpus"
    mono, _ = sf.read(corpus / f"datahive-{name}.wav", dtype="float32")
    channels = stereo(ffmpeg, root / "data/raw/datahive" / f"{name}.mp3")[: len(mono)]
    reference = json.loads((corpus / f"datahive-{name}.ref.json").read_text(encoding="utf-8"))["diarization"]
    count = len(mono) // 320
    gains = []
    for index, label in enumerate(("caller", "callee")):
        speech = np.repeat(frames_of(reference, count, label), 320)[: len(mono)]
        rms = float(np.sqrt(np.mean(channels[: len(speech), index][speech] ** 2))) if speech.any() else 1.0
        gains.append(0.1 / max(rms, 1e-6))
    balanced = channels[:, 0] * gains[0] + channels[:, 1] * gains[1]
    balanced *= 0.89 / max(np.abs(balanced).max(), 1e-6)
    return {"mono": mono, "peak": mono * (0.89 / max(np.abs(mono).max(), 1e-6)), "balanced": balanced.astype(np.float32)}, reference


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--ort-python", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    with tempfile.TemporaryDirectory() as folder:
        for name in args.cases.split(","):
            audio, reference = variants(args.root, name, args.ffmpeg)
            duration = round(len(audio["mono"]) * 1000 / RATE)
            energy = energy_reference(args.root / "data/raw/datahive", f"{name}.mp3", args.ffmpeg, duration)
            for variant, samples in audio.items():
                wav = Path(folder) / f"{name}-{variant}.wav"
                sf.write(wav, samples, RATE, subtype="PCM_16")
                turns = run_c2(args.ort_python, args.root / "data/models", wav, Path(folder) / f"{name}-{variant}.tsv", Path(folder) / f"{name}-{variant}.json")
                vad = der(reference, turns, duration, 250, False)
                alt = der(energy, turns, duration, 250, False)
                row = {"case": name, "variant": variant, "peak_dbfs": round(20 * float(np.log10(np.abs(samples).max() + 1e-9)), 1),
                       "clusters": len({t["speaker_id"] for t in turns if t["speaker_id"]}),
                       "der_vad_reference": round(vad["rate"], 4), "miss_ms": vad["miss_ms"], "false_alarm_ms": vad["false_alarm_ms"], "confusion_ms": vad["confusion_ms"],
                       "der_energy_reference": round(alt["rate"], 4)}
                rows.append(row)
                print(row, flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"scope": "Host diagnostic, C2 Python on ORT 1.31.1; not an app change", "rows": rows}, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
