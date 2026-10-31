# Offline scoring and performance evidence

`python tools/test_score_transcript.py` runs authored Russian text/timing arithmetic
cases, randomized assignment checks against exhaustive permutations, and DER checks
against an independent discrete-time oracle. These are **scorer tests, not model
accuracy**. `tools/fixtures/metrics-ru-authored.json` contains no audio and uses an
all-zero hash sentinel. It must never appear in a model leaderboard.

## Score a recording with independent annotations

```
python tools/score_transcript.py --reference reference.json --hypothesis hypothesis.json --output score.json --collar-ms 0
```

Both JSON inputs identify the same original WAV with `audio_sha256` (SHA-256 of
file bytes, not decoded PCM) and integer `audio_duration_ms`. A reference requires
`schema_version: 1`, `recording_id`, `annotation_source`, `license`, and `kind`
(for example PUBLIC_RECORDED, ACTED, SYNTHETIC, or AUTHORED_UNIT_TEST_NO_AUDIO).
Record the independent annotation source/version and rights accurately. This
metadata is a provenance requirement, not an automated verification of its truth.

- `text_segments`: reference text with `start_ms`, `end_ms`, `speaker_id`, `text`.
  Transcript chunk times are sufficient to order text; no word times are invented.
- `segments`: the same keys in the hypothesis. App JSON already supplies these;
  attach the original WAV hash and duration. Preserve its provenance/warnings.
- `diarization`: optional separate raw speech turns in **both** inputs, with
  `start_ms`, `end_ms`, `speaker_id`. Never derive these from ASR chunk intervals:
  chunks can include silence or omit detected speech whose text was empty.
- All intervals are half-open, integer milliseconds, inside the recording.
  Reference speakers must be known nonempty strings. Hypothesis null speakers
  explicitly mean unknown. Recordings are scored separately; IDs are session-local.

WER normalizes NFKC, lowercase and ё→е, then splits Unicode alphanumeric tokens.
It removes punctuation/underscores, retains numbers without expansion and does
not transliterate. Segments sort by start, then end. Sequence WER for overlapped
utterances depends on ordering; cpWER is more suitable for that comparison.
The scorer reports S/D/I counts, reference words and the unbounded error ratio.
An empty reference has an undefined ratio, while insertion counts remain visible.

cpWER concatenates words per speaker in time order, uses exact minimum-cost
one-to-one assignment, and pads absent speakers with empty sequences. Missing
speakers incur deletions, extra speakers insertions. Null or explicitly unreliable
attribution with nonempty words produces `NOT_SCORED`, with a reason; it is never
silently discarded or relabeled to get a favorable score. Empty hypotheses score
all reference words as deletions. Assignment is limited to 12 speakers per recording.

DER globally maps hypothesis clusters to reference speakers by maximum scored
co-occurrence time. It integrates exact event boundaries, without rounding to
frames. Miss = max(reference active count − hypothesis active count, 0); false
alarm is the reverse; confusion = min(counts) − correctly mapped count. All
components divide by **reference speaker time**, including overlapping speakers.
Duplicate/overlapping turns for the same speaker are unioned. Null hypothesis
speech counts as active but never maps to a known speaker. A silent reference has
undefined DER; false-alarm milliseconds remain visible.

`--collar-ms N` excludes a radius of N milliseconds on each side of every
reference start/end, clipped to the recording. Default 0. `--skip-overlap` excludes
regions with more than one reference speaker; default includes overlap. Mapping
is optimized on the same scored regions. Whole-recording [0,duration) is the
evaluation region; UEM subsets and corpus aggregation are not implemented.
Always report collar radius, overlap mode, reference speaker time and components.

Exit codes: **0** all three metrics scored, **2** one or more unavailable/undefined,
**1** invalid input/error. Missing references return `NOT_SCORED`, not zero.
An error replaces an old output with ERROR so stale favorable scores cannot survive.
The report hashes both input JSON files. Output cannot overwrite either input.
Round 7 rejects non-object JSON roots (including an explicit null reference file),
non-integer hypothesis durations and non-boolean `attribution_reliable` flags.
Invalid options are rejected even when the reference is missing. CLI corruption
tests preseed a favorable report and verify ERROR replaces it; these are evidence
integrity tests, not model benchmarks.

