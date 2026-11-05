# Codex task: Nuclear Neurostenographer, GitHub Issue #10 — experimental overlap recovery

DATE: 2026-11-05. ROLE: lead Speech ML / Android ARM64 engineer, reproducibility auditor, autonomous executor.
REPOSITORY: Ai-b0ss/nuclear-neurostenographer (private).
LOCAL WORKTREE: C:\Users\user\Documents\nn-issue10-codex-20261105
BRANCH: research/issue10-codex-20261105, based on main a10dd3954a1a53aaf749f7ef7696bf6446cc42f4.
ISSUE: https://github.com/Ai-b0ss/nuclear-neurostenographer/issues/10
SOURCE RESEARCH BRANCH (remote): research/issue-10-overlap-20261105.
RUNNER: Codex CLI 0.166.0 / gpt-6.1-sol / reasoning high / ChatGPT login (not paid API-key usage).

## Core instruction

DO THE WORK. The previous Chat and Deep Research reports were research, not a functioning benchmark. Your task is to move Issue #10 toward evidence-based closure by actually implementing, testing, fixing and retesting a reproducible A/B comparison of the existing GigaAM A3 + Nemotron C2 pipeline against isolated VoxLock target-speaker overlap repair, including Android when locally available. Keep going across all practical stages of the task; do not stop after a plan, a status report, or merely executing a trivial smoke test. Act autonomously within available workspace and existing ChatGPT subscription. There is no requested artificial wall-clock or number-of-steps limit; stop on verified completion or a genuine external blocker. Do not bypass account usage limits, approval gates or safeguards.

First read all of the following completely:
- README.md, README.ru.md, AGENTS.md if present, build and test docs.
- docs/OVERLAP_RESEARCH_20261105.md
- docs/OVERLAP_BENCHMARK_20261105.md
- docs/ISSUE10_COMMENT_20261105.md
- docs/ASR_RESEARCH_20261104.md
- docs/ASR_WORD_ATTRIBUTION_2026-11-05.md
- implementation of A3, C2, transcript fusion and current scoring scripts.
- inspect remote Issue #10, related Issues #3/#5/#7 and relevant PRs if reachable with authenticated tools; otherwise trust the copied research for context but independently check local code. GitHub CLI credentials are currently invalid: do not get stuck in interactive login, leak tokens, or mutate user-wide authentication; work locally and report push blocker if it persists.

The current CONTEST BASELINE is v0.3.3-contest: GigaAM v3 e2e RNN-T INT8 (A3) + Nemotron 3 INT8 (C2), pinned sherpa-onnx 1.12.20 and ORT 1.17.1, fully offline. Physical HONOR 10X Lite test exists. Historical PR #6 (CTC+pyannote) is obsolete; PR #6/#9 closed without merge. In latest host 29-track benchmark WER 16.8%, cpWER-U 23.8%. Physical synthetic 3-/4-speaker and 20-minute tests exist; no genuine Russian natural overlap manual ground truth or paired VoxLock test yet. Do not describe these historical measurements as newly run.

## Non-negotiable goals, in priority order

PHASE 0 — preflight and protect work
1. Record the actual git SHA, branch, diff, other running agents/processes, available CPU/GPU/disk, tools (Python, Java, SDK, NDK, adb, ffmpeg), connected Android device(s), and existing model files/datasets. Check whether anything runs in parallel and avoid conflicting shared outputs/caches.
2. Keep all work in THIS independent git worktree and task-owned temporary/cache directories. Never reset/clean the user's main worktree or other agents' files. No modifications to main/release, no auto-merge, no issue closure or publication of private audio.
3. Existing research docs were transplanted into this worktree from the verified private GitHub research branch, and are uncommitted in this worktree. Preserve them and add implementation/evidence separately.

PHASE 1 — exact baseline and test readiness
1. Understand the actual A3+C2 implementation, transcript attribution, timestamps, unknown speaker handling, worker isolation, pinned native binaries, and same-corpus evaluators.
2. Locate a lawful, shareable or private consented Russian A/B/A and 2-person overlap fixture with known words/identities/timestamps. Prefer truly naturally recorded dialogue with independent manual reference. Do not invent a human annotation; if absent, still create a reproducible deterministic synthetic DEV fixture from licensed/provided sources with isolated stems, freeze SHA and label SYNTHETIC, not HOLDOUT, so experiments can run.
3. Separate DEV and untouched holdout. Do not accidentally train/tune on holdout. Keep participant recordings and personal data out of Git and external services.
4. Verify scoring tools against elementary gold cases (simultaneous words, substitutions, deletions, duplicate/leaked words, speaker swaps, unknown speakers, overlap under 0/250 ms collar). Distinguish strict cpWER, project-specific cpWER-U, WER and overlap-aware DER. Raw diarization turns must be actually available for DER; otherwise NOT_SCORED.

