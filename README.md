# Nuclear Neurostenographer

[![Android CI](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/workflows/android.yml/badge.svg)](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/workflows/android.yml)

**Nuclear IT Hack (MEPhI, November 2026)**. Offline Android application for transcribing recorded conversations with speaker attribution and timestamps.

Status: **early Android shell**. The fusion core and sample transcript exports are implemented, but no speech recognition or diarization model is connected yet. Do not present demo transcript text as real ASR results.

### Architecture
- Android / Kotlin / Jetpack Compose: local WAV recorder, file import and transcript UI.
- Core: backend-independent alignment of time-stamped words/chunks to speaker turns; uncertainty and overlap flags; JSON/SRT/TXT.
- Future inference: sherpa-onnx, Russian GigaAM v3, pyannote segmentation and 3D-Speaker embeddings. No remote ASR.

### Build
GitHub Actions builds the debug APK on GitHub-hosted runners. Android SDK is **not** required on the developer PC for cloud builds. Core tests run on JDK 17.

### Security
No INTERNET permission. Do not upload user audio, weights, secrets or private meeting recordings to this public repository.

See [issues](https://github.com/Ai-b0ss/nuclear-neurostenographer/issues) for integration work.
