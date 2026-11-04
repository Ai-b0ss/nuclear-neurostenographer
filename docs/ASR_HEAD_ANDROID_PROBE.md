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
