# Progress — 2026-10-30

## Disjoint acted holdout preparation — result not yet measured

- Pinned four new neutral Russian acted source clips, M-D-M-D, from the same
  dataset, disjoint from the three clips used to tune threshold 0.8.
  Metadata row indices [18,49,24,51], derived WAV SHA-256
  52f34a15e35af61ac193d01ea135712e7b71df64d74c6e4d9d0c0da4772fb070,
  duration 42,237 ms. Verified original WAV hashes and local composition.
- Historical development mode retains 0.5/0.65/0.8/0.9 sweep. New holdout
  mode prohibits parameter sweeps and invokes only production default 0.8.
  The external scorer assesses all same/different source speaker relations.
  Audio is installed in the test APK without reference speaker/text labels.
- Host JNI evidence strings now report the ACTUAL 0.8 threshold rather than
  mislabeled historical 0.9. Historical archive reports remain untouched.
  Code change itself is not a new accuracy measurement; independent Android
  execution and scoring are pending.
- Same acted dataset, no independent natural conversational corpus, no
  annotated speech boundaries (DER remains NOT_SCORED). Phone ARM64, peak RAM,
  overlap quality and redistribution reviews remain open. NOT_READY;
  PR #6 remains draft and public APK publication disabled.

## Direct continuation after Codex quota — optimized APK integrity gate

- Continued saved WIP at 3a02740 directly through Windows Bridge, without
  Codex or paid APIs. Preserved both original late13 reports. Downloaded CI
  artifact from 41119745856 and independently confirmed exact JSON equality
  plus SHA-256 b09753c3df9f57c4991f5a8ff7c563ad0b77230a0c236ac6cbff1459338f8bd9.
  Prior pending ASR run 41119746029 and native 41119047210 finished SUCCESS.
- Reproduced a critical python -O integrity gap in tools/check_apk.py: bare
  asserts vanished for JNI byte equality, APK BuildConfig runtime digest,
  INTERNET permission, private worker, ZIP contents, ELF header/load alignment
  and bundled license notices. Before the fix the native-swap negative failed.
- Replaced those with explicit fail-closed checks. Added authored negatives
  for internet, exported worker, missing ABI, invalid ELF, 4KB alignment,
  missing notice, bundled audio and duplicate ZIP.
  Locally 3/3 normal and 3/3 optimized runtime identity methods PASS;
  Android workflow 5/5, optimized evidence 3/3 and dependency 3/3 PASS.
  Android CI now runs both Python modes for the new regression.
- No change to actual Android runtime, ASR, diarization threshold or model.
  Physical ARM64, untouched dialogue DER/holdout, overlap and distribution
  review remain unfinished. This is not new phone or model accuracy evidence.
  Public APK publication stays disabled and PR #6 remains draft.
  Evidence: docs/evidence/direct-after-codex-optimized-apk-guard.json.

## Late continuation 13 — verify ELF CPU identity, not only ABI paths

- Continued clean 691697e. Preserved threshold 0.8, peer worktree, recovered
  backup/evidence and draft PR #6. Previous native 41119047210 and Android repeat
  41119047036 were still IN_PROGRESS at entry; neither is relabeled as PASS.
- Reproduced an APK inspection gap with six authored corruptions: CPU machine
  headers exchanged between ARM64 and x86_64 were accepted under the original
  directory names, despite matching ELF class and alignment. These are minimal
  numeric test headers, not loadable JNI or actual device failures.
- APK inspection now requires ELF e_machine 183 for arm64-v8a and 62 for x86_64
  for all six packaged libraries, and records each actual machine value. New
  six-corruption regression and existing runtime-byte/digest tests PASS: 2 methods.
  Inventory regression remains 3 PASS; five recovered Git blobs still exactly
  match the preserved ZIP. Runtime bytes, models and clustering are unchanged.
  Actual APK cloud validation follows. Physical ARM64 execution, independent
  holdout/DER, overlap quality and distribution review remain required.

## Late continuation 12 — require dependency evidence for both native ABIs

- Continued clean ac59f21 on WIP; prior recovered files are already committed.
  Main and draft PR #6 are unchanged; threshold 0.8 and the peer worktree are
  preserved. Latest completed head build 41118545214 PASS. The actual Android
  19-instrumentation/11-UI and development-probe evidence below remains separate
  from this build-input collector change; no new accuracy or device claim.
- Reproduced a concrete inventory defect: missing/empty `_deps` for either ABI
  was accepted if the other ABI supplied records. Four authored corruption cases
  failed before the fix. Require nonempty dependency inputs independently for
  ARM64 and x86_64 before publishing the inventory. Three methods now PASS in
  normal and optimized Python, including all four negatives and valid controls.
- Rechecked all five recovered evidence Git blobs against the existing backup:
  exact bytes agree; benchmark hypothesis hash agrees with its retained score.
  No runtime/model/default changed or new license clearance inferred.
- Collector code **e4aff33**: [standard CI 41119047166](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41119047166)
  and PR CI 41119058581 PASS, including Linux inventory regression, core/lint and
  packaged-runtime identity. Source-only tracked guard PASS: 290 files.
  At the saved snapshot, [native rebuild 41119047210](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41119047210)
  and [Android repeat 41119047036](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41119047036)
  remain IN_PROGRESS, not PASS. Review their results next; no new native/device
  success is inferred. Exact snapshot: docs/evidence/late12-status.json.
  Stop at a clean pushed checkpoint to conserve quota. Physical ARM64, untouched
  dialogue holdout/DER, overlap quality and full distribution review remain open;
  verdict stays NOT_READY, public APK disabled, PR #6 remains draft.

## Late continuation 11 — preserve peer integration and recovery evidence

- Completed verification at **acb9539**: Android
  [41116632139](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41116632139)
  **19 instrumentation + 11 UI checks PASS, zero skips**, confirmed from JUnit
  and saved-file reports. New delayed/unknown/cancelled exit checks execute;
  import/native inference/provider exports, runtime identity and lifecycle pass.
  Benchmark [41116632169](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41116632169)
  PASS: 0.8 D/M/D, WER/cpWER 1/41 each, correct threshold-0.8 provenance and
  invocation/hypothesis hashes. DER remains NOT_SCORED. Build/lint/core/packaging
  [41116632309](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41116632309)
  PASS. Local benchmark 7, optimized evidence 3 and notice 2 methods PASS.
- Exact current reports: docs/evidence/late11-*.json. Retained native and old
  candidate evidence is historical: native job PASS, old UI oracle FAIL, corrected
  candidate run PASS. No old failures/snapshots overwritten or relabeled.
  Backup ZIP and peer worktree preserved. This finishes checkpoint work at low
  quota; no autonomous process, agent, new model or parameter search launched.
- Verdict **NOT_READY**: untouched Russian holdout/natural dialogue and DER,
  physical ARM64/airplane mode/spoken microphone acceptance, overlap quality,
  phone performance and complete distribution review remain open. No new runtime
  promoted and public APK publication stays disabled; PR #6 stays draft.

- Fixed a separate provenance mismatch: DiarizationModelStore.REVISION still
  hardcoded threshold-0.9 after the approved default became 0.8. It now derives
  the label from the actual production constant; a regression assertion checks
  agreement. No weights, default threshold or historical outputs are changed.
- All six interrupted files match the pre-late-recovery backup ZIP byte-for-byte.
  Their native notices digest and AAR/package identities also validate. This
  verification does not promote a new runtime or clear whole-APK redistribution.

- Continued actual HEAD 92b99a2 after PR #8 merged into WIP. Threshold 0.8,
  debug-only diagnostics and peer worktree are preserved without new tuning.
  Verified successful 0.8 acted-probe run 41069898150: WER/cpWER 1/41 each,
  D/M/D PASS, DER NOT_SCORED. This fixture was used during threshold development,
  so it is not an untouched holdout or representative conversation benchmark.
- Latest benchmark 41071541258 FAIL is retained: instrumentation stopped on
  unconfirmed prior worker exit between sequential calls; no hypothesis/score.
  Added bounded cancellable waiting for the existing Binder death signal before
  rejecting the next request. Unknown exit still blocks; no blind retry, process
  kill guess or guard removal. Added delayed/never-confirmed/cancelled wait tests.
- Restored six interrupted recovery10 files remain intact. Verified notices hash,
  ASIO notice identities and native package pin before checkpointing. Native job
  41061172511 PASS but its old candidate UI job FAIL; corrected candidate run
  41062449527 PASS. Neither is relabeled as new 0.8 Android evidence.

## Independent development — Android Russian speaker-clustering diagnostic

- Isolated experiment branch based on production WIP commit 4aff651; original
  unfinished source/evidence left untouched in the primary worktree. Original
  default **0.9** remains available as an experimental comparator; candidate
  **0.8** becomes this branch's default after actual regression checks.
- Added debug-only, range-validated threshold override propagated across private
  diarization IPC; release builds cannot switch it. The tiny externally annotated
  D/M/D Android benchmark now measures 0.5, 0.65, 0.8 and baseline 0.9
  independently, without showing reference identities to the native model.
- External scorer validates threshold order, runtime duration, eligible labels,
  and exact production-baseline identity. It reports eligible speaker count and
  clip-level recurrence for each threshold. This is NOT DER or representative
  Russian-dialogue accuracy and does not automatically select a new threshold.
- Local Python authored probes: **7 passed**; Python bytecode compilation and
  git diff --check passed. Android build 41067160535 and pinned host regression
  41067160539 **PASS**. Actual Android Russian benchmark 41067160626 **PASS**:
  0.5, 0.65 and 0.8 each yield two speakers, correct clip-level D/M/D recurrence,
  zero unknown turns; baseline 0.9 collapses all three to one speaker.
  This is one tiny acted fixture, not a general accuracy guarantee.
- Added independent Android regression checks on public four-speaker Chinese
  recurrence and clean one-speaker Russian ASR fixture using candidate 0.8,
  plus invalid-threshold guards. Actual Android x86_64 run
  https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41068127258
  **PASS: 18/18 instrumentation, 0 failed, and full UI/export flow**.
- Promoted 0.8 into WIP as the validated Android runtime default; preserved 0.9
  as explicit legacy benchmark comparator and bound benchmark output to the actual
  selected default rather than the most favorable trial afterward.
  Real Android acted Russian benchmark
  https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41069898150
  **PASS**: 0.8 gives D/M/D recurrence PASS, **WER 1/41 = 2.44%** and
  **cpWER 1/41 = 2.44%**, versus 0.9 collapsing the voices with cpWER 25/41
  = 60.98%. The same-source ASR WER is unchanged; attribution improved.
- Post-default full Android x86_64 ASR/instrumentation/UI/export run
  https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41069897802
  **PASS**; Android APK/core
  https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41069897597
  **PASS**; pinned host JNI
  https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41069897728
  **PASS**. Earlier candidate regression run 41068127258 passed 18/18.
  This is a three-utterance acted fixture, NOT representative natural
  conversational accuracy, independent DER, ARM64 performance or release approval.
- This experiment specifically targets the known baseline speaker collapse
  (WER 2.44%, cpWER 60.98%, D/M/D => one cluster on three acted clips).
  These prior metrics are not changed by this source-only experiment.


## Round 11 / continuation 3 — system documents and Russian evaluation

