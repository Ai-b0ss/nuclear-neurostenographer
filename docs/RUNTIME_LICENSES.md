# Pinned runtime and model license review

Review date: 2026-10-30. This is engineering provenance, not a blanket clearance of a binary distribution.

## Model: cleared MIT provenance
Hugging Face repository `csukuangfj/sherpa-onnx-nemo-ctc-giga-am-v3-russian-2025-12-16`, immutable revision `32a4c7cc81809bd132e2d935ab99e9e6ab47fbec`.
The model card explicitly points to GigaAM's MIT license; the same revision contains an MIT LICENSE, copyright 2024 GigaChat Team. `tools/provision_asr.py` pins that file's SHA-256 and includes it in every model ZIP. It is retained with the weights after installation. This conclusion applies to this model, not to candidate diarization models.

Sources:
- https://huggingface.co/csukuangfj/sherpa-onnx-nemo-ctc-giga-am-v3-russian-2025-12-16/blob/32a4c7cc81809bd132e2d935ab99e9e6ab47fbec/LICENSE
- https://huggingface.co/csukuangfj/sherpa-onnx-nemo-ctc-giga-am-v3-russian-2025-12-16/blob/32a4c7cc81809bd132e2d935ab99e9e6ab47fbec/README.md

## Runtime: full AAR distribution NOT cleared
The pinned official 1.12.20 AAR has SHA-256 `e3905b1258b577d8d374db798618602ceaaff5805cbf9b356ab25267cd98144d`. Its Kotlin code and native ASR API were inspected and host JNI inference exercised. JNI libraries for ARM64 and x86_64 exist. ONNX Runtime is **1.17.1**, verified both in the pinned Android build script and embedded ARM64 binary version strings.

sherpa-onnx source is Apache-2.0; ONNX Runtime is MIT (notices are bundled in app assets). However, the **full official AAR includes TTS code**, even when our app only calls ASR. The pinned upstream build scripts default `SHERPA_ONNX_ENABLE_TTS=ON`; CMake includes the espeak-ng fork at `f6fed6c58b5e0998b8e68c6610125e2d07d595a7`, whose COPYING is GPL-3.0. Android JNI and C API binaries contain `espeak-ng-data` strings. Merely not calling TTS does not establish removal of that code.

Therefore **do not describe the full AAR/APK as Apache/MIT-only or redistribute the resulting APK as cleared**. APK artifact upload is explicitly disabled in android.yml while this is unresolved. Local builds and ephemeral cloud testing remain useful engineering checks. No project-wide license was changed.

The chosen resolution is a separately built pinned source with
`SHERPA_ONNX_ENABLE_TTS=OFF`, retaining speaker diarization. It is built and tested
as described below, and is now the standard build selection. An alternative GPL distribution
strategy would require corresponding-source and application-license review; it
has not been chosen.

## Round 9: built and pinned no-TTS candidate

The earlier GitHub-access blocker is resolved. Native job in
[run 41039830327](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41039830327)
builds both ABIs from the same source commit above, NDK 27.2.12479018,
TTS=OFF and speaker diarization=ON. It checks actual CMake caches, absence of
espeak dependency source and the espeak data marker. The API JAR/manifest are
retained byte-for-byte from the checksum-verified official AAR; every JNI entry is
replaced, retaining only JNI and ORT for ARM64/x86_64. No TTS API should be invoked.

Candidate: **41,464,159 bytes**, SHA-256
`771fda6a4abf845a6f84f48e05e887fdf159671beb88cbc9aae327806511c1c8`.
The candidate contains an explicitly maintained Apache-2.0 patch in
`tools/runtime/`: clamp TopkIndex before iterator construction; preserve unknown
identity when segmentation requests more speakers than positive cluster votes.
Its exact upstream input hashes and changed-file hashes are in the artifact JSON.
Checked-STL negative replay reproduces the original invalid iterator; patched
numeric tests run with ASan/UBSan. This is not a diarization accuracy benchmark.

To reproduce explicit local selection with authenticated GitHub CLI:

```powershell
gh run download 41039830327 --repo Ai-b0ss/nuclear-neurostenographer --name asr-only-runtime-candidate-NOT-DEVICE-VERIFIED --dir .local/no-tts-candidate
python tools/provision_asr.py --runtime-file .local/no-tts-candidate/sherpa-onnx-1.12.20-no-tts-candidate.aar
```

Selection checks the digest pinned in source, not a checksum supplied with an
arbitrary file. A failure preserves the previous runtime. In round 9 no-TTS
selection was explicit; round 10 promotes the same verified bytes to the default.
GitHub Actions artifacts expire; this is a candidate
retrieval route and build recipe, not a permanent public release URL.

