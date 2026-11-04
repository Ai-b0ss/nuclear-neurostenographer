# Local C++ ASR parity probe on Android 16

The integration branch's ordinary ASR uses sherpa-onnx JNI from Kotlin. An opt-in candidate now owns the ASR model, window loop, per-window stream decoding and cancellation/progress callbacks in C++. Kotlin still chooses/refines the windows and fuses speaker/text segments. The isolated parity probe and candidate are separate build switches. Neither path makes the UI a Qt application.

## Reproduce the native runtime

Provision the pinned no-TTS AAR first with `tools/provision_asr.py`. On Windows with Git for Windows, CMake, Ninja, Python and NDK r27c installed:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/nemotron/build_sherpa_no_tts_c_api.ps1 -Ndk 'D:\android-sdk\ndk\27.2.12479018'
```

The script verifies AAR SHA-256 `771fda6a4abf845a6f84f48e05e887fdf159671beb88cbc9aae327806511c1c8`, clones sherpa-onnx tag `v1.12.20` at commit `5ce3d6d93a5f4fe11657bf11a6bf3a022eeef22f`, and builds its C API against ONNX Runtime 1.17.1 extracted from that AAR. The source patch removes upstream TTS=OFF C API stubs, which otherwise still export nonworking TTS symbols. The script checks that no TTS symbols are exported and that all ELF LOAD segments are 16 KB aligned. Generated libraries stay ignored under `.local/native-runtime/probe-jni/{arm64-v8a,x86_64}`. The copied public C API header is Apache-2.0, like the pinned sherpa runtime.

Local stripped library SHA-256: ARM64 `dd4802597478c93325c56c9d896b95f480fa02ee2cfa134f0b1e5b248436d691`; x86_64 `c778fa3019fe3b9802f15954869c9fadb9a674db0127e7a6214c1cf6ca01389e`. These are build evidence, not a reproducibility guarantee across toolchain versions.

## Android emulator parity

```powershell
$env:JAVA_HOME='C:\Program Files\Microsoft\jdk-17.0.21.21-hotspot'
$env:ANDROID_HOME='C:\Users\Anon\AppData\Local\Android\Sdk'
$env:ANDROID_SDK_ROOT=$env:ANDROID_HOME
& 'C:\Users\Anon\AppData\Local\Gradle\gradle-8.9\bin\gradle.bat' --no-daemon -PnemotronPrototype=true -PnativeAsrProbe=true '-Pandroid.testInstrumentationRunnerArguments.class=ru.neurostenographer.app.NativeAsrProbeTest' :app:connectedDebugAndroidTest
```

On `honor10x_lite_api36_16k` (API 36, `PAGE_SIZE=16384`), the one-case instrumentation test passed: C++ C API and current JNI returned identical text on the same 19.655 s public Russian WAV and GigaAM model. The test APK had both ABI libraries, no `espeak` markers in them, and passed `tools/check_android_native_pages.py` for ZIP and every packaged ELF. The probe measures text parity only; it does not establish full chunk/window attribution, cancellation, export parity, physical HONOR speed, or a full Qt application.

## Opt-in C++ ASR candidate

Run the pinned six-case C0/C2 instrumentation plan with `-PnemotronPrototype=true -PnativeAsrCandidate=true`; score the pulled `files/nemotron-evidence.json` with `tools/score_honor_cpp_emulator.py` and the same frozen references. On the API 36 16 KB AVD, all 12 runs passed after the window loop moved into C++. Every speaker turn and transcript segment was exactly equal to the pinned no-TTS JNI baseline. WER stayed C0 47/378 and C2 43/378 across these six cases; strict cpWER is unavailable on cases with unattributed words. DER is unscored because the external turn labels include substantial silence. Raw evidence and corrected scores are ignored under `.local/native-runtime/native-asr-pipeline-six-case-{evidence,scores}.json`. The instrumentation wall/inference fields time diarization, not ASR, so these results establish text parity but no ASR speedup. `NativeAsrPipelineLifecycleTest` also passed: cancellation after a native decode propagated to Kotlin and a retry succeeded, confirming model cleanup on that path.

The product-like debug build uses `-PnemotronProduct=true -Pc2Candidate=true -PnativeAsrCandidate=true`. Its locally saved APK is `.local/artifacts/honor-cpp-c2-native-asr-candidate-api36-debug.apk`, SHA-256 `97aca35af34fb5dc1396b9d35ff5fb37f0b29ba298edef5a71452850c4948104`, 58,777,613 bytes. `tools/nemotron/check_prototype_apk.py ... --native-asr` reported no problems, and `tools/check_android_native_pages.py` passed ZIP alignment and all ten ARM64/x86_64 ELF files. It installed and cold launched as `ru.neurostenographer.app.c2candidate` on the 16 KB emulator with a live PID. This is a debug-signed local candidate with no bundled model.

Before replacing the ordinary JNI path, move remaining input/fusion and UI to C++/Qt6, repeat full failure checks on that final path, and measure wall RTF, RAM and thermals on a physical HONOR. The C API adds about 3.2 MB (ARM64) or 3.5 MB (x86_64) to an APK while the old JNI runtime remains packaged.
