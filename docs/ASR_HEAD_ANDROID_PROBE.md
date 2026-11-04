# Android 16 ASR head comparison (2026-11-05)

Target: offline transcription on HONOR 10X Lite (Kirin 710A, 4 GB RAM). Measurements below are from the API 36, 16 KB page emulator configured with 4 GB RAM and four x86_64 vCPUs. The emulator is **not** a Kirin speed or thermal measurement.

## Reproducible comparison

The opt-in `AsrHeadProbeTest` runs the same six public-audio fixtures, diarization turns, ASR windows, C++ sherpa C API, and scoring normalization for both models. The candidate model is installed into the test application's `files/asr-e2e` directory; it is not packaged or selected by the product. The test verifies both candidate file hashes before running. Run with `-PnemotronPrototype=true -PnativeAsrCandidate=true -PasrHeadProbe=true` and the Android instrumentation class `ru.neurostenographer.app.AsrHeadProbeTest`, then score its `files/asr-head-evidence.json` with `python tools/nemotron/score_asr_head_probe.py EVIDENCE.json`. Fixture WAV hashes are checked against independent references during scoring.

| Diarization | Current GigaAM v3 CTC INT8 A0 | GigaAM v3 E2E CTC INT8 A1 | Sum of ASR wall time A0 → A1 |
| --- | ---: | ---: | ---: |
| C0 | 47/378 WER errors | 56/378 | 10.20 → 9.72 s |
| C2 | 43/378 WER errors | 51/378 | 10.15 → 9.90 s |

