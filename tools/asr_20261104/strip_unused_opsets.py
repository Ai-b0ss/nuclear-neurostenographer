"""Drop opset_import entries for domains that no node uses. Graph, initializers and the default-domain opset are untouched.
Why: the int8 encoders of A1/A2/A3 (onnx.quantize 0.1.0) declare ai.onnx.ml v5 etc. without using them; the ONNX Runtime
inside sherpa-onnx 1.12.20 AAR (the app's runtime) refuses ai.onnx.ml > 4 and aborts at load (phone run 04.11.2026).
Usage: python -I strip_unused_opsets.py <in.onnx> <out.onnx>   (prints removed domains and SHA-256 of both files)"""
import hashlib, sys
import onnx

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()

src, dst = sys.argv[1], sys.argv[2]
m = onnx.load(src, load_external_data=False)
used = {n.domain for n in m.graph.node} | {""}
for fn in m.functions: used |= {n.domain for n in fn.node} | {fn.domain}
keep = [o for o in m.opset_import if o.domain in used]
drop = [(o.domain, o.version) for o in m.opset_import if o.domain not in used]
del m.opset_import[:]; m.opset_import.extend(keep)
onnx.save(m, dst)
print("removed", drop, "kept", [(o.domain, o.version) for o in keep])
print("sha256 in ", sha(src)); print("sha256 out", sha(dst))
