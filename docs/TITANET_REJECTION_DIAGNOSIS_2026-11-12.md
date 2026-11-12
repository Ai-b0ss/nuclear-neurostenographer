# TitaNet rejection diagnosis, 12 November 2026

The original 20-recording oracle test reproduces exactly: 14/60 admitted,
42 agreement rejections and 4 insufficient samples. WAV and FLAC samples
are identical. The pinned TitaNet model and thresholds were not changed.

| Extraction | Initial 20 files, 60 profiles |
| --- | ---: |
| Current two samples, each at most 8 s | 14 admitted |
| Longest contiguous run in each temporal half | 6 admitted |
| Remove 80 ms near ownership boundaries | 16 admitted |
| Two samples, each at most 16 s | 28 admitted |

The fragmentation hypothesis did not improve results. Increasing evidence
duration is a useful candidate; it is not proof that duration is the only cause.

On 66 other cached files (initial recording IDs excluded), longer evidence
admitted 73/81 versus 33/81. Accepted pairwise verification has 48/48
same-source pairs above .84 and 0/2580 different-source pairs above .84.
These recordings were previously evaluated in this project and may share
source voices with the initial test. This is corroboration, not an untouched
holdout or independent population safety estimate.

A replay of cached actual product C2 turns on 15 files admitted 26/30 versus
12/30. Accepted profile pairwise verification: 8/8 same-source pairs above
.84, 0/317 different-source pairs above .84. This subset overlaps the
66-file check; do not add their counts together. Pairwise verification does
not apply global anchor/centroid margins, collision handling or enrollment
order, so it is not a global-link recall result.

The current eight-second cap provides too little consistent evidence for
many profiles on these corpora; doubling it helps substantially without
lowering the .84 threshold. It still leaves 32/60 profiles unaccepted in the
initial test and may increase CPU load. No product default was changed.
Ordinary global linking stays disabled.

Correction: the earlier compact summary said 83 different-voice pairs.
The original detailed scorer and fresh replay both give **88**:
14 choose 2 = 91 total pairs, minus 3 same-voice pairs. All 88 are below
threshold. The local compact score JSON was corrected.

## Reproduction

Use the already provisioned host Python and dependency site (Windows uses
Python 3.12 for the existing binary wheels). No ADB or phone is used.

    python tools/diagnose_titanet_rejections.py --data DATA20 --model TITANET --site SITE --output .local/qa-three-checks-current/titanet-rejection-diagnosis.json
    python tools/diagnose_titanet_rejections.py --data DATA70 --exclude-manifest DATA20/benchmark_manifest.json --methods current,long16s --model TITANET --site SITE --output .local/qa-three-checks-current/titanet-rejection-followup.json
    python tools/diagnose_titanet_rejections.py --data DATA70 --c2-predictions CACHED_HOST_PREDICTIONS --methods current,long16s --model TITANET --site SITE --output .local/qa-three-checks-current/titanet-rejection-c2.json
    python -m unittest discover -s tools -p test_titanet_diagnosis.py

The runner verifies model, audio and RTTM checksums and cached C2 WAV pins.
It writes RUNNING before inference, so an interrupted run cannot present a
previous COMPLETED result. Output is restricted to ignored .local.
It exports scores, durations and fragmentation counts, never embeddings or
transcripts. Four selection regressions pass.

[Recorded metrics](evidence/titanet-excerpt-length-20261112.json) retain the
three comparisons and their explicit limitations. Host sherpa is 1.12.40;
Android remains 1.12.20. No natural-conversation, Android runtime parity,
thermal endurance or production-readiness claim is established.

Full global-policy replay of the 15 predicted-C2 clips also completed:
the current extractor admits no returning probes, while longer evidence
admits seven returning probes and links all seven correctly, with no false
links, speaker mixes or in-block collisions observed. This is a small,
correlated host replay, not an independent production safety estimate.

Next: validate the experimental Android variant and processing cost before
changing its extraction budget. Keep consistency and matching thresholds
frozen during that comparison.
