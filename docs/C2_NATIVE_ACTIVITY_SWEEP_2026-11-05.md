# C++ C2 activity threshold sweep on Android

The C2 native pipeline previously used a fixed `logit > 0` decision for every
speaker frame. This branch exposes that decision as a debug-only argument;
release calls are restricted to the original zero threshold. The test calls
the same C++ pipeline on the Android 16 API 36, 4 GiB, 16 KiB-page emulator.
The zero-threshold AMI DER exactly matched the earlier isolated-worker result.
Research runs call the pipeline directly from instrumentation, so their memory
behavior is not a substitute for product-process PSS measurement.

`C2ActivityThresholdProbeTest` runs zero, -0.25 and -0.5 logit thresholds on
two distinct AMI meetings with manual speaker segments and two Russian
synthetic audiobook mixes with independent RTTM labels. The scorer verifies
the WAV SHA-256 against the local reference, scores 250 ms-collar DER with
overlap included, and applies the product's 150 ms boundary padding.

| Recording | Zero DER | −0.25 DER | −0.5 DER |
|---|---:|---:|---:|
| AMI ES2004a | 28.68% | 27.74% | 26.91% |
| AMI IS1009a | 7.89% | 7.63% | 7.19% |
| Russian rec_0001 | 0.08% | 0.06% | 0.06% |
| Russian rec_0275 | 3.27% | 3.25% | 3.28% |

The paired A0 text probe used ten frozen Russian clips with the product's
150 ms padding and 400 ms same-speaker window merge. The current threshold
scored WER **40/525**, strict cpWER **71/380** on seven scorable recordings.
At -0.25, WER was **46/525** and one more recording had unattributed words,
making strict cpWER unscorable. At -0.5, WER was **47/525** with the same
coverage loss. These lower thresholds are **not promoted** despite AMI DER
improvement. Timing was similar on the four diarization cases; a claim of
faster inference would not be justified.

A separate paired experiment kept the current speaker turns at 150 ms and
expanded only ASR windows to 200 ms. WER remained **40/525**, while two more
recordings lost strict cpWER eligibility. This also stays out of the product.

To reproduce: build with `-PnemotronPrototype=true -PnativeAsrCandidate=true
-PdiarThresholdProbe=true`, run `C2ActivityThresholdProbeTest` in the emulator,
pull `files/c2-activity-threshold-evidence.json` from the `.c2` app, and run
`python tools/nemotron/score_activity_threshold.py EVIDENCE.json`. Run
`C2PaddingAsrProbeTest` and score its `files/c2-padding-asr-evidence.json` with
`python tools/nemotron/score_c2_padding_asr.py EVIDENCE.json` for paired WER
and cpWER. Audio, references, and raw evidence remain in ignored `.local/`.
