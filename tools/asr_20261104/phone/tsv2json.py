"""Convert PhoneAsrBench TSV to run_asr-style JSON + HOLDOUT-only manifest for score_asr.py. Usage: tsv2json.py <corpus> <outdir> <cand> <tsv>"""
import json, sys, re
from pathlib import Path
corpus, outd, cand, tsv = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
m = json.loads((corpus/"manifest.json").read_text(encoding="utf8"))
hold = [dict(i, wav=str(corpus/i["wav"]), ref=str(corpus/i["ref"])) for i in m["items"] if i["group"] == "HOLDOUT"]
(outd/"corpus").mkdir(parents=True, exist_ok=True)
(outd/"corpus"/"manifest.json").write_text(json.dumps(dict(m, items=hold), ensure_ascii=False), encoding="utf8")
items, meta = [], {}
for l in Path(tsv).read_text(encoding="utf8").splitlines():
    if l.startswith("#"): meta = dict(kv.split("=", 1) for kv in l[1:].split()); continue
    if not l.strip(): continue
    p = l.split("\t"); items.append(dict(id=p[0], dur_s=float(p[1]), dec_s=int(p[2])/1000, text=p[3] if len(p) > 3 else ""))
assert [i["id"] for i in items] == [h["id"] for h in hold], "order mismatch"
d = sum(i["dur_s"] for i in items); t = sum(i["dec_s"] for i in items)
out = dict(candidate=cand, sherpa_onnx="1.12.20 AAR (K:/nn-bench/harness, jni md5 95988a9b)", device="HONOR DNN-LX9 arm64 Android 10", threads=int(meta["threads"]), load_s=int(meta["load_ms"])/1000,
           peak_rss_mb=round(int(meta["VmHWM_kB"])/1024), rtf_total=round(t/d, 4), items=items)
(outd/f"{cand}.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf8"); print(cand, meta)
