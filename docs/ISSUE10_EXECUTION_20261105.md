# Issue #10 — executed engineering and decision,2026-11-05

**RESEARCH ONLY; NO-GO for contest integration; Issue #10 STILL OPEN.** Actual host
and physical ARM64 experiments now exist. They do not establish a shippable
overlap-recovery feature. The signed 0.3.3 contest application, main and release
were not changed. No audio/weights/private participant text are committed.

Base: `a10dd3954a1a53aaf749f7ef7696bf6446cc42f4`. Branch:
`research/issue10-codex-20261105`. Engineering checkpoints: `1d9fdda`, `9d3b277`;
the final evidence commit follows them. The copied initial audit/protocol/comment
are preserved unchanged; their NOT_RUN descriptions are historical.

## New measured host evidence

Actual production Kotlin A3/C2, original C2 turns and same GigaAM weights; host
JNI 1.12.20/ORT 1.17.1, separate VoxLock v2 INT8 Python ORT 1.31.1 CPU. Source/model
pins, references and input hashes precede inference. Both fixtures are 20.1555 s,
**SYNTHETIC DEV from three licensed ACTED source clips**. No holdout audio read.
Scripted utterances are not manually verified words or acoustic boundaries.

| Fixture | Baseline WER | Exploratory splice WER | cpWER-U base / splice | unknown words base / splice |
|---|---:|---:|---:|---:|
| aba-clean | 0/41 | 0/41 | 2/41 / 2/41 | 2 / 2 |
| two-person-overlap | 16/53 | 19/53 | 18/53 / 18/53 | 15 / 21 |

Overlap baseline S/D/I/N=1/9/6/53; splice=2/7/10/53. Strict cpWER is NOT_SCORED
when unknown words remain. DER at 0/250 ms and overlap-only word recall remain
NOT_SCORED because independent reference activity/word times are absent, even
though actual raw C2 speech turns are saved. No fake reference or zero DER.

Strict automatic enrollment fails for the second voice: C2's longest continuous
clean turn is shorter than 3100 ms. Both fixtures retain the original baseline.
The separate provided-DEV experiment uses exactly 48,000 clean-source samples per
target, including natural pauses, with C2 cluster IDs. Crop hashes, zero other-
source energy, finiteness, length and clipping were independently checked.

Both outputs differ (overlap correlation 0.631722) and
preserve the target's scripted words. **Positive counterevidence:** assuming
enrollment identity reduces diagnostic cpWER-U 18/53→4/53. This is not a trusted
application result: there is no independently calibrated identity verifier.
Conservative recovered words remain null, so cpWER-U structurally cannot improve
them. Its definition drops unknown words and can hide unknown insertions; it is
not a guaranteed pessimistic upper bound.

Target-only S/D/I/N on overlap: D=0/0/11/29, M=0/0/20/24. Insertions are leakage
proxies. Raw source-exclusive intervals independently show retention of the
other voice: D-target keeps 11/12 M words in M-only speech; clean M-target keeps
29 D words in D-only speech. Exact overlap leakage/recall is not measurable here.
Sequence WER is also affected by interleaved simultaneous words and C2 splice
boundary artifacts. Therefore these data do not prove that VoxLock cannot help.

Correct/wrong enrollment controls reuse the two actually executed target runs
with requested identities swapped; this is not an unseen-third-speaker test.
No-enrollment and final accepted outputs were independently compared byte for
byte to baseline: identical. Clean overlap-only policy preserves 0/41 WER; both
target outputs leak clean non-target speech. Actual silence extraction is zero;
five host init/infer/free cycles and short-enrollment rejection pass.

## New physical ARM64 evidence

HONOR DNN-LX9, Android 10, 4 KB pages, airplane mode, Wi-Fi off; charging. Task-only
`app_process` DEX, no APK install/replacement, no personal-file reads. Exact stable
no-TTS AAR and ORT Java 1.17.1 libraries were transferred with hashes and their
loaded paths independently observed in the owned PID's maps. VoxLock v2 IR 8 /
opset 17 graphs run directly on pinned ORT 1.17.1: no sherpa upgrade was required.

