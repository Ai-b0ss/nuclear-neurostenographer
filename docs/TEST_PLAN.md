# Test plan — not benchmark results

Archived public provider exports can be audited without Android or downloads:
`python tools/test_android_evidence.py`, then
`python tools/verify_android_evidence.py --ui-report docs/evidence/round11-ui-flow.json --apk-report docs/evidence/round11-apk-inspection.json --directory docs/evidence --prefix round11-provider-export`.
This checks recorded hashes/byte counts, cross-format intervals and runtime
agreement. It does not authenticate external reports or execute a model/device;
its result is explicitly archived-file integrity, separate from accuracy.

Round 10 validates the standard no-TTS build and explicit upstream regression:
each passes **17 instrumentation tests and 7 actual UI checks**, zero skips.
See PROGRESS.md for exact CI URLs. UI assertions cover real microphone dialogs,
rotation, HOME stop, recorded-input document controls, cleanup and permission
revocation. Tests use an isolated emulator; screenshots/XML are retained in CI.
Round 11 adds actual system import/save: **17 instrumentation + 11 UI checks PASS**
in run 41056348245 at 12b81bb. TXT/JSON/SRT provider files are read and compared,
including cancellation and pending-picker rotation. Emulator microphone capture
is silent; no spoken microphone recognition accuracy is established. The separate
three-utterance Russian acted probe fails speaker recurrence (cpWER 60.98%),
despite WER 2.44%; DER has no independent reference. See RUSSIAN_EVALUATION.md.
Default runtime identity is checked in Gradle, packaged native bytes, DEX and
actual Android inference metadata. These checks establish no accuracy metric.

Round 9 executes the Android x86_64/API 33 suite in GitHub Actions. Russian ASR,
global recurrence, worker success/cancel/crash recovery, recorded-input pipeline,
WAV state/cleanup and exports have executed successfully. Codec failures exposed
EOF and raw-FLAC defects; exact final suite outcomes are in [PROGRESS.md](PROGRESS.md).
Final suites at code commit `d37a030`: **17/17 PASS** on both original and pinned
no-TTS runtime; **16 core groups PASS**. Native completion and overlap accuracy
are separate: original known mixture still fails its worker, candidate completes
with four unknown turns and no overlap detection. The test verifies containment.
The round-specific notes below preserve earlier test-development history; their
NOT_RUN descriptions refer to those earlier rounds. Physical ARM64, airplane mode,
independent Russian dialogue accuracy and phone peak RAM/thermal remain open.

Round 4: `python tools/test_score_transcript.py` checks original WER/cpWER/DER
arithmetic and independent assignment/time oracles. Run
`python tools/test_android_workflow.py` for shell success/failure/collection tests
with fake commands (not Android). [BENCHMARKS.md](BENCHMARKS.md) defines real
reference provenance, normalization, collar/overlap and NOT_SCORED behavior.
`PcmStreamingTest` checks 48 exact PCM comparisons, source buffering and tail
truncation. Device tests now persist real public-fixture inference JSON and memory
snapshots; these are not peak RAM and remain NOT_RUN until cloud/device execution.

Current reproducible automated checks: `python tools/provision_asr.py`, then `gradle :core:runCoreTests :app:assembleDebug`. For genuine x86_64 inference, run the manual `offline-asr.yml` workflow (or provision `--test-assets` and run `:app:connectedDebugAndroidTest` on a configured emulator). Tests use a pinned public upstream WAV; two repeat transcriptions, known Russian phrase, silent PCM, absent INTERNET permission, unknown speaker attribution, invalid model ZIPs. Evidence/status is in PROGRESS.md; compiling the instrumentation APK is not executing these tests. Host JNI results do not establish Android correctness or WER/DER.

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

Round 3 adds pure Kotlin snapshot tests (16 kHz recorded-style WAV, 44.1 kHz stereo import, source mutation, malformed/truncated/disconnected/oversized/short/long/cancelled input), exact-ms/locale/export document tests, and Android `AudioInputTest`. The Android real-public-fixture ViewModel test covers import snapshot -> actual ASR -> UI document -> TXT/SRT/JSON output, destination truncation, and changing input while a JSON export is pending. These device tests must actually execute to establish Android behavior; local instrumentation compilation is not a PASS for them. Actual microphone/permission lifecycle testing still needs an Android device.

`python tools/verify_transcript_exports.py .local/host-results` independently parses the host-produced JSON/SRT/TXT, checking text, speaker labels, cue count/order, exact millisecond intervals, duration bounds and metadata. This is serialization/timeline validation of actual inference, not WER/DER or word alignment.

Round 2 reproducible host suite: `python tools/run_host_inference.py --java /path/to/jdk17/bin/java`. Includes real global A-B-A recurrence, repetition, short input/padding, silence, cancellation cleanup, Russian ASR + inferred boundaries, and a process-isolated known-overlap regression. Native overlap failure must remain FAIL. Android instrumentation now includes worker death/restart and known mixture containment; compilation is not execution. Details and exact limits: [DIARIZATION.md](DIARIZATION.md).

Round 5: [audio import checks](AUDIO_IMPORT.md) cover bounded PCM16 writing and timestamp continuity in core, generated numeric AAC/MP3/Vorbis/Opus/FLAC fixture validation, and Android codec/cleanup/negative tests. Host FFmpeg fixture validation is not Android MediaCodec evidence. Device tests remain NOT_RUN. Generate `python tools/provision_codec_fixtures.py` before the full instrumentation suite; it requires FFmpeg on the fixture-generation host only.

Round 6: [recording checks](RECORDING.md) cover file/thread behavior with fake
captures (9 core scenarios), ViewModel failed-recording/timeout selection and two
real AudioRecord sessions on an isolated emulator. Android tests compile but remain
NOT_RUN. No microphone WAV is collected. `python tools/test_create_checkpoint.py`
checks uppercase artifact/secret/cache exclusion and disguised binary/large files;
the symlink test can skip when the OS disallows creating test symlinks.

Round 7: `WavContainerTest` checks full RIFF extent and trailing chunks before
acceptance (8 malformed-container cases, metadata/padding, fragmented reads,
cancellation and snapshot preservation). Existing 48 exact PCM parity cases
remain regression gates. The scorer suite now has 12 methods, including 18 CLI
malformed-root/duration/flag cases that must replace stale favorable reports with
ERROR. Android WAV replacement negatives compile separately from device execution.

Round 8: `DiarizationReplyTest` rejects 20 IPC corruptions, including dropped
speech windows, inserted gaps, out-of-audio/overflow intervals, invalid labels,
unknown/short reliable attribution and oversized/mismatched arrays. Silence,
unknown and real overlap semantics remain valid. Android instrumentation adds
final-unbind process exit after success/cancellation, retry and staged cleanup.
These are separate gates: core execution cannot establish Android process exit.
Collector tests seed stale lifecycle JSON and require removal on failed retrieval.
