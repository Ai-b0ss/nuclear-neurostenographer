"""C2 post-processing: tune on dev, evaluate once on speaker-disjoint test.

binarize() is the team notebook's section-9 algorithm (hysteresis onset/offset, lower onset for a second
voice during confident speech, padding, min segment, short-gap merge), evaluated in logit space exactly like
NemotronDiarizer.binarize in Kotlin. DER is frame-based (10 ms) with optimal one-to-one speaker mapping,
overlap counted, no reference forced into inference. Reported at collar 0 and 250 ms (the earlier scorer's).
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

FRAME = 0.01
SPK = 8
SEED = 20261106
KEYS = ['onset', 'offset', 'ov_onset', 'pad_on', 'pad_off', 'min_on', 'min_off']
RAW = dict(onset=0.5, offset=0.5, ov_onset=0.5, pad_on=0.0, pad_off=0.0, min_on=0.0, min_off=0.0)


def logit(p):
    return np.float32(0.0) if p == 0.5 else np.float32(math.log(np.float32(p) / (np.float32(1) - np.float32(p))))


def binarize(l, onset, offset, ov_onset, pad_on, pad_off, min_on, min_off):
    """l: float32 [T, 8] logits -> list of (start_s, end_s, speaker)."""
    T = l.shape[0]
    on, ov, low = logit(onset), logit(ov_onset), logit(min(offset, onset, ov_onset))
    hi_main = l > on
    other = hi_main.sum(1, keepdims=True) - hi_main
    hi = np.where(other > 0, l > ov, hi_main)
    lo = (l > low) | hi
    # Integer milliseconds (as in Kotlin), so merge/min-duration decisions cannot flip on rounding.
    ms = lambda sec: int(math.floor(np.float32(sec) * 1000.0 + 0.5))
    fm = ms(FRAME)
    pad_on, pad_off, min_off, min_on = ms(pad_on), ms(pad_off), ms(min_off), max(ms(min_on), 1)
    out = []
    for s in range(l.shape[1]):
        x = np.concatenate([[0], lo[:, s].astype(np.int8), [0]])
        starts, ends = np.flatnonzero(np.diff(x) == 1), np.flatnonzero(np.diff(x) == -1)
        merged = []
        for a, b in zip(starts, ends):
            if hi[a:b, s].any():
                seg = [max(0, int(a) * fm - pad_on), min(T * fm, int(b) * fm + pad_off)]
                if merged and seg[0] - merged[-1][1] <= min_off:
                    merged[-1][1] = max(merged[-1][1], seg[1])
                else:
                    merged.append(seg)
        out += [(a / 1000, b / 1000, s) for a, b in merged if b - a >= min_on]
    return sorted(out, key=lambda t: (t[0], t[2]))


def load_rttm(path):
    rows = []
    for line in path.read_text(encoding='utf-8').splitlines():
        f = line.split()
        if f and f[0] == 'SPEAKER':
            rows.append((float(f[3]), float(f[3]) + float(f[4]), f[7]))
    return rows


def matrix(turns, T, labels=None):
    labels = labels or sorted({t[2] for t in turns})
    m = np.zeros((T, max(len(labels), 1)), bool)
    for a, b, s in turns:
        i, j = int(round(a / FRAME)), min(T, int(round(b / FRAME)))
        if j > i:
            m[i:j, labels.index(s)] = True
    return m


def score(ref, hyp, T, collar):
    R, H = matrix(ref, T), matrix(hyp, T)
    co = R.T.astype(np.int64) @ H.astype(np.int64)
    ri, hi = linear_sum_assignment(-co)
    keep = np.ones(T, bool)
    if collar > 0:
        c = int(round(collar / FRAME))
        for a, b, _ in ref:
            for edge in (int(round(a / FRAME)), int(round(b / FRAME))):
                keep[max(0, edge - c):min(T, edge + c)] = False
    nr, nh = R.sum(1), H.sum(1)
    correct = np.zeros(T, np.int64)
    for r, h in zip(ri, hi):
        correct += R[:, r] & H[:, h]
    ov = nr >= 2
    k = keep
    d = dict(total=int(nr[k].sum()), miss=int(np.maximum(nr - nh, 0)[k].sum()), fa=int(np.maximum(nh - nr, 0)[k].sum()),
             conf=int((np.minimum(nr, nh) - correct)[k].sum()), total_ov=int(nr[k & ov].sum()),
             err_ov=int((np.maximum(nr - nh, 0) + np.maximum(nh - nr, 0) + np.minimum(nr, nh) - correct)[k & ov].sum()),
             n_ref=R.shape[1], n_hyp=len({t[2] for t in hyp}))
    return d


def aggregate(rows):
    tot = sum(r['total'] for r in rows)
    err = sum(r['miss'] + r['fa'] + r['conf'] for r in rows)
    return dict(DER=100 * err / tot, miss=100 * sum(r['miss'] for r in rows) / tot, fa=100 * sum(r['fa'] for r in rows) / tot,
                conf=100 * sum(r['conf'] for r in rows) / tot,
                DER_ov=100 * sum(r['err_ov'] for r in rows) / max(1, sum(r['total_ov'] for r in rows)),
                spk_count_acc=100 * sum(r['n_ref'] == r['n_hyp'] for r in rows) / len(rows), files=len(rows))


def evaluate(items, params, collar):
    return aggregate([score(ref, binarize(l, **params), l.shape[0], collar) for l, ref in items])


def load(data, logits, ids):
    items = []
    for i in ids:
        l = np.fromfile(logits / f'{i}.logits.f32', dtype='<f4').reshape(-1, SPK)
        items.append((l, load_rttm(data / f'{i}.rttm')))
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--selection', type=Path, required=True)
    ap.add_argument('--data', type=Path, required=True)
    ap.add_argument('--logits', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--trials', type=int, default=400)
    a = ap.parse_args()
    sel = json.loads(a.selection.read_text(encoding='utf-8'))
    dev = load(a.data, a.logits, [r['file_id'] for r in sel['dev']])
    rng = np.random.default_rng(SEED)
    trials = []
    for i in range(a.trials):
        onset = float(rng.choice([0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.7]))
        p = dict(onset=onset, offset=round(onset - float(rng.choice([0, 0.05, 0.1, 0.15, 0.2])), 3),
                 ov_onset=round(onset - float(rng.choice([0, 0.05, 0.1, 0.15, 0.2, 0.25])), 3),
                 pad_on=float(rng.choice([0, 0.02, 0.05, 0.1])), pad_off=float(rng.choice([0, 0.02, 0.05, 0.1])),
                 min_on=float(rng.choice([0, 0.08, 0.16, 0.24, 0.3])), min_off=float(rng.choice([0, 0.08, 0.16, 0.24, 0.4])))
        if i == 0:
            p = dict(RAW)
        r = evaluate(dev, p, 0.0)
        trials.append(dict(p, **r))
    trials.sort(key=lambda t: t['DER'])
    best = {k: trials[0][k] for k in KEYS}
    # Test is touched exactly once, after the parameters are frozen.
    test = load(a.data, a.logits, [r['file_id'] for r in sel['test']])
    report = dict(scope='HOST_C2_INT8_SYNTHETIC_RU_BOOK_MIX_NOT_PHONE_NOT_NATURAL', trials=a.trials, seed=SEED,
                  objective='dev DER collar 0', best=best, top5_dev=trials[:5],
                  dev={c: dict(raw=evaluate(dev, RAW, c), best=evaluate(dev, best, c)) for c in (0.0, 0.25)},
                  test={c: dict(raw=evaluate(test, RAW, c), best=evaluate(test, best, c)) for c in (0.0, 0.25)},
                  per_test_file=[dict(file_id=r['file_id'], n=r['n_speakers'],
                                      raw=score(ref, binarize(l, **RAW), l.shape[0], 0.0),
                                      best=score(ref, binarize(l, **best), l.shape[0], 0.0))
                                 for r, (l, ref) in zip(sel['test'], test)],
                  code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / 'result.json').write_text(json.dumps(report, indent=1, default=float), encoding='utf-8')
    (a.out / 'best.properties').write_text(''.join(f'{k}={best[k]}\n' for k in KEYS), encoding='utf-8')
    print('best', best)
    for split in ('dev', 'test'):
        for c in (0.0, 0.25):
            r = report[split][c]
            print(f"{split} collar={c}: RAW DER {r['raw']['DER']:.2f} (miss {r['raw']['miss']:.2f} fa {r['raw']['fa']:.2f} conf {r['raw']['conf']:.2f}, ov {r['raw']['DER_ov']:.2f})"
                  f" -> PP DER {r['best']['DER']:.2f} (miss {r['best']['miss']:.2f} fa {r['best']['fa']:.2f} conf {r['best']['conf']:.2f}, ov {r['best']['DER_ov']:.2f});"
                  f" spk-count {r['raw']['spk_count_acc']:.0f}% -> {r['best']['spk_count_acc']:.0f}%")


if __name__ == '__main__':
    main()
