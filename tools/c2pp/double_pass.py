"""Second C2 pass: does it beat the single pass + post-processing (PRODUCT)?

Variants (all from the product NemotronDiarizer code, host int8):
  fwd       one forward pass (current product)
  warm      second forward pass starting from the speaker cache pass 1 ended with
  fwd+rev   forward pass fused with a pass over time-reversed audio (speaker slots aligned by Hungarian
            matching on co-activity, probabilities averaged)
  warm+rev  the same with the warm pass
Each is scored with the frozen PRODUCT post-processing and with post-processing re-tuned on dev only;
test is touched once per variant after its parameters are frozen.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

from postprocess import KEYS, SPK, aggregate, binarize, load_rttm, score

SEED = 20261107


def sigmoid(x):
    return 1 / (1 + np.exp(-x.astype(np.float64)))


def fuse(a, b):
    pa, pb = sigmoid(a), sigmoid(b)
    sim = pa.T @ pb  # [8, 8] co-activity
    ri, ci = linear_sum_assignment(-sim)
    pb = pb[:, ci[np.argsort(ri)]]
    p = np.clip((pa + pb) / 2, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p)).astype(np.float32)


def load_variant(passes, name, variant):
    get = lambda k: np.fromfile(passes / f'{name}.{k}.f32', dtype='<f4').reshape(-1, SPK)
    if variant == 'fwd':
        return get('logits')
    if variant == 'warm':
        return get('warm')
    if variant == 'fwd+rev':
        return fuse(get('logits'), get('rev'))
    if variant == 'warm+rev':
        return fuse(get('warm'), get('rev'))
    raise ValueError(variant)


def evaluate(items, p, collar=0.0, until=None):
    rows = []
    for l, ref in items:
        hyp = binarize(l, **p)
        if until is not None:  # restrict both to [0, until) seconds
            T = min(l.shape[0], int(until * 100))
            cut = lambda ts: [(a, min(b, until), s) for a, b, s in ts if a < until]
            rows.append(score(cut(ref), cut(hyp), T, collar))
        else:
            rows.append(score(ref, hyp, l.shape[0], collar))
    return aggregate(rows)


def tune(items, n):
    rng = np.random.default_rng(SEED)
    best = None
    for _ in range(n):
        onset = float(rng.choice([0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.7]))
        p = dict(onset=onset, offset=round(onset - float(rng.choice([0, 0.05, 0.1, 0.15, 0.2])), 3),
                 ov_onset=round(onset - float(rng.choice([0, 0.05, 0.1, 0.15, 0.2, 0.25])), 3),
                 pad_on=float(rng.choice([0, 0.02, 0.05, 0.1])), pad_off=float(rng.choice([0, 0.02, 0.05, 0.1])),
                 min_on=float(rng.choice([0, 0.08, 0.16, 0.24, 0.3])), min_off=float(rng.choice([0, 0.08, 0.16, 0.24, 0.4])))
        d = evaluate(items, p)['DER']
        if best is None or d < best[0]:
            best = (d, p)
    return best[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--selection', type=Path, required=True)
    ap.add_argument('--data', type=Path, required=True)
    ap.add_argument('--passes', type=Path, required=True)
    ap.add_argument('--product', type=Path, required=True)
    ap.add_argument('--external', nargs='*', default=[], help='name::reference.json')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--trials', type=int, default=200)
    a = ap.parse_args()
    product = {k: float(v) for k, v in (x.split('=') for x in a.product.read_text().split())}
    sel = json.loads(a.selection.read_text(encoding='utf-8'))
    ext = []
    for e in a.external:
        name, rf = e.split('::')
        ref = json.loads(Path(rf).read_text(encoding='utf-8'))
        ext.append((name, [(d['start_ms'] / 1000, d['end_ms'] / 1000, d['speaker_id']) for d in ref['diarization']]))
    report = {}
    for variant in ['fwd', 'warm', 'fwd+rev', 'warm+rev']:
        items = lambda split: [(load_variant(a.passes, r['file_id'], variant), load_rttm(a.data / f"{r['file_id']}.rttm")) for r in sel[split]]
        dev, test = items('dev'), items('test')
        tuned = tune(dev, a.trials)
        ex = [(load_variant(a.passes, n, variant), ref) for n, ref in ext]
        r = dict(tuned=tuned,
                 dev_product=evaluate(dev, product), dev_tuned=evaluate(dev, tuned),
                 test_product=evaluate(test, product), test_tuned=evaluate(test, tuned),
                 test_product_first30=evaluate(test, product, until=30.0),
                 external_product={n: evaluate([it], product) for (n, _), it in zip(ext, ex)})
        report[variant] = r
        f = lambda d: f"DER {d['DER']:.2f} (miss {d['miss']:.2f} fa {d['fa']:.2f} conf {d['conf']:.2f}) spk {d['spk_count_acc']:.0f}%"
        print(f'== {variant}')
        print('  test PRODUCT pp :', f(r['test_product']))
        print('  test tuned pp   :', f(r['test_tuned']), ' tuned on dev:', tuned)
        print('  test first 30 s :', f(r['test_product_first30']))
        print('  external        :', '; '.join(f"{n} {d['DER']:.2f}/conf {d['conf']:.2f}" for n, d in r['external_product'].items()))
    a.out.write_text(json.dumps(dict(scope='HOST_C2_INT8_SYNTHETIC_AND_VECHE_NOT_PHONE', seed=SEED, report=report), indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