Five paired repeats, 30/30 stage processes exit 0. Each repeat: C2→baseline A3→
target0 extraction/A3→target1 extraction/A3, sequential fresh processes. The
candidate cost below includes baseline plus two whole-clip extractions and their
A3 decoding; it is not optimized overlap-window cost or signed-app performance.

| Metric | Baseline C2+A3 | Full research probe |
|---|---:|---:|
| Wall RTF, median(min–max),n=5 | 1.56 (1.21–1.64) | 19.62 (13.93–29.26) |
| Sampled standalone stage PSS MiB, median(min–max) | 839.21 (682.93–867.91) | 849.69 (819.11–867.91) |
| Native-failure exits during paired repeats |0/10|0/30|

One-second requested PSS sampling plus adb overhead gives an estimate, not true
peak or concurrent application+Binder-worker PSS. Outer wall time includes
startup/load/monitoring tail. Detailed model-load/inference/CPU counters are
retained per stage: baseline CPU includes loading; separator CPU covers inference
after loading, so full end-to-end process CPU comparison is unavailable.
Initial battery 33°C; per-stage sensor 34.0–39.0°C; SoC thermal and energy/power not measured.
OS caches warm between fresh-process runs; no cold-device claim.
RTF uses the app's truncated 20,155 ms duration (actual WAV 20.1555 s). Both measured
DEX JAR entries start at ZIP offset 41, causing Android's fallback to extraction;
this startup/cache cost is included. The measured JARs are preserved unchanged.

All five baseline outputs score 16/53 WER, 18/53 cpWER-U. Separately collected
word-sidecar quality jobs, excluded from performance, give baseline
16/53, exploratory candidate 19/53 WER;
accepted fallback remains unchanged. Every sidecar's normalized word sequence
is checked against actual app-code output. Actual ARM64 vs Python extracted PCM
correlations exceed 0.99999; numerical agreement is not speaker-quality proof.

Negative physical probes additionally reject 47,999-sample enrollment, terminate
only a verified owned native-loaded PID, confirm its death, and run A3 recovery
with identical baseline text. This tests standalone process containment only.
The first invalid-input test exposed an uncaught Java exception / exit 137 in the
research probe (not a native crash). Its PID-filtered log is retained. The guard
was repaired in a separate DEX: actual ARM64 now returns INVALID_INPUT / exit 2,
and a valid silence inference still returns OK / exit 0. Original measured DEX
and its 5-repeat evidence were preserved byte for byte.
Binder/service/UI/background cancellation, same-process repeated session lifetime,
app OOM and APK packaging remain NOT_RUN. Global logcat/tombstones were not read;
successful exits/task logs show no observed native crash, not a system-wide audit.
After collection, the exact owned remote directory was resolved/identified by its
probe hash, removed, and only the owned adb 5047 server stopped. Phone settings
and signed application remain untouched; raw evidence and models remain local.

Static ARM64/x86_64 symbol checks find no missing ORT imports. Stable sherpa native
libraries align 16 KB; `libonnxruntime4j_jni.so` aligns 4096 and still **FAILS 16 KB**.
A 4 KB phone cannot clear that gate. VoxLock graph bytes=77,584,388; DEX=2,468,280.
APK delta is NOT_BUILT, not zero.

## Engineering repairs and reproducibility

- Preserve `attribution_reliable` in both score adapters; known-but-unreliable
  words cannot receive favorable strict cpWER. Preserve unknown DER speech;
  handle null speakers and empty post-collar reference without a crash/false zero.
- Independently verify optional original WAV hash in phone-score adapter; a
  mismatch tombstones stale favorable scores. Retain legacy association-only
  calls with explicit provenance warning. Report actual thread counts.
- Atomic task journals, unknown outcome before device dispatch, exact input pins,
  bounded output paths, source/fixture/runtime manifests and no automatic retry
  after unresolved device timeout. New remote staging accepts only four pinned
  A3 files, not arbitrary files from a model directory.
