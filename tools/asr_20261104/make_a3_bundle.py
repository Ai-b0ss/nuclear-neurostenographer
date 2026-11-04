"""Build gigaam-v3-e2e-rnnt.zip for the -PasrA3=true test app from a directory holding the four A3 files
(encoder already passed through strip_unused_opsets.py). Every file is checked against the pins in
app/src/main/java/ru/neurostenographer/app/AsrModelSpec.kt before it is stored.
Usage: python -I make_a3_bundle.py <model_dir> <out.zip>"""
import hashlib, re, sys, zipfile
from pathlib import Path

SPEC = Path(__file__).resolve().parents[2] / "app/src/main/java/ru/neurostenographer/app/AsrModelSpec.kt"

def pins():
    text = SPEC.read_text(encoding="utf8").split("val E2E_RNNT", 1)[1]
    return {n: (h, int(b.replace("_", ""))) for n, h, b in re.findall(r'"(gigaam_v3_e2e_rnnt_[\w.]+)" to \("([0-9a-f]{64})" to ([\d_]+)L\)', text)}

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()

src, out = Path(sys.argv[1]), Path(sys.argv[2])
P = pins(); assert len(P) == 4, P
for name, (h, size) in P.items():
    f = src / name; got = sha(f)
    if got != h or f.stat().st_size != size:
        sys.exit(f"MISMATCH {name}: {got} {f.stat().st_size} (expected {h} {size})")
with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
    for name in P: z.write(src / name, name)
print(out, out.stat().st_size, "sha256", sha(out))
