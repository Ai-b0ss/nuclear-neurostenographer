# FDDT hybrid on physical HONOR — 2026-11-08

## Scope and isolation

Experimental branch experiment/fddt-hybrid-20261108 started from origin/main at 7597b2b.
Build flag -PfddtHybrid=true requires -PnemotronProduct=true -PasrA3=true.
Separate Android package ru.neurostenographer.app.fddtqa: original production app
ru.neurostenographer.app and published GitHub release v0.3.16-contest are unchanged.
All processing was offline, Android airplane mode = 1 on HONOR 10X Lite / DNN-LX9 / Android 10, ARM64.

Model origin: Ruzanna's fddt_rnnt 2.zip (SHA-256:
e3459a89aba3b80a1df1ddb20550bf308ee1ab517252c58af8956a7622950097),
encoder_fddt.int8.onnx, decoder.onnx, joint.onnx, tokens.txt;
original GigaAM A3 and Nemotron C2 unchanged.
File SHA-256 checks before first use and app-private model storage.
ONNX Runtime Android 1.17.1 CPU, same version as stable application.
New APK size 658738349 bytes; APK SHA-256:
89e65e6146dc63f6f1957e87e7ce98ccf36618b2581d3f6114dccb52c17d318e.

## Complete phone run — 4 speakers and overlapping speech

Test WAV: zz-mic-2-4speakers.wav, 49.402 s (original fixture on phone).
File imported by Android system file picker; app performed full C2 diarization,
A3 transduction, second pass through FDDT models for detected overlapping turns,
presented the final transcript, and exported JSON using actual Save JSON button.
Save location on test device: Download/ns-acceptance/fddt-qa-zzmic2.json.
Private transcript provenance includes fddt_e2e_rnnt_int8_hybrid_r1.
The competition JSON has {transcript: [{speaker_id,start_ms,end_ms,text}, ...]};
22 rows passed integer bounds and schema validation.

| Metric | Original A3 + C2 | Integrated A3 + C2 + FDDT |
|---|---:|---:|
| Transcript segments | 20 | 22 |
| Recognized words | 60 | 76 |
| Unknown-speaker segments | 8 | 2 |
| Unknown-speaker words | 21 | 2 |
| Labeled speakers | 4 | 4 |

Nine overlapping regions detected; two-speaker text reconstructed on several.
Example 3.91–5.52 s: Speaker 1 «Какие напоминания», Speaker 2
«Открой температуру», displayed with overlapping timestamps.
C2 15,304 ms. ASR load 4,093 ms, recognition including optional FDDT
44,853 ms, from actual NeuroStenoMetrics phone log (49.402 s audio).
Output local audit snapshot: .local/fddt-end-to-end-output.json (not committed).
Reviewable evidence committed:
- docs/evidence/fddt-qa-20261108/honor-fddt-overlap-4speakers.png — phone screenshot
- docs/evidence/fddt-qa-20261108/fddt-qa-zzmic2.json — actual exported competition JSON

This comparison DOES NOT measure cpWER. There is no verified manual reference
for this specific 49 s fixture; more words can include hallucinations or
speaker-attribution errors. Count improvements are directly measured facts,
not evidence of 45% lower WER on this recording.

## Negative control — ordinary sequential speech

syn3-clean.wav, 33.507 s, three voices and no overlapping turns:
7 segments. Every segment's text and speaker labels match the previously
saved stable A3+C2 output exactly. Provenance contains no FDDT suffix.
Baseline not replaced or degraded when no qualifying overlap occurs.

## Previous independent ONNX CPU bench, separate from app

One 33.507 s single-target pass with 4 threads and ORT 1.17.1:
RTF 0.4618, peak RSS VmHWM 681,820 KiB (665.8 MiB), cold model load 13.76 s.
This is NOT full-hybrid RTF; integration performs C2, A3 and additional passes.

## Host tests and compile