### Recovery call 10 — reconcile actual native/runtime evidence

- Continued clean a16ec20; full instructions/handoff and current PR #6/issue #7
  checked. Native 41061172511 and Android 41061172278 were still running at entry.
  No models, clustering parameters, stored outputs or default runtime changed.
- Found a candidate-workflow integration mismatch by reading the actual steps:
  bootstrap provisions upstream runtime metadata, then replaces the AAR with the
  built candidate. UI export checks must hash the actual AAR build input rather
  than trust the earlier provisioning JSON. This preserves strict comparison
  with exported BuildConfig identity and avoids a false runtime-mismatch failure.
  Existing wrong-runtime/export negatives remain unchanged; actual CI follows.

### Recovery call 9 — collect pinned ASIO nested notices

- Code **f9af8ad** [standard CI 41061172426](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41061172426)
  PASS: 2 inventory methods on Linux plus build/lint, 16 core groups and packaged
  runtime identity. Both methods also PASS locally on Windows, including exact
  persisted-byte digest. Notice Git blobs match the verified archive members;
  274-file source-only guard PASS. Native 41061172511 and automatic Android
  repeat 41061172278 remain in progress at the recorded snapshot, not PASS.
- Updated inventory from an actual new native build is still pending. Default AAR
  remains unchanged and no candidate is promoted. Prior 17+11 Android evidence,
  Russian WER/cpWER/recurrence failure and all remaining gates are unchanged.
  Exact separate statuses: round11-recovery9-status.json / build CI JSON.
  Obsolete own native/Android runs at ce06c06 were cancelled after the byte fix;
  they are not counted as successful validations. Backup and old evidence retained.

- Added actual output-byte hash regression and reproduced a Windows failure:
  text-mode newline translation changed runtime-notices.txt after hashing. Write
  exact UTF-8 bytes instead; recorded hash now matches the persisted file.
  Both local methods PASS after the fix. Prior Linux CI notice hashes remain valid.

- Continued clean e549ccb, read full instructions/handoff and checked PR #6,
  deferred issue #7 and current CI. Existing Android 41058719146 remains PASS
  17+11; runtime and Russian benchmark are unchanged. Prior files/logs preserved.
- Verified the exact upstream-pinned ASIO archive SHA cbcaaba0...b7a8a5b.
  Its COPYING and LICENSE_1_0.txt are nested in asio/, explaining the empty
  round-10 inventory entry. Preserved exact notice bytes and archive/member hashes.
  This is archive inspection, not a fresh native build or blanket license clearance.
- Collector now includes only the explicit ASIO subdirectory and preserves
  relative paths. Nested binary/oversize negatives and same-name root/nested
  notices PASS; 2 local methods. Standard CI now executes these fast tests.
  Full native workflow is triggered for actual build-input inventory verification;
  no runtime promotion, model changes or new accuracy claims are made.

### Recovery call 7 — front-page claims match measured limits

- Rechecked clean a6d9bfa, full instructions/handoff, draft PR #6, deferred issue
  #7 and actual completed code CI. No new runtime defect or lost work found.
  Code 6afd8d1 remains verified by Android 41058719146 PASS 17+11 and build
  41058718972 PASS. Interrupted backup, logs and prior snapshots remain intact.
- Corrected both README introductions: the separate Chinese-fixture recurrence
  success must not imply Russian speaker quality. The independent tiny acted
  Russian D/M/D failure and WER/cpWER scope now appear upfront. Clarified that
  Kotlin fusion preserves supplied model labels rather than fixing clustering.
  CI badge now names the WIP branch instead of silently reporting main's UI base.
- Documentation-only change; no model calls, parameter tuning, new models or
  additional Android coverage claimed. Physical-device and distribution gates
  remain open; APK publication remains disabled and verdict stays NOT_READY.

### Recovery call 6 — validation under optimized Python

- Code **6afd8d1**: [build 41058718972](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41058718972)
  PASS including optimized negatives, lint, 16 core groups and runtime packaging.
  [Android 41058719146](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41058719146)
  **17 instrumentation + 11 UI checks PASS, zero skips**, confirmed from actual
  JUnit XML and UI report. Fresh provider files also pass the optimized validator.
  Prior repeat 41058035642 likewise PASS 17+11; earlier pending snapshots preserved.
- Reports: round11-recovery6-status.json, Android/build CI JSON and exact UI flow.
  Runtime remains 771fda6a...511c1c8; original hypothesis/license Git blob hashes
  still match recorded pins. No audio/models published; backup and main preserved.
  NOT_READY: Russian merging/cpWER 60.98%, DER/representative dialogue, physical
  ARM64/spoken recording/phone performance and distribution gates remain open.

- Verified clean HEAD 5d4b05b, current CI, full AGENTS/handoff, draft PR #6 and
  deferred issue #7. Prior files/backup/logs remain intact; no new models.
- Reproduced an actual integrity-check defect: `python -O tools/test_android_evidence.py`
  fails its altered-SRT/recomputed-hash negative because Python removes assert
  statements in the shared export validator. Normal-mode previous results remain
  valid; this is not a model or Android inference failure.
- Replaced those assertions with explicit checks preserving their failure API.
  Local archive methods 3 PASS in normal and optimized mode; optimized UI methods
  6 PASS; real retained host-export corruption regression PASS. Added optimized
  negatives to standard CI. No model, threshold, app or historical evidence changed.

### Recovery call 5 — durable archived-evidence verification

- Commit 952f713 [standard CI 41058035458](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41058035458)
  PASS: new 3 evidence corruption methods, archive verification, build/lint,
  16 core groups and actual packaged runtime identity. Local UI 6 methods,
  Python compile, workflow YAML and 265-file source-only guard also PASS.
  Main still 2cec9dd; prior evidence/backup retained without replacement.
- Automatic Android repeat 41058035642 was still in progress at this evidence
  snapshot. Last completed actual device flow remains 41056348245 PASS 17+11;
  application/models/threshold are unchanged. New archive checks are not a new
  device run. Exact separate statuses: round11-recovery5-status.json / CI JSON.
  NOT_READY and the independent speaker-merging failure remain unchanged.

- Rechecked actual clean HEAD 594ebb0, preserved backup/logs, full AGENTS/handoff,
  draft PR #6 and deferred issue #7. The old picker failure is already fixed:
  run 41056348245 PASS 17+11; no repetition of the old failure as current status.
- Added lightweight archived-export verification to standard CI. It checks all
  three provider-file hashes/byte counts, cross-format millisecond timelines and
  JSON runtime against the recorded APK native/DEX identity report. It explicitly
  labels its result archived integrity, never fresh Android execution or accuracy.
  Actual retained files are the control; corrupt payloads, mismatched runtime,
  failed packaging identity and altered SRT timeline with recomputed hash are
  negative cases. No audio/models downloaded, baseline or thresholds changed.

### Completed verification after recovery call 4

- Code **12b81bb**: [Android 41056348245](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41056348245)
  **17 instrumentation + 11 actual UI checks PASS, zero skips**. System OpenDocument
  import, real public Russian ASR/diarization, CreateDocument TXT/JSON/SRT saves,
  cancellation, pending JSON-picker rotation, persisted-file readback, exact
  cross-format content/timeline, runtime hash and post-cleanup persistence pass.
  Filename is edited only after rotation settles; earlier failures remain recorded.
- Actual emulator microphone recording/lifecycle passes, but capture has no detected
  speech and correctly skips ASR. This is NOT spoken microphone accuracy evidence.
  Public imported speech exercises actual inference. Physical ARM64/airplane-mode
  spoken conversation remains a required gate.
- [Build 41056348279](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41056348279)
  PASS: 16 core groups, lint, APK/native-byte/runtime identity. Default no-TTS AAR
  hash remains 771fda6a...511c1c8. Source/notice inventory is unchanged; distribution
  review remains open and APK publication disabled.
- Independent invocation-bound run 41049800881 at dd2e1f2: WER **1/41=2.44%**,
  cpWER **25/41=60.98%**, D/M/D all Speaker 1 (**FAIL**), DER NOT_SCORED. These
  three acted clips are not a representative corpus. No parameter was tuned.
- Exact exports and reports: docs/evidence/round11-provider-export.*, round11-ui-*,
  round11-apk-inspection.json, round11-final-build-ci.json, round11-status.json.
  Three final screenshots visually reviewed; PNG/XML remain in CI artifact, no audio.
  Downloaded hypothesis Git blobs match scorer hashes; dataset license Git blob
  matches the frozen source hash. Interrupted source backup and logs preserved.
- Local UI 6, benchmark 6 (including four actual-shell failure scenarios), collector
  5, runtime identity 1, native patch 3 and notice inventory 1 methods PASS.
  Verdict **NOT_READY**: Russian speaker merging, independent DER/natural dialogue,
  ARM64/spoken capture/phone performance and license-distribution gates remain.

### Recovery call 4

- Preserved interrupted HEAD a3ff0dc, untracked exact-byte evidence and
  .gitattributes; source backup .codex-local/round11-interrupted-sources.zip remains.
  Re-read AGENTS/handoff, PR #6 and issue #7; no new models or main changes.
- Run 41050157496: 17 instrumentation PASS, whole workflow FAIL after seven UI
  checks. Actual retained JSON artifact is 66-byte `cat: ... No such file`, not
  an empty UI dump. Screenshot shows edited JSON filename before rotation;
  subsequent tree restores transcript.json. DocumentsUI recreation reset the
  filename while QA expected neuro-qa-ui.json. This is not model/diarization PASS.
- Moved filename editing after two observed stable picker-rotation trees, verify
  exact edited filename before saving, and reject adb error bytes with explicit
  provider-read diagnostics. Actual Android retry remains required.

- Added actual-shell collector regression using authored commands: fresh output,
  prior Gradle failure preservation, stale invocation and zero-exit adb error text.
  All four scenarios PASS; benchmark suite now 6 methods, UI 5, collector 5,
  scorer 12 and runtime identity 1 PASS locally. Tracked source-only guard PASS
  (248 files before the final evidence snapshot). No Android claim from fake commands.
- Second independent Android measurement (41049412108, `a1898e2`) repeats
  WER 1/41, cpWER 25/41 and merged D/M/D. The new invocation-bound benchmark and
  keyboard-driven picker are running at `dd2e1f2`; standard build/core/lint/APK
  identity PASS already (41049800892). Updated Russian APK instructions to match
  actual disabled publication instead of pointing readers at a nonexistent new APK.

- Picker run 41048853466 passes all 17 instrumentation tests but stops UI QA
  after seven checks: API33 DocumentsUI reports [0,0][0,0] for visible filename
  and SAVE controls. Screenshot and XML reviewed; no guessed coordinate used.
  Added bounded TAB navigation with matching focused node verification, and an
  authored negative/control test. This remains pending real CI execution.
- Benchmark output now carries a fresh per-invocation identity passed through
  instrumentation and checked before scoring. Missing/stale IDs must overwrite
  favorable scores with ERROR, even when the audio hash/text match; control and
  negatives PASS (benchmark methods now 5). APK asset assertion forbids reference
  text/IDs. No previous benchmark measurement is reclassified by this change.

