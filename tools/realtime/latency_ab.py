"""Summarize on-device live A/B runs (RealtimeDeviceTest metrics.json) for text latency.

latency = time the phrase text was published minus the end of that phrase's audio window, on a paced
replay of the same fixture (not a microphone). Reported per run and pooled per mode.
"""
import argparse
import json
import statistics
from pathlib import Path


def pct(values, q):
    v = sorted(values)
    if not v:
        return None
    k = (len(v) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', type=Path, required=True)
    ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    rows, pooled = [], {}
    for f in sorted(a.runs.glob('*.json')):
        label = f.stem
        mode = label.split('-')[1]
        m = json.loads(f.read_text(encoding='utf-8-sig'))
        lat = [p['latency_from_audio_end_ms'] for p in m['phrases'] if p.get('latency_from_audio_end_ms') is not None]
        first = min((p['display_at_ms'] for p in m['phrases']), default=None)
        r = dict(run=label, mode=mode, state=m.get('state'), test=m.get('test_status'), pacing=m.get('pacing_valid'),
                 phrases=len(lat), p50=pct(lat, .5), p95=pct(lat, .95), max=max(lat) if lat else None,
                 first_text_ms=first, load_ms=m.get('native_load_ms'), asr_ms=m.get('asr_ms'), c2_ms=m.get('c2_ms'),
                 finalization_ms=m.get('finalization_ms'), rtf=m.get('compute_rtf'), max_lag_ms=m.get('max_lag_ms'),
                 separate_c2=m.get('separate_c2_thread'), silence_ms=m.get('silence_ms'), max_phrase_ms=m.get('max_phrase_ms'),
                 c2_steps=len(m.get('diarization_steps', [])))
        rows.append(r)
        pooled.setdefault(mode, []).extend(lat)
        print(f"{label:5s} {r['state']:<22} phrases {r['phrases']:2d}  p50 {r['p50']:6.0f}  p95 {r['p95']:6.0f}  max {r['max']:6.0f} ms"
              f"  first text {r['first_text_ms']} ms (load {r['load_ms']})  final {r['finalization_ms']} ms  rtf {r['rtf']:.2f}"
              f"  thread={r['separate_c2']} pause={r['silence_ms']} maxPhrase={r['max_phrase_ms']}")
    summary = {mode: dict(n=len(v), p50=pct(v, .5), p95=pct(v, .95), max=max(v), mean=statistics.mean(v)) for mode, v in pooled.items()}
    for mode, s in sorted(summary.items()):
        print(f"POOLED {mode}: {s['n']} phrases  p50 {s['p50']:.0f}  p95 {s['p95']:.0f}  max {s['max']:.0f}  mean {s['mean']:.0f} ms")
    if a.out:
        a.out.write_text(json.dumps(dict(scope='HONOR_PACED_REPLAY_SYN3_NOT_MICROPHONE', runs=rows, pooled=summary),
                                    ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