- Independent regeneration matches all 10 DEV files byte for byte. Pinned A3/C2
  reprovisioning reproduces exact contest hashes. Twelve measured host source
  hashes and both measured phone source files reconcile to committed blobs,
  including checkpoint 1d9fdda; raw source snapshots are retained locally.
- 60 passed Python test executions, 1 optional Windows symlink skip
  (61 total,including optimized-mode repeats); 16 Kotlin core groups and
  plain/named/edited export corruption checks pass. The earlier export-path
  invocation failure is retained locally; it was corrected and rerun.

Full commands and environment: [tools/overlap_research/README.md](../tools/overlap_research/README.md).
Machine-readable results: [evidence directory](evidence/issue10-codex-20261105/),
[manifest](evidence/issue10-codex-20261105/evidence-manifest.json).
Raw generated WAV/reference/hypothesis/trace outputs stay in ignored
`.local/issue10`; only their paths/hashes/sizes and deidentified metrics are shared.
No paid APIs/package installs or user-wide auth/security changes. GitHub connector
read succeeded; git authenticated read also succeeded with ordinary sandbox
approval. Publishing this branch is separate from publishing an issue comment.

## Evidence ledger and original issue criteria

| Criterion | Verified status | Evidence / remaining limitation |
|---|---|---|
| 1 | PARTIAL / EXTERNAL BLOCKER | Two hash-frozen SYNTHETIC DEV fixtures; no independently manually annotated natural Russian overlap or untouched natural holdout. |
| 2 | PARTIAL | New host and 5 physical paired standalone repeats; WER/cpWER-U scored. Strict cpWER/DER/overlap word recall unavailable where annotation or attribution missing. App+worker PSS/UI/emulator remain unverified. |
| 3 | EXECUTED / RESEARCH ONLY | Correct A/B, opposite-speaker enrollment, short/no enrollment, clean/silence controls, both stems through same pinned A3; conservative accepted output falls back unchanged. Identity verifier missing. |
| 4 | PARTIAL / 16 KB FAIL | Actual ARM64 JNI/ORT 1.17.1 inference, native mapped paths, transfer hashes, 5 fresh-process repeats, standalone cancel/recovery. Existing ORT Java ELF alignment 4096 fails 16 KB. No research APK/Binder/background/OOM clearance. |
| 5 | RESEARCH COMPLETE | DiCoP live commit b9ccee411877f5e8da42e56ed27e693829f80ce1; no code license found; English CC-BY4 checkpoint, 2.47 GB. No training/conversion attempted. |
| 6 | RESEARCH COMPLETE / NO MIGRATION | audio.cpp live commit f7ac446fb75e594a6913c846bea6c85b637f6ac0; Apache2 license inspected; no Android/JNI/NDK paths in tree. No comparative Android implementation/proof. |
| 7 | EXECUTED ON SYNTHETIC DEV / STILL OPEN | Paired same-input host and physical tables, negative outcomes and diagnostic positive counterevidence retained. Natural holdout and identity/app gates not satisfied. |

Three read-only independent audits covered provenance/licensing, scoring/confounds
and Android compatibility. Their findings were checked against actual code and
outputs, not treated as measurements. Key contradictions retained: positive
assumed-identity recovery versus conservative unknown fallback; substantial clean
spill; sequence-order/splice confounds; standalone versus APK memory/lifecycle;
4KB execution versus failed 16 KB alignment.

**Decision:** keep current A3+C2 conservative fallback; VoxLock remains RESEARCH
ONLY/OPTIONAL future experiment. Do not integrate this prototype or close Issue #10.
Independent natural Russian annotation/untouched holdout, calibrated identity and
splice verification, then an optimized isolated app worker plus 16 KB/lifecycle and
physical acceptance are required. Missing human annotation is a genuine external
blocker; no assistant/ASR-generated annotation is substituted. Existing observed
quality/cost and identity gates justify stopping impractical contest integration.
