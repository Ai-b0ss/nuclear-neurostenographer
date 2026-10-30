# Experimental full-recording diarization

Implemented in round 2; round 9 executes real Android x86_64/API 33 inference,
A-B-A recurrence, repetition, silence/short input and worker lifecycle tests.
Exact suites/failures: [PROGRESS.md](PROGRESS.md). Physical ARM64 and independent
Russian dialogue accuracy remain unverified. Host results are separate evidence.

## Use

Run `python tools/provision_diarization.py` on a networked PC, transfer the resulting
`.local/diarization.zip` (45,599,092 model/license bytes before ZIP headers) by USB,
and use **Установить модели говорящих ZIP**. No app INTERNET permission is needed.
The strict importer accepts only the two pinned models and their two license files.
Previous installation survives invalid, incomplete or cancelled imports.

GigaAM remains a separate installation (`python tools/provision_asr.py --model`).
With both installed the app runs pyannote segmentation, ERes2Net embeddings and
global complete-link cosine clustering once on the whole recording, before ASR.
Models run sequentially and are released before the next engine loads.
There is no declared or forced speaker count. IDs are numbered by first appearance
within this recording; these are voice clusters, never identities or names.

The threshold is **0.9**, selected from the upstream hint for the public Chinese
example. **0.5 failed** recurrence and overclustered that file into seven voices.
0.9 is not independently tuned on Russian dialogue and can merge different voices.
No accuracy, DER, cpWER or smartphone speed claim is made.

## Timing and uncertainty

ASR decodes detected speech intervals, split at changes/overlap boundaries and at
20-second limits. It does not decode the gaps classified as non-speech. A first
integration that decoded 202/236/324 ms gaps hallucinated short text; the actual
Russian fixture regression now checks the known phrase and excludes those gaps.
Segmentation false negatives can omit speech; boundaries can cut words.
No word timestamps are manufactured. JSON records both timing and speaker sources.

Labels with negative cluster IDs and evidence shorter than 300 ms receive no
exported speaker ID. Their intervals remain in the timeline as ineligible evidence,
so a brief/unknown interruption cannot disappear and make another voice appear
reliable. Short detected speech >=100 ms can still be transcribed as unknown.
Below 100 ms it is skipped. Nonfinite/reversed native intervals fail explicitly;
padded output is clipped to the recording length. Overlapping *different* clusters
are preserved, and fusion assigns `speaker_id=null`, `overlapping_speech=true`,
`attribution_reliable=false` on their shared intervals. TXT/JSON/SRT retain warnings.
`attribution_reliable` only describes temporal agreement with model turns; it is
not a calibrated voice confidence score. Undetected overlap is still possible.

The pinned native implementation bypasses embeddings when its input fits one
10-second segmentation window. Short recordings are zero-padded to 11 seconds
to use the global path; output beyond the real duration is removed. This is tested
on a five-second clean public voice, but introduces the overlap runtime risk below.

## Known native overlap failure and containment

Mix the public fixture samples `[1s,6s)` and `[7s,12s)` at equal gain (0.5 each).
On Windows x64, pinned JNI 1.12.20 crashes with `EXCEPTION_ACCESS_VIOLATION`
inside `OfflineSpeakerDiarization.process`. The process exits before producing
diarization. This is **FAIL**, not an overlap detection success. No JVM exception
handler can catch that native fault.

Source review finds `FinalizeLabels` calls `TopkIndex(count, num_cols, k)` without
checking whether local simultaneous-speaker count `k` exceeds the global cluster
count. Round 9 reproduces the invalid iterator with checked STL and builds a
strictly pinned no-TTS candidate: clamp before iterator construction and return
unknown identity for unsupported speaker counts/zero-vote candidates. On Android,
the original worker fails this mixture; the candidate completes with four unknown
turns and no detected overlap. This is not separation or overlap accuracy, nor a
symbolicated Windows fix. See [candidate provenance](RUNTIME_LICENSES.md).

Android now runs diarization in a private, non-exported `:diarization` service
process with the same app UID. Bounded samples go through a temporary app-private
file, not Binder arrays; result IPC is bounded. On worker death, bind failure,
explicit error or timeout the caller falls back to ordinary ASR with **unknown**
speakers and `speaker_source=failed_worker_unknown_speakers`; the UI shows failure.
Round 8 makes each binding own one native request. Final unbind destroys the
service; it terminates its own dedicated `:diarization` process because Java
thread interruption cannot stop this JNI call. The process-name guard prevents
this shutdown path from killing the UI process. The caller serializes requests,
observes Binder death for up to five seconds during non-cancellable cleanup,
and refuses another request if the prior worker's exit is still unconfirmed.
Late replies are ignored and the owned temporary file is deleted. This applies
to completion, cancellation and the ten-minute processing timeout. OS lifecycle
delivery is still required; this is not a hard real-time shutdown guarantee.
Android x86_64 success/cancel/retry process-exit and staged-cleanup tests PASS in
round 9. Ten-minute timeout and physical-device scheduling remain separate risks.

