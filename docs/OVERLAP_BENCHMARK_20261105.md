# Issue #10 — Reproducible Russian overlap benchmark protocol
**Prepared 2026-11-05. Status: NOT_RUN for overlap recovery.** This is a protocol, not test results. No recordings or model weights are committed. Runs on independent research branch only; baseline `main` at `a10dd3954a1a53aaf749f7ef7696bf6446cc42f4`.

## 1. Fixture manifest and privacy

Store consented audio and references in a local encrypted or access-controlled directory **outside Git**. Freeze one manifest JSONL with:
`recording_id, wav_path, audio_sha256, sample_rate=16000, channels=1, duration_ms, category, speakers, overlap_duration_ms, annotation_source, annotators, license, consent_scope, enrollment_paths, enrollment_sha256, source_channel_paths (optional), mixture_method, recording_device, room/noise, split=dev|holdout`.
Never send private recordings to external model APIs, public HF Spaces or CI artifacts. Local inference after model download works with network disabled; record a network-disabled test.

Minimum **holdout**: 2 A-B-A no-overlap (negative control), 4 two-person natural overlaps (at least one interruption), 2 three-speaker, 2 four-speaker, 2 real-noise, 2 unknown/new-speaker, 2 short/contaminated enrollment. Include overlap lengths 0.2/0.5/1/3/5 s. Distinct speakers, rooms and recording sessions in dev vs holdout. Prefer a single actual Android microphone mixture plus separately captured source microphones; synthesized mixtures alone are development fixtures, not natural-overlap evidence.

Annotate **every audible word** with `start_ms,end_ms,speaker_id,text` and each speaker activity interval independently. Two annotators independently review overlap and adjudicate disagreements. Do not derive the reference from C2 output or ASR. For reference uncertainty, mark a documented unscorable region separately; never silently delete it after seeing results. Preserve speaker IDs within each recording; cross-session identity not assumed. Freeze reference hashes before model evaluation.

Example **reference.json** (illustrative schema, not a scored recording):
```json
{
  "schema_version": 1,
  "recording_id": "ru_overlap_holdout_001",
  "kind": "PUBLIC_RECORDED",
  "annotation_source": "manual-two-annotators-v1",
  "license": "record actual consent/license here",
  "audio_sha256": "<64 hex chars of original WAV>",
  "audio_duration_ms": 10000,
  "text_segments": [
    {"start_ms": 1000, "end_ms": 1800, "speaker_id": "A", "text": "первый голос"},
    {"start_ms": 1450, "end_ms": 2100, "speaker_id": "B", "text": "второй голос"}
  ],
  "diarization": [
    {"start_ms": 1000, "end_ms": 1800, "speaker_id": "A"},
    {"start_ms": 1450, "end_ms": 2100, "speaker_id": "B"}
  ]
}
```
Example is **only structural**, with placeholder hash/license and fabricated words. It is not evidence.

**Hypothesis**: use app JSON export `segments`, attach `audio_sha256` and `audio_duration_ms` from the exact original WAV, preserve `attribution_reliable` and null `speaker_id`. For DER, add **separate raw C2 turns** under `diarization`; never infer raw turns from text segments. Existing release export does not include raw C2 turns: instrument a private, research-only evidence path, or DER remains `NOT_SCORED`.

## 2. Candidate lock

| Run | Audio input | Model | Conditions |
|---|---|---|---|
| B0 | original mixture | contest A3+C2, unchanged | frozen main/release, no extra inference |
| V1 | same mixture | VoxLock INT8 with correct 3s enrollment per target -> same A3+C2 fusion | fixed target, frozen model SHA, no auto enrollment |
| Vwrong | same mixture | VoxLock INT8 with wrong person's enrollment | negative control |
| Vshort | same mixture | <3s/no clean enrollment | must fall back; no fake padding |
| Vclean | no-overlap mixture | VoxLock INT8 per target | verify no regression |
| optional | same mixture | MossFormer2 or TF-GridNet | only if license/runtime and benchmark budget allow |

Do not mix `onnx/v2` VoxLock model files with sherpa v2.0.1 metadata from the older model revision without validation. Download from pinned upstream release, record `sha256sum`, ONNX opset/IR, exact sherpa commit, ORT version and architecture. Compare on same holdout, never tune on it.

## 3. Executable commands (known upstream CLI; run status NOT_RUN)

```bash
# Baseline physical ARM64, requires adb-connected phone and installed signed APK
adb devices -l
python tools/phone_run_clip.py "$ANDROID_SERIAL" /secure/ru_overlap_holdout_001.wav \
  --out-dir .local/issue10/baseline --wait-minutes 20

# PC-only independent VoxLock probe. pip install voxlock in an isolated environment
# after auditing pinned package/dependencies and caching models locally.
voxlock download --precision int8
voxlock /secure/ru_overlap_holdout_001.wav \
  --sample /secure/enroll_A_3s.wav --precision int8 --threads 1 \
  -o .local/issue10/vox_A.wav
voxlock /secure/ru_overlap_holdout_001.wav \
  --sample /secure/enroll_B_3s.wav --precision int8 --threads 1 \
  -o .local/issue10/vox_B.wav

# Independent scorer, once hypothesis.json is prepared with exact original audio hash
python tools/test_score_transcript.py
python tools/score_transcript.py --reference /secure/reference.json \
  --hypothesis .local/issue10/hypothesis.json \
  --output .local/issue10/score_collar0.json --collar-ms 0
python tools/score_transcript.py --reference /secure/reference.json \
  --hypothesis .local/issue10/hypothesis.json \
  --output .local/issue10/score_collar250.json --collar-ms 250
```

