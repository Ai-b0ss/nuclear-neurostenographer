# Optional known speaker count on Android 16

The default remains automatic speaker estimation. In the app, when the C0 diarization model is installed, a user who knows the exact participant count can choose 2, 3 or 4 before transcription. This runs the existing C0 clustering with that count. It does not download or load another model, and it skips C2 for that recording because C2 has no corresponding count control. Choosing a different value clears the previous transcript, so the displayed result always belongs to the chosen setting. Export provenance records `user-speaker-count-N`; a warning states that an incorrect count may hurt attribution.

## Evidence

`DiarThresholdProbeTest.compareKnownSpeakerCount` ran the same 10 frozen WAVs through C0 and GigaAM v3 CTC on the 4 GB Android 16/API 36, 16 KB page emulator. It compared automatic clustering with a count taken from source metadata. `tools/nemotron/score_known_speakers_probe.py` verifies the audio hashes against independently stored references before scoring. Acted dialogue clips are composited, and four synthetic recordings have coarse turn labels; the dataset does not justify DER. Strict cpWER is reported only where the scorer can attribute all words.

| C0 setting | Correct speaker count | WER | Scored cpWER |
| --- | ---: | ---: | ---: |
| Automatic | 3/10 recordings | 55/525 | 143/456 |
| Source count supplied | 8/10 recordings | 55/525 | 123/456 |

The aggregate improvement is conditional on knowing the correct count. It is not a claim of automatic diarization improvement. The count hint still failed to obtain the requested count in two recordings. It also worsened `ivkond-3overlap` cpWER from 18/52 to 36/52 despite obtaining three speaker IDs, so count alone cannot ensure correct identity assignment. Global C0 threshold changes were rejected separately in `ASR_HEAD_ANDROID_PROBE.md`.

The opt-in `SpeakerCountFlowTest` installs pinned models, imports a previously frozen three-speaker WAV, selects count 3 through `TranscriptionViewModel`, runs full transcription, and verifies C0 provenance and a nonempty transcript. It also verifies that switching back to Auto clears the old transcript. This passed on the Android 16 16 KB emulator. The APK's ARM64 and x86_64 native libraries plus ZIP alignment pass `tools/check_android_native_pages.py`; the no-TTS content gate passes.

The C2 prototype debug APK was installed and launched on that emulator, and the selector was visible in the UI. The prototype release build also compiled and its unsigned APK passed the 16 KB alignment gate. The release artifact is unsigned and was not installed. The benchmark only exercises the count hint with the existing C0 model; it does not establish that the extra choice improves automatic C2 results or that the phone meets a speed target.

One already installed `.c2` package displayed the system's 16 KB ELF compatibility warning even though the APK alignment gate passed and `dumpsys package` reported `pageSizeCompat=0`. A fresh, otherwise identical `.pageprobe` application ID installed and cold launched on the same emulator without that warning. This points to package-specific persisted emulator state, but is not proof about every device. The fresh-install check is repeatable with `-PpageSizeProbe=true`; the product package and its test data were not uninstalled. Physical HONOR speed and memory remain unmeasured for this option.