Before accepting a result, the caller validates bounded array counts, interval
limits/order, nonnegative timings, canonical anonymous speaker labels, short or
unknown attribution eligibility, and the exact speech-window partition derived
from the turns. Missing windows cannot silently omit detected speech; extra
windows cannot inject silence into ASR. Invalid replies become explicit worker
failures and use the existing unknown-speaker fallback. Silence remains a valid
empty result. No partial diarization is accepted.

Instrumentation includes worker kill/restart and the actual known-mixture probe.
Round 8 adds successful/cancelled worker exit, retry and staged-file cleanup;
the collector retains metadata only and removes stale lifecycle evidence on
failed retrieval. Pure Kotlin reply-corruption tests execute independently of
Android, and do not prove Binder/process lifecycle behavior.
These tests execute on the cloud emulator; worker-death recovery and caller
survival on the original native mixture failure PASS. Direct host inference runs in a
child JVM; its exit status and lack of output are retained as failure evidence.

## Reproduce

JDK 17 and Python 3.11+ on Windows AMD64 or Linux x64:

```
python tools/run_host_inference.py --java /path/to/jdk17/bin/java
```

The script verifies AAR, host JNI and Kotlin compiler dependencies by SHA-256,
compiles the actual app inference files, and runs ASR, diarization, combined Russian
inference and the overlap regression. It writes `.local/host-results/*.json` and
logs. **A failing overlap probe makes the whole command exit 1**; earlier PASS
files are removed before each probe. No synthetic text is used as model output.
The Android AssetManager placeholder is only for host class loading; file-based
model APIs run through genuine JNI. This is not an Android simulation.

Cloud workflows: `host-inference.yml` for supplemental Linux JNI evidence;
`offline-asr.yml` for Android x86_64 instrumentation including diarization. Both
have now executed on the WIP branch. Emulator capture/worker/document paths are
checked; physical ARM64, airplane mode, realistic Russian conversations and phone
RTF/peak RAM/thermal benchmarks remain NOT_RUN.

## Pinned sources and licenses

- Android lifecycle: [bound-service lifecycle](https://developer.android.com/develop/background-work/services/bound-services#Lifecycle). Final unbind destroys a bound-only service; no startService call is used here. Killing the owned process is our containment policy, not an upstream sherpa cancellation API.

- Runtime API/example: [official Android object](https://github.com/k2-fsa/sherpa-onnx/blob/5ce3d6d93a5f4fe11657bf11a6bf3a022eeef22f/android/SherpaOnnxSpeakerDiarization/app/src/main/java/com/k2fsa/sherpa/onnx/speaker/diarization/SpeakerDiarizationObject.kt), [Kotlin API](https://github.com/k2-fsa/sherpa-onnx/blob/5ce3d6d93a5f4fe11657bf11a6bf3a022eeef22f/sherpa-onnx/kotlin-api/OfflineSpeakerDiarization.kt), [native implementation](https://github.com/k2-fsa/sherpa-onnx/blob/5ce3d6d93a5f4fe11657bf11a6bf3a022eeef22f/sherpa-onnx/csrc/offline-speaker-diarization-pyannote-impl.h).
- Segmentation: [immutable converted revision](https://huggingface.co/csukuangfj/sherpa-onnx-pyannote-segmentation-3-0/tree/9403a6902bb58e3d5ae8c7e77c3422de279db2e0), model SHA-256 `220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079` (5,992,913 bytes). Included MIT license, CNRS 2022. Original [pyannote model card](https://huggingface.co/pyannote/segmentation-3.0) declares MIT; its gated original access is distinct from the public converted artifact used here. No account/gating bypass or private credentials used.
- Embedding: official sherpa [ERes2Net release asset](https://github.com/k2-fsa/sherpa-onnx/releases/tag/speaker-recongition-models), SHA-256 `1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b` (39,593,761 bytes). Upstream [exact model owner metadata](https://modelscope.cn/api/v1/models/iic/speech_eres2net_base_sv_zh-cn_3dspeaker_16k) explicitly declares Apache License 2.0 for these weights, trained on Chinese 3D-Speaker. Included [source license](https://github.com/modelscope/3D-Speaker/blob/065629c313eaf1a01c65c640c46d77e61e9607b4/LICENSE). Russian generalization is unproven. Mutable release URL is protected by a pinned digest; replacements fail closed.
- Public test WAV: [upstream example](https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/0-four-speakers-zh.wav), SHA-256 `bedf036caed208386c67b4ef4b11f83d74dd0d420b102163a1c33cd09cde7010` (1,819,586 bytes). Used locally/ephemerally for the official example regression; separate recording redistribution rights were not established, so audio is never committed or uploaded as an artifact. Composed A-B-A uses cuts from this example and is labeled composed, not natural Russian conversation.

The full AAR's separate GPL/TTS distribution blocker still applies; see
[RUNTIME_LICENSES.md](RUNTIME_LICENSES.md). Model licenses do not clear that binary.
