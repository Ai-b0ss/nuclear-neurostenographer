# Speaker-refinement check on Android 16 emulator

The development recordings showed a possible C2+C0 rule: when C2 reports exactly two speakers and C0 at clustering threshold 0.65 reports exactly three, use C0 only if its shortest speaker has at least 1,000 ms of turns. This rule was fixed **before** inference on the new recordings below. It could improve speaker attribution, but it would run two diarizers and might change ASR windows and WER.

`tools/nemotron/provision_speaker_refinement_holdout.py --freeze` selected twelve previously unused source clips from the pinned [Dialogs Russian test split](https://huggingface.co/datasets/langswap/dialogs-ru-emotional-conversations). The committed `tools/fixtures/dialogs-ru-speaker-refinement-holdout-lock.json` records the upstream revision, source paths and SHA-256 values, four generated WAV hashes, and four independent script-reference hashes. Normal provisioning verifies the lock. Each test file concatenates three acted single-speaker utterances with fixed half-second gaps. These are **not natural conversations**, and script text was not manually re-audited; clip bounds are not DER ground truth. Audio and text references stay ignored in `.local`.

The Android 16 API 36 x86_64 emulator was configured with 4 GiB RAM and 16 KiB pages. `AsrHeadProbeTest` ran the current C2 product policy (150 ms padding, 400 ms same-speaker window merge, A0 GigaAM CTC) and recorded speaker count. `DiarThresholdProbeTest` ran C0 on the same WAVs at thresholds 0.50, 0.65, 0.80, 0.90. `tools/nemotron/score_speaker_refinement_probe.py` verifies the locked WAV/reference hashes and the matching audio hashes in both evidence files before scoring the frozen rule.

| File | C2 speaker count | C0 0.65 count | Rule switches? | C2 WER | C2 strict cpWER |
| --- | ---: | ---: | --- | ---: | ---: |
| `speaker-holdout-0` | 2 | 2 | No | 1/37 | 16/37 |
| `speaker-holdout-1` | 3 | 3 | No | 0/39 | NOT_SCORED: unattributed words |
| `speaker-holdout-2` | 2 | 2 | No | 0/37 | 14/37 |
| `speaker-holdout-3` | 3 | 2 | No | 0/36 | NOT_SCORED: unattributed words |

The frozen rule changed **no** new case. Both baseline and selected result have WER **1/149** and cpWER **30/74 on the two scorable cases**; two cases remain unscorable and must not be silently included in that denominator. The rule looked promising on earlier development cases (cpWER 115/538 to 49/538 on their existing scorable subset, with WER worsening 42/683 to 47/683), but this new holdout gives no independent support for deploying a second diarizer. It is **not promoted**. The product's C2, A0, and native inference settings remain unchanged.

Separately, a debug-only C2 activity-logit threshold sweep on the earlier four acted cases tried -1, -0.5, 0, 0.5, and 1. The threshold did not create a third speaker for the two worst merges. At -1 it created an unstable third slot on another case but worsened its WER 2/34 to 16/34 and left 14 hypothesis words unattributed. The native threshold experiment was reverted; the product remains at zero. Its raw evidence is ignored under `.local/c2-activity-asr-asr-holdout-evidence.json`.

Reproduce the new holdout with `python tools/nemotron/provision_speaker_refinement_holdout.py`, build opt-in instrumentation with `-PnemotronPrototype=true -PnativeAsrCandidate=true -PdiarThresholdProbe=true -PasrHeadProbe=true`, run `AsrHeadProbeTest` with `suite=speaker-refinement-holdout`, `heads=a0`, `backends=c2`, `c2ProductPolicy=true`, then run `DiarThresholdProbeTest#compareC0Thresholds` with the same suite. Pull `files/asr-head-product-speaker-refinement-holdout-evidence.json` and `files/diar-threshold-evidence.json` from the debug app and pass them to `score_speaker_refinement_probe.py` in that order. The pinned audio and references are local-only; raw transcripts are not committed.
