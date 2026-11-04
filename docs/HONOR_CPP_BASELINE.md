# C++ Android port: baseline and limits

Source branch: `integration/c2-honor-20261104`. This local branch must preserve the working GigaAM ASR, Nemotron C2 diarization, export, cancellation and C0 fallback while moving application code to C++.

## HONOR 10X Lite constraints

- DNN-LX9, Kirin 710, ARM64, Android 10. ONNX Runtime uses at most 4 threads: measured 42 s diarization took 95.9 s at 2 threads, 63.5 s at 4, 101.4 s at 8 (`InferenceThreads.kt`).
- On the 20-minute recording, current release took ASR 413.8 s and C2 253.3 s, about 690 s total; wall RTF 0.57. Peak combined app and worker PSS was about 650–656 MiB and battery temperature rose from 42 to 49 °C (`ACCEPTANCE_2026-11-04.md`). Target wall RTF is at most 0.5 without extra sustained memory or thermal pressure.
- Short physical C2 trials: median inference RTF 0.1909; combined PSS peak 669.5 MiB; speaker count 3/3 correct. These figures are not long-recording acceptance (`C2_PHYSICAL_HONOR_2026-11-04.md`).

## Local emulator baseline, 2026-11-04

- API 33, x86_64, 4 virtual CPUs, 4 GiB RAM, WHPX. This is a functional and metric regression environment, not a Kirin 710 speed or thermal proxy.
- Existing Kotlin/JNI C0 benchmark, GigaAM v3 CTC INT8; pinned upstream sherpa runtime SHA-256 `e3905b1258b577d8d374db798618602ceaaff5805cbf9b356ab25267cd98144d` used explicitly for local regression. This differs from the pinned no-TTS product runtime.
- Frozen acted/composed D–M–D audio: SHA-256 `61354eefab1ba60e41e54c2c34e6ddd1b60d99bc923a9b798f26004dd98b3861`, duration 19,655 ms. WER 1/41 and strict cpWER 1/41 (2.44%); recurrence probe passed. DER is unavailable without independent speech boundaries. Raw local output is in `.local/dialogue-benchmark/scores.json` and is ignored by Git.
- Development clustering sweep 0.5, 0.65 and production 0.8 all passed this tiny recurrence probe; 0.9 merged both speakers. Do not select a threshold from this fixture alone.

## Port gate

Run the exact same audio and scorer against each C++ candidate. Preserve segment text, speaker identity/return, timing, unknown-speaker handling, exports and cancellation. Track process time, wall RTF and peak combined PSS separately. Do not promote a candidate based on emulator CPU timing or a score from a different runtime/model. Compare Android ARM64 before declaring a performance gain on HONOR-class hardware.
