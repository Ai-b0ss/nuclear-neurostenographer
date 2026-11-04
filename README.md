# Nuclear Neurostenographer

Offline-first Qt 6/C++ desktop shell for recording and importing conversation audio. Speech recognition and diarization are not connected yet; the app does not claim to generate a real transcript.

## Build

Requires Qt 6.4 or newer with Qt Multimedia and CMake 3.21+.

```sh
cmake -S . -B build
cmake --build build
```

The Qt build is checked by `.github/workflows/qt.yml`. The previous Android/Compose prototype remains in `app/` and `core/`; the Qt app is the active desktop entry point. Microphone recordings are local raw PCM audio. No network access is used.

## Android APK

The Android target uses Qt for Android with the `arm64-v8a` ABI. It declares microphone access and requests runtime permission before recording. Build it with a matching Qt Android kit, Android SDK/NDK, JDK, and Gradle:

```powershell
$env:JAVA_HOME = 'C:\path\to\jdk-17'
$env:ANDROID_SDK_ROOT = "$env:LOCALAPPDATA\Android\Sdk"
$env:ANDROID_NDK_ROOT = "$env:ANDROID_SDK_ROOT\ndk\26.1.10909125"
& 'C:\Qt\6.7.3\android_arm64_v8a\bin\qt-cmake.bat' -S . -B build-android -G Ninja
cmake --build build-android --target apk
```

The available Qt 6.7.3 kit uses its bundled Android Gradle Plugin, so the app targets API 34 for Android 16 backward compatibility. Runtime compatibility still needs verification on a device. Qt's documented Android 16 support starts with Qt 6.10.