- Actual external acted-probe Android run **41048642815 PASS execution** at
  `ab46587`: one instrumentation test, WER 1/41 (2.44%), cpWER 25/41 (60.98%),
  **A-B-A FAIL** (all D/M/D clips merged into Speaker 1). DER NOT_SCORED, no
  independent speech boundaries. 5,129 ms / RTF 0.261 on API33 x86_64 cloud CPU,
  including engine load/worker lifetime, excluding import/model verification;
  memory snapshots exclude worker and are not peak. Exact original artifacts
  copied to docs/evidence/round11-acted-*.json under the attached dataset license.
  No threshold tuned and no representative accuracy claim. This is a P0 quality
  blocker revealed by the independent source, not a successful dialogue demo.
- Exposed metric/recurrence status in the benchmark Actions summary so a green
  execution job cannot hide the speaker failure. Benchmark triggers now include
  production engine/core/runtime changes. Reference text/IDs stay outside the
  instrumentation APK; only public audio and required license are copied to assets.
  UI now explicitly warns that voices can merge/split and need manual review.
  Local benchmark 4, UI 4 and scorer 12 methods PASS; workflow YAML parses.

- Re-read full AGENTS.md/handoff and historical round-8 status; continued clean
  HEAD `94d7680` on the WIP branch. Fetch shows no divergence. Main is untouched;
  draft PR #6 remains open. New owner issue #7 is an alternative-model evaluation,
  explicitly lower priority than ongoing Android fixes; no model swap attempted.
- Extended actual UI QA to import the pinned public Russian WAV through the
  system document picker and run real in-app inference. TXT/JSON/SRT must then
  survive real CreateDocument save, cancellation and JSON-picker rotation. Saved
  bytes are read from the disposable Downloads provider, checked for the known
  public phrase, runtime identity and independent exact cross-format timeline.
  App cleanup must leave provider-owned exports unchanged.
- UI selectors now combine role/resource/text constraints and refuse ambiguous
  matches. Four selector/export corruption methods PASS locally; collector five
  PASS. First host-export test invocation used a JSON-only downloaded artifact
  and failed because SRT/TXT were absent; corrected execution against retained
  actual round-8 host exports PASS, including corruption negatives.
- New system-picker UI flow remains pending CI. Audio is public, transient and
  excluded from artifacts; screenshots and text exports contain only that fixture.
- First picker run (41047018642) executes the import picker successfully but
  fails safely on an ambiguous QA selector: the status sentence repeats the
  recognition button label. Changed action taps to exact labels while keeping
  substring searches for status messages. The repeated-label negative now checks
  the selected coordinate comes from the button, not the surrounding prose.
- Added a separately opted-in Android evaluation using three public acted Russian
  test utterances. Verified the full dataset OpenRAIL license at immutable revision
  `a74ff44...`; no paid contract is required for this lawful evaluation. Full terms
  are copied for dataset-derived artifacts; app/model licenses remain separate.
  Publisher consent statements are not independently audited by this project.
- Frozen selection before inference: first neutral D, first neutral M, second
  neutral D in pinned test.csv order. Unchanged 44.1-kHz PCM with two 500-ms gaps;
  exact composite SHA `61354eef...98b3861`, 19,655 ms. Only external scripted text
  and source-speaker labels become references. No speech/word boundaries guessed;
  DER deliberately has no reference. Scope: ACTED_COMPOSED, not natural meetings.
- Provisioning/integrity/scoring methods 4 PASS, existing scorer 12 PASS; fixture
  byte hashes regenerated identically. Android inference/actual metrics pending.
  See RUSSIAN_EVALUATION.md for limitations and the separate workflow. No accuracy
  threshold or favorable result is asserted before model execution.
- First evaluation CI (41048414798) stopped before model provisioning: its first
  alphabetically ordered unit test needed the workspace .local directory, which
  existed locally but not on a clean runner. Moved directory creation into test
  setUp for every method; no test/measurement skipped or relabeled as success.
- Second picker run (41047975190) reaches public import and export cancellation,
  then safely rejects three Downloads labels (toolbar, breadcrumb and root
  drawer). The captured system UI tree supplies a distinct android:id/title
  resource for the drawer item; selector now uses that observed resource plus
  exact text. Added the repeated-root-name negative locally. This is a QA-selector
  repair, not evidence of an application export failure or successful save yet.

## Round 10 / continuation 2 — default no-TTS runtime and identity

- Entire AGENTS.md/handoff and round-8/9 status re-read; continued clean WIP HEAD
  `c19f325`, draft PR #6. Fetch succeeds; remote main still `2cec9dd`. Previous
  documentation HEAD cloud builds also PASS (41042795276 / 41042803870).
- Default provisioning now selects the Android-tested no-TTS AAR locked in
  `tools/runtime/runtime.properties`. Verified local cache needs no CLI/network;
  uncached acquisition uses existing GitHub CLI authentication for exactly this
  repo/run/artifact. Wrong/expired/unauthorized artifact fails without upstream
  fallback or replacing the previous runtime. No credential lookup/settings edit.
- Upstream GPL/TTS AAR is explicit `--upstream-runtime` regression only. Gradle
  verifies the selected bytes before preBuild; upstream and new source-build
  candidates require explicit validation opt-ins. JSON document and Android
  inference metadata include the actual AAR SHA-256 from generated BuildConfig.
- APK inspection compares all four packaged JNI/ORT files byte-for-byte with the
  selected AAR and checks its digest in DEX. Authored native-swap/fake-digest
  negatives PASS. New downloader tests: 5 PASS; existing integrity/cache/selection
  negatives PASS. Collector 4 methods PASS; patch tests 3 PASS.
- Local offline Gradle core/runtime gate PASS: 16 core groups, 5 tasks, 58s.
  No SDK/emulator/toolchain installed; reused ignored portable build tools.
- Native workflow now collects bounded actual dependency/notice input inventories
  from both ABI builds. Missing notices and toolchain/stdlib review stay visible;
  inventory is not blanket legal clearance. Inventory corruption/TTS negatives
  PASS locally. Cloud build/emulator/rebuilt-native verification follows.
- Default no-TTS build/core/lint/APK identity verification PASS in cloud:
  https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41044063915 .
  This checks the actual packaged four native libraries and BuildConfig digest,
  not merely successful AAR selection. Emulator/native rerun still in progress.
- Added tree-driven disposable-emulator UI flow: real permission denial/grant,
  actual landscape capture plus continued recording, HOME auto-stop, recorded
  transcription/export controls, UI cleanup and permission-revocation restart.
  Uses the android-emulator-qa skill's UI-tree coordinate rule. Screenshots/XML
  and explicit failure metadata are retained; no private/microphone audio.
  Selector negatives 2 PASS and collector tests 5 PASS locally; real UI flow
  remains pending until cloud execution. A UI failure must fail the workflow.

### Round 10 completed verification

- Validated code `f1dbfb9`; no main merge. Default no-TTS Android suite and actual
  UI flow PASS: **17 instrumentation tests / zero skips + 7 UI checks**,
  https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41044710621 .
- Explicit original-runtime regression also PASS **17 + 7**, preserving known
  mixture native worker failure as containment-only evidence:
  https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41044824154 .
  Default runtime completes that mixture with four unknown turns and no detected
  overlap. Neither result is Russian dialogue accuracy or source separation.
- The seven UI checks execute real permission deny/grant dialogs, confirmed
  landscape recording, HOME auto-stop/finalization, recorded-input transcript and
  export controls, cleanup and expected OS process restart after permission
  revocation. Four default-run screenshots viewed: readable portrait/landscape,
  recording guards, empty recorded-emulator transcript and cleaned state. This
  does not drive the document-provider save picker or establish physical-phone UI.
- Latest build/core/lint/static identity PASS, 16 core groups:
  https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41044710275 .
  All four packaged JNI/ORT byte hashes match the locked AAR; DEX and real JSON
  inference metadata identify the same SHA-256. No APK/audio/model published.
- Full independent native rebuild + candidate Android job PASS:
  https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41044063814 .
  Rebuilt AAR is **byte-identical** to run 41039830327, SHA-256 `771fda6a...511c1c8`.
  This establishes these two same-source/NDK/patch builds, not every toolchain.
- Local actual-byte Gradle negatives PASS: upstream AAR is rejected by default,
  accepted only with explicit regression property, then no-TTS is restored and
  passes. `round10-runtime-gate-negative.json` records exit codes/log hashes.
- New Python methods PASS: default provisioning 5, APK identity 1 (four native
  swaps + wrong DEX digest), UI selectors 2, collector 5 (including UI-failure exit
  preservation), dependency inventory 1, runtime patch 3. Earlier round-9 scorer
  and codec model results were not relabeled as new measurements.
- Dependency inventory/notices retained from both real builds. Missing ASIO-root
  notice, Eigen optional-license/header scope and toolchain/stdlib review remain
  explicit; downloaded source is not proof of linked code. Default GPL/TTS
  provisioning blocker is removed; final redistribution clearance is still open.

Machine status and reproducible metadata: `docs/evidence/round10-status.json` and
`round10-*.json`; source-tree notice text is `round10-runtime-source-notices.txt`.
PNG/XML UI evidence stays in the linked Actions artifacts, with hashes/dimensions
committed. No microphone samples are collected or committed. Git main remains
`2cec9dd`; draft PR #6 remains open, no force push or paid API.

Verdict **NOT READY** pending physical ARM64/airplane mode/spoken dialogue,
independent licensed Russian annotations/metrics, overlap quality, phone peak
RAM/thermal/power and final notices/distribution review. Actions artifact expiry
is a provisioning limitation with an explicit failure; no permanent release URL
is claimed. Those open gates do not negate the executed Android/UI improvements.

## Continuation 1 / round 9 — GitHub access restored
- Supervisor preserved rounds 1–8 in WIP commit `8d9c1e7` on
  `codex/overnight-20261030-wip`. Current authenticated fetch succeeds; main is
  untouched. Earlier permission blockers below describe historical runs.
- Cloud build/core/lint PASS for recovered source:
  https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41038678251 .
- First Android inference CI FAILED before emulator startup because FFmpeg was
  absent: https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41038678364 .
  Added explicit runner-only FFmpeg installation. No local machine installation.
- New workflow files cannot dispatch while absent from default branch (HTTP 404).
  Added narrowly filtered WIP-branch push triggers for no-TTS native build and
  independent Linux host inference. No default-branch merge is needed.
- Runtime and Android results remain pending; no device success inferred.
- Independent Linux host JNI suite PASS (all four processes exit 0):
  https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41039298647 .
  The known mixture completes with three turns but overlap_detected=false;
  this is crash-probe completion, NOT successful overlap recognition. Historical
  Windows native fatal remains valid. Cloud build for `733e2d2` also PASS:
  https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41039298469 .
- Source inspection found an independent bounds defect: upstream TopkIndex
  forms begin()+topk before clamping to size. Diarization requests segmentation
  speaker count even when clustering leaves fewer identities. A strict-hash
  candidate patch clamps before iterator construction and emits unknown identity
  when positive cluster votes cannot support the detected speaker count. It does
  not synthesize identities or separate simultaneous voices. Exact Windows crash
  root cause is not yet proven by a patched full-runtime replay.
