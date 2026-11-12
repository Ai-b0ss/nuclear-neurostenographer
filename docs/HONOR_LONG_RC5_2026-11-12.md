# HONOR RC5 sustained screen-off acceptance — 2026-11-12

Status: RUNNING, no endurance pass claimed yet.

This named opt-in test runs the ordinary RC5 A3+C2 pipeline in the existing isolated Sol QA application: realtime compiled, global speakerbook OFF. It uses the same pinned public 20m40s continuous fixture (39,680,044 bytes, SHA-256 d57edf4aee0fc50629e2c7239b74f7cd7ea24ed0a68382aad1d81f1f00f5ba45), copied into the QA application's own private files, not private user audio.

The host route is --test-case powerLong, with two-second polling and a 1200-second outer bound. It retains all existing cool-start and battery/CPU/Android/sensor cutoffs, limits forced cleanup to Sol QA and its test package, and adds numeric temperature samples over time. The app independently checks battery/Android severe status, verifies the display stays off, writes numeric stage/progress heartbeats, and requires the complete duration, Russian segments in every five-minute interval, end coverage, and CPU-lock/service release. No model, thread count, processing logic, ordinary feature flag or production APK was changed for this test.

The first setup attempt failed before inference when the external-storage fixture was unavailable to the test. Battery and CPU stayed 33 C; this was not a thermal result. A byte-identical copy in the QA private directory was hash-verified and the setup corrected. The controlled run is now in progress; logs remain local until a terminal result is available.

Local validation: 14 watchdog unit tests, APK instrumentation build, unchanged signed RC5 product preserved as the sole ready production APK. Physical evidence must be labeled separately from the existing emulator result.
