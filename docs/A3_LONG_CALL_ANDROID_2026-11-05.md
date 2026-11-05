# A3 RNN-T on a 20-minute natural call (2026-11-05)

The short-clip Android probes found a small A3 RNN-T WER gain over product A0
CTC: 2 fewer errors on 180 Golos farfield words, 4 fewer on 389 SOVA RuDevices
words, and 1 more error on the earlier 683-word mixed/acted set. To check the
cost on realistic recording length, both heads ran on the same first 1,200 s of
the pinned [DataHive Russian call](https://huggingface.co/datasets/datahiveai/multilingual-conversations-sample),
WAV SHA-256 `e9933e55693151a6f2c5d0f34188348d62053b66a70d9dad0dd25ffd3a408df5`.
The call has no independent transcript or speaker labels. These runs can measure
completion, time, and sampled memory, **not** WER, cpWER, or DER.

The opt-in `C2LongAsrProbeTest` verified A3's four model-file hashes. It ran C2
on the 4 GiB, Android 16 API 36 x86_64, 16 KiB page emulator and applied the
same product 150 ms boundary padding and 400 ms same-speaker window merge to
both heads. Both decoded exactly 429 windows. A0 used four ASR threads, A3 two.

| Head | ASR wall | Model load | Decode | Sampled app PSS peak |
| --- | ---: | ---: | ---: | ---: |
| A0 CTC | 24.602 s | 0.962 s | 23.421 s | 670,446 KiB |
| A3 RNN-T | 34.997 s | 0.985 s | 33.675 s | 650,631 KiB |

A3 took **42.25% longer** for the same windows, while yielding 301 transcript
segments versus A0's 314. Segment count and text hashes do not establish
accuracy. The app PSS samples are not a clean memory comparison because tests
ran sequentially, allocator state may differ, and the isolated C2 worker was
not active during ASR. C2 itself completed in 21.348 s for A0 and 22.329 s for
A3, with roughly 610 MiB simultaneous app+worker sampled PSS. The prior A0
run measured 23.481 s with the same policy; the current-build rerun establishes
the direct 24.602 s comparison.

This strongly disfavors promoting A3 on the weak-phone target: its measured
short-clip WER gain is small, and its long-call cost is large on the emulator.
A0 remains the product head. Emulator x86_64 ratios may differ on Kirin 710A;
ARM64 performance and a long-call human reference are still needed.

Reproduce with `-PnemotronPrototype=true -PnativeAsrCandidate=true
-PdiarThresholdProbe=true`, the verified natural-call fixture from
`tools/nemotron/provision_natural_long_android.py`, and
`C2LongAsrProbeTest#longRecordingPairedPolicy` with `head=a0` and `head=a3` in
separate instrumentation runs. Pull the resulting
`files/c2-natural-long-asr-evidence.json` and
`files/c2-natural-long-a3-evidence.json`, then run
`python tools/nemotron/score_long_asr_head_probe.py A0.json A3.json`.
