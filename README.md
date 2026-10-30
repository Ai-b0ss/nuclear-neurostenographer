# Nuclear Neurostenographer

[![WIP branch Android CI](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/workflows/android.yml/badge.svg?branch=codex%2Fovernight-20261030-wip)](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/workflows/android.yml?query=branch%3Acodex%2Fovernight-20261030-wip)

**Nuclear IT Hack (MEPhI, November 2026)**. Offline Android application for transcribing recorded conversations with speaker attribution and timestamps.

Status: **experimental, NOT_READY**. Real offline Russian GigaAM v3 recognition and the import/export flow execute on Android x86_64/API 33. **Speaker attribution fails the independent three-utterance acted Russian probe:** D/M/D collapses into Speaker 1 (WER 2.44%, cpWER 60.98%, A-B-A FAIL; DER has no independent reference). The separate upstream Chinese-fixture recurrence check passes; it does not establish Russian dialogue quality. Worker recovery and the no-TTS bounds patch are tested, but overlap recognition/separation remains unproven. Physical ARM64, spoken microphone dialogue and representative accuracy remain open. See [probe scope](docs/RUSSIAN_EVALUATION.md), [diarization details](docs/DIARIZATION.md) and [exact runs](docs/PROGRESS.md).

### Architecture
- User WAV imports are validated bounded local snapshots; failed replacement keeps the previous input/result. Export captures one inference document, so a returning document picker cannot export a later input by mistake. UI/TXT/SRT show exact chunk milliseconds; JSON also retains duration, provenance and warnings. Word alignment is not implemented.
- Android / Kotlin / Jetpack Compose: local WAV recorder, file import and transcript UI.
- Core: backend-independent alignment of time-stamped words/chunks to speaker turns; uncertainty and overlap flags; JSON/SRT/TXT.
- Inference: sherpa-onnx 1.12.20 / Russian GigaAM v3 INT8 CTC, CPU. Full-recording segmentation, ERes2Net embeddings and global clustering; worker failure falls back to unknown speakers. No remote ASR.

### Build
GitHub Actions builds the debug APK on GitHub-hosted runners. Android SDK is **not** required on the developer PC for cloud builds. Core tests run on JDK 17.

Before Gradle, run `python tools/provision_asr.py` (Python 3.11+, standard library). This selects the Android-tested **no-TTS runtime** pinned in `tools/runtime/runtime.properties`, using a verified local cache or existing GitHub CLI authentication for the exact source-build artifact. An unavailable artifact fails explicitly; it never falls back to the full GPL/TTS AAR. An exact local file can be supplied with `--runtime-file`. Then `gradle :core:runCoreTests :app:assembleDebug` with JDK 17 / Gradle 8.9 / Android SDK 35. Gradle rejects unapproved runtime bytes. No model weights are bundled in the APK.

### Offline model installation and use
1. On a networked PC run `python tools/provision_asr.py --model`. It creates `.local/gigaam-v3.zip` (~225 MB), using an immutable Hugging Face revision and SHA-256 for every file.
2. Transfer the ZIP to the phone using USB/local storage. In the app choose **Установить модель ZIP**. Only the pinned model/tokens/MIT license are accepted. Allow at least 500 MB free for import/replacement.
3. Record audio or import **PCM16 WAV**, mono/stereo, 8–48 kHz, 0.1–120 seconds. Generated MP3/AAC/Vorbis/Opus/FLAC imports pass on Android x86_64/API 33; codec availability varies by device and AMR remains untested. See [codec limits](docs/AUDIO_IMPORT.md). Press **Распознать офлайн**. Airplane mode is supported by design; physical-device verification is pending.
4. Export TXT/JSON/SRT from actual output. **Intervals are input windows up to 20 seconds, not aligned utterance/word times**; fixed boundaries may cut words. Without the optional diarization bundle, speakers remain `null`. Run `python tools/provision_diarization.py`, transfer `.local/diarization.zip` (~46 MB) and install it with the speaker-model ZIP button to enable experimental inferred turns. With it, timing uses detected speech boundaries and 20-second limits. Voice cluster IDs are session-local; unknown/overlap and failure states are retained. Do not use this as an independent diarization benchmark.

The manual **Real offline Russian ASR (x86_64)** workflow provisions a checksum-verified public upstream WAV and model outside Git, disables emulator Wi-Fi/data and runs genuine JNI inference, repetition/silence/invalid-ZIP tests. Current run status is in PROGRESS.md. No physical ARM64 claim.

**APK publication is currently disabled** pending distribution/notices review and device acceptance. The standard build now uses the pinned no-TTS runtime for ARM64/x86_64, verified on the emulator. The full upstream GPL/TTS AAR is an explicit regression option. JSON exports identify the actual runtime hash; CI compares packaged JNI bytes with the selected AAR. See [runtime provenance and instructions](docs/RUNTIME_LICENSES.md). Main-branch APKs still contain only the UI/demo baseline. Integration remains on `codex/overnight-20261030-wip`, without merging main.

### Reproducible metrics and performance

Run `python tools/test_score_transcript.py` for checked WER/cpWER/DER arithmetic
tests. [Scoring format and conventions](docs/BENCHMARKS.md) document reference
provenance, collars, overlap, unknown speakers and missing ground truth. The public
Russian WAV has no full independent annotations: its metrics remain **NOT_SCORED**.
The separate [three-utterance acted Russian probe](docs/RUSSIAN_EVALUATION.md)
now has external scripted references: WER 2.44%, cpWER 60.98%, **A-B-A FAIL**
(voices merged), DER NOT_SCORED. These small-probe results do not establish
natural-dialogue accuracy or contest readiness.
Round 4 reduces WAV import allocation with exact PCM parity; host allocation
evidence is not Android peak RAM or ASR speed. Cloud tests retain public-fixture
JSON and memory snapshots on failure. Emulator snapshots and timing are not
physical-phone peak RAM, thermal or power measurements.

### Security
No INTERNET permission. The local-audio cleanup button deletes app recordings and cached inputs; exported documents need separate deletion. This is ordinary deletion, not forensic erasure. A document provider may independently use cloud storage. See [privacy and codec limits](docs/AUDIO_IMPORT.md). Do not upload user audio, weights, secrets or private meeting recordings to this public repository.

See [issues](https://github.com/Ai-b0ss/nuclear-neurostenographer/issues) for integration work.