- Added original-C++ negative replay with checked STL, patched helper ASan/UBSan
  numeric tests, deterministic API-preserving candidate AAR packaging and a
  dependent Android emulator job using that exact candidate. Python patch tests
  3 PASS locally; native compilation and candidate Android execution pending CI.
- First real Android x86_64/API 33 execution (run 41039298448): **9 PASS / 2 FAIL**.
  Russian public fixture repeats with identical text and expected phrase; silence,
  ViewModel import/snapshot and TXT/JSON/SRT path pass. Fresh-recognizer load
  1191/1179 ms, decode 1404/1371 ms for 11290-ms audio (emulator only). Two actual
  AudioRecord capture sessions pass, not a spoken microphone-ASR accuracy test.
  WAV replacement/cleanup/export and fake recording error-state tests pass.
- Failures are concrete: codec sampleFlags=-1 at EOF was mistaken for encrypted
  input; flags now checked only after a real sample. JUnit refused the diarization
  test class because runBlocking inferred Int from Log.i; all such tests now have
  explicit Unit signatures. Diarization execution in that run did NOT occur.
- Evidence collector found another real defect: AGP uninstalled the app before
  retrieval, and adb exec-out returned zero with run-as error text. Pinned AGP
  BooleanOption confirms leaveApksInstalledAfterRun; now enabled for disposable
  emulator testing. Collector rejects non-object/non-JSON output and requires all
  expected metadata on green runs. Four collector tests PASS, including zero-exit
  adb corruption. No missing JSON is treated as valid inference evidence.
- Added explicit candidate-run input to Android workflow so fixed app/tests can
  validate the same no-TTS artifact without rebuilding native code or merging main.
- Unpatched no-TTS native candidate build PASS for both ABIs:
  https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41039298608 .
  Candidate SHA-256 `c39f58ed711872374b59570588e5f46331cfc65fe5855a7ae8280088b6c9561e`,
  14,948,166 bytes. Download inspection finds only ARM64/x86_64 JNI + ORT, no
  espeak-ng-data string, and 16-KB ELF LOAD alignment. This candidate is NOT
  selected for app distribution; patched candidate/testing remains in progress.
- Added Android platform-recording -> ViewModel -> actual worker -> transcript
  document/cleanup test. It collects only duration/count/provenance metadata and
  deletes captured audio; it is not a spoken microphone accuracy benchmark.
  Added structured known-mixture evidence separating native completion, caller
  survival, unknown turns and actual overlap detection. Collector includes both
  records; four collector methods PASS locally. New instrumentation pending CI.
- Android run 41040228527 executes **14 PASS / 1 FAIL**. Genuine diarization
  recurrence/repetition/silence/short-input, Russian combined ASR, process-death
  recovery and success/cancel/retry worker-exit tests PASS. Raw JSON collection
  now works (six metadata records retrieved). The known mixture crashes its
  worker and caller survives; that is containment PASS, overlap accuracy unproven.
  Remaining failure is FLAC reported as audio/raw, not a compressed MediaCodec
  MIME. AOSP Android 13 FLACExtractor source confirms it decodes PCM and supplies
  PCM encoding explicitly. Added bounded raw-PCM16 path and float-output negative.
- Patched no-TTS native build PASS in run 41039830327. Original C++ checked-STL
  replay aborts on the invalid iterator; patched numeric ASan/UBSan tests PASS.
  Candidate SHA-256 `771fda6a4abf845a6f84f48e05e887fdf159671beb88cbc9aae327806511c1c8`.
  Official Kotlin API bytes retained, all JNI replaced with only two intended
  ABI/library pairs. Added explicit --runtime-file selector with hardcoded digest;
  wrong binary negative preserves previous runtime. Candidate emulator run pending.
- Raw-FLAC fix passes all five generated codec imports on Android. Run
  41041113969 is **15 PASS / 1 FAIL** because the new high-bit FLAC test assumed
  float output. Actual Android extractor safely returns PCM16 for that file.
  Corrected this test assumption: separate format probe inspects the actual
  extractor encoding, accepts valid PCM16 conversion and rejects raw non-PCM16.
  Production format restrictions are unchanged; no failing inference gate hidden.

## Round 9 / continuation 1 — final verified result