On the two acted fixtures, A1 improves C0 by one word and C2 by one word. On the four synthetic ivkond fixtures it is worse, especially C2 on `ivkond-4overlap` (3/76 → 12/76). Some synthetic references have coarse or incorrect turn labels, so their cpWER is unscored. The sample is too small and partly synthetic for a general accuracy ranking. It is sufficient to **reject promotion of A1 on current evidence**. A1 came from [`nocmt/GigaAM-v3-E2E-CTC-int8-ONNX`](https://huggingface.co/nocmt/GigaAM-v3-E2E-CTC-int8-ONNX), revision `0928919f7df949871b507e16497b9e8cff7d0c6b`. Its model file is 224,893,668 bytes; the A0 file is 224,721,476 bytes. A1 SHA-256: `784d77aaa7a0899a247e72c71d667792087ee4dec985db1f57961767a5f6014f`; tokens SHA-256: `142de7570b3de5b3035ce111a89c228e80e6085273731d944093ddf24fa539cd`.

An additional opt-in `WindowPolicyProbeTest` evaluated decoding all gaps between diarized speech intervals. C2 stayed at 43/378 errors while summed ASR time rose from 9.23 to 11.40 s; C0 worsened 47/378 → 48/378 and time rose 8.99 → 10.96 s. The product therefore retains speech-only windows. These wall times come from a separate run and should not be compared directly with the A0/A1 table.

## Other model and runtime candidates

* [Nemotron 3.5 Transcribe 30B-A4B](https://docs.nvidia.com/nemotron/nightly/nemotron/transcribe35/README.html): NVIDIA's FP8 serving profile specifies a 96 GB GPU. It cannot run locally within this phone's 4 GB RAM. This is distinct from the small Nemotron diarization model already used for C2.
* [MOSS-Transcribe-Diarize 0.9B](https://github.com/OpenMOSS/MOSS-Transcribe-Diarize): a joint multilingual ASR/diarization model built from a Whisper-Medium encoder and Qwen3-0.6B. The official implementation uses PyTorch/Transformers; Android memory, speed, and Russian accuracy on our cases are unmeasured. It is a research candidate, not a verified replacement.
* [VibeVoice-ASR-BitNet / VibeASR.cpp](https://github.com/microsoft/VibeASR.cpp): official CPU C++ runtime with a 1.58 GB quantized model. Published RTF figures use server, desktop, or Apple CPUs, not Kirin 710A. The weights alone consume a large fraction of the phone's RAM; Android feasibility must be measured before integration. VibeVoice Realtime 0.5B is a synthesis model, not this ASR model.
* [sherpa-onnx releases](https://github.com/k2-fsa/sherpa-onnx/releases): releases have advanced beyond our pinned 1.12.20 runtime, including ONNX Runtime updates. Upgrading the Android native build requires repeat 16 KB page, no-TTS, ABI, parity, WER, and memory gates. A newer version by itself is not evidence of better recognition.

The [GigaAM upstream project](https://github.com/salute-developers/GigaAM) documents that v3 E2E CTC adds punctuation and normalization, but those features did not improve this evaluation. Research on [overlapped-speech separation](https://arxiv.org/abs/2011.02014) suggests a possible next experiment, targeted only at overlapped spans. It would need an Android sized separation model, clean speaker references, and a memory/time budget before product use.

No ASR weights were fine-tuned in this experiment; there is no demonstrated gain that justifies a model change. The C++ native C2 and ASR implementation in this branch remains the candidate, while the UI and some orchestration remain Kotlin/Compose. Physical HONOR validation and a representative Russian holdout are still needed.

## RNN-T follow-up (same emulator, 2026-11-05)

The C++ ASR candidate can now load an explicitly selected Sherpa NeMo transducer bundle (`encoder.int8.onnx`, `decoder.onnx`, `joiner.onnx`, `tokens.txt`) as well as the existing CTC bundle. The production model store still installs and verifies only A0. The comparison instrumented test accepts `-Pandroid.testInstrumentationRunnerArguments.heads=a0,a3` to run a subset without distributing the other research models.

| Head | Provenance | Model files | C0 WER | C2 WER | C2 summed ASR wall time |
| --- | --- | ---: | ---: | ---: | ---: |
| A0 v3 CTC INT8 | Current pinned product model | 224.7 MB model | 47/378 | 43/378 | 11.16 s |
| A2 v3 E2E RNN-T INT8 | [Alexxerm conversion](https://huggingface.co/Alexxerm/gigaam-v3-e2e-rnnt-sherpa-onnx), revision `c0acd38c8aeb2bdc04da221bd661ffcdb9645f7d` | 226.4 MB total | 52/378 | 49/378 | 14.40 s |
| A3 v3 RNN-T INT8 | [sherpa-onnx model](https://huggingface.co/csukuangfj/sherpa-onnx-nemo-transducer-giga-am-v3-russian-2025-12-16), revision `0424d62637b37d8b7b1eb0f75a04d78dec55fdcc` | 229.3 MB total | 51/378 | 42/378 | 15.43 s |

A2 and A0 timings came from one run; A3 and A0 timings came from a second run. The A3 C2 improvement is one word on a tiny mixed set, with roughly 38% longer ASR time in its paired run (11.16 → 15.43 s). A3 is worse on the four-speaker overlap case (3/76 → 5/76) and worse on C0 overall. The extra model is **not promoted**. The app process PSS sampled during the paired A0/A3 test peaked around 762 MiB for both, but sequential model loading and allocator retention make that an exploratory number, not a clean memory comparison. The model card's published phone speed uses a much faster device; these x86_64 emulator timings cannot establish HONOR throughput.

The [GigaAM authors' evaluation](https://github.com/salute-developers/GigaAM/blob/main/evaluation.md) reports v3 RNN-T ahead of v3 CTC on many Russian datasets, while both E2E heads have higher normalized WER. Our narrow results are consistent with treating the plain RNN-T as the better research candidate than E2E, but do not establish a deployable gain. A larger independent acted or real Russian holdout should be frozen before tuning any selection rule.

## Frozen acted holdout and thread tuning

`tools/fixtures/dialogs-ru-asr-holdout-lock.json` freezes twelve previously unused clips from the pinned [Dialogs test split](https://huggingface.co/datasets/langswap/dialogs-ru-emotional-conversations), selected by a deterministic file-name hash before model inference. Four D-M-S three-voice composites total 147 reference words. `tools/nemotron/provision_asr_holdout.py` validates the source metadata, license, clip hashes and PCM shape, then creates ignored WAV assets and reference JSON. The snippets are acted and composited, not natural meetings; script text is not manually re-audited, and clip extents are not DER ground truth.

| Suite | C2 A0 (CTC, 4 threads) | C2 A3 (RNN-T, 2 threads) | Paired ASR wall sum |
| --- | ---: | ---: | ---: |
| Original six, 378 words | 43 errors | 42 errors | 10.56 → 12.65 s |
| New four, 147 words | 5 errors | 3 errors | 6.04 → 6.79 s |
| Combined, 525 words | 48 errors (9.14%) | 45 errors (8.57%) | 16.60 → 19.44 s |

On the new four-recording set, A3 at four threads kept 3/147 errors but took 7.75 s. Two threads reduced that paired sum to 6.79 s. The speed comparison is emulator-only and can vary with thermal/allocator state. The error reduction is small and source diversity remains weak, so A3 is an **unpromoted research candidate**; the product continues using the smaller/faster A0 CTC path.

On three of four acted composites, C2 merges two of the three true speakers; C0 also merges them on three. For example, in `acted-holdout-0`, M and S are emitted as a single speaker in both backends. This explains cpWER such as 17/33 despite WER 1/33. Tuning ASR alone cannot fix that speaker error. Speaker separation and diarization need their own independent validation, particularly on genuinely recorded multi-speaker audio.

## C0 diarization threshold probe

`DiarThresholdProbeTest` ran the same A0 ASR on C0 clustering thresholds 0.50, 0.65, 0.80 (current), and 0.90. It recorded turns and speech windows as well as transcripts; `score_diar_threshold_probe.py` verifies WAV hashes and scores against references. This is a debug-only measurement, not a product setting.

On the four newly frozen three-speaker acted composites, cpWER at 0.80 was 68/147 versus 46/147 at 0.65 and 34/147 at 0.50, with WER 8/147 at all three thresholds. But 0.50 split the two-speaker original holdout into **four** identities and raised cpWER from 2/92 to 44/92. Threshold 0.65 kept that original case at 2/92, yet worsened the synthetic two-speaker overlap cpWER from 21/48 at 0.80 to 33/48, with four predicted speakers instead of three. The synthetic annotations are too coarse for DER, but the extra identities are observable. Global threshold changes therefore fail the cross-case gate; 0.80 remains the product value.
