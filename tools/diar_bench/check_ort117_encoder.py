"""Run only the Nemotron encoder on the current ONNX Runtime, with a log-mel saved by another runtime.

ORT 1.17.1 fails in preprocessor_core.onnx (STFT), so this isolates whether the encoder graph itself works.
python -I check_ort117_encoder.py save ONNX_DIR in.wav mel.npy
python -I check_ort117_encoder.py run ONNX_IR9_DIR MODEL in.wav mel.npy turns.tsv
"""
import importlib.util
from pathlib import Path
import sys

import numpy as np
import onnxruntime
import soundfile


def load(onnx_dir):
    spec = importlib.util.spec_from_file_location("nemotron_diarize", Path(onnx_dir) / "diarize.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main():
    mode, onnx_dir = sys.argv[1:3]
    module = load(onnx_dir)
    if mode == "save":
        wav, out = sys.argv[3:5]
        audio, rate = soundfile.read(wav, dtype="float32")
        np.save(out, module.OnnxDiarizer(onnx_dir=Path(onnx_dir), threads=2).log_mel(audio))
        return
    model, wav, mel_path, turns = sys.argv[3:7]
    audio, rate = soundfile.read(wav, dtype="float32")
    engine = module.OnnxDiarizer(onnx_dir=Path(onnx_dir), threads=2, model_filename=model)
    mel = np.load(mel_path)
    engine.log_mel = lambda _: mel
    segments = module.extract_speaker_dict(engine.diarize(audio, sample_rate=rate), threshold=module.THRESHOLD)
    limit = round(len(audio) * 1000 / rate)
    lines = [f"{round(s['Start'] * 1000)}\t{min(round(s['End'] * 1000), limit)}\t{s['Speaker']}\n" for s in segments if round(s["End"] * 1000) > round(s["Start"] * 1000)]
    Path(turns).write_text("".join(lines), encoding="ascii")
    print("onnxruntime", onnxruntime.__version__, "segments", len(lines))


if __name__ == "__main__":
    main()
