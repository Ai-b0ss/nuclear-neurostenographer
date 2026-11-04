# Nuclear Neurostenographer

Offline-first Qt 6/C++ desktop shell for recording and importing conversation audio. Speech recognition and diarization are not connected yet; the app does not claim to generate a real transcript.

## Build

Requires Qt 6.4 or newer with Qt Multimedia and CMake 3.21+.

```sh
cmake -S . -B build
cmake --build build
```

The Qt build is checked by `.github/workflows/qt.yml`. The previous Android/Compose prototype remains in `app/` and `core/`; the Qt app is the active desktop entry point. Microphone recordings are local raw PCM audio. No network access is used.
