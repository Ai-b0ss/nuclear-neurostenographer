# Architecture and non-functional constraints

## Mandatory functionality
1. Android application.
2. Audio transcription **on device**, without cloud ASR.
3. Automatic speaker diarization: same speaker retains ID on later utterances.
4. Structured transcript with speaker IDs and time ranges.

Online streaming, personal name identification and word-level timestamps are optional extensions, not contest requirements.

## Target on-device pipeline

Current implemented baseline is `PCM16 WAV -> bounded mono/resampling -> verified GigaAM v3 CTC -> 20-second input chunks -> TranscriptFusion.attributeChunks(empty speaker turns) -> UI/export`. Optional pinned pyannote + ERes2Net full-recording diarization runs in a private worker process before ASR, and supplies speech windows/global cluster IDs through a strictly validated reply. Worker failure falls back to unknown speakers. See DIARIZATION.md for the known native overlap crash and unexecuted Android containment tests. Native resources are owned by the IO worker and released in `finally`; ViewModel retains operations across rotation. ASR cancellation is cooperative between blocking JNI steps. Diarization cancellation releases the bound service, which terminates its guarded dedicated process; the caller observes death and blocks another request while prior exit is unknown. Android execution of that lifecycle is NOT_RUN. Model installation switches the selected directory only after all hashes pass. The compressed-codec decoding is implemented through Android platform APIs (execution NOT_RUN); word alignment remains unimplemented. See [audio import and privacy](AUDIO_IMPORT.md).

```
Recorded/imported audio -> decoder -> PCM16 mono -> 16 kHz -> samples
                                            |
              +-----------------------------+-----------------------------+
              |                                                           |
       ASR segmentation + recognition                          Full-audio diarization
       Silero VAD + GigaAM v3 CTC/RNNT                     pyannote segmentation + embeddings
              |                                                           |
       word timestamps if available                               speaker turns/RTTM
              |                                                           |
              +-----------------> TranscriptFusion <---------------------+
                                     |
                            JSON / SRT / TXT + UI
```

Important: run diarization on the **entire conversation or globally reconciled windows**, not independently isolated VAD chunks; otherwise speaker labels may change with each chunk.

Imported WAVs are copied into bounded app-private cache snapshots and validated before replacing the selected source. A bad/short/oversized/cancelled import removes its staged copy and keeps the previous result. This avoids relying on document-provider access or mutable source bytes during subsequent inference. A successful `TranscriptDocument` owns the output intervals, audio duration, model/timestamp/speaker provenance and warnings. Export captures its UTF-8 body before opening the document chooser; selecting a new source cannot silently change that pending export. JSON retains metadata even when no text was recognized; TXT/UI retain milliseconds and SRT uses the same chunk boundaries. No provider URI or private path is exported. Cache eviction and process death can require reimport; transcript history persistence is not implemented.

`TranscriptFusion.attributeWords` requires genuine timestamps for each recognized word. When ASR only gives timestamps for entire chunks, use `attributeChunks`, which refuses to invent speaker identity if a chunk crosses two speakers. Do not interpolate word times and present them as model evidence.

## Engineering constraints
- Audio samples and diarization must share a time origin. Resampling changes the sample index, not the timeline in seconds.
- 16 kHz mono float32 is a common runtime input; input MP3/M4A/OGG should be decoded and resampled on device.
- Approximate word alignment should be clearly identified as approximate.
- Reuse a single diarization configuration for the entire session; tune clustering threshold on held-out audio.
- Preserve unknown speaker and overlapping-voice states.
- Consider limited memory and thermal throttling on midrange Android devices.
- Never display fixture/demo transcription as real inference output.

## Quality gates
- Build and launch APK on emulator.
- Use an offline smartphone in flight mode to record, process and export a multi-speaker conversation.
- Verify A-B-A, two speakers, interruptions, noisy audio and silent segments.
- Measure WER, DER (explicit collar and overlap setting), cpWER, RTF, peak RAM and APK size.
