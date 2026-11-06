"""Frozen PRODUCT post-processing vs RAW on recordings never used for tuning (reference.json schema v1).

Veche clips: scripted human Russian meetings with overlap (CC-BY-4.0). syn3/syn4: TTS dialogues whose
reference intervals include pauses (coarse), so their miss is inflated for every system alike.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from postprocess import RAW, SPK, aggregate, binarize, score


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pairs', nargs='+', required=True, help='name=logits.f32::reference.json')
    ap.add_argument('--params', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    best = {k: float(v) for k, v in (x.split('=') for x in a.params.read_text().split())}
    rows = []
    for pair in a.pairs:
        name, rest = pair.split('=', 1)
        lf, rf = rest.split('::')
        ref_json = json.loads(Path(rf).read_text(encoding='utf-8'))
        ref = [(d['start_ms'] / 1000, d['end_ms'] / 1000, d['speaker_id']) for d in ref_json['diarization']]
        l = np.fromfile(lf, dtype='<f4').reshape(-1, SPK)
        r = {c: dict(raw=score(ref, binarize(l, **RAW), l.shape[0], c), pp=score(ref, binarize(l, **best), l.shape[0], c)) for c in (0.0, 0.25)}
        rows.append(dict(name=name, kind=ref_json.get('kind', ref_json.get('annotation_source', '')), **{str(c): v for c, v in r.items()}))
        for c in (0.0, 0.25):
            ra, pa = aggregate([r[c]['raw']]), aggregate([r[c]['pp']])
            print(f"{name:24s} collar={c}: DER {ra['DER']:6.2f} -> {pa['DER']:6.2f}  (miss {ra['miss']:.1f}->{pa['miss']:.1f}, fa {ra['fa']:.1f}->{pa['fa']:.1f},"
                  f" conf {ra['conf']:.1f}->{pa['conf']:.1f}); speakers ref {r[c]['raw']['n_ref']} hyp {r[c]['raw']['n_hyp']}->{r[c]['pp']['n_hyp']}")
    a.out.write_text(json.dumps(dict(scope='HOST_C2_INT8_EXTERNAL_NOT_TUNED_ON', params=best, files=rows), indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
