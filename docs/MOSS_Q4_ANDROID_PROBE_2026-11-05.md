# MOSS Q4 on the 4 GiB Android emulator

We evaluated the proposed MOSS-Transcribe-Diarize model as a standalone native
C++ candidate on the same Android 16 API 36 x86_64, 16 KiB page, 4 GiB RAM
emulator used for the app. This was a device-side CPU run, not a desktop speed
projection. It was not linked into the app or added to its APK.

The C++ runtime was [audio.cpp](https://github.com/0xShug0/audio.cpp), commit
`1d077bc68047d38de8c3986dd08cf48812ea21ee`, built with NDK 26.1 for
Android API 34 (executable run on API 36), x86_64 CPU, no OpenMP or host ISA
specialization, 16 KiB ELF load alignment. The complete
[MOSS Q4_K GGUF](https://huggingface.co/audio-cpp/audio.cpp-gguf/tree/main/MOSS-Transcribe-Diarize-GGUF)
is 758,293,216 bytes, from repository revision
`fd2fe4c3195bc410f8b817bf7c7519fd822686fb`, SHA-256
`4e3020379ff592bbb22a4e3d47a7cd6709951cc5d451c561b69df955b5f0a220`.
The model was copied to `/data/local/tmp`; neither weights nor WAVs are in Git.

Two pre-existing RINCO WAVs were selected for this first probe: q144, on which
the current ASR makes no error, and i1321, on which it makes two. Both have
manual ELAN text references. MOSS ran on the complete WAV and emitted its own
speaker/timestamp segments; A0/A3 used the product C2 windows. The WER scorer
uses only text and the same normalization for each output. Speaker labels from
RINCO are not independently verified, so cpWER/DER are not scored here.

| Recording | A0 current | A3 | MOSS Q4, 2 threads/default tokens | MOSS Q4, 4 threads/256 tokens |
|---|---:|---:|---:|---:|
| q144, 35.9 s, 62 words | 0/62, 1.755 s | 0/62, 2.952 s | 0/62, 137.35 s | — |
| i1321, 23.0 s, 45 words | 2/45, 1.539 s | 3/45, 1.778 s | **1/45, 74.79 s** | **1/45, 33.43 s** |

The 256-token setting preserved all 196 generated tokens and the exact i1321
text while reducing the decoder cache capacity from 5,501 to 637 steps. A
`dumpsys meminfo` sample during the default i1321 run showed **2,866,209 KiB
PSS**, including **1,160,416 KiB swap PSS**. A sample during the tuned run
showed **1,243,574 KiB PSS** and no swap. These are samples, not peak values,
and were measured for a standalone process; the app's previously measured PSS
includes different components. On q144, `/proc` reported 2,615,284 KiB peak
RSS and about 970 MiB swap near completion.

MOSS improved one word on one of two short files, but even the tuned run took
about 22 times as long as A0 on i1321. These two files do not establish a
general quality gain, and the standalone runtime does not establish an
integrated Android app. MOSS is not promoted for the weak HONOR target. It may
be revisited as an optional accuracy mode if a larger held-out Russian set and
an end-to-end memory/latency budget justify it.

## Reproduce

Clone `audio.cpp` at the commit above including its pinned submodule; configure
with the Android NDK x86_64 toolchain, `ANDROID_PLATFORM=android-34`,
`ENGINE_ENABLE_OPENMP=OFF`, `ENGINE_ENABLE_LLAMAFILE=OFF`,
`ENGINE_ENABLE_NATIVE_CPU=OFF`, `CMAKE_EXE_LINKER_FLAGS="-Wl,-z,max-page-size=16384 -llog"`;
build `audiocpp_cli`. Download the Q4 GGUF from the pinned revision and check
its SHA-256. Copy the binary, model, and pinned RINCO WAVs to the emulator.
For i1321, run:

```text
audiocpp_cli --task asr --family moss_transcribe_diarize \
  --model model.gguf --model-spec-override embedded --backend cpu \
  --threads 4 --audio i1321.wav --request-option max_tokens=256 \
  --segments-out i1321-tuned.segments.json --log
```

Pull the JSON files to ignored `.local/moss-audio-cpp/`; run
`python tools/moss/score_android_probe.py`. The scorer checks the model, WAV
and baseline audio hashes before reporting WER.