Metric definitions/reference implementations consulted:
[MeetEval cpWER](https://github.com/fgnt/meeteval/blob/main/meeteval/wer/wer/cp.py),
[dscore DER](https://github.com/nryant/dscore#diarization-error-rate).
This is an original compact implementation, not copied upstream code. It has
arithmetic/oracle tests, but parity with NIST md-eval or MeetEval on a licensed
annotated corpus is **NOT_RUN**; do not describe it as an officially certified scorer.

## Available audio versus ground truth

The pinned 11.29-second upstream Russian WAV has a phrase smoke assertion but
no independent full transcript or reference speech-boundary/speaker annotation
in its pinned `test_wavs` directory. A recognized string, poem source text or
model-generated turns are not ground truth. WER/DER/cpWER on that recording remain
**NOT_SCORED**. The upstream Chinese four-speaker example and composed A-B-A only
test recurrence; threshold selection used that example, so it is not held out.
No private audio or external dataset was uploaded or assigned invented annotations.

## Android and parser performance

The cloud offline workflow now persists public-fixture inference JSON (audio hash,
raw ASR/diarization, load/decode times, SDK/ABI/device information). It collects
these and logcat on shell exit, including failing test runs. Missing outputs remain
missing; a later assertion does not turn incomplete inference into a pass. The
workflow clears app data before tests to discard stale evidence. Final
`dumpsys meminfo` and before/
after in-process PSS snapshots are **not peak RAM**, and exclude the worker. Fresh
recognizer load per run is not a cold-process startup measurement. Reported RTF
includes model load + decode, excluding hash verification/import and diarization.
Round 9 includes real Android x86_64 execution and retains per-run metadata.
Physical ARM64, peak PSS/RAM and thermal tests remain **NOT_RUN**. Emulator RTF
is not smartphone performance. Independent dialogue WER/DER/cpWER remain unscored.

The PCM parser buffers 64 KiB of source bytes and linearly resamples using two
source mono frames. It allocates the output float buffer directly, avoiding the
extra full-rate mono float buffer (23,040,000 payload bytes for a 120-second 48 kHz
input). All source PCM is consumed even when downsampling ignores tail samples,
so truncated tails still fail. Exact output matches the previous algorithm for
48 rate/channel/length cases; this does not improve linear-resampling quality.

`tools/PcmImportBenchmark.kt` compares the parser to the preserved round-3 source
from `.local/round3-source.zip`, renamed into a baseline package for the probe.
It uses generated numeric stereo PCM, no speech. `round4-pcm-benchmark.json`
reports host current-thread allocated bytes and counted in-memory source reads,
plus elapsed parser time. It is not Android peak RAM, storage throughput or ASR RTF.

Reproduce with JDK 17: `python tools/run_pcm_benchmark.py --java /path/to/java`.
It requires the preserved source-only round-3 ZIP (not committed), verifies the
baseline parser hash, and downloads only checksum-pinned Kotlin compiler jars
if missing. The report records both parser source hashes. Without that recovery
archive, baseline comparison is unavailable; exact PCM/oracle tests still run
from the public source alone. No model/audio/SDK download is needed by this probe.

## Separate disjoint acted Russian speaker-recurrence check

The original three-utterance D-M-D acted benchmark was used to adjust the
speaker clustering threshold. Its 2.44% WER/cpWER is development evidence,
not a previously untouched holdout. Baseline threshold 0.9 is retained
as a historical comparator in that development suite; production is 0.8.

The optional holdout suite freezes four DIFFERENT original WAV clips
(positions 18, 49, 24, 51 in the same pinned external test.csv) and composes
them into a M-D-M-D clip-level recurrence check. Lockfile:
tools/fixtures/dialogs-ru-disjoint-holdout-lock.json. Exact composed WAV:
SHA-256 52f34a15e35af61ac193d01ea135712e7b71df64d74c6e4d9d0c0da4772fb070,
duration 42,237 ms. The first three development clips and these four clips
share no source filenames or hashes. The reference contains original
scripted text and speaker IDs, not verified spoken word timestamps.
Dataset OpenRAIL terms apply; audio is excluded from Git and CI artifacts.

Run on an authorized pinned Android environment:

    python3 tools/provision_dialogue_benchmark.py --suite holdout
    BENCHMARK_SUITE=holdout bash tools/run_android_benchmark.sh

Or dispatch the dialogue-benchmark.yml workflow with suite=holdout. The
development mode retains the 0.5/0.65/0.8/0.9 historical sweep. On the
holdout, Android executes only actual production 0.8: NO threshold sweep
and no reference IDs/text supplied to the application. The scorer
verifies per-clip dominant inferred raw clusters: same-source speaker
pairs must share a cluster, different-source pairs must differ.
Missing or tied speaker assignments are UNDETERMINED, never PASS.
It reports WER and cpWER; DER remains NOT_SCORED because independent
speech-boundary annotations are missing. Benchmark suites and invocation
identities are checked on both sides; outcomes never become default tuning.

Scope: previously unused acted same-dataset clips, NOT natural dialogue
or a representative corpus, no proof of training disjointness or physical
ARM64 performance. A failed holdout must remain recorded, not used for
post-hoc production threshold selection.

## Measured disjoint acted four-clip evaluation — 2026-10-30

Run 41127309893, production 0.8 only, Android x86_64 emulator API 33,
code 423eed6. SHA-256 pinned original M-D-M-D recording
52f34a15e35af61ac193d01ea135712e7b71df64d74c6e4d9d0c0da4772fb070
(42,237 ms), same external acted dataset but source clips disjoint from the
three used in threshold tuning. The run passes its single device instrumentation
test. Downloaded hypothesis/reference and invocation IDs were independently
verified against exact recorded input hashes. APK test media contains no
reference text/speaker IDs; output archive contains no raw WAV.

- WER: 2 substitutions out of 92 scripted reference words = 2.17%.
- cpWER: same two errors (2.17%) after global D/M to Speaker 2/1 matching.
- Speaker recurrence: M-D-M-D = Speaker 1-2-1-2; all six source-clip pair
  relations match, status PASS. This is a clip-recurrence probe, NOT DER.
- DER: NOT_SCORED (no independently marked speech boundaries).
- Total measured inference: 16,596 ms; RTF 0.393 on emulated x86_64, not
  a physical Android smartphone performance estimate.

A separate development sweep on the same commit (41127281473) failed at
a second worker call with the known safety guard that refuses reuse before
the preceding service's Binder death is confirmed. Its failure is real and
remains tracked separately. These results do not clear real conversations,
overlap, device memory, or distribution licenses. See machine-readable summary
in docs/evidence/holdout-first-run-20261030.json and the CI artifact:
https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41127309893
