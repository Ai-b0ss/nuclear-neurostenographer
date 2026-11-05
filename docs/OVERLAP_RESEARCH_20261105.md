# Issue #10 — Overlap recovery research and engineering decision
**Date:** 2026-11-05 (MSK). **Baseline:** `main` at `a10dd3954a1a53aaf749f7ef7696bf6446cc42f4`; release `v0.3.3-contest`. **Status:** research review completed, overlap-specific experiments NOT_RUN, Issue #10 must remain OPEN. **Branch:** `research/issue-10-overlap-20261105`. No production code, dependencies or model files modified.

## Executive decision

**NO-GO for adding neural overlap recovery to the contest APK before 2026-11-06.** Keep GigaAM A3 + Nemotron C2 and its conservative unknown/overlap fallback. **OPTIONAL**: independently benchmark VoxLock INT8 as a post-diarization, target-conditioned overlap-only module. **RESEARCH ONLY**: DiCoP, WeSep, DiCoW, MossFormer2, SepFormer, TF-GridNet and multi-talker ASR. **REJECT now**: automatic sherpa-onnx upgrade, wholesale migration to audio.cpp, and pretending that timestamp fusion recovers unheard speech.

This is an **integration NO-GO**, not proof that offline separation is impossible. The core missing evidence is paired Russian overlap WER/cpWER and device RTF/PSS on the same manually annotated audio. The research acceptance checklist in Issue #10 is **not complete**; do not close without experiments or explicit scope change.

## 1. Repository audit and historical corrections

Private GitHub access succeeded; Issue #10 body, comments (0), events (0), issues #3/#5/#7, PR #6/#9/#16/#20/#24/#25/#26, release and current main were inspected. GitHub Actions `41942088669` passed for the audited main SHA. Issue #3 and #7 are closed, #5 and #10 open.

- Issue #10 described the then-WIP PR #6 CTC + pyannote/ERes2Net baseline. This is **obsolete**. PR #16 validated C2 on ARM64; PR #20 made Nemotron 3 INT8 (C2) + GigaAM v3 e2e RNNT INT8 (A3) the contest path; PR #24 improved continuous speech windows and token-based word attribution. PR #25 added reversible dictionary edits. The product remains offline; AndroidManifest does not request INTERNET.
- `app/build.gradle.kts` still pins `sherpa-onnx-1.12.20.aar`, runtime SHA checks, `onnxruntime-android:1.17.1` in Nemotron build, `arm64-v8a` and `x86_64`. The `:diarization` private process owns one native job per lifetime; `IsolatedDiarization` waits for worker death before another request. Never bypass this to add VoxLock.
- `OfflineAsr.kt`: 16 kHz Float32; speech windows from diarization, QuietCuts max ~20 s, GigaAM A3 greedy decoding; token timestamps -> `TokenWords` -> `TranscriptFusion`. `TranscriptCore.kt` returns `speaker_id=null` when attribution is ambiguous, sets `overlapping_speech`, and never fabricates a second stream. `DiarizationTimeline` derives windows from C2 turns. Stable `Speaker N` labels are **within one recording**, not biometric identity across sessions.
- Confirmed repository baseline: 29-track paired host A3+C2 WER 16.8% (304/1812), cpWER-U 23.8% after PR #24; previous 20.9% / 24.7% comparison is a different version. Physical HONOR 10X Lite: 3-voice synthetic WER 3/52, 4-voice synthetic WER 10/61 and cpWER-U 27/61, 21 unknown words, 20-minute RTF 0.45 for 0.3.2. Earlier peak PSS ~793 MiB is NOT the 0.3.3 peak. C2 DER 2.8–13.3% on realmix and 4.2% with 250 ms collar on a 20-minute track use automatically generated VAD/channel references, **not human-verified overlap ground truth**.
- Physical device evidence exists for A3+C2; no physical-device VoxLock, DiCoP, audio.cpp or overlap-recovery A/B test was found. No new measurements were run in this audit: Windows Bridge offline, SentinelX no connected hosts; no phone execution environment available.

