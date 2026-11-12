# HONOR RC5 long screen-off acceptance — 2026-11-12

## Decision

**No physical endurance pass. Correct foreground-to-background acceptance is pending an unlocked HONOR.** The main RC5 application remains installed and unchanged. Global speaker linking stays disabled. Do not treat low temperatures from a suspended run as successful thermal optimization.

## What was measured

The existing isolated Sol QA app has the ordinary RC5 A3+C2 pipeline, realtime compiled, global speakerbook OFF. Input is the same public 20m40s fixture used in emulator QA: 39,680,044 bytes, SHA-256 d57edf4aee0fc50629e2c7239b74f7cd7ea24ed0a68382aad1d81f1f00f5ba45. Its byte-identical private QA copy was hash-verified. No private recording or microphone was used.

| Attempt | Outcome | Observed maximum battery / CPU |
|---|---|---|
| External fixture setup | Rejected before processing because test could not open the fixture | 33 / 38 C |
| Private fixture, headless service launch | Progress froze at 679 ms; manually stopped after 256.91 s | 34 / 42 C |
| Same headless launch, temporary QA-only Android Doze exception | Progress froze at 2693 ms; manually stopped after 126.33 s | 33 / 37 C |

While stalled, the system reported the QA transcription lock under **Force Released WakeLocks**, and the sampled process CPU was inactive. Host battery/CPU telemetry remained available. All QA processes were stopped and their absence verified. The temporary exception applied only to Sol QA, did not resolve the stall, and was removed and its original state verified. No product/global power policy, lock setting or PIN was changed.

The headless launch did not match a user's normal foreground Activity -> foreground service -> screen-off flow. Therefore it does not prove that the main product stalls in that user flow. OEM background-power management is a plausible cause of the observed QA suspension; HONOR documents per-app launch/background controls, but these controls have not been altered or validated here.

Numeric metadata: [honor-long-rc5-investigation.json](evidence/honor-long-rc5-investigation.json). Detailed temperature samples remain local. There is no completed long transcript, comparative RC4 thermal result or energy measurement.

## Corrected test and guard

BatchLongPowerDeviceTest now explicitly requires an interactive, normally unlocked HONOR, launches the real MainActivity first, starts ordinary batch processing, and then switches the display off. It checks the full duration, Russian text in every five-minute interval, end coverage, and eventual CPU-lock/service cleanup. It writes stage/progress heartbeats.

The fixed --test-case powerLong host route retains the existing cool start and stop/warning limits (CPU 75/78 C, battery 43/45 C, severe Android/sensor status or lost telemetry). It captures a numeric thermal timeline. A new progress watchdog aborts a run after 30 seconds without an advancing app heartbeat, or 240 seconds without an initial heartbeat, instead of leaving a frozen QA process waiting for the full outer limit. Stale completed records cannot hide a new hung startup. Only Sol QA and its test package can be stopped by this route.

Seventeen host tests pass, including a full mocked frozen-run stop/cleanup check, timer recovery, invalid/startup/stale-terminal heartbeat cases and all prior thermal cases. The corrected Android instrumentation compiled locally. Actual corrected foreground-flow testing is blocked by the PIN keyguard; no credential was entered or lock bypass attempted. No model, inference setting, normal app binary or ready RC5 APK was changed for these harness fixes.

## Vendor references

- HONOR background restart guidance (per-app background launch/optimization): https://www.honor.com/sa-en/support/content/en-us00406916/
- HONOR background apps forced closed: https://www.honor.com/my/support/content/en-us00428704/
- Android app power management and testing: https://source.android.com/docs/core/power/app_mgmt
