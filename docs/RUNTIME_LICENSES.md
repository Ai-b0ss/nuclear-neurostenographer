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

Preferred resolution: build the same pinned source with `SHERPA_ONNX_ENABLE_TTS=OFF`, retain speaker diarization, verify no espeak dependency, test both ABIs, then pin the resulting AAR SHA-256 and update provisioning. A manual cloud workflow is supplied for that build, but is NOT_RUN until GitHub writes are available. Its output is a candidate, not automatically selected by the app. An alternative GPL distribution strategy would require corresponding-source and application-license review; it has not been chosen.

Sources:
- https://github.com/k2-fsa/sherpa-onnx/blob/5ce3d6d93a5f4fe11657bf11a6bf3a022eeef22f/LICENSE
- https://github.com/k2-fsa/sherpa-onnx/blob/5ce3d6d93a5f4fe11657bf11a6bf3a022eeef22f/build-android-arm64-v8a.sh
- https://github.com/k2-fsa/sherpa-onnx/blob/5ce3d6d93a5f4fe11657bf11a6bf3a022eeef22f/cmake/espeak-ng-for-piper.cmake
- https://github.com/csukuangfj/espeak-ng/blob/f6fed6c58b5e0998b8e68c6610125e2d07d595a7/COPYING
- https://github.com/microsoft/onnxruntime/blob/v1.17.1/LICENSE

Public upstream WAV test provenance: same immutable HF revision, `test_wavs/example.wav`, SHA-256 `d8aaaa18a5098d7c6de0595ae7ac1e64cacd0d4022af3595213bdaf23be77e69`. This is a single clean public upstream example, not independent Russian conversational accuracy evidence. No private recording is used or uploaded.
