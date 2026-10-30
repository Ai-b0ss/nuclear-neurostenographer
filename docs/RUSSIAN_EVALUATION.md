# Tiny acted Russian evaluation — scope and reproduction

This is a **three-utterance composed probe**, not natural conversation, a
representative benchmark, or a competition accuracy certification. It exercises
real Android GigaAM v3 + global pyannote/ERes2Net inference against external text
and source-speaker annotations rather than checking only one known phrase.

## Data and permission boundary

Source: [Langswap Dialogs](https://huggingface.co/datasets/langswap/dialogs-ru-emotional-conversations),
immutable revision `a74ff44d8d27ca3d21098ea3ed4d31a32923fbdd`.
The full [dataset OpenRAIL license](licenses/dialogs-OpenRAIL.md) permits lawful
evaluation/modification/redistribution without a fee, subject to its Section 2
use restrictions and distribution flow-down. Dataset-derived reference and
hypothesis artifacts are supplied with that license; recipients must comply with
Section 2. This does not change application or model licenses. No paid commercial
agreement, private audio, voice cloning, training or external inference is used.
The dataset publisher states that professional actors consented to release; this
project has not independently audited those consent records.

`tools/fixtures/dialogs-ru-smoke-lock.json` pins the license, external test.csv,
three WAV byte hashes and exact composite WAV hash. Selection was fixed before
model inference: first neutral D, first neutral M, second neutral D in the pinned
test.csv order. No examples are chosen by recognition results and no model or
clustering parameter is tuned on this probe.

The source PCM16 mono 44.1-kHz samples are concatenated unchanged, adding two
500-ms zero gaps. The app's normal PCM reader/resampler processes the resulting
19,655-ms WAV. Composite SHA-256:
`61354eefab1ba60e41e54c2c34e6ddd1b60d99bc923a9b798f26004dd98b3861`.
Audio remains ignored and never appears in public build artifacts or Git history.

## What is and is not scored

- WER uses external scripted text under the existing documented normalization.
- cpWER uses anonymous inferred speaker labels and global minimum-permutation
  matching. Unattributed words remain NOT_SCORED, never assigned a reference ID.
- An A-B-A recurrence probe reports the dominant eligible inferred cluster per
  source clip. It is a narrow structural check, not DER or calibrated confidence.
- **DER remains NOT_SCORED.** File extents include silence and are not independently
  labeled speech boundaries. No evenly spaced words/guessed turns become truth.
- External text has not been manually audited word-for-word against the audio.
  Training contamination is unknown. Three clean acted clips cannot support
  claims about noisy Russian meetings, interruptions or overlapping voices.
- Timing/PSS evidence is from an emulator. Memory snapshots exclude the worker
  and are not peak RAM; RTF is not physical-phone speed or energy use.

The workflow can succeed in collecting an explicitly partial measurement;
`metric_availability=PARTIAL_NO_DER_REFERENCE` and recurrence/attribution failures
remain visible. No competition accuracy threshold has been invented.

## Reproduce

```powershell
python tools/test_dialogue_benchmark.py
python tools/provision_asr.py --test-assets
python tools/provision_diarization.py --test-assets
python tools/provision_dialogue_benchmark.py
```

On an isolated emulator run `bash tools/run_android_benchmark.sh`, or run the
**Tiny acted Russian dialogue evaluation** GitHub workflow on the WIP branch.
The opt-in `-PrussianBenchmark=true` instrumentation class is excluded from
ordinary UI QA. It receives only audio/models; reference text/speaker labels are
not supplied to either inference engine. Scoring occurs after inference on the
runner. Fixed outputs and stale score files are removed before a new generation;
malformed/missing hypotheses replace favorable scores with explicit ERROR.

Artifacts contain the reference/provenance, actual hypothesis, scoring result,
test report and full dataset license, never audio/models. Read the report's scope
and metric availability together with its numbers. Exact executed results are
recorded in PROGRESS.md; provisioning or compilation alone is not model evidence.

## Executed baseline — 30 October 2026

[Android run 41048642815](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41048642815)
at `ab46587` completed real CPU inference on API 33/x86_64 with the default
no-TTS runtime. **WER 1/41 = 2.44%; cpWER 25/41 = 60.98%; A-B-A FAIL**:
all three source clips were assigned Speaker 1. DER remains NOT_SCORED.
This exposes a speaker-merging failure, despite good text recognition on these
three clips. The workflow succeeded in collecting measurements; quality did
not pass the recurrence probe. No threshold was changed in response.

Inference took 5,129 ms / RTF 0.261 on that cloud emulator, including worker
bind/load/process/exit and ASR load/decode, excluding import/model verification.
PSS snapshots are not peak memory and exclude the worker. These figures do not
predict physical-phone performance. Exact dataset-derived reference, hypothesis,
scores and provenance are in `docs/evidence/round11-acted-*.json`, subject to
the full [dataset license](licenses/dialogs-OpenRAIL.md), including Section 2.
