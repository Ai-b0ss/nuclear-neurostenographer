"""J1 MOSS-Transcribe-Diarize 0.9B (OpenMOSS-Team, HF rev 10304d9, code rev 79c675f) on ONE WAV; official README API, greedy.
Usage: K:/nn-moss-venv/Scripts/python.exe -I run_moss.py <wav> <out.json> [device=cpu|cuda] [max_new_tokens=2048]
Records raw output, parsed segments, wall time, peak RSS, torch/transformers versions. Fails are written as status=FAIL (never dropped)."""
import json, sys, time, traceback, hashlib, platform
from pathlib import Path
import psutil, torch, transformers
wav, out = Path(sys.argv[1]), Path(sys.argv[2]); dev = sys.argv[3] if len(sys.argv) > 3 else "cpu"; mnt = int(sys.argv[4]) if len(sys.argv) > 4 else 2048
res = {"candidate": "J1", "wav": wav.name, "wav_sha256": hashlib.sha256(wav.read_bytes()).hexdigest(), "device": dev, "torch": torch.__version__,
       "transformers": transformers.__version__, "status": "FAIL", "max_new_tokens": mnt}
try:
    from moss_transcribe_diarize import parse_transcript
    from moss_transcribe_diarize.inference_utils import build_transcription_messages, generate_transcription, resolve_device
    d = resolve_device(dev); dt = torch.bfloat16 if d.type == "cuda" else torch.float32
    t0 = time.time(); mid = "K:/nn-moss/model"
    from transformers import AutoModelForCausalLM, AutoProcessor
    model = AutoModelForCausalLM.from_pretrained(mid, trust_remote_code=True, dtype="auto", attn_implementation="sdpa").to(dtype=dt).to(d).eval()
    proc = AutoProcessor.from_pretrained(mid, trust_remote_code=True); res["load_s"] = round(time.time() - t0, 1)
    t0 = time.time(); r = generate_transcription(model, proc, build_transcription_messages(str(wav)), max_new_tokens=mnt, do_sample=False, device=d, dtype=dt)
    res["gen_s"] = round(time.time() - t0, 1); res["raw"] = r["text"]
    res["segments"] = [dict(start=s.start, end=s.end, speaker=s.speaker, text=s.text) for s in parse_transcript(r["text"])]; res["status"] = "OK"
except Exception as e:
    res["error"] = repr(e)[:500]; res["trace"] = traceback.format_exc()[-1500:]
mi = psutil.Process().memory_info(); res["peak_rss_mb"] = round(getattr(mi, "peak_wset", mi.rss) / 2**20)
if dev.startswith("cuda") and torch.cuda.is_available(): res["peak_vram_mb"] = round(torch.cuda.max_memory_allocated() / 2**20)
out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf8")
print(res["status"], res.get("load_s"), res.get("gen_s"), res.get("peak_rss_mb"), res.get("error", ""))
