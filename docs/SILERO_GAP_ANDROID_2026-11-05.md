# Silero VAD gap recovery on Android

The 4 GiB Android 16 API 36 x86_64 emulator ran an opt-in C++ Silero VAD pass
through the existing sherpa-onnx C API. The model is the pinned 643,854-byte
[`silero_vad.onnx`](https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx),
SHA-256 `9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6`.
It is an ignored Android test asset, not part of the product APK. The probe
accepts 16 kHz mono samples, processes them in 8192-sample chunks on one CPU
thread, and returns speech intervals to the test. For each threshold (0.35,
0.50, 0.65), the test decodes Silero intervals of at least 300 ms outside the
current C2 windows, alongside the unchanged C2 windows.

The same ten frozen Russian recordings and manually reviewed text references
used for the [all-window experiment](C2_ALL_WINDOWS_ANDROID_2026-11-05.md)
were scored. All four modes used C2's zero activity threshold, 150 ms boundary
padding, 400 ms same-speaker merge and C++ GigaAM v3 CTC inference. Each
Silero mode added 57 windows in total; the number and boundaries varied on
some recordings by threshold. Every resulting transcript was byte-for-byte
identical to its baseline transcript; the extra windows added no final text.

| Mode | WER | Strict cpWER on same scorable cases | Sum of ASR load + decode |
|---|---:|---:|---:|
| Current C2 windows | 40/525 | 71/380 | 14.809 s |
| Silero 0.35 gaps | 40/525 | 71/380 | 16.534 s |
| Silero 0.50 gaps | 40/525 | 71/380 | 16.489 s |
| Silero 0.65 gaps | 40/525 | 71/380 | 16.807 s |

This candidate did not improve accuracy and increased ASR time by 11–13%.
VAD inference time was not separately captured, so the table understates its
total cost. The candidate is not promoted. Raw evidence is in ignored
`.local/nemotron/c2-silero-gaps-evidence.json`; the checked-in test and scorer
reproduce it without adding model weights or audio to Git.

Reproduce: download the pinned model above to
`.local/androidTestAssets/silero_vad.onnx`; build with
`-PnemotronPrototype=true -PnativeAsrCandidate=true -PdiarThresholdProbe=true`;
run `C2PaddingAsrProbeTest` with `-e experiment silero_gaps`; pull
`files/c2-silero-gaps-evidence.json` from `ru.neurostenographer.app.c2`; then
run `python tools/nemotron/score_c2_padding_asr.py EVIDENCE.json`.

## Larger model candidates

The [NVIDIA Nemotron 3.5 Transcribe 30B A4B NVFP4
checkpoint](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B-NVFP4/tree/main)
is 21.6 GB; [its model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B-NVFP4)
lists Blackwell GPU deployment. It cannot replace the 225 MB ASR model in a
4 GiB CPU-only phone build. Its Russian multispeaker output could be useful as
an external research reference, but it has not been run on this corpus.

[MOSS-Transcribe-Diarize 0.9B](https://huggingface.co/OpenMOSS-Team/MOSS-Transcribe-Diarize)
supports joint text, speaker tags and timestamps in Russian and is much
smaller. The published checkpoint is BF16 (about 1.8 GB for weights alone);
community quantizations exist, but this Android C++ runtime has no validated
implementation for its encoder/LLM pair. Its phone memory, latency and Russian
cpWER/DER remain unmeasured. It is a worthwhile separate candidate only after
an Android ARM64 runtime and identical-corpus evaluation exist.

[VibeVoice-ASR-BitNet and its C++ runtime](https://github.com/microsoft/VibeASR.cpp)
reduce the model to 1.58 GB and report CPU inference, but the weight size is
still roughly seven times the current ASR weight. No comparable Android HONOR
peak memory, latency or Russian cpWER/DER evidence exists yet. It is a research
candidate, not a demonstrated phone replacement.
