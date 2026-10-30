# Local audio import and erasure

Round 5 implements Android platform decoding. **Compilation and host core tests
are separate from device execution. MediaCodec tests are NOT_RUN until actual
Android evidence is recorded.** No compressed-codec/device success is claimed yet.

## Accepted input

PCM16 RIFF WAV continues through the strict Kotlin parser, with 1–2 channels,
8–48 kHz and 0.1–120 seconds. RIFF input is never retried through a more permissive
decoder after failing WAV validation.

Round 7 validates the **entire** RIFF container before returning PCM. Valid unknown
metadata chunks before/after audio and odd-byte chunk padding are consumed. A
second `data`/`fmt `, truncated metadata/padding, incomplete chunk header, invalid
RIFF extent or bytes outside that extent fail explicitly. Multiple audio data
chunks are unsupported: previously only the first was silently transcribed. The
normalized samples/resampling algorithm is unchanged. Container sizes and padding
follow the [Microsoft RIFF description](https://learn.microsoft.com/en-us/windows/win32/xaudio2/resource-interchange-file-format--riff-).
This structural validation does not interpret every metadata schema.

Other containers are parsed by Android MediaExtractor and decoded by MediaCodec.
On Android 13 the FLAC extractor may already emit `audio/raw` PCM16; this path
uses the same bounded WAV writer/timeline checks without creating another codec.
An explicit PCM16 encoding is required for raw extractor output; float PCM and
unknown bit depth are rejected. A generated high-bit FLAC probe checks actual
extractor encoding: safe platform conversion to PCM16 is accepted, raw float is
rejected. The source file's bit depth alone does not determine decoder output.
The allowlist is MP3 (`audio/mpeg`), AAC/M4A (`audio/mp4a-latm`), Ogg Vorbis/Opus,
FLAC, AMR-NB and AMR-WB. Availability depends on the Android version/device and
container. AMR has no generated test fixture yet. Unsupported codecs/formats,
DRM/encrypted or partial input packets, more than one audio track, decoded
non-PCM16 output, multichannel audio and changing sample rates/channels fail
explicitly. No decoder/model is downloaded by the app. FFmpeg is used only on the
developer/CI host to generate test tones; it is not packaged or invoked by the app.

Imports accept document/file URIs only. Provider bytes are copied to an owned
private file, capped at 24,088,584 bytes (about 24 MB), before MediaExtractor opens
that local path. The app never passes a network URL to a media API. Decoded PCM is
also capped at 120 seconds independently of metadata. A cooperative 60-second
deadline bounds the codec polling loop; provider reads and native setup calls
can block and are not hard-preempted by it. Cancellation is checked during copy,
polling, PCM writing and validation. Partial/staged files are deleted on failure;
the previous selection/result survives an unsuccessful replacement.

Decoder output becomes PCM16 WAV in private cache, then uses the existing
mono/16-kHz resampling path. Resampling remains linear, with its documented
quality limitations. Output timestamps must follow decoded sample count within
100 ms; larger gaps/discontinuities fail rather than silently compressing a
recording timeline. The first decoded sample is time zero. Encoder delay/padding
handling is platform-dependent: exported intervals refer to this decoded audio,
not guaranteed frame/word alignment with the original compressed container.
No word offsets or speaker identities are manufactured.

## Privacy and cleanup

The **Удалить локальное аудио и результат** button removes app-generated WAV
recordings, accepted import copies and abandoned import/diarization temporary
files, and clears the current source/result and pending export body. It is disabled
while recording/processing. It does not traverse arbitrary directories or remove
models. Exported documents remain with their selected document provider and must
be deleted there. This is ordinary file deletion, not a claim of forensic erasure
from flash storage. Cache eviction/process death can require reimport; recording
files may persist until explicit cleanup or app-data removal. No transcript history
database is implemented. Backup/device-transfer exclusions and absence of INTERNET
permission remain in place; the chosen Android document provider may itself use
cloud storage independently of the app.

## Reproduce the checks

```
python tools/provision_codec_fixtures.py
python tools/test_codec_fixtures.py
gradle :core:runCoreTests :app:lintDebug :app:assembleDebug :app:assembleDebugAndroidTest
```

Fixture generation needs FFmpeg on PATH. It generates numeric 440/880-Hz stereo
tones, **not speech**, as AAC, MP3, Vorbis, Opus and FLAC; also two-audio-track and
121-second negative AAC fixtures. All audio stays in ignored `.local/` test assets.
The manifest records generator version, source PCM hash, output byte counts and
SHA-256 hashes. Ogg container serial numbers and encoder versions can change file
bytes, so the generated manifest is checked rather than claiming immutable fixture
hashes across hosts. A generator failure clears stale fixtures/manifest. Python
checks independently decode the five fixtures through FFmpeg and test their extent
and energy; **these are fixture checks, not Android decoder tests**.

Core tests cover eight PCM writer roundtrips, fragmented/offset input buffers,
exact PCM16 samples, maximum duration, short/partial/cancelled output, cleanup,
timestamp gaps, overflow and state preservation after rejected timeline buffers.
`WavContainerTest` adds valid metadata/fragmented-read cases, eight malformed
container negatives, cancellation after PCM decoding and snapshot cleanup/previous
input preservation. Android replacement tests also cover duplicate data and bytes
outside RIFF; their execution remains NOT_RUN.
`CodecImportTest` on Android checks generated fixture hashes, actual MediaCodec
output bounds/energy, source mutation, malformed/ambiguous/long input, cancellation,
local-URI restrictions and file cleanup. It writes `codec-import-evidence.json`
only after all five positive codecs pass. Device failure remains a failing test.
`AudioInputTest` covers failed replacement and explicit local-audio cleanup.

The offline cloud workflow generates fixtures and its collector retrieves codec
JSON, removing a stale/missing collected file on failure. Android instrumented
tests must run in an isolated test installation; they clear app data/audio and
must not run against a user's real recordings. Microphone, real compressed
Russian conversations, codec delay/alignment on each device and ARM64 execution
remain unverified. Numeric tones do not measure ASR, WER, DER or speech quality.

## Official API references

- [MediaExtractor local sources and sample flags](https://developer.android.com/reference/android/media/MediaExtractor)
- [MediaCodec buffer ownership, output format and EOS](https://developer.android.com/reference/android/media/MediaCodec)
- [Android supported media formats](https://developer.android.com/media/platform/supported-formats)

The implementation is original project code using Android APIs; no third-party
decoder source or library was copied into the app.