PHASE 2 — real VoxLock experiment on host
1. Audit VoxLock https://github.com/arbazsiddiqui/voxlock and https://github.com/k2-fsa/sherpa-onnx/releases/tag/v2.0.1 before running third-party code or pulling model weights: pinned provenance, license, hashes, dependency and command correctness. Prefer a controlled Python/ONNX or separate sherpa v2.0.1 research runtime; do NOT upgrade the app's pinned sherpa.
2. Run correct-enrollment target A, correct-enrollment target B, wrong-enrollment negative control, no reliable enrollment fallback, and clean-speech negative control. Capture isolated target stems and inspect duration, clipping, leaked words, silence and errors. The output for A and B must not simply duplicate each other.
3. Critical missing step from prior reports: implement and run the SAME pinned GigaAM A3 decoding on both extracted stems, map words onto original mixture time, attach speaker IDs from original C2 and compare to the untouched baseline on IDENTICAL fixtures. Never compare a desktop-only whole-clip A3 runner to the app pipeline as if they were equivalent; document exact parity limitations, and build an app-equivalent path if feasible.
4. Produce reproducible scripts, minimal tests, fixtures manifests (without forbidden audio), provenance, machine-readable raw outputs and a summary with WER S/D/I/N, strict cpWER if scorable, cpWER-U, overlap word recall, added/leaked words and uncertain attribution. Run counterexamples. If results regress, keep them.
5. If host quality cannot possibly improve or another hard viability gate fails, explain evidence and stop only the impractical integration steps, while finishing audit/docs.

PHASE 3 — isolated Android ARM64 feasibility
1. If `adb devices -l` shows a usable physical phone, use it for controlled task-owned tests in airplane mode, without reading unrelated private phone files. Try an isolated research app flavor or limited on-device inference probe that does not replace existing binaries or signed contest APK.
2. Verify JNI/API/ABI/ORT, lifecycle, worker/process isolation, cancellation, 16 KB page compatibility, repeated init/free, background operations, memory/OOM and native-crash behavior.
3. Run repeated same-fixture baseline and candidate under comparable conditions: process and wall-clock RTF, total cross-process peak sampled PSS (distinguish sampled estimate from true peak), thermal, model bytes, APK delta, battery, failures/tombstones. At least 5 repeats if feasible, more for uncertain results.
4. If no phone/JDK/SDK/model/corpus is available, do not claim device proof. Independently validate all possible host checks and leave exact commands, blockers, checksums and expected acceptance gates. Never fabricate measurements.

PHASE 4 — independent audit, decision, handoff
1. Where supported, spawn up to THREE meaningful parallel subagents with separate read-only focus: (a) research/candidate provenance and licenses, (b) scoring/benchmark correctness and confounds, (c) Android native compatibility/risk. Keep repository edits and end-to-end orchestration in the main agent only, so parallel agents cannot overwrite each other's files.
2. Review independent findings against implementation and test results. Investigate contradictions; do not score assistant text as evidence.
3. Do not use confidence thresholds not provided by GigaAM. No magically perfect speaker assignment. Preserve unknown/overlap fallback; distinguish overlap detection from actual word recovery.
4. Keep code, tests, benchmark protocol, Evidence Ledger, evidence manifests, regression results and a concise decision log in the worktree; commit meaningful checkpoints, but never commit private audio, model weights, secrets, huge binaries, or synthetic results mislabelled as real.
5. Prepare an updated ready-to-post Issue #10 comment: explicit criterion-by-criterion status; links to existing research and new reproducible evidence; decision INTEGRATE / OPTIONAL / RESEARCH ONLY / REJECT; clear DONE / NO-GO versus STILL OPEN recommendation. Do not close issue unless all original acceptance requirements are actually verified. Do not pretend a failed online GitHub push is success.
6. End with a practical summary: exact branch/commits, tests run with actual results, files changed, reproduction commands, remaining blockers and independent verification needed.

## Safety, engineering and execution policy
- Keep stable v0.3.3 contest release untouched. Never overwrite base main, other agent worktrees, local private recordings, security config or existing model files.
- Work autonomously with allowed read/write/test/network inside the isolated task area, using preinstalled free tools and ChatGPT-authenticated Codex. No paid API keys, purchases or new subscription charges; no unsigned drivers and no modifications to system security controls.
- Do not use dangerous sandbox-bypass flags, do not disable safety, do not make unbounded destructive cleanup. Ask only if an operation genuinely requires owner authorization; otherwise make a best-effort safe decision.
- Never send user/participant recordings or any private repository material to third-party web applications. Pin and inspect dependencies before installing them; prefer sandboxed venv and reversible installs.
- You may push a new research branch ONLY if the authenticated git route works and it contains no secrets/private audio; never force-push, merge to main, publish issue comments or close the issue automatically.
- The amount of work may be long. Iterate implementation→tests→fixes until done or blocked; do not impose a time or action quota beyond account/tool limits. If a blocker emerges, continue other independent work rather than ending prematurely.

Begin now. Inspect actual files and environment, build a short internal plan, execute. No need to ask confirmation for ordinary bounded research/code/test changes in this isolated worktree.