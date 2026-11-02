"""Run the pinned third-party Nemotron ONNX loop on one 16 kHz mono WAV in this process.

python -I run_c1.py ONNX_DIR model.int8.onnx in.wav turns.tsv meta.json
The module is loaded by explicit path, so nothing is imported from the model folder implicitly.
infer_ms covers diarization and post-processing up to the written turns file, the same boundary as C0.
"""
import importlib.util
import json
from pathlib import Path
import sys
import time


def main():
    onnx_dir, model, wav, turns, meta = sys.argv[1:6]
    spec = importlib.util.spec_from_file_location("nemotron_diarize", Path(onnx_dir) / "diarize.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    import onnxruntime
    import soundfile
    read_started = time.perf_counter()
    audio, rate = soundfile.read(wav, dtype="float32")
    started = time.perf_counter()
    engine = module.OnnxDiarizer(onnx_dir=Path(onnx_dir), threads=2, model_filename=model)
    loaded = time.perf_counter()
    probs = engine.diarize(audio, sample_rate=rate)
    segments = module.extract_speaker_dict(probs, threshold=module.THRESHOLD)
    duration_ms = round(len(audio) * 1000 / rate)
    lines = []
    for s in segments:
        start, end = round(s["Start"] * 1000), min(round(s["End"] * 1000), duration_ms)
        if end > start:
            lines.append(f"{start}\t{end}\t{s['Speaker']}\n")
    Path(turns).write_text("".join(lines), encoding="ascii")
    done = time.perf_counter()
    Path(meta).write_text(json.dumps({
        "read_ms": round((started - read_started) * 1000), "load_ms": round((loaded - started) * 1000),
        "infer_ms": round((done - loaded) * 1000), "threshold": module.THRESHOLD, "threads": 2,
        "onnxruntime": onnxruntime.__version__, "model": model}) + "\n")


if __name__ == "__main__":
    main()
