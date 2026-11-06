"""Kotlin NemotronDiarizer.binarize vs Python binarize on the same saved logits and parameters (all 62 files)."""
import argparse
from pathlib import Path

import numpy as np

from postprocess import binarize, SPK


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--logits', type=Path, required=True)
    ap.add_argument('--kotlin', type=Path, required=True, help='DumpLogits output with *.pp.tsv')
    ap.add_argument('--params', type=Path, required=True)
    a = ap.parse_args()
    p = {k: float(v) for k, v in (x.split('=') for x in a.params.read_text().split())}
    files = sorted(a.logits.glob('*.logits.f32'))
    turns = 0
    for f in files:
        name = f.name.removesuffix('.logits.f32')
        py = binarize(np.fromfile(f, dtype='<f4').reshape(-1, SPK), **p)
        kt = [(float(a_), float(b_), int(s)) for a_, b_, s in (x.split('\t') for x in (a.kotlin / f'{name}.pp.tsv').read_text().splitlines())]
        assert len(py) == len(kt), (name, len(py), len(kt))
        for (pa, pb, ps), (ka, kb, ks) in zip(py, kt):
            assert ps == ks and abs(pa - ka) < 1e-4 and abs(pb - kb) < 1e-4, (name, (pa, pb, ps), (ka, kb, ks))
        turns += len(py)
    print(f'PARITY OK: {len(files)} files, {turns} turns, |dt| < 0.1 ms')


if __name__ == '__main__':
    main()
