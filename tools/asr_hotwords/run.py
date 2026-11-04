"""Decode the Podlodka manifest with A3 under one configuration; writes per-clip JSON (texts stay local, not committed).
  python -I run.py MODEL_DIR CORPUS_DIR OUT.json CONFIG [SCORE]
CONFIG: greedy | beam | oracle | oracle-cyr | distractor
  (beam + per-clip hotwords, see terms.py; oracle-cyr = only Cyrillic terms: names, Russian-written brands)"""
import json, re, sys, time, hashlib
from pathlib import Path
import soundfile as sf
sys.path.insert(0, str(Path(__file__).parent))
from common import recognizer, decode
from terms import terms, hotword_string, norm

mdir, cdir, out, cfg = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
score = float(sys.argv[5]) if len(sys.argv) > 5 else 1.5
man = json.loads((cdir / "manifest.json").read_text(encoding="utf8"))["items"]
refs = {it["id"]: (cdir / it["ref"]).read_text(encoding="utf8") for it in man}
own = {i: terms(r) for i, r in refs.items()}

def distractor(it):
    """Terms of the next clip (manifest order) from a different episode that has terms; own spoken words removed."""
    k = man.index(it)
    for j in list(range(k + 1, len(man))) + list(range(0, k)):
        o = man[j]
        if o["episode"] != it["episode"] and own[o["id"]]:
            said = {norm(w) for w in refs[it["id"]].split()} | {norm(w) for w in own[it["id"]]}
            cand = [w for w in own[o["id"]] if norm(w) not in said]
            if cand:
                return cand, o["id"]
    return [], None

rec = recognizer(mdir, "greedy_search" if cfg == "greedy" else "modified_beam_search", score=score)
res = {"config": cfg, "score": score if cfg not in ("greedy", "beam") else None, "items": []}
for it in man:
    assert hashlib.sha256((cdir / it["wav"]).read_bytes()).hexdigest() == it["wav_sha256"]
    x, sr = sf.read(cdir / it["wav"], dtype="float32")
    if cfg == "oracle": hw, src = own[it["id"]], it["id"]
    elif cfg == "oracle-cyr": hw, src = [w for w in own[it["id"]] if not re.search(r"[A-Za-z]", w)], it["id"]
    elif cfg == "distractor": hw, src = distractor(it)
    else: hw, src = [], None
    t = time.time(); text = decode(rec, x, sr, hotword_string(hw) if hw else None); dt = time.time() - t
    res["items"].append({"id": it["id"], "group": it["group"], "dur_s": it["duration_s"], "dec_s": round(dt, 3),
                         "hotwords": hw, "hotwords_from": src, "text": text})
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf8")
print(cfg, score, "clips", len(res["items"]), "dec_s", round(sum(i["dec_s"] for i in res["items"]), 1))
