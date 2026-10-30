# Architecture and non-functional constraints

## Mandatory functionality
1. Android application.
2. Audio transcription **on device**, without cloud ASR.
3. Automatic speaker diarization: same speaker retains ID on later utterances.
4. Structured transcript with speaker IDs and time ranges.

Online streaming, personal name identification and word-level timestamps are optional extensions, not contest requirements.

## Target on-device pipeline

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
