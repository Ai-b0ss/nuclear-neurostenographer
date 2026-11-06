"""Does post-processing change what audio reaches ASR? Host check without a phone.

Mirrors DiarizationTimeline.speechWindowsOf: turns (all speakers) merged when the gap is < 500 ms; each
window is ASR input. Reports audio covered by RAW windows that PRODUCT windows no longer cover (speech
that would no longer be transcribed), and extra audio PRODUCT adds.
"""
import argparse
from pathlib import Path

import numpy as np

from postprocess import RAW, SPK, binarize

MERGE_GAP_MS = 500


def windows(turns):
    spans = []
    for a, b, _ in sorted((round(a * 1000), round(b * 1000), s) for a, b, s in turns):
        if spans and a - spans[-1][1] < MERGE_GAP_MS:
            spans[-1][1] = max(spans[-1][1], b)
        else:
            spans.append([a, b])
    return spans


def mask(spans, n):
    m = np.zeros(n, bool)
    for a, b in spans:
        m[a:b] = True
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--logits', type=Path, nargs='+', required=True)
    ap.add_argument('--params', type=Path, required=True)
    a = ap.parse_args()
    best = {k: float(v) for k, v in (x.split('=') for x in a.params.read_text().split())}
    lost_total = added_total = raw_total = 0
    worst = []
    for f in a.logits:
        l = np.fromfile(f, dtype='<f4').reshape(-1, SPK)
        n = l.shape[0] * 10
        r, p = mask(windows(binarize(l, **RAW)), n), mask(windows(binarize(l, **best)), n)
        lost, added = int((r & ~p).sum()), int((p & ~r).sum())
        lost_total += lost; added_total += added; raw_total += int(r.sum())
        worst.append((lost, f.name.removesuffix('.logits.f32'), len(windows(binarize(l, **RAW))), len(windows(binarize(l, **best)))))
    worst.sort(reverse=True)
    print(f'files {len(a.logits)}; RAW window audio {raw_total / 1000:.1f} s; no longer sent to ASR {lost_total} ms '
          f'({100 * lost_total / raw_total:.3f}%); newly sent {added_total} ms')
    for lost, name, nr, npp in worst[:6]:
        print(f'  {name}: lost {lost} ms, windows {nr} -> {npp}')


if __name__ == '__main__':
    main()
