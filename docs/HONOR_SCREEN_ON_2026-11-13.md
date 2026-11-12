# HONOR screen-on processing and balanced batch ASR — 2026-11-13

## Owner display instruction

Never turn off or lock the physical HONOR during these checks. Both physical short/long tests now use a foreground QA Activity, wait for RESUMED and hold only its FLAG_KEEP_SCREEN_ON. They send no display power commands and change no global timeout/security/battery policy. Window ownership is restored at cleanup even after other cleanup failures.

## RC5 sustained result: thermal abort

The ordinary RC5 A3+C2 pipeline, realtime compiled and global speaker linking OFF, processed the pinned public 20m40s fixture with display ON. It was stopped by the host guard after 172.91 s at CPU78 C, battery40 C. Warnings began at143.3 s / CPU75 C. Last app heartbeat was at165.908 s in ASR stage3, with stage-local progress0.6; this is not 60% of the complete recording. Both isolated QA packages were stopped and absence verified. No endurance PASS or complete long transcript.

An interim live reading of43–44 C was taken after the force-stop and represented cooling; it was not evidence of a still-running safe workload. [Authoritative thermal timeline and last app heartbeat](evidence/honor-rc5-screen-on-thermal-abort.json).

## Concrete reduction before repeating

RC6/code27 candidate limits batch OfflineAsr inference to two threads per session. Model weights, input windows, greedy decoding, word timing and fusion are unchanged. Realtime still calls modelConfig with its existing four-thread default; C2 keeps four threads and its previously validated blocking workers. This targets ASR concurrency after the observed ASR-stage cutoff; it does not prove that ASR was the only source of heat.

An explicit inferenceThreads argument allows the physical test to compare the same public10-second probe at4 then2 threads using the exact Android runtime. The emitted text hashes match. Times were7580 and7973 ms; one ordered cold/warm pair is not a statistical speed, accuracy or energy benchmark. Host max CPU63 C / battery36 C; normal cleanup verified. Runtime assertions also confirmed the batch default2 and unchanged realtime model-config default4. [Paired numeric evidence](evidence/honor-rc6-asr-thread-parity.json).

The RC6 long run ended THERMAL_ABORT after607.16 s: battery45 C, peak CPU71 C. Both QA processes were stopped and cleanup verified. See [terminal evidence](evidence/honor-rc6-screen-on-result.json). Existing cool start and stop/warning thresholds are unchanged. The app wait bound is19 min within the existing20-min host bound to accommodate slower processing. No RC6 endurance pass, production installation or updated ready release is claimed yet; the installed and sole ready product APK remains RC5 until validation finishes.

Local core checks, QA app/instrumentation builds and18 host watchdog unit tests passed. Only the test route can select the paired probe, and forced cleanup is still restricted to Sol QA and its test package.

## Current owner direction

Physical HONOR endurance testing is suspended. Do not implement cooling pauses now. Continue quality evaluation and development on PC and accelerated cloud Android emulators. Hardware endurance remains unverified and is not a blocker for off-device development. Never lock or turn off the physical display.
