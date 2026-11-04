# C++ Android port: baseline and limits

Source branch: `integration/c2-honor-20261104`. This local branch must preserve the working GigaAM ASR, Nemotron C2 diarization, export, cancellation and C0 fallback while moving application code to C++.

## HONOR 10X Lite constraints

- DNN-LX9, Kirin 710A family (4 Cortex-A73 + 4 Cortex-A53), ARM64, Android 10/API 29, 4 GB nominal / about 3.6 GB usable RAM, 1080 x 2400 display. The device manual identifies the exact SoC as 710A; older project notes shorten it to 710. ONNX Runtime uses at most 4 threads: measured 42 s diarization took 95.9 s at 2 threads, 63.5 s at 4, 101.4 s at 8 (`InferenceThreads.kt`, `PROGRESS.md`).
- On the 20-minute recording, current release took ASR 413.8 s and C2 253.3 s, about 690 s total; wall RTF 0.57. Peak combined app and worker PSS was about 650–656 MiB and battery temperature rose from 42 to 49 °C (`ACCEPTANCE_2026-11-04.md`). Target wall RTF is at most 0.5 without extra sustained memory or thermal pressure.
- Short physical C2 trials: median inference RTF 0.1909; combined PSS peak 669.5 MiB; speaker count 3/3 correct. These figures are not long-recording acceptance (`C2_PHYSICAL_HONOR_2026-11-04.md`).

## Local emulator baseline, 2026-11-04

- API 33, x86_64, 4 virtual CPUs, 4 GiB RAM, WHPX. This is a functional and metric regression environment, not a Kirin 710 speed or thermal proxy.
- Existing Kotlin/JNI C0 benchmark, GigaAM v3 CTC INT8; pinned upstream sherpa runtime SHA-256 `e3905b1258b577d8d374db798618602ceaaff5805cbf9b356ab25267cd98144d` used explicitly for local regression. This differs from the pinned no-TTS product runtime.
- Frozen acted/composed D–M–D audio: SHA-256 `61354eefab1ba60e41e54c2c34e6ddd1b60d99bc923a9b798f26004dd98b3861`, duration 19,655 ms. WER 1/41 and strict cpWER 1/41 (2.44%); recurrence probe passed. DER is unavailable without independent speech boundaries. Raw local output is in `.local/dialogue-benchmark/scores.json` and is ignored by Git.
- Development clustering sweep 0.5, 0.65 and production 0.8 all passed this tiny recurrence probe; 0.9 merged both speakers. Do not select a threshold from this fixture alone.

## Port gate

Run the exact same audio and scorer against each C++ candidate. Preserve segment text, speaker identity/return, timing, unknown-speaker handling, exports and cancellation. Track process time, wall RTF and peak combined PSS separately. Do not promote a candidate based on emulator CPU timing or a score from a different runtime/model. Compare Android ARM64 before declaring a performance gain on HONOR-class hardware.

## Local C++ log-mel candidate

- The C2 Android variant now builds a C++17 JNI log-mel kernel for ARM64 and x86_64. It reads existing Java float arrays without another full-recording copy. The app UI, ASR, ONNX inference and most diarization orchestration still run through the integration branch's Kotlin code; this is a partial C++ port.
- On API 33 x86_64, two instrumentation tests passed: synthetic boundary frames and the pinned Nemotron filter/window coefficients match the Kotlin reference within absolute tolerance 0.0002. The 300-frame kernel-only median was 3.885 ms in C++ and 5.555 ms in Kotlin (five repetitions, one emulator run). This does not measure full inference or HONOR performance.
- The same 19.655 s A-B-A audio and a disjoint 42.237 s M-D-M-D holdout from the pinned internet dataset ran through C0 and C2 in the isolated worker. All four runs succeeded; TXT/SRT/JSON exports were nonempty and speaker return was preserved. The local scorer `tools/score_honor_cpp_emulator.py` verifies WAV SHA-256 and audio duration before scoring. On A-B-A, C0 WER/cpWER was 1/41 and C2 0/41; on holdout C0 was 2/92 and C2 3/92. This mixed result does not establish a general accuracy improvement. DER is unavailable without independent speech boundaries. Evidence and scorer output are under ignored `.local/dialogue-benchmark/`.
- A dedicated `honor10x_lite_api33` AVD is stored on D: with 4 GB configured RAM, 1080 x 2400 at 400 dpi, and 4 homogeneous x86_64 virtual cores. Android reports 3,915 MiB `MemTotal`. The older `neuro_honor_33` AVD remains intact for baseline comparisons. This profile matches memory and display geometry, not the heterogeneous Kirin CPU or thermals. The full two-recording instrumentation test passed on the new AVD and reproduced the same WER/cpWER; raw output is `.local/dialogue-benchmark/cpp-honor-profile-evidence.json`.
- No C++ candidate has yet been timed or thermally checked on physical HONOR hardware. Android 16/API 36 installation and runtime remain unverified; target SDK 35 and ARM64 compilation alone do not establish compatibility. The APK's ZIP alignment passes 16 KB verification, and the new ARM64 `libnemotron_mel.so` now has 16 KB ELF LOAD alignment. The bundled `libonnxruntime4j_jni.so` from ONNX Runtime 1.17.1 remains 4 KB aligned. Updating it independently of the sherpa runtime risks an ABI/version mismatch, so 16 KB page devices are not yet certified.

## Research candidates, not promoted

- ONNX Runtime [mobile guidance](https://onnxruntime.ai/docs/tutorials/mobile/) recommends starting with the CPU provider for quantized models; XNNPACK and NNAPI require measurements because model partitioning and device drivers can reduce performance. The HONOR's existing four-thread cap is based on physical measurements and should stay until a controlled ARM64 comparison changes it.
- NVIDIA's [speaker diarization guidance](https://docs.nvidia.com/nemo/curator/v26.09/curate-audio/process-data/quality-filtering/speaker-separation) describes speech-only concatenation as a way to avoid spending diarization time on long silences. Applying this to the app requires exact timestamp restoration and checks on overlapping speech and speaker recurrence; it is a candidate, not a score gain yet.
- [Meeting recognition with separation and transcription-supported diarization](https://arxiv.org/abs/2309.16482) motivates checking ASR word and sentence boundaries when assigning speakers. That needs independent timing annotations before adoption. No generic deduplication or threshold adjustment should be applied merely to improve the development fixture.
- The installed Qt 6.7.3 Android kit predates official Android 16 support. [Qt 6.10's platform table](https://doc.qt.io/qt-6.10/supported-platforms.html) lists API 36 and NDK r27c; a full Qt/C++ Android application needs that toolchain and feature parity with the integration branch. The JNI kernel here is only an initial C++ port.
