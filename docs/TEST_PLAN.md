# Test plan — not benchmark results

## Device acceptance
1. Install debug APK on Android 8+.
2. Disable Wi-Fi and cellular connectivity (flight mode).
3. Record 45–60 s Russian conversation with two voices alternating A → B → A.
4. Import a pre-recorded audio file with three voices.
5. Verify stable speaker IDs, readable transcript and millisecond-based time ranges.
6. Export JSON/SRT/TXT; compare outputs against raw model evidence.
7. Repeat with interruptions and two voices speaking simultaneously.
8. Monitor RAM, total processing time and failures (OOM, crash, hangs).

## Accuracy
- **WER** = word substitutions + deletions + insertions divided by reference word count. Normalize punctuation/casing consistently.
- **DER** = diarization time errors divided by total reference speaker time; document collar, speaker mapping and whether overlapped speech is scored.
- **cpWER** = sum of concatenated-per-speaker word errors after selecting minimum-error speaker permutation; tests both ASR and speaker attribution.
- **RTF** = processing seconds / recording seconds. Record warm/cold model load separately.
- **Memory** = peak app RSS/PSS and observed model peak, measured on an actual Android phone.

## Datasets
- https://huggingface.co/datasets/ivkond/synthetic-speech-diarization-ru — 2000 synthetic Russian tracks with speaker labels/timestamps, noise and overlap.
- Genuine consented Russian conversations, independently transcribed, are needed to test real-world conditions.
- Do not confuse clean single-speaker Golos/Common Voice audio with multi-speaker diarization benchmark.
- Keep private audio outside GitHub Actions, GitHub issues, PR comments and public artifact uploads.

Do not claim benchmark accuracy or timing from a desktop source as mobile measurements.
