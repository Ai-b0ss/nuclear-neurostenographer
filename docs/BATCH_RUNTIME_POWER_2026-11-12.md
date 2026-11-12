# Batch processing: CPU waiting and screen lifetime — 2026-11-12

## Decision and scope

Keep the four-thread cap, GigaAM A3, Nemotron C2 weights, two passes and product postprocessing unchanged. Disable ORT thread-pool spinning for batch C2 only. Real-time inference is unchanged. Experimental global voice linking remains off in the ordinary app.

Replace the display-awake requirement during transcription with a user-initiated dataSync foreground service and a bounded partial CPU wake lock. This lets the display sleep while local file processing continues. Recording keeps its existing display/foreground behavior. Import, model setup and export retain their foreground fallback.

The service has an ongoing notification with a stop action, reference-counted work leases, an idempotent release, stop-on-task-removal and no sticky restart. The CPU lock is released after the last work lease (checked every 500 ms), on service destruction, or after a six-hour upper bound. Android 15's onTimeout also cancels active work and stops the service. Cancellation preserves the source audio via the existing view-model path. A synchronous foreground-service launch denial retains the old display-awake foreground fallback. No Internet permission or battery-optimisation exemption was added.

## Measured host evidence

One frozen public 60-second Russian book-mixture clip; exact pinned ORT 1.17.1 and C2 assets; each configuration warmed once, then three measured rounds in rotating order. Each case creates and closes its session. CPU time sums process threads; wall time measures C2 inference, excluding session creation. Both product passes run. Every emitted millisecond turn matches the reference in every measured round.

| ORT configuration | Median wall ms | Median process CPU ms | Median CPU ms in subsequent 200 ms idle |
|---|---:|---:|---:|
| 4 threads, spinning | 3922.60 | 15046.88 | 46.88 |
| 4 threads, blocking | 3971.62 | 12906.25 | 0.00 |
| 2 threads, blocking | 6535.25 | 12125.00 | 0.00 |

Four blocking threads used 14.23% less process CPU time at 1.25% longer wall time in this experiment. Two threads took 66.60% longer than the baseline, so changing thread count is not justified.

**These are Windows measurements, not HONOR energy, temperature, sustained throughput, or proof of a fixed overheating problem.** One clip and three repetitions do not establish population-wide accuracy or performance. Source pins and individual measurements are in [batch-runtime-host.json](evidence/batch-runtime-host.json).

Reproduce with `python tools/c2pp/measure_runtime.py --wav <public-wav> --model <pinned-c2> --harness <compiler-and-ort-cache> --java <jdk17-java>`. Outputs stay under .local; no recording, transcript or embedding is published.

## Android validation

The emulator-only QA route wakes/foregrounds the app, starts real processing, verifies the foreground service and CPU lock, then turns the emulator display off. The ordinary repeat, different-sources, absent-model and real 20m40s cases retain their previous functional assertions. Service lifecycle checks cover overlapping owners, duplicate release, restart, notification cancellation and release before service startup. Completion must release both service and lock.

All four emulator cases passed on code commit 3ffdc4b3dc7a01acc60db4d6e4e00665f8d05084 ([workflow 43278838801](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/43278838801)). Repeat took 40,145 ms (24 segments), differentSources 33,398 ms (25), absent model 40,402 ms (24), and the real 20m40s fixture 317,235 ms (252 segments, 21 unknown, five profiled blocks). The long result retains text in every five-minute interval: [61, 61, 61, 61, 8]. All cases verified screen-off processing and subsequent CPU lock release. The repeat case also passed every lease/cancellation lifecycle check. Local core groups, QA APK/instrumentation build, actionlint and ordinary [Android CI](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/43278849760) passed. Public host C2/TitaNet regression passed. Numeric metadata: [batch-runtime-android.json](evidence/batch-runtime-android.json). Emulator battery fields are placeholders, not temperature measurements. An emulator validates lifecycle and functional behavior, not real-device thermals, OEM background restrictions, ARM performance, or battery health.

## Physical device

No new physical inference was started. The earlier sustained HONOR test was stopped at the configured CPU 78 C cutoff. That is a test watchdog result, not evidence that the phone shut down, that the battery was 78 C, or that charging damaged the device. A subsequent read-only ADB check found DNN-LX9 on external power at 81%, battery 33.0 C, Android battery health GOOD and display ON. The global plugged-in stay-awake option was 0 (off); this does not negate the app's own display-awake flag. No charging or display setting was changed. Software battery health does not measure remaining battery capacity. A second idle read reported Android thermal status 0 (NONE), maximum reported CPU cluster temperature 41 C, no neurostenographer line in the sampled cpuinfo output, and no app-owned display-awake window. These are idle observations, not sustained-load evidence.

The next physical acceptance run requires the existing host thermal guard, cool preflight (battery below 39 C, CPU below 65 C, charge at least 40%), and this concrete load reduction. Keep stop thresholds battery 45 C, CPU 78 C, severe Android thermal status, or unreliable telemetry. Run off the charger with a sleeping display; do not change global stay-awake settings without restoring them, and never fake battery telemetry to simulate unplugging. A thermal abort remains a failure of sustained acceptance, not a reason to raise thresholds.

## Primary references

- Pinned ORT 1.17.1 spin keys and default: https://github.com/microsoft/onnxruntime/blob/v1.17.1/include/onnxruntime/core/session/onnxruntime_session_options_config_keys.h
- ORT threading: https://onnxruntime.ai/docs/performance/tune-performance/threading.html
- Android foreground types (dataSync includes local file processing): https://developer.android.com/develop/background-work/services/fgs/service-types
- Android bounded wake locks: https://developer.android.com/develop/background-work/background-tasks/awake/wakelock/set
- HONOR charging heat guidance: https://www.honor.com/global/support/content/en-us00409974/
