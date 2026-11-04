# Local C++ ASR parity probe on Android 16

The integration branch's production ASR still uses sherpa-onnx JNI from Kotlin. This probe establishes a version-matched C++ path before changing that product flow. It never runs in ordinary or C2 candidate builds.

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

The product path should move the ASR window loop to C++, rerun the six pinned internet recordings and failure/cancellation tests, then compare wall RTF and combined PSS on the physical HONOR before replacing JNI. The C API currently adds about 3.2 MB (ARM64) or 3.5 MB (x86_64) to a probe APK; removing the old JNI path is a separate step.
