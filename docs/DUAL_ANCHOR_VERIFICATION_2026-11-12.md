# Dual-anchor return-only speaker verification,12 November2026

Implemented in the experimental Small-based path. Ordinary global linking
remains OFF; identity thresholds, model pins and physical thermal limits
are unchanged. This is a limited improvement, not a readiness declaration.

A new speaker still needs two temporally disjoint >=3s excerpts agreeing
at cosine .84 before enrollment. For an already enrolled speaker ONLY,
a disagreeing pair may reuse an ID if BOTH excerpts independently pass
the .84 anchor/centroid similarities and .07 margins for the SAME earlier
entry. Ambiguity, one bad half, slot-switching or collision blocks reuse.
Rescued evidence cannot enroll a new entry or update any centroid/anchor.

All candidates compare against the pre-block snapshot, so an enrollment
from the current block cannot validate another candidate in that block.
Legacy trusted core callers remain supported; Android identity transport
requires version2 with both192D samples and independently bounded durations.
Unknown versions, missing/invalid pairs or malformed optional metadata
discard identity evidence while retaining valid diarization/ASR output.
Mixed embedding dimensions are rejected.

The extractor still performs two model forward passes per planned speaker.
A permissive zero cosine cutoff is used ONLY to construct the averaged
vector; it is not an admission gate. The book independently enforces
.84 consistency for enrollment and both .84/.07 checks for return-only reuse.
Android IPC adds at most12KiB of sample-vector payload (8x2x192x4 bytes).

## Host verification

| Fixed data snapshot | Old assignments | New assignments | Old correct returns | New correct returns |
| --- | ---: | ---: | ---: | ---: |
| Dialogs,35 actor/style profiles |14|15|8/11|9/12|
| Oracle bookmix,60 profiles |28|31|6/6|9/9|
| Actual C2 bookmix,30 profiles |26|26|7/7|7/7|

No wrong-person links or mixed global identities were observed in this
replay. Dialogs still has20 unassigned profiles and3 returning false splits.
Different admission denominators are not comparable recall populations;
the gain is modest. These are previously used, correlated actor/audiobook
snapshots, not an untouched natural-conversation benchmark.

Constructed speaker-switch controls combine the first available early
sample from one source with the late sample of a different source:

| Data | Ordered disagreeing pairs | Both sources enrolled | Wrongly reused ID |
| --- | ---: | ---: | ---: |
| Dialogs |6|6|0|
| Oracle bookmix |1190|462|0|
| Actual C2 bookmix |506|342|0|

All1702 pairs were below .84 mutual agreement; none qualified for ordinary
consistent enrollment. This checks the new reuse path under constructed
speaker switches, not population false-accept safety.

The actual Kotlin book reproduced all72 Python-replay assignments over47
blocks from real model outputs. Temporary local vectors were deleted after
verification and are never committed or uploaded. Pure policy regressions
cover immutable centroid behavior after40 rescues, one bad half hidden by
the average, different speakers, collision and no-anchor rejection.
Core tests additionally cover margin ambiguity, same-block enrollment,
malformed evidence, mixed dimensions and version2 IPC rejection/downgrade.

Local experimental Android APK and instrumentation APK assembled; all20
core test groups and the real-model parity harness passed. Android emulator
end-to-end verification subsequently passed; see the result below.

## Evidence and reproduction

[Metrics](evidence/dual-anchor-20261112/result.json),
[JVM parity](evidence/dual-anchor-20261112/jvm-parity.json),
[Dialogs-derived data license](evidence/dual-anchor-20261112/LICENSE.md).

    python tools/compare_speaker_embedding_candidates.py --dual-anchor-experiment --output .local/dual-anchor-current --site SITE

Set NEURO_DUAL_ANCHOR_REPLAY to the ABSOLUTE output directory, then run
the core runCoreTests Gradle task. Delete private-replay.tsv and
expected-links.tsv after successful parity verification. They contain
temporary local test vectors/links, not publishable artifacts.

Source attribution: [Dialogs](https://huggingface.co/datasets/langswap/dialogs-ru-emotional-conversations),
OpenRAIL, and [mexus/ru-book-mix-10h](https://huggingface.co/datasets/mexus/ru-book-mix-10h),
CC-BY-4.0 and its listed source attributions. Host sherpa1.12.40 differs
from Android1.12.20. No phone or natural-conversation acceptance claim.

## Android end-to-end result

All four emulator cases passed on29ada9d in
[run43254970270](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/43254970270).
Repeat: both controlled voices linked across blocks; different-source
negative: no shared global IDs; absent model: only block-local labels,
zero profiles, exact model restoration. Cleanup verified for all cases.

Continuous20m40s input completed in370038ms (6m10.038s),252 segments,
21 unknown-speaker segments, five profiled blocks and all timeline/end
coverage checks passing. This is an uncontrolled separate-runner wall time;
do not attribute differences from earlier runs to this policy change.

[Android metadata](evidence/dual-anchor-20261112/android.json) contains only
sanitized metrics. Host Linux baseline and16 Python guard/policy tests also
passed. The host suite's main speaker_link summary is the legacy admission
baseline; new-policy quality metrics are in result.json. Ordinary Android
build/core CI passed as well. Final metadata-only changes retain identical
runtime source blobs; the deliberate trigger marker is removed to avoid
repeating unchanged Android endurance on merge.

This validates IPCv2 and the complete Android pipeline, not independent
Android identity-quality recall. The additional rescues were scored on
host sherpa1.12.40 plus actual Kotlin-book parity; Android uses1.12.20.
No physical phone test was performed, and ordinary global linking remains
disabled because overall identity quality is still inadequate.