- Validated code: `d37a030` on `codex/overnight-20261030-wip`. Main reconfirmed
  unchanged at `2cec9ddf47a4fe6a53d25cec0bef0b206a8c0f58`. Six development
  commits pushed after the supervisor recovery, no history rewrite or main merge.
  [Draft PR #6](https://github.com/Ai-b0ss/nuclear-neurostenographer/pull/6).
- **Original runtime Android: 17/17 PASS, zero skips**:
  https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41041829357 .
  This includes caller-survival on the known native worker failure, NOT native
  mixture success. Structured evidence preserves native_completed=false.
- **Exact pinned no-TTS candidate Android: 17/17 PASS, zero skips**:
  https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41041827147 .
  Same public mixture completes without native crash, returns four unknown turns,
  overlap_detected=false. Nine valid metadata JSON records retrieved in each run;
  no private/microphone audio uploaded. Empty recorded-emulator transcript is not
  a spoken microphone accuracy claim.
- Both suites execute real CPU Russian ASR, repeat/silence, global A-B-A on the
  public Chinese four-voice fixture, combined Russian single-voice inference,
  model ZIP negatives, WAV snapshot/state/cleanup, actual TXT/SRT/JSON exports,
  generated AAC/MP3/Vorbis/Opus/FLAC import, high-bit format probe, codec negatives,
  real AudioRecord sessions and ViewModel -> worker -> document/cleanup.
- **Build/core/lint/static packaging PASS**, 16 core groups, 77 tasks, 1m23s:
  https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41041827026 .
  Source-only tracked-file guard finds no model/audio/APK/AAR/signing artifact and
  no file over 2 MiB. Native candidate reinspection confirms intended two ABIs,
  absent espeak data marker and 16-KB ELF LOAD alignment. Not a 16-KB device test.
- Local Python: collector 4, patch 3, scorer 12, checkpoint 4 methods PASS (no
  symlink skip in restored permissions); codec-fixture 2 methods PASS; pinned
  download corruption/cache and candidate rejection/selection/cache PASS.
- Machine status: `docs/evidence/round9-status.json`; final Android reports,
  metadata, earlier failing reports, Linux host output, exact native source/binary
  pins and C++ bounds-negative provenance are retained alongside it. No model
  accuracy inferred from synthetic/numeric or public single-voice fixtures.

Verdict **NOT READY**: physical ARM64/airplane-mode/spoken recording, independent
licensed Russian dialogue annotations and WER/DER/cpWER, phone peak RAM/thermal/
power, visual/background/rotation/permission-revocation acceptance remain open.
Overlap recognition/separation is unproven; the patch preserves uncertainty.
Patched Windows JNI has not been replayed. Default provisioning still selects
the full upstream GPL/TTS AAR; no-TTS selection is explicit, and distribution/
notices review remains open. APK publication stays disabled. These limits do not
erase the new verified Android execution or the original failure evidence.

## Baseline inspected
- Entire AGENTS.md and CODEX_HANDOFF_2026-10-30.md read; no direct chat access.
- Local main and live GitHub main: `2cec9ddf47a4fe6a53d25cec0bef0b206a8c0f58`; working tree initially clean. No open PRs found. Issues #2–#5 open, #1 closed.
- Baseline build succeeded: https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/40987151101 ; UI smoke: https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/40986838387 . These do not prove ASR.
- Environment constraint: `.git` is explicitly read-only; `git fetch` failed with permission denied on FETCH_HEAD. Local JRE is Java 8, no Gradle/Android SDK installed for this work. No heavy local SDK/emulator installation. Isolated remote branch/commits use GitHub REST; source changes remain recoverable in this working tree. Main is untouched.

## P0 ASR implementation (Android build verified; Android inference pending)
- Official sherpa-onnx AAR 1.12.20 downloaded and SHA-256 verified locally: `e3905b1258b577d8d374db798618602ceaaff5805cbf9b356ab25267cd98144d`. Inspected classes.jar (contains Kotlin OfflineRecognizer) and JNI entries (ARM64 and x86_64 present). APK filters to those two ABIs.
- Upstream tag resolves to `5ce3d6d93a5f4fe11657bf11a6bf3a022eeef22f`. APIs inspected at https://github.com/k2-fsa/sherpa-onnx/blob/v1.12.20/sherpa-onnx/kotlin-api/OfflineRecognizer.kt and OfflineStream.kt; `nemo`, file paths, `acceptWaveform`, `decode`, `getResult`, explicit stream/recognizer `release`.
- GigaAM CTC model pinned to HF revision `32a4c7cc81809bd132e2d935ab99e9e6ab47fbec`; 224,721,476-byte INT8 ONNX SHA-256 from HF LFS metadata, tokens/LICENSE hashes checked from downloaded bytes. Converter confirms 16 kHz / 64 features, v3 CTC, character vocabulary. Official compatibility: https://github.com/k2-fsa/sherpa-onnx/issues/2852 . Model card directs license to GigaAM MIT; pinned bundle also contains MIT copyright GigaChat Team. Full license included in provisioned ZIP.
- Added checksum-verified AAR/model provisioning, local ZIP installation, strict entry/size/hash checks, bounded WAV reader (PCM16 mono/stereo 8–48kHz -> 16kHz), background inference with cancellation between native decode steps and explicit cleanup. Recorder/import -> actual ASR -> conservative fusion -> TXT/JSON/SRT. Demo transcript removed from this screen.
- Input limited to 120 seconds, ASR windows to 20 seconds to bound attention memory. Boundaries can cut words. Display/export intervals represent input windows, NOT speech/word boundaries. Linear resampling is baseline quality; compressed codecs unsupported and fail explicitly. No speaker inference/identity claim. No INTERNET permission.
- Added cloud x86_64 inference instrumentation (public upstream fixture, repeated ASR, silence, malformed model imports) and pure Kotlin WAV negative/regression tests. New build/inference evidence will be appended after execution.

## Still NOT contest-ready
Android inference is NOT_RUN. ARM64 physical device, microphone behavior, WER/DER/cpWER, RAM/thermal behavior and airplane-mode physical test remain NOT_RUN. Genuine diarization and stable inferred A-B-A speakers remain unimplemented. Do not close #2–#5 or present this as a complete stenographer.

## Completed local verification and concrete blockers
- GitHub CLI public reads work, but `gh auth status` confirms invalid Ai-b0ss token. Attempted remote `POST git/trees` returned HTTP 401; no remote tree/commit/branch was created. Connected GitHub confirms push permission, but its create_tree call was rejected before execution: **MCP tool call requires approval, but approval policy is never**. No alternative write surface was used after that rejection. Commit/push/PR/new Actions runs are BLOCKED. The earlier intended REST publication did not occur.
- Downloaded pinned public model and test fixture with checksum verification. Actual `OfflineAsr.kt` compiled against the AAR's Kotlin classes and executed through verified Windows x64 JNI 1.12.20. A host-only Android AssetManager placeholder permits class loading; inference uses file paths, never asset APIs. Windows dependency loading required explicitly preloading the matching onnxruntime.dll before sherpa JNI.
- **Host inference PASS**: 11,290 ms public WAV; two independently loaded model runs returned identical Russian text, including “у лукоморья дуб зеленый”. Final run load 2,437/2,431 ms; decode 1,194/1,174 ms. All speakers unknown; intervals within audio. Two seconds of all-zero PCM and a 20.01-second silent clip with a short final window returned no text. Tiny audio rejected; cancellation after decode followed by successful new inference proves that cleanup path on this host. This is Windows host evidence, NOT Android, ARM64, WER or conversational/diarization evidence. Raw recognized text/provenance: `docs/evidence/round1-host-asr.json`.
- **8 Kotlin core test groups PASS**, including pre-existing fusion/export regressions plus PCM16 negative/normalization/stereo/resampling and strict model ZIP adversarial tests. No synthetic fixture is described as inferred diarization.
- License review found a distribution blocker in full upstream AAR: TTS is enabled and includes espeak-ng GPL-3.0. Detailed pinned source evidence: `docs/RUNTIME_LICENSES.md`. APK upload disabled until an ASR-only runtime is built, reviewed, pinned and tested; manual ASR-only runtime workflow provided but NOT_RUN. No project license was changed. Model MIT provenance is separate and verified.
- For local build fallback only, portable JDK 17, Gradle 8.9 and SDK platform/build-tools 35 were placed under ignored `.local/`; no Android Studio, emulator, NDK or machine-wide settings installed. Free disk before setup was 24.76 GiB. Build-tools explicitly pinned to 35.0.0 after AGP default tried to install 34.0.0. Standard debug-keystore lock failed inside sandbox; a workspace-owned ignored debug key and optional `localDebugStore` Gradle property avoid writing user-wide signing state. Final build result follows below.

## Android build phase and attempted cloud execution
- Local `:core:runCoreTests :app:lintDebug :app:assembleDebug :app:assembleDebugAndroidTest` **PASS**. Lint initially exposed MissingPermission in recorder; fixed with an explicit permission contract and ViewModel recheck. Added Android 12+ cloud backup/device-transfer exclusions and launcher icon. Final lint: **0 errors, 7 warnings**, all pinned dependency update suggestions. No lint baseline/suppression added.
- Ordinary APK inspected with real Android aapt: no INTERNET permission; ARM64/x86_64 only; JNI, ONNX Runtime and Compose graphics native libraries all have 16,384-byte ELF LOAD alignment; unused C/C++ wrapper libraries excluded; no ONNX/WAV bundled. See `docs/evidence/round1-apk-inspection.json` for exact final APK size/hash. This is packaging evidence, not execution or a 16-KB device test.
- Python pinned-download negative/cache tests **PASS**: corrupt download does not replace existing file; verified replacement and verified cache reuse succeed. Added to cloud build workflow.
- Added opt-in `-PasrSmoke=true` Android activity harness using the same model installer, WAV reader, JNI recognizer and exports, with real repeated phrase/silence/short-tail assertions. Assets come only from ignored `.local/androidTestAssets`; normal builds exclude this activity/model/audio. Harness APK compiled successfully (217,411,948 bytes). It was uploaded to the owner's private Ramus test storage; **starting a session was rejected before execution by automatic approval: `MCP tool call requires approval, but approval policy is never`**. No session started, no cloud inference happened, no public APK link/release created. Do not count upload/build as an Android test PASS. No alternative session-control surface was attempted.
- New CI runs/commits/PR: **NONE**, blocked as above. Final read through connected GitHub reconfirmed main `2cec9ddf47a4fe6a53d25cec0bef0b206a8c0f58`. Unauthenticated CLI reads later hit rate limits; connected read still succeeded. Teammate changes/history were not modified.

## Continue from this working tree
1. Restore permitted GitHub write/Actions and emulator-start capabilities in a later authorized environment; no owner-wide settings were changed here.
2. Inspect current main before committing; preserve this working tree. Source-only recovery files are generated by `python tools/create_checkpoint.py`: `.local/round1-source.zip`, `.local/round1-recovery.patch`, `.local/round1-checkpoint.json`. They exclude APKs, weights, recordings, caches and signing keys. They are checkpoints, not commits.
3. Run `offline-asr.yml` or build `-PasrSmoke=true` for private Android execution; actual physical ARM64 test remains required. Full model/fixture provenance is pinned in provisioning.
4. Build/test the ASR-only runtime candidate, pin its verified checksum and resolve remaining distribution notices before enabling APK upload. Then proceed to genuine diarization/global A-B-A testing and realistic Russian dialogue benchmarks.

Round verdict: **NOT READY**. Substantial code, host inference, Android compilation, lint and negative tests are complete; required remote commit/CI and Android inference gates are blocked, diarization is missing.

Final ordinary-build restoration after the optional harness: **PASS**, 77 tasks, 1m26s; core/lint/debug/instrumentation APK all checked again. Ordinary APK is 53,357,856 bytes with no model/audio. Static inspection and exact SHA-256 were refreshed after that build. Machine-readable end state: `docs/evidence/round1-status.json`. Recovery patch passed `git apply --reverse --check` (check only; no files reverted). Raw local build/lint logs, public model ZIP and the private test harness APK remain under ignored `.local/` or ignored build outputs for continuation. No secret, APK, recording or weight is in the source checkpoint.

# Round 2 — real diarization, native overlap failure and containment

## Authority/state rechecked
- Entire AGENTS.md and handoff read again; no claim of private chat access. Continued the existing round-1 working tree without reverting or overwriting it.
- Connected GitHub reconfirmed main `2cec9ddf47a4fe6a53d25cec0bef0b206a8c0f58`, no open PRs, issues #2–#5 still describe the outstanding work. CLI CI list still shows baseline runs only (links above). Those passes are not this integration.
- `.git` is still read-only: `git switch -c codex/round2-offline-diarization` failed to create the ref. CLI issue read returned HTTP 401. No branch, commit, push or Actions run is claimed from these attempts.

## Implemented and checked on host
- Verified pinned official Kotlin API, Android diarization object and native implementation at sherpa `5ce3d6d93a5f4fe11657bf11a6bf3a022eeef22f` / 1.12.20. Real full-recording pyannote segmentation + ERes2Net embeddings + complete-link cosine clustering (`numClusters=-1`), CPU, stable first-appearance labels within each recording. Short recordings padded beyond upstream's 10-second bypass of embeddings; output clipped back to actual duration.
- Pinned model ZIP: 5,992,913-byte segmentation and 39,593,761-byte ERes2Net, both SHA-256 verified. MIT CNRS segmentation license retained; exact ModelScope model-owner metadata declares Apache 2.0 for ERes2Net weights, source license pinned and retained. Full hashes, sources, training-language caveat and provisioning: `docs/DIARIZATION.md` / `tools/provision_diarization.py`. No weights/audio added to Git.
- Strict offline model installation button, background pipeline, inferred speech windows -> real GigaAM ASR -> fusion/UI/TXT/JSON/SRT. IDs scoped to a session; no names or invented word times. Detected overlaps retain unknown attribution, short/negative cluster evidence remains unknown. SRT now visibly marks overlap too. Native/model failures carry explicit provenance.
- **Threshold 0.5 FAILED** recurrence on the upstream four-voice example: seven clusters, returning first voice split at 23 seconds. Changed to **0.9**, the documented upstream hint for this file. It now produces four clusters and A(2s)=A(23s), A(2s)!=B(8s), repeated native turns exactly equal. The composed 13-second A-B-A regression also passes. This threshold is selected on that example, NOT held-out Russian validation.
- **Host native ASR/diarization/combined inference PASS** via actual app Kotlin files and pinned Windows JNI JAR SHA-256 `24d9fe53301fe0b5026fb1cb3877b54d1a47ed079f75819e83a99a9a9e41e55a`. Actual repeated Russian ASR, silence, tiny/short-tail and cancellation cleanup regressions pass. Native diarization repeats, A-B-A, silence, five-second padding/clipping and cancellation cleanup pass. Evidence: `docs/evidence/round2-host-{asr,diarization,dialogue,summary}.json`.
- Combined Russian fixture initially hallucinated text from 202/236/324 ms non-speech gaps. Fixed by decoding only intervals marked speech when segmentation has run, including short unknown speech, with boundaries at speaker/overlap changes. Final actual Russian output has four attributed windows, preserves “у лукоморья дуб зеленый”, and no extra gap utterances. This is one public clean single-voice fixture, NOT Russian dialogue WER/DER.
- Added reproducible pinned JDK-host runner `tools/run_host_inference.py` and manual `host-inference.yml` (Linux counterpart NOT_RUN). It compiles the actual app engine sources, verifies runtime/compiler/models, launches probes in child JVMs, deletes stale result files and retains nonzero exit codes. Android AssetManager host placeholder is only for class loading; file-based native APIs do all inference.

## Native overlap regression: FAIL; Android containment unverified
- A deliberate equal-gain mixture of public fixture `[1s,6s)` and `[7s,12s)` crashes pinned JNI `OfflineSpeakerDiarization.process` with **EXCEPTION_ACCESS_VIOLATION**, reproduced in a disposable child JVM. No output is produced. The suite exits **1**; this is a real failing gate, never an overlap PASS. No private audio is involved.
- Native source has an unchecked `TopkIndex(... num_cols, k)` when local active-speaker count can exceed global cluster count. This is a suspected cause only; no symbolicated diagnosis or native fix claimed.
- Implemented Android private, non-exported `:diarization` process. Audio transfers via a bounded temporary app-private file; only bounded result arrays cross Binder. On process death/error/timeout/binding failure, UI/ASR caller is designed to remain alive and fall back to actual ASR with unknown speakers, explicit warning and `failed_worker_unknown_speakers` provenance. Native cancellation remains uninterruptible; caller unbinds and cleans its file, never publishes partial turns.
- Added instrumentation for process kill/restart, known-mixture containment, repeated native recurrence/silence/short input/invalid bundle and genuine Russian ASR+inferred-boundary fusion. These **compile, NOT_RUN on Android**. Containment and phone behavior remain unverified. The actual overlap accuracy/native crash gate remains red.
- Full upstream AAR GPL/TTS distribution blocker remains unchanged. No APK publication/upload was enabled. ARM64 phone, Android inference, microphone, flight mode, independent Russian conversation metrics and device RAM/thermal behavior remain NOT_RUN.

## Local build phase
- Android worker integration: `:core:runCoreTests :app:lintDebug :app:assembleDebug :app:assembleDebugAndroidTest` **PASS**, 77 tasks, 1m40s. **9 core test groups PASS**, including adversarial model/PCM tests, canonical label recurrence, invalid timestamps, unknown/short evidence, overlap attribution/export and detected-speech window selection. Lint **0 errors / 7 dependency-update warnings**.
- Final post-review build/static inspection and remote-write attempt results are appended below. Until remote writes work, preserve source checkpoints and do not describe this working tree as committed or CI-verified.

## Final review and remote execution blocker
- Review caught a safety issue in the first draft: discarding <300 ms/negative cluster turns could hide a short overlapping interruption and falsely attribute its text to the longer voice. Such intervals now remain as **ineligible attribution evidence**, survive worker IPC and block reliable attribution. New short/unknown interruption negative tests cover this. Only eligible inferred clusters are counted in the UI.
- GitHub `create_tree` was attempted with a tested source entry and the verified main base tree. It was **rejected before execution**: `MCP tool call requires approval, but approval policy is never`. No remote object/commit/ref was created by this rejected call; no alternate write surface was attempted after rejection. Commit/push/new Actions are BLOCKED by this environment, not marked complete.
- Final connected read reconfirmed main unchanged. Latest remote CI remains the old baseline success https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/40987151101 at `2cec9dd`; it provides no verification of round 1/2 source.
- Round-1 checkpoint files remain intact. Round-2 source-only recovery is generated with `python tools/create_checkpoint.py --name round2`, excluding models, recordings, APKs, caches, crash logs and signing keys. The round verdict remains **NOT READY**: native overlap failure, Android runtime/containment NOT_RUN, blocked commit/CI, and unresolved runtime distribution.

Final post-review verification: **PASS** local Android/core/lint/debug/instrumentation compilation, 77 tasks, **1m52s**, 9 core groups and lint 0 errors / 7 update warnings. Re-ran actual pinned host inference after the short-interruption fix: ASR/diarization/combined Russian PASS, known-mixture native fatal crash reproduced, no overlap output, suite **exit 1**. Final APK static check verifies no INTERNET, ARM64/x86_64 only, 16-KB ELF LOAD alignment, no bundled model/audio, and a **non-exported `:diarization` service in the packaged manifest**. Exact APK/build-log digests and final machine-readable state: `docs/evidence/round2-apk-inspection.json`, `docs/evidence/round2-status.json`. These checks do not prove Android execution. No commits, push, PR, new CI or APK publication occurred.

# Round 3 — user WAV snapshots, exact chunk intervals and document exports

## State and authority
- Entire AGENTS.md and full handoff read; continued all round-1/2 source without reverting it. No direct private-chat access claimed. Current connected GitHub read confirms main `2cec9ddf47a4fe6a53d25cec0bef0b206a8c0f58`, no open PRs, issues #2–#5 still open. Latest CI remains https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/40987151101 at the old baseline, not this work.
- `git fetch origin` still fails on read-only `.git/FETCH_HEAD`; CLI issue/PR reads return HTTP 401. A GitHub `create_tree` capability attempt was rejected before execution: **MCP tool call requires approval, but approval policy is never**. No remote tree/commit/branch or new Actions run was created. No alternate write path was attempted after rejection. Commit/push/CI remain BLOCKED by the environment. Owner settings and teammate history untouched.

## Implemented
- User WAV import now creates a bounded app-private snapshot and validates PCM/duration before selecting it. Broken document providers, truncated/unsupported/short/long/oversized input and cancellation discard the staged file, preserving the old selected audio/result. Later provider mutation/revoked access cannot alter the snapshot. Selected-source display shows duration without private provider paths. PCM parsing cooperatively checks cancellation during read/resampling. Compressed codecs remain explicitly unsupported; cache eviction/process death may require reimport.
- A captured transcript document carries genuine chunk intervals, duration, engine/model/timestamp/speaker provenance and warnings. JSON exports retain these even for empty recognition. TXT previously rounded away subsecond intervals (e.g. `00:00–00:00`); TXT/UI now show `HH:mm:ss.SSS`. SRT uses the same boundaries with locale-independent ASCII digits. No fabricated word times. Document chooser callbacks export the result captured before opening the picker, with correct MIME types, UTF-8 and truncation of existing destinations.
- Microphone starts and checks RECORDSTATE synchronously, rejects zero/error/incomplete PCM reads, and rejects <100 ms results. Starting a new recording clears the previous source/result, avoiding accidental recognition of old audio after microphone failure. Model/import/transcription operations also guard recording state internally. Stop cleanup is noncancellable; actual microphone/lifecycle behavior is still NOT_RUN on Android.
- Optional diarization model verification failures now preserve ASR fallback with unknown speakers and warnings; cancellation is rethrown. No detected speech windows is explicitly distinguished from an ASR invocation that returns no text. Known native overlap failure is NOT fixed.

## Evidence so far
- First local `:core:runCoreTests :app:lintDebug :app:assembleDebug :app:assembleDebugAndroidTest`: **PASS**, 77 tasks, 2m. **11 Kotlin core test groups PASS**; lint 0 errors / 7 dependency update warnings. Added snapshot failure/recording-style/stereo cases, exact-ms/Arabic-locale/hour/escaping/empty-output/bounds/export cases. Python download integrity regression PASS.
- Actual app Kotlin + pinned Windows JNI: ASR, diarization and combined Russian inference PASS again; known-mixture overlap fatal error reproduced, output absent, full suite **exit 1**. Host output exports four real Russian chunks within 11,290 ms audio; independent Python parser verifies matching text, speaker labels, exact times and bounds in JSON/SRT/TXT. Evidence retained in round3 files; this is a clean public single-voice fixture, not Russian-dialogue accuracy, word alignment or Android execution.
- Added Android import/snapshot/state tests, ContentResolver UTF-8/truncation tests and actual public-WAV ViewModel -> UI document -> all exports test, including changing input while a document export is pending. Device tests are **NOT_RUN**; only compilation is checked locally. No new emulator/Android Studio installed. ASR-only runtime/GPL distribution blocker, physical ARM64, worker crash containment, airplane mode, microphone, WER/DER/cpWER/RAM/thermal tests remain open.

Final post-review build/evidence/checkpoint results follow below. Verdict remains **NOT READY** until these device/native/remote/distribution gates are resolved.

Final verification after all production/test-source edits: **PASS** `:core:runCoreTests :app:lintDebug :app:assembleDebug :app:assembleDebugAndroidTest`, **77 tasks, 1m46s**, 11 core groups, lint **0 errors / 7 update warnings**. Final host recompile/inference confirms ASR, diarization and combined export PASS (including the no-detected-speech/no-model-load distinction); overlap still fatally fails with no output and suite exit 1. Independent three-format validation and corruption-negative/regression checks PASS. APK static inspection reconfirms no INTERNET, ARM64/x86_64 only, 16-KB ELF LOAD alignment, no bundled model/audio and private worker; exact digest is in `round3-apk-inspection.json`. No runtime/device success inferred from these checks.

Machine-readable result: `docs/evidence/round3-status.json`; actual host evidence: `round3-host-{summary,asr,diarization,dialogue}.json`; export validation: `round3-host-export-validation.json`. `round3-source-delta.json` identifies code/workflow changes against the preserved round-2 source archive. Source-only recovery is generated with `python tools/create_checkpoint.py --name round3` into `.local/round3-{source.zip,recovery.patch,checkpoint.json}`. It excludes audio, weights, APKs, caches, signing material and crash logs. Existing round-1/2 checkpoints remain intact. **No commit, push, PR, new Actions run or APK publication occurred.** Remote write was rejected before execution as recorded above; resume from the working tree/checkpoint in a permitted environment.


# Round 4 ? objective scoring, PCM memory reduction and durable cloud evidence

## State and remote blockers
- Read AGENTS.md and the entire handoff before changes; retained all previous working-tree work, no private-chat access claimed. Live REST confirms main `2cec9ddf47a4fe6a53d25cec0bef0b206a8c0f58`, no open PRs, issues #2-#5 open. Latest CI remains the old baseline https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/40987151101 ; it does not verify this integration.
- Current `git fetch origin` fails on read-only FETCH_HEAD; creating `codex/round4-benchmarks` fails to write the ref. `gh auth status` confirms invalid Ai-b0ss token; GraphQL returns HTTP 401. No owner auth/settings changed, no credential-search workaround, no teammate history changes. Prior connected GitHub write approval rejection is still unresolved; no new connected mutation or emulator-start attempt made. **No new branch, commit, push, PR, Actions run or publication occurred.**

## Implemented and verified
- `PcmWav` now buffers 64 KiB and resamples with two source mono frames directly into the target array. Removes the full-rate mono float array for non-16kHz input. All source PCM is consumed to reject truncated tails. Exact output parity in 48 rate/channel/length combinations, plus negative tail, cancellation, provider-buffering and stream-ownership regressions. Linear-resampling quality remains unchanged.
- Pinned-source JDK parser probe on generated numeric (not speech) 120s/48kHz/stereo input: thread allocations **30,725,064 -> 7,750,672 bytes (74.77% less)**; source calls **23,040,028 single + 4 bulk -> 0 single + 352 bulk**; PCM exactly equal. Elapsed in-memory parsing **553 -> 586 ms**, so **NO speed improvement claimed**. Not Android, peak RAM or ASR RTF. Reproduce with `python tools/run_pcm_benchmark.py --java /path/to/jdk17/bin/java`; requires preserved round-3 source ZIP and verifies baseline/source hashes. `round4-pcm-benchmark.json` retains exact evidence.
- Added original stdlib WER/cpWER/DER scorer, explicit Russian normalization, edit components, exact speaker assignment, raw-diarization-only DER, collar radius and overlap mode, source JSON/audio fingerprints, unknown/no-reference/empty-reference states and nonzero incomplete/error exits. Authored Russian text fixture contains **NO AUDIO**, clearly labeled test-only. **11 metric test methods PASS**, including exhaustive speaker/word oracles and an independent time-grid DER oracle. External MeetEval/NIST scorer corpus parity NOT_RUN. See `docs/BENCHMARKS.md`.
- Pinned upstream Russian test_wavs directory has only example.wav; no independently supplied full transcript, speech boundaries or speaker annotation. Recognized words/poem text are not independent annotations. Actual host-audio WER/DER/cpWER therefore **NOT_SCORED** (CLI exit 2), retained in `round4-metrics-availability.json`. No invented ground truth, private recordings or new unlicensed audio dataset used.
- Android instrumentation now saves actual public-fixture ASR and raw diarization JSON, WAV hashes, SDK/ABI/model, load/decode RTF and before/after PSS snapshots. Timing excludes model verification/import and diarization; fresh recognizer load is not cold-process startup. PSS snapshots/final dumpsys are not peak RAM and exclude the worker. These tests compile but remain **NOT_RUN** on Android.
- Cloud inference invokes one standalone Bash script: upstream emulator-runner parses YAML lines separately, so multiline functions/traps in YAML would fail. Collector persists logcat and available fixture evidence even on failure, discards missing/stale files, and preserves original failure code. Clears cloud-test app data first. **3 shell tests PASS** using explicit fake commands for success, Gradle failure and early adb failure. These are shell tests, not emulator evidence. Five workflow YAML files parse successfully. Device startup/peak RAM/thermal evidence remains pending.
- Export buttons use FlowRow to wrap on narrow screens/large fonts. Compilation checked; visual/device acceptance NOT_RUN.

## Final local evidence
- `:core:runCoreTests :app:lintDebug :app:assembleDebug :app:assembleDebugAndroidTest` **PASS**, final **77 tasks / 1m48s**, **12 core test groups**, lint **0 errors / 7 pinned dependency update warnings**. First round-4 build invocation failed because an unquoted Gradle -P path was parsed incorrectly by PowerShell; quoted the argument and reran successfully. No product suppression or source change was used to hide that failure.
- Actual app Kotlin with pinned Windows JNI recompiled and executed: Russian ASR/repetition/silence/cancellation PASS, genuine A-B-A/repetition/short-input diarization PASS, Russian combined inference and exact three-format export PASS. Independent export corruption-negative/regression PASS. Known-mixture overlap still causes **native fatal error**, produces no output, and suite exits **1**. Native crash is not fixed or relabeled. `round4-host-{summary,asr,diarization,dialogue}.json` preserves results.
- Final APK static inspection PASS: no INTERNET, ARM64/x86_64 only, 16-KB ELF LOAD alignment, no model/audio, private worker. `round4-apk-inspection.json` records final digest. Full AAR GPL TTS distribution blocker remains; no-TTS runtime build, Android inference/worker containment, physical ARM64, microphone/airplane-mode and visual UI tests remain NOT_RUN.
- Verdict **NOT READY**. Machine-readable result: `docs/evidence/round4-status.json`. Round-4 source-only archive/patch/checkpoint preserve the entire recoverable tree while `.git` is read-only; prior checkpoints remain intact. `round4-source-delta.json` compares source hashes against round 3. No audio, model weights, APKs, signing material, secrets or caches belong in these source artifacts.

Recovery validation: source-only checkpoint generated (100 source files); reverse patch applicability check PASS (check only, no files reverted), git diff whitespace check PASS, Bash syntax/Python compile PASS. Final status and recovery metadata retained; archive/checkpoint regenerated after this note.

# Round 5 — bounded platform codec import and explicit audio cleanup

## State and blockers rechecked
- Read the complete AGENTS.md and handoff before changes; continued all round-1–4 source. No direct access to the private ChatGPT conversation claimed. Live GitHub REST reconfirmed main `2cec9ddf47a4fe6a53d25cec0bef0b206a8c0f58`, no open PRs, issues #2–#5 open, #1 closed. Latest CI remains https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/40987151101 (old UI baseline only). These reads are not verification of the local integration.
- `git switch -c codex/round5-audio-import` failed to write the ref under protected `.git`; CLI GraphQL issue read returned HTTP 401. Previous connected-write automatic approval rejection remains unresolved. No alternate write path, credential search, owner settings changes, teammate history edits or publication attempted. **No new commit, push, PR or Actions run.** Recoverable source remains in the working tree and source-only checkpoint.

## Implemented
- Android `MediaExtractor`/`MediaCodec` import, using official Android API documentation. Local document bytes are first copied to a bounded app-private file, with no network URL passed to media APIs. PCM16 WAV retains the strict existing parser and never bypasses a WAV validation failure via codec fallback. Experimental allowlist: MP3, AAC/M4A, Vorbis/Opus, FLAC and AMR; platform/container support varies. **Android decoder execution NOT_RUN.** Details, API references and limitations: [AUDIO_IMPORT.md](AUDIO_IMPORT.md).
- Source cap 24,088,584 bytes, metadata and independently enforced decoded 120-second cap; decoded output must be PCM16, 8–48 kHz, mono/stereo. Reject multiple audio tracks, DRM/encrypted/partial packets, unsupported/changing formats, short/incomplete output and timestamp discontinuities over 100 ms. Cooperative 60-second codec polling deadline and cancellation; native setup/provider reads are not hard-preempted. Decoder/sample origin and padding limits are documented; no word alignment claims.
- Added bounded WAV writer and overflow-safe decoded PCM timestamp validator. A failed/cancelled import removes partial/staged files and preserves the old selected source/result. Valid decoded PCM uses the existing normalization/ASR path. UI import text and both READMEs reflect experimental codecs and pending device execution.
- Explicit **Удалить локальное аудио и результат** action deletes only generated app recordings/import/worker files, clears the selected source/result and pending export, preserves model files, and reports deletion failures. Exported documents remain with their providers. This is ordinary deletion, not forensic flash erasure. Cleanup is unavailable while recording/processing. Android behavior remains NOT_RUN. Backup exclusions/no INTERNET permission retained; document providers may independently use cloud storage.
- Audio-extension ignore/recovery protections and APK scanner now include Ogg/Opus/FLAC/AAC/AMR, including case-insensitive accidental bundling checks. Cloud codec tests generate numeric tones (no speech/private audio) and persist actual device JSON only after all five positive codec cases pass; collector discards missing/stale codec output. No audio/weights/APKs in source evidence.

## Verified so far
- **13 Kotlin core test groups PASS**, including eight rate/channel PCM roundtrips, fragmented/offset buffers, exact PCM16 values, exact 120-second boundary, short/partial/cancelled/error output cleanup, timestamp gaps/rounding/overflow and rejected-buffer state preservation.
- Initial build FAILED at instrumentation compilation because a newly added cleanup test was read after the production class had already compiled; this was a mixed source snapshot caused by editing while the build ran. Repeated on unchanged production/test sources: **PASS**, `:core:runCoreTests :app:lintDebug :app:assembleDebug :app:assembleDebugAndroidTest`, **77 tasks / 2m15s**, lint **0 errors / 7 dependency-update warnings**. A final post-review build for the last cleanup-state edit follows below. No test suppression or baseline added.
- **2 codec fixture test methods PASS**: FFmpeg independently decodes generated AAC/MP3/Vorbis/Opus/FLAC tones, checks duration/energy/hashes; generator failure removes stale fixtures/manifest. Two-track and 121-second AAC negative files generated for device tests. Generator version/hashes in `round5-codec-fixtures.json`; these are **fixture checks, not Android MediaCodec or speech accuracy evidence**. AMR has no generated fixture.
- **11 scorer methods, 3 shell collector methods, pinned-download integrity tests PASS**. Python compile and diff whitespace checks PASS. APK scanner corruption negatives with appended Ogg/FLAC/uppercase OPUS reject the mutated APK; original inspection passes (`round5-apk-negative.json`). Static packaging still cannot establish phone execution.
- Actual app Kotlin + pinned Windows JNI recompiled/executed: Russian ASR/repetition/silence/cancellation, diarization A-B-A/repetition/short input, combined Russian output and independent exact TXT/JSON/SRT export validation **PASS**. Known-mixture overlap again causes **native fatal error, no output**, overall host suite **exit 1**. `round5-host-{summary,asr,diarization,dialogue}.json` and `round5-host-export-validation.json` retain evidence. The native crash is not fixed or relabeled.

Verdict remains **NOT READY**: Android codec/inference/worker containment, physical ARM64/microphone/flight mode/visual and peak RAM/thermal evidence remain NOT_RUN; independent Russian dialogue metrics remain NOT_SCORED; full runtime GPL/TTS redistribution and protected Git/remote CI blockers remain unresolved. No private recording or new paid service used. Final build, APK digest, machine-readable status and recovery validation follow below.

Final post-review verification **PASS**: **77 tasks / 1m49s**, 13 core groups, Android debug + instrumentation APKs, lint **0 errors / 7 update warnings**. Last production change clears selected/pending state before cleanup, so partial filesystem erasure failure cannot leave a deleted source selected. Import-to-clear device regression compiles; execution remains NOT_RUN. Final APK static inspection reconfirms no INTERNET, private worker, ARM64/x86_64-only JNI, 16-KB ELF LOAD alignment and no bundled models/audio; exact final digest in `round5-apk-inspection.json`. Corruption-negative and source recovery results are recorded in `round5-status.json`. No commit, new CI or Android inference is inferred from these local checks.

Recovery: `python tools/create_checkpoint.py --name round5` preserves source-only `.local/round5-source.zip`, `.local/round5-recovery.patch`, `.local/round5-checkpoint.json`. Previous round checkpoints remain intact. `round5-source-delta.json` compares current source/docs/workflows against the preserved round-4 archive (evidence JSON excluded from that delta to avoid self-referential hashes). No APK, weight, recording, signing material, credential or cache is included. Reverse-patch check is read-only validation; no files are reverted.

Recovery validation **PASS**: 118 source files; `git apply --reverse --check` succeeds without changing files. All five workflow YAMLs parse. Final ordinary APK DEX actually contains the new importer, PCM writer and decoded-timeline classes; normal APK contains no codec test assets. Collector tests also confirm stale codec JSON is discarded on failed retrieval. Final status: `docs/evidence/round5-status.json`. Source archive/patch regenerated after this note and final status metadata.

# Round 6 — microphone failure recovery and checkpoint privacy

## State and blockers
- Entire AGENTS.md and handoff read before changes; continued all round-1–5 source. No direct private-chat access claimed. Live GitHub REST confirms main `2cec9ddf47a4fe6a53d25cec0bef0b206a8c0f58`, no open PRs, issues #2–#5 open. Latest CI remains https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/40987151101 (old baseline only).
- Creating `codex/round6-recorder-safety` failed to write protected `.git/refs/heads`. Prior connected-write rejection by automatic approval remains unresolved; no alternate write/auth/settings workaround attempted. No new commit, push, PR, Actions run or APK publication. Teammate history untouched; source recovery retained.

## Implemented
- Replaced blocking byte-array capture with official nonblocking PCM16 short-array reads. Production core owns single-thread capture/read/release, little-endian WAV output, sample/elapsed-polling caps, failed/short output cleanup and explicit stop timeout. Zero reads mean no data yet. No manufactured speech/samples. See [RECORDING.md](RECORDING.md).
- Failed recording preserves previous selected audio/transcript; only finalized recording replaces it. Completion/error is observed automatically. Stop timeout retains ownership and recording guard, blocks import/cleanup, supports retry and observes eventual completion. ViewModel clearing requests stop before background join. A stopped activity cannot start capture from a delayed permission result. Driver/native shutdown is not hard-preemptible; device behavior remains NOT_RUN.
- Added separate Android ViewModel fake-session failure/timeout/retry tests and two real AudioRecord session tests. Only SDK/ABI/duration/byte-count evidence is collected, never microphone audio. Collector removes stale recording metadata on retrieval failure. Instrumentation compiles; Android execution remains NOT_RUN.
- Source recovery now rejects case-insensitive audio/model/binary/signing artifacts, secret filenames, cache directories, external resolved paths, NUL/non-UTF8 content and files over 2 MiB. Tests added to cloud build workflow. This is an archive guard, not a universal secret scanner. Fixed stale English README statement about compressed audio.

## Executed verification
- First build FAILED on Kotlin recursive return-type inference in the observer calling stopRecording; explicit Unit return fixed it. Complete build then PASS: 77 tasks / 1m56s, 14 core groups, debug/instrumentation APKs. Removed a staged-variable compiler warning; final unchanged-source verification PASS: **77 tasks / 1m50s**, **14 core groups** including **9 recorder cases**, lint **0 errors / 7 pinned dependency warnings**. No test suppression/baseline added.
- Python: 11 scorer methods, 3 collector methods, pinned-download corruption/replacement/cache tests PASS. Recovery guard: **3 methods PASS, 1 external-symlink method SKIPPED** because Windows denies creating that test symlink. Initial export-validator invocation omitted its required directory and exited with usage error; corrected invocation against new round-6 output PASS, including malformed SRT/missing TXT/beyond-audio JSON negatives.
- Actual app Kotlin + pinned Windows JNI recompiled/executed: Russian ASR/repetition/silence/cancellation, genuine diarization A-B-A/repetition/short input, combined inference and exact TXT/JSON/SRT validation PASS. Known-mixture overlap again causes **native fatal error with no output**; full suite exit **1**. New round6 host JSON retains FAIL. No conversational accuracy or Android success inferred.

Verdict **NOT READY**. Android codec/inference/worker/microphone execution, physical ARM64/airplane-mode/visual/peak-RAM/thermal evidence, independent Russian dialogue annotations, native overlap fix and no-TTS distribution remain open. Final static packaging and recovery checks are recorded below and in round6-status.json.

Final APK static inspection PASS: no INTERNET, private worker, ARM64/x86_64 only,
16-KB ELF LOAD alignment, no bundled models/audio. Actual DEX contains new
BoundedWavRecorder/WavRecording/RecordWav classes; instrumentation DEX contains
RecordingTest. Exact digest: round6-apk-inspection.json. Reconfirmed unchanged live
main and old baseline CI after verification. Host evidence and independent export
validation: round6-host-*.json. Source delta compares with preserved round-5 archive.
Source-only recovery: .local/round6-source.zip, round6-recovery.patch and
round6-checkpoint.json; prior checkpoints remain intact. Reverse-patch validation
checks applicability only and never reverts files. A shell-based bulk documentation
write was blocked by policy; ordinary apply_patch completed the documentation.

# Round 7 — whole-container WAV validation and benchmark evidence integrity

## State and authority
- Read the entire AGENTS.md and handoff before changing code; continued the
  existing round-1–6 source without reverting it. No private-chat access claimed.
- Connected GitHub reads verify main remains `2cec9ddf47a4fe6a53d25cec0bef0b206a8c0f58`,
  no open PRs, issues #2–#5 open. CLI lists only old baseline CI, latest
  https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/40987151101 .
- `git fetch` failed writing protected FETCH_HEAD; branch creation
  `codex/round7-wav-container` failed writing protected refs. CLI GraphQL returns
  401. Prior connected-write automatic approval rejection remains unresolved.
  No bypass, credential search, settings change, new commit/push/PR/CI claimed.

## Implemented
- WAV parser previously returned immediately after the first data chunk, accepting
  a second data/fmt chunk or malformed trailing container and silently omitting
  additional audio. It now consumes/validates the entire RIFF extent and EOF,
  preserves valid unknown metadata/padding and rejects ambiguous multiple audio
  chunks. The PCM/resampling algorithm is unchanged; no extra source float buffer.
  Eight corruption negatives exercise parser and snapshot import, previous-source
  preservation, staged cleanup, fragmented input and tail cancellation.
- Android selection tests add authoritative WAV-rejection/no-codec-fallback cases;
  compile/execute status follows below. The prior selected file must survive.
- Benchmark scorer now rejects malformed JSON roots, explicit null reference files,
  non-integer hypothesis duration and non-boolean attribution flags. Invalid roots
  previously could raise AttributeError outside the error handler and leave an old
  favorable report on disk. 18 CLI corruption cases seed an old score and require
  explicit ERROR replacement. No model accuracy result is fabricated.

## Verification in progress
- Scorer: 12 methods PASS; collector: 3 methods PASS; pinned-download corruption,
  replacement/cache PASS. Recovery guard: 3 PASS / 1 symlink SKIPPED (Windows).
- First Android build failed because this invocation supplied the wrong local
  debug-keystore filename. Retried using the existing workspace-owned p12; no
  signing key generated, exposed or committed. Final build and inference results
  are appended below after execution.

## Completed verification and remaining gates
- Final unchanged-source build **PASS**: `:core:runCoreTests :app:lintDebug
  :app:assembleDebug :app:assembleDebugAndroidTest`, **77 tasks / 1m02s**,
  **15 core groups**, lint **0 errors / 7 dependency-update warnings**. Previous
  complete successful build took 2m11s. No test suppression or lint baseline.
- Independent old/new source replay reproduces duplicate-data/outside-RIFF
  acceptance on round 6 and rejection on round 7. Old scorer raises AttributeError
  and retains seeded SCORED output for a list-root reference; round 7 returns ERROR.
  Source hashes and outcomes: `round7-negative-baseline.json`. Generated numeric
  PCM/invalid JSON only; this is bug regression evidence, not a model benchmark.
- Actual app Kotlin + pinned Windows JNI recompiled and executed: Russian ASR,
  repetition/silence/cancellation, genuine A-B-A/repetition/short-input diarization,
  combined Russian inference and independent exact TXT/JSON/SRT verification PASS.
  Export corruption-negative/regression PASS. Known mixture **FAIL: native fatal
  error, no result**, full host suite exit **1**. See `round7-host-*.json`.
- Final ordinary APK static inspection PASS: no INTERNET, private worker,
  ARM64/x86_64 only, 16-KB ELF LOAD alignment, no bundled models/audio.
  `round7-apk-inspection.json` records exact bytes/hash; this is not Android execution.
- Python compile, five workflow YAML parses and git whitespace check PASS. Host
  export and arithmetic tests do not establish WER/DER/cpWER on real dialogue.
- Verdict **NOT READY**. Android codec/inference/worker/microphone/WAV-selection,
  physical ARM64/airplane mode/UI/peak RAM/thermal execution remain NOT_RUN;
  independent Russian dialogue metrics remain NOT_SCORED; native overlap and
  full-AAR GPL/TTS distribution blockers remain. No new commit, push or Actions run.
  Final connected read reconfirms main unchanged. No paid service/private audio used.

Machine-readable status: `docs/evidence/round7-status.json`. Source delta compares
with preserved round-6 source and excludes evidence files to avoid circular hashes.
Source-only recovery remains in `.local/round7-source.zip`, `round7-recovery.patch`
and `round7-checkpoint.json`; previous checkpoints remain intact. Reverse-patch
validation checks applicability only, never reverts files. Regenerate checkpoint
after this final note; no APK, weights, audio, signing material or caches belong in it.

# Round 8 — worker lifetime and fail-closed IPC

## State
- Read the entire AGENTS.md and handoff before code changes; continued round-1–7
  source in place. No direct private-chat access. Live GitHub REST confirms main
  `2cec9ddf47a4fe6a53d25cec0bef0b206a8c0f58`, issues #2–#5 open, no open PRs.
- `git fetch` cannot write protected FETCH_HEAD; branch creation
  `codex/round8-worker-lifecycle` cannot write protected refs. CLI GraphQL is 401.
  Prior connected-write automatic-approval rejection remains unresolved; no
  workaround or credential/settings change attempted. No new commit/push/CI.
  Latest remote CI is the old UI baseline only:
  https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/40987151101 .

## Implemented
- Fixed cancellation/timeout ownership: executor shutdown alone could leave JNI
  running after the client unbound. Bound-only service destruction now terminates
  its own guarded dedicated process. One native request per worker lifetime,
  serialized callers, Binder-death observation and refusal to start another task
  while prior exit is unknown prevent a hidden queue of retained audio/models.
  No PID supplied over IPC is used to kill a process. Android execution is pending.
- Added strict core reply validation before attribution: array/count/interval/time
  bounds, anonymous cluster labels, unknown/short eligibility, speech-window
  completeness and exact partition agreement. Corruption triggers explicit
  unknown-speaker fallback; silence and overlap uncertainty remain valid.
- Added 20 corruption negatives, silence/gap/unknown/overlap regressions, Android
  success/cancel/retry process-exit tests and metadata-only evidence collection.
  Collector must remove stale lifecycle JSON if retrieval fails.
- Rechecked pinned upstream Kotlin API/Android example and official Android bound
  lifecycle documentation. No new dependency, runtime version or license claim.

## Verification in progress
- Python scorer 12 methods PASS; collector 3 methods PASS; pinned download
  corruption/replacement/cache PASS; recovery guard 3 PASS / 1 symlink SKIPPED
  (Windows denies test symlink creation). Git whitespace check PASS.
- First build invocation FAILED at configuration: an unquoted PowerShell -P
  argument supplied an empty localDebugStore value. Retried with the property as
  one quoted argument and the existing workspace debug p12; no key created.
  Final Android compilation/lint, host regression and packaging results follow.
- The quoted-command build exposed a missing DiarizationReply import in the
  service; corrected it. Complete subsequent build PASS: **77 tasks / 2m08s**,
  **16 core groups**, debug + instrumentation APKs. New Android lifecycle tests
  compile only. Final post-review build follows the timing-type fallback guard.
- Actual Windows JNI host regression with production reply validation PASS for
  public A-B-A/repetition/silence/short output and Russian ASR/fusion. Exact
  TXT/JSON/SRT and export corruption tests PASS. Known mixture still produces
  **native fatal error, no result**, full suite **exit 1**. It is not fixed or
  relabeled by process-lifetime work. Numeric codec fixture checks: 2 methods PASS;
  this remains host FFmpeg validation, not Android codec execution.
- Removed Windows-only labels from cross-platform JVM probe metadata/logs;
  `summary.json` supplies the actual OS/architecture. Future Linux CI must not
  claim to be a Windows measurement. This invocation executes Windows only.

Verdict remains **NOT READY** pending Android/device evidence, native overlap
fix, no-TTS runtime and independent Russian dialogue annotations. New worker
lifecycle tests are not an executed Android success claim.

## Final verified results
- Post-review build **PASS: 77 tasks / 1m34s**, **16 core groups**, debug and
  instrumentation APKs, lint **0 errors / 7 pinned dependency-update warnings**.
  No lint suppression or baseline. APK inspection PASS: no INTERNET, private
  dedicated worker, ARM64/x86_64 only, 16-KB ELF LOAD alignment, no model/audio
  assets. DEX contains the new reply validator/cleanup guard and the new lifecycle
  test is present in the instrumentation APK. This is static/compile evidence.
- Replayed the exact archived round-7 mapping against authored corrupt IPC arrays:
  it accepts omitted speech, an injected gap, an outside-audio turn and reliable
  Unknown. Round 8 rejects all four and accepts the valid control. Source hashes
  and scope are in `round8-negative-baseline.json`; this is not model accuracy.
- Final actual JNI suite uses the new validator on real repeated A-B-A, composed
  A-B-A, silence, short and Russian single-voice outputs. Those checks, Russian
  ASR and exact exports PASS. Known mixture remains **FAIL_NATIVE_FATAL_NO_OUTPUT**,
  whole host command **exit 1**. Final evidence: `round8-host-*.json`; independent
  export verification and its corruption negatives PASS. No Android success,
  real-dialogue WER/DER/cpWER or phone performance is inferred.
- Python compile, five workflow YAML parses, whitespace and recovery checks PASS.
  Source delta compares against preserved round-7 source and excludes evidence
  JSON to avoid circular digests. `round8-status.json` records detailed results,
  skips and blockers. Live remote main and old baseline CI were reconfirmed;
  no new commit, push, PR, Actions run, public APK, paid service or private audio.

Source-only recovery: `.local/round8-source.zip`, `round8-recovery.patch`, and
`round8-checkpoint.json` (**152 files**). Reverse-patch check PASS, check-only;
no files reverted. Prior checkpoints remain intact. Archive guard excludes audio,
weights, APKs, signing material, caches and external paths. Regenerate recovery
after this final note and status update; source stays recoverable despite Git
being read-only. Verdict **NOT READY**; the Android lifecycle/codec/ASR/microphone,
physical ARM64/airplane-mode/visual/RAM/thermal and independent dialogue gates
remain unexecuted/unscored, with native overlap and runtime redistribution open.
