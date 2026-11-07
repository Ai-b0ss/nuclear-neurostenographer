"""Optional clean-checkout baseline acquisition; exact pinned bytes, task-local only.

Existing verified --a3/--c2 directories can instead be passed directly to run_host.
Only the established unused-opset/IR fixes are applied, with final SHA checks.
Requires already installed onnx for A3 conversion; never installs packages.
"""
import json
from pathlib import Path
import re
import sys
from common import REPO,LOCAL,owned,fetch,sha,write_json

if __name__=='__main__':
    import onnx
    a3=owned(LOCAL/'baseline/a3');original=owned(LOCAL/'baseline/original-a3')
    spec=(REPO/'app/src/main/java/ru/neurostenographer/app/AsrModelSpec.kt').read_text(encoding='utf-8').split('val E2E_RNNT',1)[1]
    pins={n:h for n,h in re.findall(r'"(gigaam_v3_e2e_rnnt_[\w.]+)" to \("([0-9a-f]{64})"',spec)}
    if len(pins)!=4:raise ValueError('Expected four app A3 pins')
    base='https://huggingface.co/Smirnov75/GigaAM-v3-sherpa-onnx/resolve/6888903da215c7735f51101d939f3bfa679fb2b8/'
    for name,digest in pins.items():
        if 'encoder' in name:
            fetch(base+name,original/name,'2cac62d0c270bd128f898f2be1a2d34780d524a6e9483888ebac7b00f97410f1')
            model=onnx.load(str(original/name),load_external_data=False)
            used={n.domain for n in model.graph.node}|{''}
            for function in model.functions:used|={n.domain for n in function.node}|{function.domain}
            kept=[o for o in model.opset_import if o.domain in used]
            del model.opset_import[:];model.opset_import.extend(kept);onnx.save(model,str(a3/name))
            if sha(a3/name)!=digest:raise ValueError('A3 serialization differs from contest pin; do not run unpinned model')
        else:fetch(base+name,a3/name,digest)
    sys.path.insert(0,str(REPO/'tools'))
    from provision_nemotron import SOURCE,patch_ir_version,PATCHED_MODEL_SHA256,ONNX_REV,LITERT_REV
    c2=owned(LOCAL/'baseline/c2')
    for name,(url,digest) in SOURCE.items():fetch(url,c2/name,digest)
    patch_ir_version(c2/'model.int8.onnx',c2/'model.int8.ir9.onnx')
    if sha(c2/'model.int8.ir9.onnx')!=PATCHED_MODEL_SHA256:raise ValueError('C2 model pin mismatch')
    (c2/'CHANGES.txt').write_bytes((f'model.int8.ir9.onnx is model.int8.onnx from joosthel/Nemotron-3-Diarization-ONNX@{ONNX_REV} with the ONNX IR version byte changed from 10 to 9.\n'
        f'mel_filters.bin, hann400.bin and silence_embeds.bin come from litert-community/Nemotron-3-Diarization-LiteRT@{LITERT_REV}.\n').encode('utf-8'))
    write_json(LOCAL/'baseline/provenance.json',dict(onnx=onnx.__version__,a3={n:sha(a3/n) for n in pins},c2_model=sha(c2/'model.int8.ir9.onnx'),
        transformations='Existing repository opset removal and IR10->9 conversion only; bytes must equal pinned app files'))
    print('PINNED BASELINE READY')