The VoxLock commands **only produce isolated audio**. They do **not** produce comparable ASR/cpWER results until decoded with the same pinned A3 and attributed to the same C2 timeline. Existing host `tools/asr_20261104/run_asr.py` is a *whole-clip manifest* A3 runner, not an app-equivalent overlap-window/fusion runner; do not label its results as app parity. Use `tools/asr_20261104/run_a3_attribution.py` only after checking its manifest, Java17 and private model path requirements. The research-only A3 runner must accept extracted WAV, map timestamps to the original mixture and emit the same hypothesis schema.

For a direct sherpa v2.0.1 **PC-only** C++ model proof (not app integration), use the documented command:
```bash
./bin/sherpa-onnx-offline-denoiser \
 --speech-denoiser-voxlock-enroll-model=/models/voxlock/enroll.onnx \
 --speech-denoiser-voxlock-chunk-model=/models/voxlock/chunk_int8.onnx \
 --speech-denoiser-voxlock-voice-sample=/secure/enroll_A_3s.wav \
 --input-wav=/secure/ru_overlap_holdout_001.wav \
 --output-wav=.local/issue10/sherpa_A.wav
```
Verify output duration, 16 kHz sample count, finiteness, clipping, no non-target leak, and whether the A3 transcript preserves target words. Do not substitute a desktop RTF for ARM64.

## 4. Metric definitions and reporting

Use existing `tools/score_transcript.py` as-is with **0 ms collar and overlap INCLUDED** for primary DER. Report a 250 ms collar sensitivity and a separate overlap-excluded result only as secondary. DER uses speaker-time denominator and globally optimal label mapping. Reference intervals are half-open. Record missed, false-alarm and confusion time. If raw turns absent, DER is `NOT_SCORED`, not zero.

- **WER**: project Unicode normalization NFKC/lowercase/ё→е; S/D/I and N. Overlap word ordering can affect WER.
- **cpWER**: speaker concatenation and permutation; project scorer returns `NOT_SCORED` for unknown/unreliable hypothesis words. Do not silently relabel them.
- **cpWER-U**: project-specific conservative unknown-aware score, separately named; never claim equality to standard cpWER. Also report unknown word count and percentage.
- **Overlap-only word recall**: matched correct reference words per speaker / reference words within manually annotated overlap; false extra words, deletion rate and leakage/duplicate rate. Explicit temporal matching tolerance and duplicate policy, e.g. ±250 ms midpoint, frozen before run.
- **Speaker attribution**: correctly attributed matched words / all matched words; separate known-speaker coverage, unknown, false positive speaker labels and identity switches. A wrong but confident speaker is worse than unknown.
- **Performance**: RTF = wall-clock inference time / audio duration, record model-load and processing separately; 5 cold/warm repeats; device temperature/battery, threads, ABI, Android build, airplane mode, battery saver state. Peak PSS: repeated `adb shell dumpsys meminfo <package>` for app **and** `:diarization`/`:overlap` workers plus VmHWM/native allocation; sampled PSS is an estimate, not an exact instantaneous maximum. Report model file bytes, APK bytes, failures, logcat tombstones and restarts.
- **Reproducibility**: same fixture hash, C2 turns, A3 weights, reference, scoring code, and language normalization; include confidence intervals from recording-level paired bootstrap; distinguish PC, x86_64 emulator, physical ARM64. Emulator is a smoke/ABI check, not speed evidence.

## 5. Gates and stop conditions

**Host feasibility gate**: correct enrollment exists; two distinct target outputs contain different intended words, no severe leakage/duplication; paired A3 cpWER-U improves on at least a frozen subset; no material degradation on no-overlap. Failed gate -> reject VoxLock integration, record negative results.

**Android gate**: build research flavor without replacing pinned 1.12.20, pass AAR/ORT/JNI/ABI/16KB-page checks, native worker death/timeout/OOM and cancel tests, fully offline; 5 repeats on physical ARM64 with RTF/PSS/thermal and no native crash. Failed gate -> no integration even if PC quality improves.

**Acceptance gate**: preregister numerical quality and device-budget thresholds before running the holdout. Do not declare an improvement from an English benchmark or a single synthetic clip. Without natural Russian manual ground truth and physical A/B, Issue #10 remains open. No automatic PR merge or release change.

## 6. Evidence table to fill after real runs

| Fixture SHA | Source | Device | Candidate SHA | Enrollment SHA | WER S/D/I/N | cpWER | cpWER-U | overlap recall/leak | DER collar0 | RTF | peak PSS | failures |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NOT_RUN | baseline | PC/ARM64 | pinned | n/a | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| NOT_RUN | VoxLock | PC/ARM64 | pinned | pinned | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |

**No test results were generated by preparing this protocol.**
