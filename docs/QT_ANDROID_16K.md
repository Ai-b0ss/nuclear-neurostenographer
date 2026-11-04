# Qt/C++ Android 16 toolchain smoke check

The product source branch is `cpp/honor-local-performance`, based on `integration/c2-honor-20261104`. The Qt smoke source used for toolchain validation is in the separate local worktree `D:\neuro-qt-smoke` (branch `cpp/native-core`); it is only a record/import UI without ASR or diarization. It is not a replacement for the integrated app.

Installed locally: Qt 6.10.1 host `mingw_64`, Android `android_x86_64` and `android_arm64_v8a` kits, including Qt Multimedia; Android SDK platform 36; NDK 27.2.12479018 (r27c); JDK 17. The HONOR-like `honor10x_lite_api36_16k` AVD has 4 GiB RAM, four x86_64 virtual cores and 1080 x 2400 at 400 dpi. `adb shell getconf PAGE_SIZE` returned 16384. The AVD does not simulate Kirin 710A, ARM64 performance, thermals or battery use.

Qt's default Android Multimedia deployment pulled in FFmpeg. Its bundled `libavformat.so` was only 4 KB aligned, and the smoke app crashed on the 16 KB AVD with `UnsatisfiedLinkError: failed to setup 16KiB App Compat`. The NDK 26 `libc++_shared.so` was also only 4 KB aligned. The working smoke configuration uses NDK r27c and excludes the FFmpeg media plugin while retaining Qt's native Android media plugin:

```cmake
find_package(Qt6 6.10 REQUIRED COMPONENTS Widgets Multimedia)
qt_add_executable(nuclear-neurostenographer qt-app/main.cpp)
target_link_libraries(nuclear-neurostenographer PRIVATE Qt6::Widgets Qt6::Multimedia)
if(ANDROID)
    qt_import_plugins(nuclear-neurostenographer EXCLUDE Qt6::QFFmpegMediaPlugin)
    set_property(TARGET nuclear-neurostenographer PROPERTY QT_ANDROID_MIN_SDK_VERSION 26)
    set_property(TARGET nuclear-neurostenographer PROPERTY QT_ANDROID_TARGET_SDK_VERSION 34)
endif()
```

The custom Android template's `settings.gradle` must set `rootProject.name = 'android-build'` when Qt deploys into an `android-build` directory. Qt 6.10.1's `androiddeployqt` constructs its expected Gradle APK filename from the output directory name; a different project name makes the CMake package target fail with exit 20 after Gradle has successfully built an APK.

On the fresh `D:\neuro-qt-smoke\build-android-x86-ndk27c-native` build, CMake/Gradle completed successfully, ZIP alignment passed, no packaged x86_64 `.so` had a 4 KB ELF LOAD segment, and the Qt activity launched cold on the 16 KB AVD with a live PID. The debug APK was about 32 MB. This is a toolchain gate only. A full Qt application still needs the integration branch's model installation, C0/C2/ASR orchestration, recording/import, cancellation and exports in C++ plus parity checks.

The separate ARM64 kit also built an APK at `D:\neuro-qt-smoke\build-android-arm64-ndk27c-native\android-build\nuclear-neurostenographer.apk`. Its ZIP alignment and every packaged ARM64 ELF LOAD alignment passed the 16 KB check. It cannot execute on the x86_64 AVD; ARM64 runtime and sustained RTF still require a physical compatible device.

Qt's [Android deployment dependency property](https://doc.qt.io/qt-6/cmake-target-property-qt-android-deployment-dependencies.html) and [plugin import control](https://doc.qt.io/qt-6/qt-import-plugins.html) describe how to keep unused plugins out of the APK. [Qt Multimedia](https://doc.qt.io/qt-6/qtmultimedia-index.html) documents the native Android backend. The exit-20 filename behavior is visible in the [Qt 6.10.1 `androiddeployqt` source](https://github.com/qt/qtbase/blob/v6.10.1/src/tools/androiddeployqt/main.cpp).
