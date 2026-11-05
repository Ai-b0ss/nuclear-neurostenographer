# Candidate models for the 4 GiB HONOR Android target

The application currently runs the quantized C2 diarizer and A0 Russian ASR
through native C++ inference on Android. New models must beat the same frozen
Russian WER/cpWER and diarization DER cases while remaining within the emulator
memory budget. An x86_64 emulator result still cannot prove Kirin 710A speed.

| Candidate | Verified upstream facts | Device decision |
|---|---|---|
| [Nemotron 3.5 Transcribe 30B-A4B](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B) | 30B total, about 4B active, 40 languages; published inference hardware table lists server GPUs and Jetson Thor, not Android. | Research/server reference only; no 4 GiB phone deployment path shown. Distinct from the much smaller C2 diarizer already in the app. |
| [MOSS Transcribe-Diarize 0.9B](https://huggingface.co/OpenMOSS-Team/MOSS-Transcribe-Diarize) | Joint ASR, speakers and timestamps; Russian among supported languages; BF16 weights, Python/Transformers with custom code and CUDA-oriented quickstart. | Most relevant quality challenger for a host benchmark. A quantized Android C++ port and memory test would be separate research work. |
| [VibeVoice ASR](https://github.com/microsoft/VibeVoice) | Joint long-form ASR/diarization. Its [BitNet C++ runtime](https://github.com/microsoft/VibeASR.cpp) is 1.58 GB of model files and reports CPU benchmarks on server, desktop and Apple M4; the official repository shows no Android/HONOR measurement. | C++ route exists, but a 1.58 GB model plus working memory may exceed the 4 GiB phone budget. Benchmark on device before considering integration. |

The AMI test added on this branch shows C2 speaker identity is mostly correct;
missed activity and overlapping speech dominate its English meeting DER. This
fits published work on [target-speaker VAD](https://arxiv.org/abs/2208.13085)
and [overlap-aware diarization](https://arxiv.org/abs/2303.05397). A compact
speaker-conditioned activity model is the next experiment to justify, with
paired Russian WER/cpWER and Android PSS checks. The present test also shows
why changing a boundary constant cannot be judged from DER alone.
