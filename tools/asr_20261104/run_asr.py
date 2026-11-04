"""Decode a manifest of WAVs with ONE candidate (fresh process => clean RSS). Writes per-clip JSON.
Usage: python -I run_asr.py <cand A0|A0s|A1..A4> <models_dir> <corpus_dir> <out_json> [threads]
A0 = app model (k2-fsa official int8, K:/nn-bench/data/models/asr); A0s = Smirnov75 conversion (control).
Greedy decoding, whole clip (clips are ~24 s, i.e. same order as the app's 20 s QuietCuts windows; NOT identical)."""
import json, sys, time, hashlib, platform
from pathlib import Path
import numpy as np, soundfile as sf, psutil, sherpa_onnx as so

cand, mdir, cdir, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
threads = int(sys.argv[5]) if len(sys.argv) > 5 else 4
G = mdir / "A0"; 
def mk():
    kw = dict(num_threads=threads, sample_rate=16000, decoding_method="greedy_search", debug=False)
    if cand == "A0":
        d = Path("K:/nn-bench/data/models/asr"); return so.OfflineRecognizer.from_nemo_ctc(str(d/"model.int8.onnx"), str(d/"tokens.txt"), num_threads=threads)
    if cand == "A0s": return so.OfflineRecognizer.from_nemo_ctc(str(G/"gigaam_v3_ctc_int8.onnx"), str(G/"gigaam_v3_ctc_tokens.txt"), num_threads=threads)
    if cand == "A2":
        d = mdir/"A2"; return so.OfflineRecognizer.from_nemo_ctc(str(d/"gigaam_v3_e2e_ctc_int8.onnx"), str(d/"gigaam_v3_e2e_ctc_tokens.txt"), num_threads=threads)
    if cand == "A4":
        d = mdir/"A4/x/sherpa-onnx-nemo-ctc-gigaam-multilingual-int8"; return so.OfflineRecognizer.from_nemo_ctc(str(d/"model.int8.onnx"), str(d/"tokens.txt"), num_threads=threads)
    n = {"A1": "rnnt", "A3": "e2e_rnnt"}[cand]; d = mdir/cand
    return so.OfflineRecognizer.from_transducer(str(d/f"gigaam_v3_{n}_encoder_int8.onnx"), str(d/f"gigaam_v3_{n}_decoder.onnx"),
        str(d/f"gigaam_v3_{n}_joint.onnx"), str(d/f"gigaam_v3_{n}_tokens.txt"), num_threads=threads, decoding_method="greedy_search", model_type="nemo_transducer")

proc = psutil.Process(); t0 = time.time(); rec = mk(); load_s = time.time() - t0
man = json.loads((cdir/"manifest.json").read_text(encoding="utf8"))
res = {"candidate": cand, "sherpa_onnx": so.__version__, "threads": threads, "python": platform.python_version(),
       "cpu": platform.processor(), "load_s": round(load_s, 2), "rss_after_load_mb": round(proc.memory_info().rss/2**20), "items": []}
for it in man["items"]:
    x, sr = sf.read(cdir/it["wav"], dtype="float32"); assert sr == 16000
    got = hashlib.sha256((cdir/it["wav"]).read_bytes()).hexdigest(); assert got == it["wav_sha256"], "WAV SHA mismatch"
    t = time.time(); s = rec.create_stream(); s.accept_waveform(16000, x); rec.decode_stream(s); dt = time.time() - t
    res["items"].append({"id": it["id"], "group": it["group"], "dur_s": it["duration_s"], "dec_s": round(dt, 3), "rtf": round(dt/it["duration_s"], 4),
                         "text": s.result.text, "n_tokens": len(s.result.tokens)})
mi = proc.memory_info(); res["peak_rss_mb"] = round(getattr(mi, "peak_wset", mi.rss)/2**20)
tot = sum(i["dec_s"] for i in res["items"]); dur = sum(i["dur_s"] for i in res["items"]); res["rtf_total"] = round(tot/dur, 4)
out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf8")
print(cand, "load", res["load_s"], "s  RTF", res["rtf_total"], " peakRSS", res["peak_rss_mb"], "MB  n", len(res["items"]))
