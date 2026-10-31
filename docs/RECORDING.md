# Recording ownership and failure behavior

Round 6 uses the official AudioRecord PCM16 short-array READ_NON_BLOCKING API
(available before minSdk 26). Zero means no data yet; negative counts fail.
Samples become little-endian 16 kHz mono WAV through the bounded core writer.
No padding or speech synthesis is introduced.

A new recording is staged while the previous selected audio/transcript remains
in memory. Recognition/export/import/cleanup are disabled during capture. Only
successful stop replaces the selection and clears the previous transcript. Failed
initialization, read, WAV finalization or release keeps the old source/result.
Short/failed partial files are deleted. Older successful microphone recordings can
remain in filesDir until explicit cleanup; import snapshots are discarded after
successful replacement.

Capture has both a 120-second sample cap and elapsed polling limit. All-zero
samples are recorded audio, not proof of audible speech. Stalled hardware is not
filled with invented samples. WAV time refers to captured sample count; hardware
latency and lost frames are not calibrated. The observer notices completion/error
and finalizes without another button press. Leaving the activity stops capture;
rotation retains the ViewModel/session. A permission result received while the
activity is stopped cannot start background capture.

One writer thread owns read and release. Stop requests termination and joins for
up to five seconds. A join timeout is an explicit unknown completion state: the
UI retains ownership/recording guard, blocks import/cleanup, permits retry and
observes completion. No concurrent forced release or deletion occurs. Native
start/read/stop/release and filesystem calls are not hard-preemptible. A broken
driver can still stall; no absolute shutdown guarantee is claimed. Clearing the
ViewModel requests stop immediately, then joins off the UI thread.

## Evidence boundaries

Core tests use generated signed numeric PCM and injected capture errors: zero
reads, exact sample values, negative/oversized counts, short capture, start/release
failure, timeout ownership/retry, one-shot/repeated stop and exact sample cap.
They execute production file/thread/cleanup code on a JVM. They are not Android
microphone, speech accuracy or ASR evidence.

Android RecordingTest separately checks ViewModel failed start/stop, preservation
of old input, blocked cleanup on timeout, successful replacement and two actual
AudioRecord sessions. Actual-capture tests are for an isolated emulator, save only
SDK/ABI/duration/byte-count metadata and delete captured WAVs. No microphone audio
is collected. The collector removes stale recording JSON on retrieval failure.
Round 9 cloud Android x86_64 execution passes these tests and a separate platform
recording -> ViewModel -> real diarization worker -> transcript document/cleanup
test. The emulator supplies non-speech samples; empty output is valid and does not
establish microphone speech accuracy. Background stopping, rotation, permission
denial/revocation and physical ARM64/airplane-mode record-to-export need execution.

Round 10 executes real permission denial/grant, landscape rotation during capture,
HOME auto-stop and expected OS process restart after permission revocation through
the actual UI on Android x86_64/API 33. A subsequent UI launch has no phantom
recording and explicit cleanup removes abandoned owned audio. Screenshots and
tree-driven assertions are retained in the Actions artifact. This verifies the
emulator path, not physical-phone permissions, audible microphone ASR accuracy,
document-provider save dialogs or all background-driver behavior.

## References

- [Official AudioRecord API: short-array reads, READ_NON_BLOCKING, error codes,
  recording state and release](https://developer.android.com/reference/android/media/AudioRecord)
- Production: core BoundedWavRecorder, Android RecordWav and TranscriptionViewModel.
  Existing [privacy/cleanup limits](AUDIO_IMPORT.md) apply.