Gradle --offline --no-daemon :core:runCoreTests :app:assembleDebug
-PnemotronProduct=true -PasrA3=true -PenglishAuto=true -PfddtHybrid=true:
PASS, including FddtOverlapPlan tests and 20 core test groups.
Android debug APK installed side-by-side and launched successfully.
Additional Gradle :app:lintDebug and :app:assembleDebugAndroidTest: PASS
(62 actions, one existing deprecated-API warning in RealtimeDeviceTest).

## Cancellation during FDDT on actual phone

Re-imported the same four-speaker overlap WAV, waited for
«Разделяю перекрытия: 1 из 9», then tapped the actual round Cancel icon
(center of the button, not the non-clickable text label).
App returned to the source/audio-ready screen showing:
«Расшифровка остановлена. Аудио можно расшифровать снова или удалить.»
No new transcript was written after cancellation. A3/C2 model state remained
installed; source WAV remained available for immediate retry.
Screen evidence:
- docs/evidence/fddt-qa-20261108/honor-fddt-cancel.png.

The first automation attempt touched the static text label rather than the
round Cancel icon; that was a test-driver error. Repeating with the real
button independently confirmed cancellation works.

## App memory sample (not peak)

During an additional run on HONOR, adb dumpsys meminfo reported TOTAL PSS
735,468 KiB (~718 MiB), including native heap 623,996 KiB. This is one
point-in-time sample, NOT proven worst-case memory; the independent standalone
FDDT pass peak remains separately recorded above.

## Known gaps and acceptance for merging to main

- Ruzanna reported cpWER 19.8% A3 -> 10.9% hybrid on same 24 synthetic
  conversations (ONNX int8 hybrid 10.8%). These are research results,
  not independently reproduced in this experiment; per-record hybrid STM
  and run_local.py are absent from delivered zip.
- Same 24 conversations selected word-count fallback threshold and context.
  Independent annotated speech required.
- Expanded overlap regions replace baseline words with FDDT output times
  at region granularity. Need independent check for token duplication and
  timestamps, especially at 20-second boundaries.
- Missing/empty speaker hypothesis never substituted for another speaker;
  batch fallback to unchanged A3 is conservative.
- Peak process memory of full app with multiple speakers not yet measured.
- APK + FDDT assets ~659 MB debug, versus 420 MB signed stable product.
- Experimental variant increases ORT dependency footprint. Before merging
  to main, gate FDDT runtime and verify default APK compatibility.
- Current implementation does not repair chunked long-audio global speaker IDs;
  it fixes regular (<=20 min) file handling.


## Reproducing this experimental APK on another computer

Prerequisites: JDK 17, Gradle 8.9, Android SDK, project sherpa-onnx AAR,
and the exact Ruzanna Telegram archive fddt_rnnt 2.zip, never an arbitrary
unverified model download.

1. From repository root run:

       python3 tools/prepare_fddt_assets.py --archive "/path/to/fddt_rnnt 2.zip"
       python3 tools/prepare_fddt_assets.py --verify-only

   The tool verifies full archive SHA256 and SHA256/size of each of the
   four ONNX/tokens assets, then installs only those four files atomically
   under .local/fddtAssets. It never imports or executes Python from the zip.
   A second invocation is idempotent. A wrong 448 KB previous archive fails
   closed. Fresh extraction and repeated validation were both tested.

2. Make the existing project A3/C2 assets available as described in the
   standard build instructions. Build with flags:

       gradle :core:runCoreTests :app:assembleDebug -PnemotronProduct=true -PasrA3=true -PenglishAuto=true -PfddtHybrid=true

3. Install the experimental build by adb install -r
   app/build/outputs/apk/debug/app-debug.apk. Package ID is
   ru.neurostenographer.app.fddtqa, separate from production app ID.

The delivered GitHub PR intentionally excludes bulky 328 MB model files
and does not require user credentials or a paid API to compile.
