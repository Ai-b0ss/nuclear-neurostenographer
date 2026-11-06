"""Independent analysis of saved device exports; missing metrics never imply PASS."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from score_clip_run import clamp_reference, hypothesis_from_export
from score_transcript import evaluate


def percentile(values, q):
    if not values:
        return None
    values = sorted(values)
    pos = (len(values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(values) - 1)
    return round(values[lo] + (values[hi] - values[lo]) * (pos - lo), 3)


def analyze(folder, references):
    run = json.loads((folder / 'run.json').read_text(encoding='utf-8'))
    row = {'run': folder.name, 'instrumentation': run['status'], 'method': run['method']}
    path = folder / 'metrics.json'
    if not path.exists():
        return dict(row, inference='NOT_RUN_OR_MISSING_EVIDENCE')
    metrics = json.loads(path.read_text(encoding='utf-8'))
    row.update({k: metrics.get(k) for k in ['state', 'audio_ms', 'elapsed_ms', 'native_load_ms', 'asr_ms', 'c2_ms', 'vad_ms',
                                         'compute_rtf', 'cpu_ms', 'max_lag_ms', 'fallback', 'silence_ms', 'pcm_exact',
                                         'pacing_valid', 'max_feed_lateness_ms', 'sampled_pss_kb', 'recognizer_loads']})
    for phase, values in [('asr_latency', [p['latency_from_audio_end_ms'] for p in metrics['phrases'] if p.get('latency_from_audio_end_ms') is not None]),
                          ('c2_step', [s['process_ms'] for s in metrics['diarization_steps']])]:
        row[phase + '_count'] = len(values)
        row[phase + '_p50_ms'] = percentile(values, 0.5)
        row[phase + '_p95_ms'] = percentile(values, 0.95)
    row['e2e_wall_rtf'] = round(metrics['elapsed_ms'] / metrics['audio_ms'], 5)
    row['cpu_core_equivalent'] = round(metrics['cpu_ms'] / metrics['elapsed_ms'], 4)
    monitor = json.loads((folder / 'monitor.json').read_text(encoding='utf-8'))
    pss = [int(n) for item in monitor for n in re.findall(r'^Pss:\s*(\d+)', item['meminfo'], re.M)]
    row['kernel_sampled_peak_pss_kb'] = max(pss) if pss else None
    temps = [int(n) / 10 for item in monitor for n in re.findall(r'^\s*temperature:\s*(\d+)', item['battery'], re.M)]
    row['battery_c_minmax'] = [min(temps), max(temps)] if temps else None
    export = json.loads((folder / 'transcript.json').read_text(encoding='utf-8'))
    row['speakers'] = len({s['speaker_id'] for s in export['segments'] if s['speaker_id'] is not None})
    row['unknown_segments'] = sum(s['speaker_id'] is None for s in export['segments'])
    reference_path = references / (metrics['clip'] + '.reference.json')
    if reference_path.exists():
        ref = clamp_reference(json.loads(reference_path.read_text(encoding='utf-8')))
        if ref['audio_sha256'] != metrics['fixture_sha256']:
            raise ValueError('Fixture/reference identity mismatch: ' + folder.name)
        hyp = hypothesis_from_export(export, ref)
        if 'diarization_turns' in metrics:
            hyp['diarization'] = metrics['diarization_turns']
        score = evaluate(ref, hyp, collar_ms=250)
        score.update(scope='SYNTHETIC_TTS_NOT_NATURAL_HUMAN_ANNOTATIONS',
                     export_sha256=hashlib.sha256((folder / 'transcript.json').read_bytes()).hexdigest())
        (folder / 'independent-score.json').write_text(json.dumps(score, ensure_ascii=False, indent=2), encoding='utf-8')
        row['wer'] = score['wer']; row['cpwer'] = score['cpwer']; row['der'] = score['der']
        row['reference_speakers'] = len({s['speaker_id'] for s in ref.get('diarization', ref.get('text_segments', []))})
    row['timing_validity'] = 'PACED_CONFIRMED' if metrics.get('pacing_valid') is True else 'UNVERIFIED'
    return row


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--evidence', type=Path, default=ROOT / 'docs/evidence/realtime-honor-20261105')
    p.add_argument('--references', type=Path, default=Path('C:/Users/user/Documents/nuclear-neurostenographer/.local/synthetic-ru'))
    a = p.parse_args()
    rows = [analyze(f, a.references) for f in sorted(a.evidence.iterdir()) if f.is_dir() and (f / 'run.json').exists()]
    (a.evidence / 'summary.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    for row in rows:
        print(json.dumps({k: row.get(k) for k in ['run', 'instrumentation', 'state', 'compute_rtf', 'asr_latency_p50_ms',
            'asr_latency_p95_ms', 'speakers', 'timing_validity']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
