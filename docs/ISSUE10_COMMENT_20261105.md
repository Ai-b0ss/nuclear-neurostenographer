## Issue #10 — independent research decision (2026-11-05)

**Status: NO-GO for contest integration; keep issue OPEN.** No evidence yet justifies shipping overlap-recovery inference to the 6 November Nuclear IT Hack build. This is **not** a claim that offline separation is impossible. The existing A3+C2 pipeline remains the verified, conservative baseline.

### Current state (not the obsolete PR #6 description)
- `main` `a10dd3954a1a53aaf749f7ef7696bf6446cc42f4`, release `v0.3.3-contest`: **GigaAM v3 e2e RNN-T INT8 (A3) + Nemotron 3 INT8 (C2)**, sherpa-onnx **1.12.20**, ORT **1.17.1**, fully offline. PR #16/#20/#24 addressed the previous Nemotron device gap and speaker-boundary ASR losses. CI `41942088669` passed.
- Measured **existing baseline**: 29-track host WER **16.8%**, cpWER-U **23.8%** (PR #24); physical HONOR 10X Lite synthetic 3-voice WER **3/52**, 4-voice WER **10/61**, cpWER-U **27/61**; 20-min RTF **0.45** measured on 0.3.2. Earlier PSS ~793 MiB is not a verified 0.3.3 peak. C2 DER references for realmix are automatically derived, **not** manually annotated natural overlap. No candidate overlap-recovery measurements exist on these same recordings.
- C2 detects speaker activity, A3 decodes a mixed waveform once, and uncertain words remain `speaker_id=null`. This avoids false attribution but **does not recover simultaneously spoken words**.

### Technology verdict
| Candidate | Decision | Why |
|---|---|---|
| Current A3+C2 + unknown/overlap flags | **INTEGRATE / KEEP** | physically exercised, no invented second transcript |
| **VoxLock INT8** | **OPTIONAL isolated experiment** | real 27M/16kHz target extractor, public Apache-2.0 ONNX ~74 MB, sherpa v2.0.1 support; but requires a **clean 3s enrollment per speaker** and has no Russian A3/ARM64 proof |
| **DiCoP v0.1** | **RESEARCH ONLY** | English 618M/2.47 GB diarization-conditioned target ASR, not separation; no Russian/Android/ONNX evidence, code license absent in repo |
| **audio.cpp** | **RESEARCH ONLY runtime; REJECT migration now** | C++ GGUF families exist, but no equivalent verified Android NDK/JNI + A3/C2 benchmark or measured overlap advantage |
| WeSep, MossFormer2, SepFormer, TF-GridNet, DiCoW | **RESEARCH ONLY** (TF-GridNet contest **REJECT**) | English/read-speech/2-source or heavy models, identity permutation, mobile gaps and/or weight-license uncertainty |

VoxLock primary sources: [paper, 29 Oct 2026](https://arxiv.org/abs/2610.40727), [code](https://github.com/arbazsiddiqui/voxlock), [weights](https://huggingface.co/arbazsiddiqui/voxlock), merged sherpa [#4085](https://github.com/k2-fsa/sherpa-onnx/pull/4085), [#4101](https://github.com/k2-fsa/sherpa-onnx/pull/4101), [v2.0.1](https://github.com/k2-fsa/sherpa-onnx/releases/tag/v2.0.1). Author's English Krisp WER 4.95% vs raw 23.21% **cannot** be transferred to Russian GigaAM/Android. On frozen AMI, wrong-speaker enrollment raised WER from 10.63% to 23.23%: enrollment correctness is a gating risk.

### Acceptance criteria (original Issue #10)
1. Licensed Russian A/B/A, natural overlap and manual word/speaker/time ground truth — **PARTIAL** (natural manually annotated overlap missing).
2. Same-test baseline WER/cpWER/DER/RTF/peak RAM, emulator vs physical separately — **PARTIAL** (historical measurements, not complete same-test natural-overlap/device baseline).
3. VoxLock overlap-only, clean enrollment and both speakers — **NOT_RUN**.
4. Isolated Android API/ABI/JNI/ORT/worker/security/license validation, no auto-upgrade — **PARTIAL** (source audit only; build/device gate NOT_RUN).
5. DiCoP source/checkpoint/language/conversion feasibility — **RESEARCH COMPLETE**; Android implementation **RESEARCH ONLY**.
6. audio.cpp runtime/Android example/license comparison — **RESEARCH COMPLETE**; parity benchmark **NOT_RUN**.
7. Baseline vs candidates table on identical **measured** audio — **PARTIAL** (baseline exists, candidate columns **NOT_RUN**).

### Minimum actions before closing
1. Freeze at least one small **consented, manually annotated natural Russian overlap** holdout with text, speaker IDs, activity intervals and SHA-256. Do not publish private audio.
2. Run paired baseline vs VoxLock correct/wrong enrollment on **the same** holdout, through the **same pinned A3**; report strict cpWER, cpWER-U, overlap-only word recall, insertions/deletions/leakage and DER collar **0 ms** (overlap included), plus 250 ms sensitivity. Unknown words remain unknown.
3. Run isolated Android ARM64 proof on the physical HONOR or equivalent: 5 repeats, full offline, RTF, sampled peak PSS of **all processes**, model/APK bytes, native crashes/tombstones, 16 KB pages, ORT/JNI/ABI compatibility and license verification. **Do not upgrade sherpa-onnx automatically**.
4. Record a paired measured decision. If no quality/device advantage, close **NO-GO** only after completing the original research gates or explicitly revising them.

### Research artifacts (independent branch, no production modifications)
- [Full report + matrix + Evidence Ledger + falsification](https://github.com/Ai-b0ss/nuclear-neurostenographer/blob/research/issue-10-overlap-20261105/docs/OVERLAP_RESEARCH_20261105.md)
- [Reproducible benchmark protocol, commands, schema and stop gates](https://github.com/Ai-b0ss/nuclear-neurostenographer/blob/research/issue-10-overlap-20261105/docs/OVERLAP_BENCHMARK_20261105.md)

**Verification scope:** private GitHub and upstream source/model cards reviewed; current main CI passed. No phone/PC inference executed during this research session (Windows Bridge offline; no connected SentinelX hosts). No test measurements fabricated. **Do not close Issue #10 yet.**
