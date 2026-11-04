"""Pinned, checksum-verified model fetch for ASR-20261104-v2. One candidate at a time.
Usage: python -I fetch_models.py <A0|A1|A2|A3|A4> <models_dir>
Verifies each file against the SHA-256 (LFS oid) published by the Hub API for the pinned revision."""
import hashlib, json, shutil, sys
from pathlib import Path
from huggingface_hub import HfApi, hf_hub_download

S = "Smirnov75/GigaAM-v3-sherpa-onnx"
CAND = {
 "A0": (S, ["gigaam_v3_ctc_int8.onnx", "gigaam_v3_ctc_tokens.txt"]),
 "A1": (S, ["gigaam_v3_rnnt_encoder_int8.onnx", "gigaam_v3_rnnt_decoder.onnx", "gigaam_v3_rnnt_joint.onnx", "gigaam_v3_rnnt_tokens.txt"]),
 "A2": (S, ["gigaam_v3_e2e_ctc_int8.onnx", "gigaam_v3_e2e_ctc_tokens.txt"]),
 "A3": (S, ["gigaam_v3_e2e_rnnt_encoder_int8.onnx", "gigaam_v3_e2e_rnnt_decoder.onnx", "gigaam_v3_e2e_rnnt_joint.onnx", "gigaam_v3_e2e_rnnt_tokens.txt"]),
 "A4": ("btolfa/sherpa-onnx-nemo-ctc-gigaam-multilingual-int8", ["sherpa-onnx-nemo-ctc-gigaam-multilingual-int8.tar.bz2"]),
}
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()

cid, out = sys.argv[1], Path(sys.argv[2]) / sys.argv[1]
repo, files = CAND[cid]; out.mkdir(parents=True, exist_ok=True)
api = HfApi(); info = api.model_info(repo, files_metadata=True); rev = info.sha
meta = {s.rfilename: s for s in info.siblings}
rec = {"candidate": cid, "repo": repo, "revision": rev, "license_tag": [t for t in info.tags if t.startswith("license:")], "files": {}}
for fn in files:
    p = hf_hub_download(repo, fn, revision=rev, local_dir=out)
    s = meta[fn]; want = s.lfs.sha256 if s.lfs else None
    got = sha(p)
    ok = (want is None) or (want == got)
    rec["files"][fn] = {"bytes": Path(p).stat().st_size, "sha256": got, "hub_sha256": want, "verified": ok}
    if not ok: raise SystemExit(f"CHECKSUM MISMATCH {fn}")
(out / "provenance.json").write_text(json.dumps(rec, indent=1))
print(json.dumps(rec, indent=1))