Repository evidence: [ASR research](https://github.com/Ai-b0ss/nuclear-neurostenographer/blob/main/docs/ASR_RESEARCH_20261104.md), [word attribution](https://github.com/Ai-b0ss/nuclear-neurostenographer/blob/main/docs/ASR_WORD_ATTRIBUTION_2026-11-05.md), [physical C2](https://github.com/Ai-b0ss/nuclear-neurostenographer/blob/main/docs/C2_PHYSICAL_HONOR_2026-11-04.md), [benchmarks](https://github.com/Ai-b0ss/nuclear-neurostenographer/blob/main/docs/BENCHMARKS.md), [CI](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41942088669).

## 2. Technology review (primary sources, as of 2026-11-05)

### VoxLock — OPTIONAL experiment, not production-integrated

[Code](https://github.com/arbazsiddiqui/voxlock) (Apache-2.0); [weights](https://huggingface.co/arbazsiddiqui/voxlock) (Apache-2.0, ungated, actual ONNX and safetensors); [paper](https://arxiv.org/abs/2610.40727) (29 Oct 2026). A 27.26M-parameter causal target-speaker BSRNN/REAL-TSE derivative: 16 kHz mono; STFT 512, hop 128; six band-split blocks; sample spectrogram attention plus ECAPA frame-level conditioning; spectral mask estimation, ISTFT/overlap-add; algorithmic latency 24 ms. Enrollment is **exactly 3 seconds** in the ONNX graphs; default selects the loudest 3 s from the first 15 s. In a meeting this default selects a dominant voice, not an arbitrary C2 speaker. To extract N speakers, call N times with **distinct, clean, speaker-specific** enrollment; the model does not output N tracks in one pass.

VoxLock ONNX separates enrollment graph from stateful chunk graph. Published INT8 files ~74 MB total (enroll + chunk); fp32 ~94 MB. Published author-reported results: 265 Krisp recordings, English Parakeet v2, WER 4.95% fp32 vs 23.21% raw, INT8 5.11%; 400 *blind-frozen* AMI windows, WER 10.63% vs 42.95% raw with English Parakeet v3. Not a Russian GigaAM benchmark, not whole meetings, not a blind multicandidate Android trial. On blind AMI a **wrong speaker's enrollment** raises WER to 23.23% (vs 10.63%), and target missed-word rate to 16.97% (vs 8.26%): target identity is a critical failure mode. Other AMI development sets were seen during tuning; 8 of 19 meetings were unavailable in the frozen evaluation. On Intel Xeon 2.2 GHz, ONNX Runtime 1.31.1, author reports single-thread INT8 streaming CPU/audio 0.61 (80 ms chunks), 0.77 (40 ms), 1.10 (20 ms), plus initial state warm-up stall; **no ARM64 RTF/PSS measured**. Published gains must not be extrapolated to Russian spontaneous 2–4 speakers.

Upstream integration is **real**, not hypothetical: [sherpa PR #4085](https://github.com/k2-fsa/sherpa-onnx/pull/4085) merged 25 Oct 2026 (C++); [#4101](https://github.com/k2-fsa/sherpa-onnx/pull/4101) merged 26 Oct (model files); [#4104](https://github.com/k2-fsa/sherpa-onnx/pull/4104) C API; [#4107](https://github.com/k2-fsa/sherpa-onnx/pull/4107) Java/Kotlin JNI; [release v2.0.1](https://github.com/k2-fsa/sherpa-onnx/releases/tag/v2.0.1), 26 Oct. This does NOT mean 1.12.20 AAR supports VoxLock or that v2.0.1 can be dropped into the current app safely. The sherpa PR model metadata pins VoxLock 1.1.1 while current VoxLock README refers to v2 models: pin exact checkpoint/revision and graph pair, verify SHA and opset/IR before tests.

Failure modes: wrong/contaminated or <3s enrollment; multiple similar voices; background leakage, suppression of target consonants; sequential streams duplicate words; C2 missed overlaps; cross-window speaker swaps; silence/noise hallucinations downstream; longer enrollment and context may increase CPU and latency. The separator is English-trained; language transfer and downstream GigaAM A3 accuracy are unknown.

### DiCoP — RESEARCH ONLY

[Code](https://github.com/BUTSpeechFIT/DiCoP) and [checkpoint](https://huggingface.co/BUT-FIT/DiCoP_v0.1) exist. Hugging Face API confirms public 2,473,072,640 bytes of repository storage, `en` language, CC-BY-4.0 weights; 618M parameters, 16 kHz, 24-layer FastConformer, Parakeet-TDT-0.6B-v2 base. **Repository has no root LICENSE** as of audit: do not assume code reuse rights from weight license. DiCoP is **diarization-conditioned target-speaker ASR**, not source separation. STNO masks label silence/target/non-target/overlap; per-layer FDDT transforms condition the encoder; ASR is decoded per speaker. It needs a good RTTM/C2 mask. NeMo + PyTorch 2.9.1 and custom classes are required; standard `transcribe()` is intentionally disabled. ONNX/Android conversion, Russian acoustic/tokenizer adaptation and ARM64 RTF/PSS are unproven. Reported AMI/NOTSOFAR/LibriMix cpWER values use **oracle diarization** and English; 3mix Libri3Mix test clean cpWER 33.12%, showing substantial failure even in controlled English 3-speaker data. Do not train/port 618M before contest.

### audio.cpp — RESEARCH ONLY runtime, REJECT migration now

[Source](https://github.com/0xShug0/audio.cpp) and [LICENSE](https://github.com/0xShug0/audio.cpp/blob/main/LICENSE): Apache-2.0 C++/ggml inference runtime; weights retain original licenses. Supports `gigaam_asr`, `nemotron_3_diar`, `mossformer2`, `tf_gridnet`, GGUF packaging and optional C ABI (`AUDIOCPP_BUILD_C_API`); CMake has optional NEON. The audited public tree has **no verified Android NDK/JNI application or ARM64 device benchmark** for this pipeline. GGUF is not a universal ONNX adapter. Its [TF-GridNet](https://github.com/0xShug0/audio.cpp/blob/main/docs/models/tf_gridnet.md) WSJ0-2mix checkpoint is 8 kHz/two output tracks, identity not stable across long gaps; original checkpoint license **not stated**. Converting A3+C2 and migrating the Android runtime would introduce an unmeasured regression surface for no demonstrated overlap benefit. Review [model licenses](https://github.com/0xShug0/audio.cpp/blob/main/docs/model_licenses.md); optional GPL eSpeak build is off by default but dependencies must still be audited.

### Other candidates and negative evidence

- [WeSep / REAL-TSE](https://github.com/REAL-TSE/wesep-real-tse), [REAL-TSE challenge paper](https://arxiv.org/abs/2607.15198), 16 Jul 2026: open TSE training/evaluation; real Mandarin+English data, speaker consistency and intelligibility often trade off. **RESEARCH ONLY**; VoxLock is the nearer deployable derivative.
- [ClearerVoice-Studio](https://github.com/modelscope/ClearerVoice-Studio), [MossFormer2](https://arxiv.org/abs/2312.11825), [model](https://huggingface.co/alibabasglab/MossFormer2_SS_16K): two-source separation and weights exist, but track permutation, mobile CPU/PSS and Russian ASR are unverified. **RESEARCH ONLY**.
- [SpeechBrain SepFormer](https://github.com/speechbrain/speechbrain), [paper](https://arxiv.org/abs/2010.13154), [LibriMix](https://arxiv.org/abs/2005.11262): source separation on read-speech mixtures; high compute and domain shift, no stable identity by itself. **RESEARCH ONLY**.
- [TF-GridNet](https://arxiv.org/abs/2211.12433), [ESPnet](https://github.com/espnet/espnet): strong offline separation, but 8k WSJ0-2mix checkpoint license unresolved in audio.cpp and no Android proof. **REJECT for contest**.
- [DiCoW](https://arxiv.org/abs/2501.00114), [DiCoW code](https://github.com/BUTSpeechFIT/DiCoW), [SE-DiCoW](https://arxiv.org/abs/2601.19194): target-speaker ASR using diarization; accuracy degrades with imperfect diarization and heavy multi-pass decoding; no measured Russian Android advantage. **RESEARCH ONLY**.
- [Speaker leakage correction paper](https://arxiv.org/abs/2608.22196), 23 Aug 2026: cascaded separation can duplicate the wrong speaker's words; up to 29% relative cpWER improvements in selected leakage-heavy subsets are **not** general absolute gains. Conservative pruning may help after independent validation. **OPTIONAL algorithmic experiment**.
- Low-cost options: C2 overlap detection + mark unknown + manual review, no additional heavy model. **INTEGRATE/KEEP**. Microphone array beamforming only if device actually provides synchronized independent channels and geometry; not assumed for mono Android capture. **RESEARCH ONLY**. Multiple ASR passes on the same mono mixture do **not** recover missing simultaneous words; **REJECT** as a recovery claim.

## 3. Comparison matrix (not cross-dataset score ranking)

| Candidate | Task | Public weights | RU/Android proof | License concerns | Decision |
|---|---|---|---|---|---|
| Existing A3+C2 + unknown fallback | mono ASR + diarization | already bundled | YES, baseline only | pinned AAR/ORT, OpenMDW-1.1 | **INTEGRATE / KEEP** |
| VoxLock INT8 per target | target voice extraction | YES, ~74 MB | NO RU paired/ARM64 | Apache-2.0 weights, upstream version pin | **OPTIONAL** |
| DiCoP v0.1 | diarization-conditioned ASR | YES, ~2.47 GB repo | NO | CC-BY-4.0 weights, code LICENSE absent | **RESEARCH ONLY** |
| audio.cpp | inference runtime | GGUF families | NO app-equivalent Android comparison | code Apache-2.0, model-specific terms | **RESEARCH ONLY**; migration **REJECT** |
| WeSep/REAL-TSE | target extraction framework | YES, model-specific | NO | checkpoint-by-checkpoint | **RESEARCH ONLY** |
| MossFormer2 | blind 2-source separation | YES | NO | verify exact checkpoint | **RESEARCH ONLY** |
| SepFormer / Conv-TasNet | blind 2-source separation | YES, variant-specific | NO | dataset/weights distinct | **RESEARCH ONLY** |
| TF-GridNet 8k | blind 2-source separation | YES | NO | original weights license unclear | **REJECT contest** |
| DiCoW/SE-DiCoW | conditioned ASR | model-dependent | NO | model-specific | **RESEARCH ONLY** |
| C2 overlap flag + human review | conservative workflow | bundled | YES flagging, not restoration | no new dependency | **INTEGRATE / KEEP** |
| Mic-array beamforming | spatial source filtering | algorithmic | hardware capability UNKNOWN | low | **RESEARCH ONLY** |

**Only like-for-like baseline figures are measured.** No VoxLock/DiCoP/audio.cpp result on the same Russian recordings exists; leave their WER/cpWER/DER/RTF/PSS table cells **NOT_RUN**, never substitute upstream English numbers.

## 4. Proposed optional architecture and interfaces

Current default: `Audio PCM16k mono -> C2 diarization in isolated worker -> continuous speech windows -> A3 -> token word timing -> conservative attribution -> transcript`.

Research flavor only: `C2 turns -> overlap spans (intersection of distinct speaker intervals) -> verified enrollment per speaker -> VoxLock per target over overlap + context -> A3 each target -> identity/leakage verifier -> candidate transcript -> accept/reject against baseline`.

Interfaces (all timestamps are original recording milliseconds, PCM Float32 mono at 16,000 Hz):
- `OverlapSpan(startMs,endMs,activeSpeakerIds,detectorVersion)` (bounded, sorted, no fabricated missing speakers).
- `Enrollment(speakerId,pcm16k[48000],sourceStartMs,sourceEndMs,qualityFlags,sourceHash)`; only clean single-speaker segments >=3 s, guard boundaries, no overlap, clipping or noise; otherwise `NO_ENROLLMENT`.
- `ExtractionResult(speakerId,span,pcm16k,modelSha256,status,processingMs)` with `status = OK|NO_ENROLLMENT|LOW_IDENTITY|LEAKAGE|OOM|TIMEOUT|NATIVE_FAILURE`.
- `CandidateWord(speakerId,startMs,endMs,text,sourceModel,verification)`; keep parallel speakers with simultaneous timestamps, never force non-overlapping output ordering.

Do **not** use the loudest-three-seconds auto-enrollment. For speaker A/B require independent, C2-consistent clean speech. For 3–4 speakers or unknown IDs, decline extraction unless enrollment and identity checks pass. Run VoxLock on bounded windows with explicit pre/post context and deterministic crossfade; whole-file inference is safer for initial host proof. Avoid repeating A3 on non-overlap audio. Validate speaker embedding similarity/identity with a **separately calibrated** threshold; C2 activity alone is not a reliable identity verifier. Reject duplicate/leaked words conservatively, never hallucinate words.

Android isolation: separate private `:overlap` worker, one job per lifetime, never concurrently resident with `:diarization` if peak PSS would exceed budget; pass bounded PCM via private files, Binder only small metadata; use SHA-256 and offline asset provisioning. Timeouts/abort must terminate only the owned worker, wait for binder death before retry, clean temp files, and return unchanged baseline transcript. Check 16 KB page compatibility, JNI/ORT symbol collisions, thread counts, model IR/opset, dynamic shapes, native crashes, no INTERNET, all model/third-party licenses, reproducible NDK/AAR build. Do **not** replace the pinned 1.12.20 AAR with v2.0.1 without a separate regression matrix. On the current HONOR the physical RTF/PSS and crash rate of this architecture are **unknown**.

## 5. Evidence ledger

| Claim | Primary evidence | Verification | Confidence | Limitation |
|---|---|---|---|---|
| Current A3+C2, no source separation | main `OfflineAsr.kt`, `TranscriptCore.kt`, PR #20/#24 | source inspected | HIGH | no new run |
| Pinned sherpa 1.12.20 + ORT 1.17.1 | `app/build.gradle.kts` | source inspected | HIGH | flavor-specific dependency |
| 29-track WER 16.8%, cpWER-U 23.8% | `docs/ASR_WORD_ATTRIBUTION_2026-11-05.md` | evidence inspected | HIGH as recorded | synthetic + host; no manual natural overlap |
| HONOR 20-min RTF 0.45 | same doc | recorded result inspected | MEDIUM | version 0.3.2; not rerun |
| C2 DER on realmix | `docs/C2_SAME_TRACKS.md` | protocol inspected | MEDIUM | automatic VAD reference, not human |
| VoxLock code and ONNX weights public | GitHub + HF model API | direct source/artifact listing | HIGH | not downloaded or executed |
| VoxLock English WER gain | arXiv 2610.40727, 29 Oct | author method/results reviewed | MEDIUM | author measurement, different ASR, no Russian |
| VoxLock wrong enrollment degrades WER | same paper Table 3 | negative result inspected | MEDIUM | specific AMI windows |
| sherpa v2.0.1 includes VoxLock APIs | PR #4085/#4101/#4104/#4107, release 26 Oct | merged PRs inspected | HIGH | not the app's pinned AAR |
| DiCoP checkpoint English 618M | HF model API/card | weights listing, language, size checked | HIGH | no ONNX/ARM64 evidence |
| DiCoP code redistribution permitted | GitHub root tree | no LICENSE found | LOW / UNRESOLVED | separate permission needed |
| audio.cpp supports GigaAM/Nemotron/TF-GridNet | code/docs/CMake | source inspected | HIGH | Android app parity unverified |
| Neural separation improves RU cpWER on HONOR | none | NOT_RUN | NONE | decisive missing evidence |

## 6. Reproducible test plan

See [companion protocol](OVERLAP_BENCHMARK_20261105.md). Freeze SHA-256 of every audio/reference/model/runtime and Git commit. Minimum corpus: A/B/A clean, 2-person natural overlap, interruptions, 3–4 people, 0.2/0.5/1/3/5 s overlap, domestic noise, unknown voice, 1–2 s/3 s/5 s clean enrollment. Prefer separately recorded source channels **and** the actual single-microphone mixture; reference transcripts, word boundaries and speaker IDs must be manually checked by two annotators. Private user audio stays outside Git.

Run same audio with (a) baseline 0.3.3, (b) baseline + VoxLock per target, (c) negative controls wrong enrollment and no overlap, first on PC, then emulator smoke, then physical ARM64. Compare WER, strict cpWER and cpWER-U, overlap-only word recall/precision/deletions/insertions, speaker attribution accuracy, overlap-aware DER (primary collar 0 ms, overlap scored, secondary 250 ms sensitivity), RTF, model-load time, peak PSS/RSS, size, native crashes, repeat variance. Report confidence intervals by recording; no cherry-picking.

Minimum integration gate: on **manually annotated natural Russian overlap**, paired cpWER-U and overlap word recall improve with no material degradation on non-overlap, no identity swaps or serious leakage; physically measured RTF/PSS fit the device budget with repeated runs, 0 native crashes, full offline operation and license/API/ABI checks. Pre-register numerical thresholds before viewing candidate results; do not retroactively choose them.

## 7. Attempt to falsify this recommendation

1. **VoxLock could be inexpensive enough on ARM64:** 74 MB INT8 is not automatically prohibitive, and its author reports excellent x86 streaming. A two-target host proof may reveal a real gain; the present NO-GO is a deadline/evidence judgment, not an impossibility proof.
2. **C2 can mis-detect overlap:** overlap-only gating might miss the very words we hope to recover. Compare oracle overlap intervals with predicted C2 intervals and measure detection recall separately; if low, optional extraction has little ceiling.
3. **Clean 3 s per speaker may not exist:** natural interruptions and new speakers make automatic enrollment unreliable. Explicitly test short/contaminated and wrong-speaker references.
4. **Separation can hurt GigaAM:** SI-SDR improvements need not improve Russian WER. Measure raw and separated A3 on identical words; use the unmodified baseline on non-overlap.
5. **Synthetic corpus may overstate gains:** test held-out natural room recordings and external voices; confidence intervals across recordings.
6. **A different runtime might be better:** audio.cpp has C ABI and NEON, but absent verified Android parity/RTF and weights licensing, migrating now is a hypothesis rather than a result.
7. **Conservative fallback is incomplete:** unknown attribution avoids false certainty but loses information. Preserve this limitation in the UI and issue status, not market it as solved overlap.

## 8. Acceptance checklist / closure verdict

Original Issue #10 checkboxes:
1. Freeze licensed Russian A/B/A + natural overlap reference text/ID/intervals: **PARTIAL** (synthetic and automatic references exist; manual natural overlap missing).
2. Honest baseline WER/cpWER/DER/RTF/peak RAM emulator/physical: **PARTIAL** (existing host and physical baseline, but no same-test manually annotated overlap or 0.3.3 PSS repeat).
3. VoxLock offline post-diarization overlap-only, enrollment and two targets: **NOT_RUN**.
4. API/ABI/JNI/security/licensing Android validation without auto-upgrade: **PARTIAL** (source review; no isolated build or device run).
5. DiCoP code/checkpoint/language/conversion feasibility: **RESEARCH COMPLETE**, engineering runtime NOT_RUN; RESEARCH ONLY.
6. audio.cpp alternative runtime/Android parity/license: **RESEARCH COMPLETE**, comparative Android run NOT_RUN; migration NO-GO.
7. Short same-test measured baseline vs candidate table and decision: **PARTIAL** (decision matrix exists; candidate measurements NOT_RUN).

**Issue #10 must remain OPEN.** The minimum path to close without scope change: (i) one small, manually verified natural Russian overlap corpus; (ii) baseline and VoxLock A/B on it with exact references and failure cases; (iii) physical ARM64 RTF/PSS/crash + pinned-runtime compatibility and license gate; (iv) commit comparison and explicit decision. If owners explicitly narrow the issue to *research-only feasibility*, record changed acceptance criteria first and close with documented NO-GO; never silently check experimental items.

## 9. Sources and provenance

- Repo: [Issue #10](https://github.com/Ai-b0ss/nuclear-neurostenographer/issues/10), [Issue #5](https://github.com/Ai-b0ss/nuclear-neurostenographer/issues/5), [PR #6](https://github.com/Ai-b0ss/nuclear-neurostenographer/pull/6), [PR #9](https://github.com/Ai-b0ss/nuclear-neurostenographer/pull/9), [PR #16](https://github.com/Ai-b0ss/nuclear-neurostenographer/pull/16), [PR #20](https://github.com/Ai-b0ss/nuclear-neurostenographer/pull/20), [PR #24](https://github.com/Ai-b0ss/nuclear-neurostenographer/pull/24), [release](https://github.com/Ai-b0ss/nuclear-neurostenographer/releases/tag/v0.3.3-contest).
- VoxLock [paper 2026-10-29](https://arxiv.org/abs/2610.40727), [repo](https://github.com/arbazsiddiqui/voxlock), [weights](https://huggingface.co/arbazsiddiqui/voxlock), sherpa [v2.0.1 2026-10-26](https://github.com/k2-fsa/sherpa-onnx/releases/tag/v2.0.1).
- DiCoP [repo](https://github.com/BUTSpeechFIT/DiCoP), [weights](https://huggingface.co/BUT-FIT/DiCoP_v0.1), DiCoW [paper 2024-12-30](https://arxiv.org/abs/2501.00114).
- audio.cpp [repo](https://github.com/0xShug0/audio.cpp), [model licenses](https://github.com/0xShug0/audio.cpp/blob/main/docs/model_licenses.md), [GGUF support](https://github.com/0xShug0/audio.cpp/blob/main/docs/gguf.md).
- REAL-TSE [challenge 2026-07-16](https://arxiv.org/abs/2607.15198); [WeSep 2026-07-29](https://arxiv.org/abs/2607.27436); [speaker leakage 2026-08-23](https://arxiv.org/abs/2608.22196); [LibriMix 2020-05-22](https://arxiv.org/abs/2005.11262).
