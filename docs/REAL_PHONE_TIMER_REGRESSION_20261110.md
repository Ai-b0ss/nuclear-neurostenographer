# HONOR live-recording timer regression — 10 November 2026

Observed on physical HONOR 10X Lite (Android 10) using signed 0.4.1-rc2
(versionCode 23). Screen capture was performed locally and saved privately:
K:/nn-issue50-20261110/.local/live_honor_screen/session-20261110-214624/.
No user audio, utterance text, or private screenshots are published.

## Reproduction and confirmed cause

- During diarization the UI displayed native C2 progress 3/12 and a very wide
  00:25–01:00 predicted interval.
- After native C2 completed, the UI still said «Кто говорит» but its
  progress/estimate disappeared, replaced by «Запускаю определение
  говорящих…». The total elapsed timer kept advancing.
- Device logcat confirms C2 completed normally after 48.639 seconds and
  transcription then proceeded through VAD and ASR. This was a UI state
  transition defect, not a restarted diarizer or lost results.
- Root cause: TranscriptionViewModel.endDiarizationTiming() cleared
  diarizationClock but left stage == 2 until the first ASR callback.
  Model/VAD/language initialisation took time, exposing an incorrect start
  placeholder in ProcessingCard.
- Separate UX defect: showing a large ETA uncertainty range looked like a
  broken countdown. Stage ETA is inherently approximate.

## Fix / acceptance

1. Exit stage 2 as soon as C2/C0 completes successfully. Show
   Говорящие определены. Готовлю текст… until the text stage starts.
   If neither diarizer succeeds, move to the text stage explicitly with
   a clear status; never strand the screen with a null diarization clock.
2. Show one rounded approximate remaining time at each stage when
   calibrated, not a range; use a non-numeric Уточняю... for unavailable
   estimates. Actual elapsed time and native chunk counts remain exact.
3. Core regressions test approximate 5-second rounding, unknown/expired,
   and never displaying 00:00 while native work is active.
4. Real-device acceptance replays a public Veche Bench 172-second recording:
   after native 1/N progress, Запускаю определение говорящих… must never
   appear again; stage 3 must appear before ASR completes, and countdowns
   may not jump sharply upwards.

No speech/model weights/ASR text/storage/certificates changed. Do not modify
user media or erase application data. Install a signed RC only after the
full core + Android instrumentation compilation + lint gate.

## Follow-up: inaccurate ASR-stage ETA (same physical device)

The first fix (0.4.1-rc3) correctly maintained stages and completed a
172-second test in approximately 132 seconds. But at the final ASR callback
(17/17 decoded windows) it still claimed around 20 seconds remaining, whereas
the saved result appeared about 5 seconds later. The extrapolation of the
overall processing duration from an earlier, slower Nemotron phase is not
a reliable forecast for ASR. This is a separate verified error.

The next revision uses AsrWindowEta: actual completion timestamps of individual
ASR windows determine text-stage throughput, with smoothing and bounded
deadline corrections. Until a window-time sample exists, ETA is unknown.
At the final callback, numeric countdown is removed and the screen displays
finalization status. Long recording processingClock remains separate.
