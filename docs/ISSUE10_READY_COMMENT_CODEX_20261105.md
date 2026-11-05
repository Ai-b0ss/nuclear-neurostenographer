## Issue #10 — executable A/B update,2026-11-05

**RESEARCH ONLY / NO-GO for contest integration; STILL OPEN.** The earlier
NOT_RUN gap now has actual host and physical ARM64 evidence. Contest 0.3.3/main
remain untouched; no audio/weights/participant text published.

- Frozen licensed SYNTHETIC DEV A/B/A and overlap, same pinned app-code A3+C2,
  both VoxLock targets, correct/opposite/short/no-enrollment and clean controls.
- Host overlap: WER 16/53→19/53; conservative cpWER-U 18/53 unchanged; strict cpWER,
  DER and overlap-word recall unavailable under unknown/annotation limitations.
  Assumed-identity diagnostic cpWER-U 18/53→4/53 shows potential, not verified
  identity. Non-target speech retention and splice/order confounds are preserved.
- Physical HONOR ARM64/Android 10/airplane mode: 5 paired repeats, 30/30 stage exits 0.
  Median standalone wall RTF 1.56 baseline vs
  19.62 full two-target whole-clip probe.
  Sampled standalone PSS maximum 867.9 MiB;
  this is not app+worker peak or optimized overlap-window cost. Same A3 decodes
  both physical stems; separate sidecar quality runs exclude duplicate decode cost.
- Exact pinned ORT 1.17.1/JNI bytes execute VoxLock v2 directly, without sherpa
  upgrade. Invalid enrollment, owned-process cancellation and recovery pass.
  Existing ORT Java 4 KB ELF alignment still fails 16 KB; APK/Binder/background/OOM
  gates are unverified. No production integration attempted after failed gates.
- 60 Python checks pass, 1 optional Windows symlink skip; 16 core groups,
  three export regression suites, fixture/source/model hash reproduction pass.

Original criteria: 1 PARTIAL(manual natural holdout missing); 2 PARTIAL(standalone
metrics, no independent DER/word times/full APK acceptance); 3 EXECUTED RESEARCH
ONLY(identity verifier missing); 4 PARTIAL/ 16 KB FAIL; 5 DiCoP RESEARCH COMPLETE;
6 audio.cpp RESEARCH COMPLETE/no migration; 7 same-fixture measured table DONE
for synthetic DEV, natural/app gates STILL OPEN.

[Execution and criterion ledger](https://github.com/Ai-b0ss/nuclear-neurostenographer/blob/research/issue10-codex-20261105/docs/ISSUE10_EXECUTION_20261105.md) ·
[Reproduction commands](https://github.com/Ai-b0ss/nuclear-neurostenographer/blob/research/issue10-codex-20261105/tools/overlap_research/README.md) ·
[Machine-readable evidence](https://github.com/Ai-b0ss/nuclear-neurostenographer/blob/research/issue10-codex-20261105/docs/evidence/issue10-codex-20261105/evidence-manifest.json).

Keep baseline fallback. Next independent requirements are consented natural Russian
manual word/speaker/activity annotation, untouched holdout and calibrated identity,
then splice validation and isolated app-worker/ 16 KB acceptance. No issue closure
without completing these gates or an explicit owner-approved scope change.
