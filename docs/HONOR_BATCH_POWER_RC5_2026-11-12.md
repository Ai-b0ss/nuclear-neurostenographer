# HONOR batch power check and RC5 — 2026-11-12

## Result

The ordinary A3 + C2 batch path completed a 10-second public Russian fixture on physical HONOR DNN-LX9 / Android 10 ARM64 with the display off. Experimental global speaker linking was disabled; realtime support was compiled as in the normal product. This was an isolated Sol QA installation, not instrumentation of the user's main application.

- Actual pipeline: 24,196 ms including cold processing setup; three nonempty Russian transcript segments with valid time bounds and C2 provenance.
- Display verified off throughout the busy wait. Foreground processing and CPU lock verified active before sleep and released after completion.
- Host guard: 30.25 seconds including instrumentation setup/cleanup; battery 33 C throughout, live CPU clusters 34 C initially and maximum 52 C. Android/sensor thermal status stayed NONE; no warning.
- CPU numeric readings came from the CURRENT HAL block. Existing warning/stop thresholds remain unchanged: CPU 75/78 C, battery 43/45 C.
- Both isolated QA packages were force-stopped afterwards and absence verified. No microphone, private recording, permission grant, battery telemetry spoofing, or global stay-awake change.
- Phone was externally powered. These single short cold-start observations do not establish endurance, energy savings, warm throughput, an improvement relative to RC4, or a 20-minute thermal pass.
- [Sanitized device and watchdog evidence](evidence/honor-batch-power-rc5.json).

## Reproduction

Build the existing isolated Sol QA package with product A3+C2, realtime compiled, and globalSpeakerBook=false. Sign both app and instrumentation with the existing Sol QA key; update in place. Run the new named class only via:

`python tools/run_android_long_thermal_guard.py --adb <adb> --serial <HONOR> --test-case power --poll-s 1 --limit-s 150 --log <new-log>`

The host route fixes the Sol QA application/runner, supplies its explicit short-test opt-in, retains cool-start/CPU/battery/OS protection, and cannot target the product package. The test requires DNN-LX9, Android 10 and ARM64; other normal/emulator test routes skip it. A short PASS requires both new app-side evidence and JUnit/host success, not a skipped or stale test.

## Build and release

Version 0.4.1-rc5 / code 26 built with A3, C2, realtime=true and globalSpeakerBook=false. Core checks, QA app/instrumentation build, normal product build and 13 host watchdog tests passed.

The original external production keystore was found and its public certificate matched the installed RC4. APK signature, application ID, version, product flags and SHA-256 were verified. Only the newest ready production APK is retained under .local/releases/current with its checksum. The original production key stays outside the working tree; its location and alias are recorded in ignored .local/release-signing-context.json. No key, password or APK is committed.

## Completed in-place installation

After the owner normally unlocked HONOR, the original-certificate RC5 APK installed successfully over the main ru.neurostenographer.app package using adb install -r. No uninstall or data clear was performed. Installed version code26 / 0.4.1-rc5 and the unchanged original signing certificate were verified. MainActivity cold launch returned Status: ok; the app process remained alive and its working screen was verified (31 app UI nodes, recording action present, no startup-error label). No additional inference or sustained load was started.

The earlier installation attempts were blocked after screen-off QA activated the existing PIN keyguard. The owner resolved that lock normally; no credential was entered by automation and no lock or global verification/power policy was changed. Sol QA had already updated in place and passed the short physical flow. Unknown-source confirmations were handled only for the named, verified application updates.
