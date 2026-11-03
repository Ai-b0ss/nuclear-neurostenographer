# C0 clustering-threshold sweep (host, synthetic tracks)

Host runs of the real pyannote + ERes2Net pipeline on synthetic 2-4 voice tracks
(`tools/run_threshold_sweep.py`, one JVM per file, `tools/analyze_threshold_sweep.py`).
Synthetic data is diagnostic only, not evidence of quality on live meetings.

| Threshold | Tune (48) exact | over/under | Holdout (51) exact | over/under | Holdout mean abs error |
|---:|---:|---:|---:|---:|---:|
| 0.80 | 46% | 22 / 4 | 45% | 26 / 2 | 0.75 |
| 0.85 | 54% | 17 / 5 | 61% | 16 / 4 | 0.53 |
| 0.90 | 60% | 12 / 7 | 75% | 9 / 4 | 0.28 |
| 0.95 | 73% | 1 / 12 | not run | | |

Holdout at 0.90 by speaker count: 2 voices 18/28, 3 voices 15/15, 4 voices 5/8.
Mean speaker-confusion share of reference speech stays ~8-10% at every threshold.

Conclusion: no single threshold fixes C0. Higher values reduce over-splitting but
merge real speakers (the actor D/M/D clip collapses to one speaker at 0.90; both
actor clips pass at 0.85). A threshold change is a trade-off, not a fix; the
decision moves to the C2 (Nemotron) comparison on the physical HONOR.
