"""Negative / robustness tests for ONE candidate (fresh process).
 (1) NON-SPEECH hallucination: SYNTHETIC signals only (silence, white noise -60/-40/-20 dBFS, 440 Hz tone, click train). Real music/room noise NOT_RUN.
 (2) WINDOW BOUNDARY: clips >24 s decoded (a) whole, (b) hard 20 s cuts, (c) quiet-point cuts <=20 s (min RMS in last 4 s; approximates, does NOT replicate, app QuietCuts).
     Reports WER and boundary-adjacent duplicate words (last hyp word of window k == first of k+1 AND ref has no such repeat -> counted as a candidate duplicate).
Usage: python -I run_stress.py <cand> <models_dir> <corpus_dir> <out_json>"""
import json, sys, re, unicodedata
from pathlib import Path
import numpy as np, soundfile as sf
sys.argv_backup = sys.argv
cand, mdir, cdir, out = sys.argv[1:5]
sys.argv = ["run_asr.py", cand, mdir, cdir, "NUL"]   # reuse recognizer factory
src = Path(__file__).with_name("run_asr.py").read_text(encoding="utf8").split("proc = psutil.Process()")[0]
exec(compile(src, "run_asr_head", "exec")); out = sys.argv_backup[4]; rec = mk()
sys.path.insert(0, str(Path(__file__).parent)); import score_asr_lib as L
def dec(x):
    s = rec.create_stream(); s.accept_waveform(16000, x.astype(np.float32)); rec.decode_stream(s); return s.result.text
rng = np.random.default_rng(20261104); sr = 16000; n = 30*sr
db = lambda d: 10**(d/20)
sig = {"silence_30s": np.zeros(n), "white_-60dBFS": rng.normal(0, db(-60), n), "white_-40dBFS": rng.normal(0, db(-40), n),
       "white_-20dBFS": rng.normal(0, db(-20), n), "tone_440Hz_-20dBFS": db(-20)*np.sin(2*np.pi*440*np.arange(n)/sr)}
clk = np.zeros(n); clk[::sr//4] = 0.5; sig["click_train_4Hz"] = clk
res = {"candidate": cand, "nonspeech": {}, "boundary": []}
for k, x in sig.items():
    t = dec(x); res["nonspeech"][k] = {"text": t, "words": len(L.words(t))}
man = json.loads((Path(cdir)/"manifest.json").read_text(encoding="utf8"))
for it in man["items"]:
    if it["duration_s"] <= 24: continue
    x, _ = sf.read(Path(cdir)/it["wav"], dtype="float32"); ref = (Path(cdir)/it["ref"]).read_text(encoding="utf8"); rw = L.words(ref)
    W = 20*sr; hard = [x[i:i+W] for i in range(0, len(x), W)]
    quiet, i = [], 0
    while i < len(x):
        if len(x) - i <= W: quiet.append(x[i:]); break
        seg = x[i+W-4*sr:i+W]; fr = seg[:len(seg)//160*160].reshape(-1, 160); r = np.sqrt((fr**2).mean(1)); cut = i+W-4*sr+int(np.argmin(r))*160
        quiet.append(x[i:cut]); i = cut
    row = {"id": it["id"], "dur_s": it["duration_s"], "ref_words": len(rw)}
    for name, segs in (("whole", [x]), ("hard20", hard), ("quiet20", quiet)):
        texts = [dec(s) for s in segs]; hw = L.words(" ".join(texts)); S, D, I, _ = L.align(rw, hw)
        dup = sum(1 for a, b in zip(texts, texts[1:]) if L.words(a) and L.words(b) and L.words(a)[-1] == L.words(b)[0])
        row[name] = {"windows": len(segs), "errors": S+D+I, "S": S, "D": D, "I": I, "boundary_repeat_words": dup}
    res["boundary"].append(row)
Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf8")
agg = {k: {m: sum(r[k][m] for r in res["boundary"]) for m in ("windows", "errors", "boundary_repeat_words")} for k in ("whole", "hard20", "quiet20")}
print(cand, "nonspeech words:", {k: v["words"] for k, v in res["nonspeech"].items()}, "| boundary:", agg, "refw", sum(r["ref_words"] for r in res["boundary"]))
