"""Warm second C2 pass with the speaker-count guard (0.3.10, NemotronDiarizer.chooseWarm).

The warm turns are used only if they have at least as many speakers as the first pass.
Scores fwd / warm / guard on the dev/test split with the frozen PRODUCT post-processing, from the
cached host logits of tools/c2pp/run_host.py --passes warm (Windows host, int8, not the phone).

  python -X utf8 tools/c2pp/warm_guard.py --passes <logits dir> --data <ru-book-mix dir> --out <json>
"""
import argparse
import json
from pathlib import Path

import numpy as np

from postprocess import aggregate, binarize, load_rttm, score

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / 'docs/evidence/c2-postprocess-20261106'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--passes', type=Path, required=True)
    ap.add_argument('--data', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    params = {k: float(v) for k, v in (x.split('=') for x in (EV / 'best.properties').read_text().split())}
    sel = json.loads((EV / 'selection.json').read_text(encoding='utf-8'))
    get = lambda n, k: np.fromfile(a.passes / f'{n}.{k}.f32', dtype='<f4').reshape(-1, 8)
    nspk = lambda t: len({s for _, _, s in t})
    report = {}
    for split in ['dev', 'test']:
        rows = {'fwd': [], 'warm': [], 'guard': []}
        fallbacks = []
        for r in sel[split]:
            n = r['file_id']
            ref = load_rttm(a.data / f'{n}.rttm')
            f, w = get(n, 'logits'), get(n, 'warm')
            hf, hw = binarize(f, **params), binarize(w, **params)
            hg = hw if nspk(hw) >= nspk(hf) else hf
            if hg is hf:
                fallbacks.append(dict(file=n, first_pass_speakers=nspk(hf), warm_speakers=nspk(hw), reference_speakers=nspk(ref)))
            for k, h in (('fwd', hf), ('warm', hw), ('guard', hg)):
                rows[k].append(score(ref, h, f.shape[0], 0.0))
        report[split] = dict({k: aggregate(v) for k, v in rows.items()}, fallbacks=fallbacks)
        for k in rows:
            d = report[split][k]
            print(f"{split:4s} {k:5s} DER {d['DER']:.2f} conf {d['conf']:.2f} speakers {d['spk_count_acc']:.0f}%")
        print(f'{split:4s} fallbacks: {fallbacks}')
    a.out.write_text(json.dumps(dict(scope='HOST_C2_INT8_NOT_PHONE', collar=0.0, report=report), indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
