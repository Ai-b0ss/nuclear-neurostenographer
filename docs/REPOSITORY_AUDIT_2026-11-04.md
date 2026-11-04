# Repository audit and intended main merge — 2026-11-04

Owner repository: `Ai-b0ss/nuclear-neurostenographer`, PRIVATE. No change to `main` in this audit. Keep signed `v0.2.0-contest-rc1` prerelease as the working recovery baseline, not final general release.

## Architecture actually in source

- `app/`: Kotlin/Compose Android UI, `TranscriptionViewModel`, recording/import via Android media APIs, local SHA-256 model installation, export TXT/JSON/SRT. No required INTERNET permission.
- `app/src/main/.../OfflineAsr.kt`: GigaAM v3 CTC INT8 via pinned sherpa-onnx native runtime. It uses speech windows up to 20 s and QuietCuts, not word alignment. It cannot dynamically switch to other GigaAM architectures.
- `app/src/nemotron/`: Nemotron 3 INT8 C2 diarization; enabled with `-PnemotronProduct=true`, with C0 pyannote segmentation + ERes2Net fallback.
- `core/`: transcript models, window/time handling, speaker attribution, export and pure Kotlin tests.
- `.github/workflows/`: base Android/debug CI plus separate opt-in emulator, runtime, C2 and research checks. **Normal Android CI passes without certifying the C2 product release or physical ARM64.**
- `tools/`: deterministic model provisioning, fixtures, export/quality scoring, device and research experiments. External runtime AAR, signing key and large models stay outside Git.

## Evidence and constraints

- HONOR Android 10 ARM64: signed RC1 works offline; 20-min inference completes without crash (wall RTF ≈0.57 vs self-imposed 0.5 gate, 650–656 MiB PSS, up to 49 °C battery), short 2- and 3-speaker flows and TXT/SRT/JSON export tested.
- Natural 3/4-speaker meeting with manually annotated DER/cpWER remains NOT_RUN. Unknown speakers, short turns, overlap errors remain. Short development clips and pseudo-labels cannot establish general accuracy.
- Transcript state is not persisted across restart (FAIL); exported files remain. Signed C2→C0 fallback and repeatability NOT_RUN.
- GigaAM-v3 e2e/RNNT are untested. Separate desktop Whisper comparison is not a like-for-like same-window model benchmark.
- Runtime notices/provenance exist; private GitHub does not negate conditions for later distribution. Do not remove notices. No private source audio or signing key intentionally committed.

## PR review and consolidation

The graph is `main` → #6 legacy WIP → #9 long recordings → #16 integrated C2. Integration contains #6, #9, #11, #15 and Opus's C0–C1 predecessor. #8 and #12 are already merged into intermediate branches.

Two branches with unique content were inspected and cherry-picked into `integration/c2-honor-20261104`, retaining source SHA via `cherry-pick -x`:

- #13: `09be079` — C0/C1/C2 version-2 reports, public data evidence, manual review tools; historical research, not new HONOR quality evidence.
- #14: `2d5cbcb` and `2fe45ca` — 3 Nov decision history, A+C MOSS/VibeVoice comparison and distillation gates. No raw private chats or model weights imported.

Cherry-picking reproduces content but does NOT make source SHA ancestors. Before closing those PRs as superseded, verify useful content is in #16 and retain links to original history.

## Main decision — deliberately deferred

**Recommend ONE main-bound PR, not seven independent merges:** retarget #16 from `feature/long-recordings` to `main`, run CI on the final HEAD and review the explicit acceptance exceptions. Then merge #16 with a normal merge commit (preserve history, avoid squash). `main` is an ancestor of the integration branch; no divergent source history needs to be overwritten.

Why merge: `main` should contain the reproducible Android product, tests, evidence and docs rather than an old skeleton; retaining all commits supports rollback and traceability. **No main merge was performed during this audit.** Known partial/NOT_RUN gates must remain visible if a prerelease-grade codebase is accepted into main.

After #16 becomes the main-bound integration PR and is ready to land, annotate and close #6, #9, #11, #13, #14, #15 as superseded, not separately merged. Do not delete working branches or rewrite history.

## Independent checks

- 45 Python regression tests PASS using `K:\nn-bench\venv` and `PYTHONPATH` (diarization-score 15, comparison-trials 7, transcript-score 12, provision ASR 5, Android UI 6).
- 38 Markdown documents examined, 177 relative links checked, 0 broken. Basic credential-pattern scan of newly imported files found no matches (not a complete secrets audit).
- No new Android runs, no new model downloads. CI for final HEAD must be confirmed after push.
