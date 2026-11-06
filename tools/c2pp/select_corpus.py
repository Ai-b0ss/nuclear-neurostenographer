"""Deterministic, speaker-disjoint dev/test selection from mexus/ru-book-mix-10h (CC-BY-4.0).

Dev is used to tune C2 post-processing; test is never used for tuning. The six recordings of the
earlier frozen consensus holdout stay in test, and the three earlier development clips are excluded.
Selection uses only manifest metadata (speaker ids, counts), never audio, RTTM or model output.
"""
import argparse
import hashlib
import json
from pathlib import Path

SEED = 'NN-C2-POSTPROCESS-20261106-V1'
FROZEN_TEST = ['rec_0259', 'rec_0129', 'rec_0388', 'rec_0345', 'rec_0528', 'rec_0514']
EXCLUDED = ['rec_0150', 'rec_0300', 'rec_0437']
PER_COUNT = 10


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    rows = [json.loads(x) for x in a.manifest.read_text(encoding='utf-8').splitlines() if x.strip()]
    by_id = {r['file_id']: r for r in rows}
    spk = lambda r: set(r['speakers'].values())
    test = list(FROZEN_TEST)
    test_spk = set().union(*(spk(by_id[x]) for x in FROZEN_TEST))
    order = sorted((r for r in rows if r['n_speakers'] in (2, 3, 4) and r['file_id'] not in FROZEN_TEST + EXCLUDED),
                   key=lambda r: hashlib.sha256((SEED + r['file_id']).encode()).hexdigest())
    # Partition SPEAKERS first (frozen-test speakers forced to test), then a recording belongs to a side
    # only if all of its voices do. Among 2000 deterministic partitions keep the most balanced one.
    import random
    rng = random.Random(SEED)
    free = sorted(set().union(*(spk(r) for r in order)) - test_spk)
    best = None
    for _ in range(2000):
        side = {s: rng.random() < 0.5 for s in free}  # True = dev
        dev_side = {s for s, d in side.items() if d}
        test_side = (set(free) - dev_side) | test_spk
        dn = {n: [r for r in order if r['n_speakers'] == n and spk(r) <= dev_side] for n in (2, 3, 4)}
        tn = {n: [r for r in order if r['n_speakers'] == n and spk(r) <= test_side] for n in (2, 3, 4)}
        score = min(min(len(v), PER_COUNT) for v in list(dn.values()) + list(tn.values()))
        if best is None or score > best[0]:
            best = (score, dn, tn)
    _, dn, tn = best
    dev = [r['file_id'] for n in (2, 3, 4) for r in dn[n][:PER_COUNT]]
    test += [r['file_id'] for n in (2, 3, 4) for r in tn[n][:PER_COUNT]]
    dev_spk = set().union(*(spk(by_id[x]) for x in dev))
    test_spk = set().union(*(spk(by_id[x]) for x in test))
    print('per count: dev', {n: min(len(v), PER_COUNT) for n, v in dn.items()},
          'test', {n: min(len(v), PER_COUNT) for n, v in tn.items()})
    assert not dev_spk & test_spk and len(dev) >= 24 and len(test) >= 24 + len(FROZEN_TEST)
    pick = lambda ids: [dict(file_id=i, shard=by_id[i]['shard'], n_speakers=by_id[i]['n_speakers'],
                             overlap2=round(by_id[i]['overlap_stats']['overlap2'], 4)) for i in ids]
    a.out.write_text(json.dumps(dict(seed=SEED, dataset='https://huggingface.co/datasets/mexus/ru-book-mix-10h',
        license='CC-BY-4.0', scope='SYNTHETIC_RUSSIAN_AUDIOBOOK_MIX_NOT_NATURAL_CONVERSATION',
        manifest_sha256=hashlib.sha256(a.manifest.read_bytes()).hexdigest(),
        rule='sha256(seed+file_id) order; dev first, speakers of frozen test excluded; test speakers disjoint from dev',
        dev=pick(dev), test=pick(test)), indent=1), encoding='utf-8')
    print('dev', len(dev), 'test', len(test), 'speakers dev/test', len(dev_spk), len(test_spk))


if __name__ == '__main__':
    main()