Android x86_64 run
[41040637994](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41040637994)
exercises this exact candidate: Russian ASR/diarization/worker tests pass and the
known mixture completes with four unknown turns, no detected overlap. Overall
run fails on the separate FLAC-import bug fixed subsequently. Full final-suite
results are tracked in PROGRESS.md. ARM64 compile is not physical-device evidence.
Default APK publication remains disabled pending runtime distribution/notices
review; absence of one marker string alone is not blanket license clearance.

Final candidate execution at code `d37a030`:
[run 41041827147](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41041827147)
**17/17 PASS, zero skips**, all nine JSON evidence records retrieved. This run
uses the same pinned candidate bytes above after the codec-test fixes. It includes
actual ASR, diarization, worker success/cancel/death recovery, imports, recording
pipeline and exports. Detailed output is retained in `docs/evidence/round9-*.json`.

## Round 10: default no-TTS build and verifiable identity

`python tools/provision_asr.py` now uses this exact no-TTS SHA-256 by default.
The lock is shared with Gradle in `tools/runtime/runtime.properties`. Valid
installation/cache requires no CLI/network. Otherwise the existing GitHub CLI
login (or Actions ephemeral token) retrieves only the pinned artifact from this
repository. Auth/expiry/network/corruption failures preserve the prior runtime
and do not select the upstream AAR. No credentials or settings are changed.

The old baseline is explicitly `--upstream-runtime`, with Gradle opt-in
`-PallowUpstreamRuntime=true`; it remains unsuitable for cleared distribution.
New native builds can be tested with an explicit candidate hash before promotion.
Ordinary Gradle preBuild rejects other bytes. Generated BuildConfig hashes the
actual input AAR; JSON exports and Android inference evidence retain that digest.
The APK check compares all four packaged JNI/ORT files byte-for-byte to the AAR
and verifies its digest is present in DEX. This is packaging identity, not accuracy.

Default build/core/lint/packaging identity PASS:
[41044063915](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41044063915).
Default runtime Android instrumentation **17/17 PASS**:
[41044063778](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41044063778).
Both use the same no-TTS digest above; exact native hashes are retained in evidence.
The round-10 independent native rebuild produces the same AAR digest byte-for-byte.

The rebuild also inventories downloaded dependency source trees and their
top-level license/notice files. These are build inputs, not proof that every
downloaded component is linked. Eigen's tree includes MPL2 and optional GPL/LGPL
texts; listing those files is not a determination that GPL code is present in
the selected Dense headers. The earlier inventory missed ASIO's nested notices
(resolved below). Toolchain/stdlib notices, exact header/link scope and redistribution packaging
still require review. APK publication remains disabled; no blanket clearance.

## Recovery call 9: ASIO nested notices

The pinned [upstream CMake input](https://github.com/k2-fsa/sherpa-onnx/blob/5ce3d6d93a5f4fe11657bf11a6bf3a022eeef22f/cmake/asio.cmake)
selects ASIO 1.24.0 archive SHA-256 `cbcaaba0f66722787b1a7c33afe1befb3a012b5af3ad7da7ff0f6b8c9b7a8a5b`.
That exact archive was verified and inspected without building native code.
Its [COPYING](licenses/asio-COPYING) and [Boost license](licenses/asio-LICENSE_1_0.txt)
are under `asio/`, rather than the FetchContent root. The collector now includes
that explicitly mapped directory, preserving relative paths and existing
size/binary/containment guards. It does not recursively collect arbitrary files.

Exact archive/member hashes are in `evidence/round11-recovery9-asio-notices.json`.
This closes the known collection gap, not linked-header/toolchain analysis or
whole-APK distribution clearance. Old round-10 inventory is retained unchanged;
a subsequent native build must produce its own updated inventory.

Sources:
- https://github.com/k2-fsa/sherpa-onnx/blob/5ce3d6d93a5f4fe11657bf11a6bf3a022eeef22f/LICENSE
- https://github.com/k2-fsa/sherpa-onnx/blob/5ce3d6d93a5f4fe11657bf11a6bf3a022eeef22f/build-android-arm64-v8a.sh
- https://github.com/k2-fsa/sherpa-onnx/blob/5ce3d6d93a5f4fe11657bf11a6bf3a022eeef22f/cmake/espeak-ng-for-piper.cmake
- https://github.com/csukuangfj/espeak-ng/blob/f6fed6c58b5e0998b8e68c6610125e2d07d595a7/COPYING
- https://github.com/microsoft/onnxruntime/blob/v1.17.1/LICENSE

Public upstream WAV test provenance: same immutable HF revision, `test_wavs/example.wav`, SHA-256 `d8aaaa18a5098d7c6de0595ae7ac1e64cacd0d4022af3595213bdaf23be77e69`. This is a single clean public upstream example, not independent Russian conversational accuracy evidence. No private recording is used or uploaded.
