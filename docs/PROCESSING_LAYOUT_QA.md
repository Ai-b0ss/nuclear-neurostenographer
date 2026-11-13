# Processing layout regression QA

Issue51 concerns stage-to-stage movement of processing controls and player/cancel usability. The source already has the compact cancel and round player thumb. This continuation measures the rendered processing layout, including large text, on a cloud x86_64 Android10 emulator. No physical device, audio, models or recognition is used.

Opt-in build: `gradle -PlayoutQa=true -Prealtime=false :app:assembleDebug :app:assembleDebugAndroidTest`. The isolated application ID is ru.neurostenographer.app.layoutqa; model assets are excluded and only x86_64 is packaged. Compose test-host dependencies and the dedicated test class exist only in this variant. Ordinary APKs do not acquire a test Activity or test dependencies.

The test renders seven authored processing states at font scales1.0/1.3/2.0 and360 dp width. It records real geometry, checks TextLayoutResult overflow, requires the progress track to stay within2 px across states, and clicks the accessible cancel action before checking the disabled cancelling state. Screenshots and fresh-run JSON are captured. This is UI regression evidence, never inference/quality evidence.

The host runner refuses physical serials/properties, requires both JUnit and fresh complete21-state evidence, rejects duplicate/missing states, clipping, moved progress or stale IDs, and stops only the isolated QA packages. Workflow execution is manual or a deliberate push to the named QA branch.

Current status: local QA APK and test APK compile; four host evidence regressions pass; the new workflow passes actionlint. Cloud baseline rendering is being checked before a layout fix or acceptance claim.
