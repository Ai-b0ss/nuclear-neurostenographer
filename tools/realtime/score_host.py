"""Score saved native replay, never pass reference labels to inference.

Exit 1 is a visible FAST speaker-count regression, not a harness failure.
DER uses the same coarse TTS intervals/collar as the original HONOR report.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from score_clip_run import clamp_reference
from score_transcript import der


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('reference', type=Path)
    args = parser.parse_args()
    reference = clamp_reference(json.loads(args.reference.read_text(encoding='utf-8')))
    inputs = json.loads((args.folder / 'inputs.json').read_text(encoding='utf-8'))
    if inputs['fixture_sha256'] != reference['audio_sha256']:
        raise SystemExit('Fixture/reference hash mismatch')
    expected = len({s['speaker_id'] for s in reference['diarization']})
    rows = {}
    for path in sorted(args.folder.glob('*.tsv')):
        if path.stem.endswith('-trace'):
            continue
        turns = []
        for line in path.read_text().splitlines():
            start, end, speaker = line.split('\t')
            end = min(int(end), reference['audio_duration_ms'])
            if end > int(start):
                turns.append(dict(start_ms=int(start), end_ms=end, speaker_id=speaker))
        count = len({s['speaker_id'] for s in turns})
        rows[path.stem] = dict(speakers=count, reference_speakers=expected,
            speaker_count_gate='PASS' if count == expected else 'FAIL',
            der=der(reference['diarization'], turns, reference['audio_duration_ms'], 250, False),
            turns_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    report = dict(scope='HOST_C2_ONLY_COARSE_TTS_NOT_HUMAN_GOLD',
        reference_sha256=hashlib.sha256(args.reference.read_bytes()).hexdigest(), results=rows)
    (args.folder / 'scores.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    for name, row in rows.items():
        print(name, row['speaker_count_gate'], row['speakers'], round(row['der']['rate'] * 100, 3))
    raise SystemExit(0 if rows['fast']['speaker_count_gate'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
