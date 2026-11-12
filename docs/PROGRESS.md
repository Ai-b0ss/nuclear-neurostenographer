## 2026-11-12 — move C2 + TitaNet QA off the overheating phone

Primary QA now has a portable PC host runner and a dedicated Linux Actions
workflow with separate actual-inference and x86_64 Android emulator jobs.
The physical HONOR was not accessed or loaded in this work.

- Fresh Windows PC inference: 15 fixed two-speaker files / 900 s of speech
  in 124.516 s including compilation/scoring; DER 3.20017% at 250 ms.
  Actual C2 -> TitaNet replay admitted 12/30 profiles, zero admitted returning
  probes; no release quality claim. This repeats the regression corpus.
- Android isolated QA APK + instrumentation APK build PASS (71 tasks).
  No product logic/default changed; no new production release APK.
- Six emulator-isolation / false-success regressions PASS. The new runner
  cannot select a physical target; it verifies ADB serial, qemu and x86_64.
  On-device simulated-temperature bypass requires explicit emulator mode
  AND ranchu/goldfish x86_64. Physical thermal policy remains unchanged.
- New workflow passes actionlint 1.7.12. CI uses standard public Linux
  runners, pins Python dependencies and all model checksums; no paid service.
- Emulator suite covers repeat/different source/missing model, plus 20m40s.
  Functional positive rec_0058 was selected for known admitted profiles;
  this is deliberately NOT counted as independent accuracy validation.
- Only sanitized JSON metadata is uploaded; audio, models, embeddings and
  raw transcript previews/logs remain excluded. Current outputs replace
  task-owned files in .local/speakerbook-offdevice-current.
- GitHub integration can write the QA branch despite expired local Git
  credentials; no owner login or foreground browser is required.
- Final accelerated x86_64 Android CI: all FOUR cases PASS. Repeat linked
  both expected voices across the boundary; different-source control had no
  shared IDs; absent optional model retained only block-local IDs.
- Continuous 20m40s input completed: recognition 218.948 s (RTF 0.17657),
  252 segments, 21 uncertain speaker segments, 5 profiled blocks and
  [61,61,61,61,8] segments by five-minute interval. End/timeline checks PASS.
  Full long-test wrapper 232.066 s. This is NOT HONOR performance evidence.
- KVM version 12 explicitly checked usable in all four cases; no software
  VM-acceleration fallback. Boot ~33 s. The bootstrap udev rule contained
  an incorrect GROUP equality condition; runner-user ownership + strict
  acceleration checks replaced it. Earlier slow runs were canceled.
- The first accelerated tests exposed an unreadable host-staged TitaNet
  file. Fixed by copying a pinned instrumentation asset under the target
  app UID. Confirmed asset hash in test APK and absence from main APK.
- Heavy QA now runs only on workflow_dispatch or a deliberate change to
  .github/run-speakerbook-offdevice.txt, preventing repeated heavy runs on
  ordinary edits. CI matrix case outputs are independent; normal CI PASS.
- Linux current host: 107.15 s for 900 s corpus, same DER and admitted
  profile counts as Windows. Independent identity readiness still NO-GO.
- CI: https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/43174151953
  tested runtime code cac43214; results and source blob pins are saved in
  docs/evidence/speakerbook-offdevice-20261112.json.
  Instructions: docs/SPEAKERBOOK_OFFDEVICE_QA.md.

## 2026-11-12 — final acceptance verification: Veche and corrected independent scope

**Decision remains NO-GO for default globalSpeakerBook.** The requested
verification stage is closed with explicit outstanding release blockers;
no new model tuning, APK, phone endurance run or product change.

- Found the completed Veche hard 2/3/5-speaker host inference and re-scored
  all three WAVs (848.247 s): DER 6.78699% at 0 ms, 2.77843% at 250 ms,
  overlap included. Exact exhaustive and Hungarian scorers agree to the
  millisecond on product/raw at both collars (12 comparisons).
- Verified 37 compiled-input source fingerprints against current files,
  all four model artifacts, ORT 1.17.1 jar and source WAV fingerprints.
  These are provenance checks of saved inference, not a fresh model run.
- Veche uses human-read scripted assembled meetings with background noise;
  it cannot establish spontaneous natural Russian conversation DER.
  Only local diarization was evaluated, never biometric identity linkage.
- Corrected scope: four of 20 Russian bookmix recordings had prior project
  evaluation. Strict 16-file exclusion yields DER 4.9013% / 2.9538%.
- Keep oracle 14/60 admitted TitaNet profiles separate from actual C2
  13/61 profiles; the latter has only one accepted returning probe.
  Neither supports a general global identity accuracy claim.
- Reconciled 140.64 s CPU-78C THERMAL_ABORT and verified isolated QA cleanup.
  No repeat thermal stress; endurance is unpassed.
- WER/cpWER for these exact latest-build recordings remains NOT SCORED.
- Reproduction: system Python 3.13 (existing NumPy/SciPy) with
  tools/verify_speakerbook_acceptance.py --qa-dir .local/qa-three-checks-current
  --output .local/qa-three-checks-current/final-recheck.json.
  The data venv lacks SciPy; no packages were installed.
- Sanitized final evidence and corrected scope:
  docs/evidence/speakerbook-final-acceptance-20261112.json.
- Confirmed remote main bb0ab7a (#54) and passing post-merge Actions run
  https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/43115747309.

## 2026-11-12 — three speakerbook release checks (20m, false joins, Russian)

**Decision: NO-GO for enabling globalSpeakerBook by default.**
See docs/evidence/speakerbook-three-release-checks-20261112.json for all
checksums, measured results, evidence and precise limitations.

- **Actual HONOR 20m40s endurance did NOT complete:** host stopped it after
  140.64 seconds when CPU cluster1 reached 78 C; battery was 42 C.
  Test-only processes were confirmed stopped; no full transcript exists.
  The test audio repeats a public two-speaker excerpt, not a natural
  twenty-minute meeting.
- **Russian independent identity, oracle RTTM:** fixed first 70 synthetic
  audiobook clips; 42 distinct true source voices, 85 speaker appearances.
  TitaNet double-evidence accepted 34/85; rejected 51/85 (60%).
  It linked 12 of 13 accepted returning probes correctly, split one,
  and produced zero observed false identity merges. Oracle source turns
  bypass C2 errors; this is not an end-to-end Android result.
- **Actual host Kotlin Nemotron C2 DER:** first 15 two-speaker Russian
  synthetic mixtures, 15 minutes, pinned IR9 INT8 model and ORT 1.17.1.
  Pooled DER 3.20% (250 ms collar, overlapping speech included);
  speaker count 2 on 15/15. Median DER 1.95%, worst file 14.18%.
- **C2 predicted turns -> TitaNet global-link replay:** 12/30 profiles
  accepted and 18/30 rejected. Zero observed wrong joins, but **zero
  accepted returning probes**, so this subset cannot establish true
  returning-speaker recall on real C2 predictions.
- Generator RTTM labels are **not human-reviewed speech annotation**;
  independent human Russian natural-conversation DER and paired cpWER
  remain NOT SCORED. Pretraining exclusion also unverified.
- New 8 hermetic scorer tests pass; existing 12 host thermal tests and
  7 voice metric tests pass. Only one Git checkout and ready production APK.
  The normal product feature remains disabled.

## 2026-11-12 — independent battery + CPU thermal limits

- Owner requested a less restrictive but still bounded experimental
  thermal policy: battery abort at **45 C**, CPU cluster abort at **78 C**;
  warnings at battery **43 C**, CPU **75 C**.
- Confirmed HONOR Android 10 Thermal HAL exposes current readings for
  cluster0, cluster1 and Android Thermal Status via ADB. Both CPU readings
  were ~35 C when the battery was 36 C; /sys/class/thermal is not
  accessible on this stock phone.
- Host watchdog reads CURRENT (not cached) CPU HAL readings and battery
  every 2 seconds, checks severe OS/sensor status, and fails closed
  when telemetry is unavailable. Android QA independently checks battery
  and OS severe status. CPU numeric enforcement requires host watchdog.
- Previous tests with the 42 C cutoff remain historically accurate.
  CPU threshold change needs CI, Android compile and fresh hardware
  negative-control/endurance evidence before claiming completion.

## 2026-11-12 — device negative-control attempt and thermal gate

- A second HONOR instrumentation run used distinct public speakers
  after the positive test. It started at battery 38°C and reached
  the 42°C safety cutoff after 112.73 s.
- Host watchdog recorded **THERMAL_ABORT** and verified both isolated
  QA processes stopped. The Android instrumentation 'Process crashed'
  line is a force-stop consequence, not evidence of an app crash.
- Application evidence remained RUNNING (as intended when forcibly
  stopped); there is **no negative-control accuracy result**.
- Local failure evidence: docs/evidence/speakerbook-honor-negative-thermal-abort-20261112.json.
- Expanded host watchdog now allows only named QA test classes and
  known QA modes; Python tests exercise invalid class/mode rejection.
- The phone must cool before any new sustained workload.

## 2026-11-12 — repository consolidation and HONOR post-review QA

- Removed 29 historical Git worktrees, preserving a single canonical tree
  at C:/Users/user/Documents/nuclear-neurostenographer; archived unique
  reports and interrupted integration Git state to the verified local ZIP
  .local/retained-unique-work-20261111.zip.
- Kept exactly one ready release APK at
  .local/releases/current/Neurostenographer-0.4.1-rc4.apk; discarded older
  RC1/RC2/RC3/posthack duplicates, retaining Git history.
- Restored Gradle 8.9, Temurin JDK 17.0.21 and Android SDK, validated
  executables, and restored Maven dependencies after isolated QA builds.
- PR #54 review: addressed conflicting app ID, early-exit watchdog and
  stale instrumentation evidence. GitHub Actions passed for these fixes.
- **HONOR short test after review: PASS**. Repeated 370.453 s public WAV,
  8 segments, two profiled windows, one speaker linked across windows;
  the remaining IDs are deliberately local and unlinked. RTF 0.294;
  peak battery temperature 41°C, cutoff 42°C; no QA process left running.
  Evidence: docs/evidence/speakerbook-honor-repeat-postreview-20261112.json
- Still a release NO-GO: only one returning speaker linked on this fixture,
  no new-revision different-source negative control, no safe successful
  20+ minute test or independent Russian manual speaker DER/cpWER.

# Progress — 2026-10-30

## 2026-11-11 — independent Codex Sol 6.1 High audit hardening

- Independent read-only auxiliary audit flagged two concrete identity
  vulnerabilities: ineligible overlapping speech contaminated "clean"
  audio, and incremental centroid updates could drift away from
  an original speaker. Fixed both with fail-closed semantics.
- Added clean-frame mask with every turn contributing as a blocker,
  immutable enrollment anchor in GlobalSpeakerBook, and TWO
  temporally disjoint (>=3s each) TitaNet fingerprints per local
  speaker with required within-block similarity >=0.84.
- New Kotlin regression tests for false overlap, sub-frame fragments,
  gradual identity drift, independent temporal evidence and mixed-speaker
  detection. All 20 core test groups passed locally after the changes.
  Android QA + instrumentation Kotlin compilation PASSED (32 tasks).
- Corrected cancellation/persistence race by making final history
  save + audio move + UI publication one non-cancellable commit.
- Fixed stale success evidence in 20m QA instrumentation: RUNNING,
  PASS only after assertions, FAIL/THERMAL_ABORT always written.
  Added independent host ADB watchdog with 39C preflight and 42C
  cutoff, with pure unit tests for battery parser.
- PC VCTK proxy of two independent excerpts/person: 15/24 people
  had consistent profiles at 0.84, 9 rejected; of 15 resulting profiles,
  14 linked a third utterance, 1 rejected, 0 wrong links.
  This is NOT a physical C2 five-minute-block test.
- IMPORTANT: new dual-voice code has not been retested on HONOR
  because previous sustained inference reached battery 47C.
  Earlier HONOR PASS evidence applies to single-profile revision.
  Feature remains QA-only and MUST NOT ship before new physical
  revalidation plus speaker-disjoint Russian field data.

## 2026-11-11 — PR #54 review fixes and workspace consolidation

- Git workspace copies reduced from 31 to one canonical checkout
  (during the final consolidation step); unique uncommitted reports
  preserved separately, one latest RC4 production APK retained.
- Additional read-only review detected QA application-ID suffix collision,
  host watchdog early exit, and stale short-device evidence.
  All three fixed and tested with Python unit tests and Android compilation.
- Unrelated shared NonCancellable transcript save change reverted to
  origin/main while speakerbook QA remains opt-in.
- Latest tests: Android debug + AndroidTest Kotlin compile PASS;
  Gradle negative-flag configuration test PASS; host watchdog five tests PASS.
- Merge remains blocked on untested continuous 20+ minute physical
  run and Russian held-out identity/diarization validation.

## 2026-11-11 — correctness hardening after independent code review

- Ineligible/short overlapping turns are explicitly excluded from
  identity evidence; regression covers 200ms and sub-frame overlaps.
- Global voice-book matching now checks original immutable enrollment
  anchor as well as adaptive centroid, blocking identity drift.
- Two temporally separated clean voice excerpts must agree for a
  TitaNet profile to be accepted (conservative; can reduce coverage).
- Long physical QA has terminal evidence status and an optional host
  temperature watchdog that stops only QA packages.
- Core tests passed; current newly hardened Android behavior still
  requires a physical recheck after phone cooling.

## 2026-11-11 — speaker-disjoint VCTK quantitative validation

- 108 VCTK mic2 excerpts, 36 labelled people, 3 distinct clips each.
- First 6 people used to calibrate 0.632, next 6 for preliminary holdout;
  a fresh set of 24 was evaluated with both 0.84 and FROZEN 0.632.
- Fresh 24: 0.84 -> 0/2484 false pair matches but 26/72 false rejects.
  0.632 -> 10/2484 false pair matches, 0/72 false rejects.
- In two-rotation unknown-voice enrollment test, at 0.632 there were
  5/72 wrongly accepted unknown utterances, from 4 actual people;
  at 0.84 there were 20/48 rejected known utterances.
- Simulated noise, echo and telephone filter revealed severe
  enrollment/probe acoustic mismatch; do not promote thresholds to
  production. Model uses English VCTK and no verified Russian DER.
- Evidence and clip checksum manifest stored in docs/evidence;
  pure Python scorer and its 6 regression tests added to CI.

## 2026-11-11 — TitaNet Small speaker verification, physical HONOR QA

- After the first negative-control C2 false-match warning, switched active QA
  cross-window matching from unverified Nemotron C2 hidden embeddings to an
  independent sherpa-onnx TitaNet Small 192D speaker-embedding extractor.
  Exact model SHA256 pinned; optional 40 MB weights remain only in the QA
  sandbox and are not bundled into the released APK.
- Physical HONOR ARM64 tests: repeated-source positive 2/2 matching IDs,
  different-source negative 0 ID cross-links (old C2 had 1 shared ID),
  missing optional model fails closed to local block IDs with full ASR text,
  independent utterance of same C2 speaker cosine 0.845 vs other voice 0.250.
- Source clips do not have independently verified identity labels;
  none of these numbers is a held-out DER or speaker-verification FPR.
- Sanitized evidence: evidence/speakerbook-titanet-honor-20261111.json.
- QA-only, do not merge into production until continuous 20+ minute
  processing and held-out DER/cpWER/false-match validation pass.
- 20m40s continuous QA test attempted on HONOR, but **manually aborted**
  after the battery sensor reached 47 C. Android showed a test process
  termination because we force-stopped the QA packages; this is NOT proof
  of a software crash or successful 20+ min processing.
  Observations: evidence/speakerbook-titanet-thermal-abort-20261111.json.
  Do not re-run a sustained load on this phone without a thermal cutoff
  and a cooling/power plan.



## 2026-11-11 — experimental cross-window voice identity, QA only

- Separate worktree/branch feat/global-speakerbook-20261111 from origin/main 459773f. Main app/release unchanged.
- Added GlobalSpeakerBook, NemotronVoiceProfiles and opt-in globalSpeakerBook flag. Old block-scoped IDs preserved when evidence is missing, ambiguous or invalid. Not a validated speaker-verification model.
- Core:runCoreTests passed (including new identity/overlap tests). App:compileDebugKotlin passed for QA product C2+A3 build with local equivalent ONNX Runtime 1.17.1 AAR (temporary file dependency used only to work around offline cache; normal Maven declaration restored).
- New same-file WER/cpWER scorer and three Python unit tests passed; end-to-end synthetic CLI fixture also passed. Python CI test added.
- **HONOR physical smoke:** experimental APK + test APK installed side by side; 6:10 repeated permitted fixture passed 1/1 Android instrumentation, 102.8 seconds wall time (RTF 0.277 on a silence-heavy file), two stable speaker IDs across two blocks, eight transcript segments. Repeated clip text differed by 2/141 words (not ground-truth WER). Logs and evidence retained locally only.
- **Regression retest:** second physical instrumentation PASS 1/1 after removing false unknown-speaker warning (pipeline 101.812s, 0.2748 RTF); all eight segments and timestamps exactly match first run. The production-length threshold remains unchanged; a separate QA flag triggers long-file processing after five minutes. Sanitized evidence: evidence/speakerbook-honor-smoke-20261111.json.
- **Negative source control on HONOR:** two separate audio sources (2-speaker + 3-speaker), 421.3s audio, 135.264s processing, 21 segments, both C2 blocks profiled. One global Speaker 2 was reused across sources, so the negative QA assertion failed. Voice identities were not independently human-labelled; this is a **potential false merge**, and blocks enabling the feature in the default APK. See evidence/speakerbook-honor-negative-20261111.json.
- **Not yet tested:** independent/new speakers in 20+ minute continuous audio, held-out DER/cpWER, direct Skvor comparison on identical annotated recordings.
- Architecture, safety limits and validation steps: GLOBAL_SPEAKER_BOOK_QA_2026-11-11.md.


> **Обновлено 07.11.2026:** текущий выпуск — 0.3.14-contest. Сводка метрик (ПК / телефон / не проверено): [CHECKPOINT_2026-11-07.md](CHECKPOINT_2026-11-07.md). Ниже — журнал, новые записи сверху.

## 2026-11-07 (вечер) — 0.3.14: официальный JSON для жюри в основном экспорте

- Из слайдов организаторов (20 картинок, прочитаны под входом владельца) стало известно: вывод строго `{"transcript":[{"speaker_id","start_ms","end_ms","text"}]}`; жюри ставит APK на эмулятор Android 4 ГБ ОЗУ, импортирует три записи диалогов, считает WER и RTF; баллы: транскрипция 40, диаризация 25, метки 10, скорость 10, UX 10, защита 5. В main (0.3.4–0.3.13) этого формата не было: PR #30 (черновик) не был слит. Требования: [CONTEST_REQUIREMENTS_2026-11-07.md](CONTEST_REQUIREMENTS_2026-11-07.md), комплект сдачи: [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md).
- 0.3.14: PR #30 влит; кнопка «JSON» (и «Экспорт JSON» в живом режиме) теперь официальный формат, расширенный — «JSON расш.»; фрагмент перекрытия получает id первого из перекрывающихся говорящих; текст без правок словаря. Ядро 16 групп PASS, валидатор `tools/verify_contest_json.py` в CI.
- Не сделано: видео, прогон на эмуляторе с 4 ГБ, локальная LLM (признана ошибкой слайда).

## 2026-11-07 (ночь) — 0.3.13: корпоративный IT-сленг и повестка российского IT

- Владелец уточнил: нужно, чтобы приложение хорошо понимало русский IT-сленг на созвонах, планёрках и собраниях, темы и проблемы российского IT и ведомства (РКН, Минцифры и т. п.). Сначала исследование (словари сленга, церемонии Scrum, SLO и постмортемы, обзоры рынка 2026, госзаказ, российские аналоги), потом словарь: 379 записей, около 1300 вариантов. [TERM_DICTIONARY_RU_IT_2026-11-07.md](TERM_DICTIONARY_RU_IT_2026-11-07.md).
- Варианты — из реального вывода A3 на 117 фразах (gTTS, ПК). **ПК:** ядро 16 групп PASS; Podlodka DEV 6,47 %, 0 вредных; **0 ложных правок** на 29 диалогах; на пробе 86 правок, неверных нет. **Телефон:** новый словарь не прогонялся; интерфейс не менялся с 0.3.11.

## 2026-11-07 (ночь) — 0.3.12: словарь терминов под кейс Hex.Team

- Владелец уточнил: кейс от Hex.Team (кибербезопасность, реверс-инжиниринг, АСУ ТП, встраиваемка, Android; основной сценарий — рабочие созвоны). Тематический блок Росатом (ТВЭЛ, МАГАТЭ, КИУМ) заменён словарём этой области: 247 записей, около 900 вариантов. [TERM_DICTIONARY_HEX_2026-11-07.md](TERM_DICTIONARY_HEX_2026-11-07.md).
- Варианты — из реального вывода A3 на 131 рабочей фразе (gTTS, ПК) плюс регулярные транслитерации. Двусмысленные слова («гидра», «люкс», «зум», «сиви»…) помечены и по умолчанию не отмечены.
- **ПК:** ядро 16 групп PASS (+ новый тест словаря); Podlodka DEV 6,96 → 6,47 %, 0 вредных правок; HOLDOUT без изменений; **0 ложных правок** на 29 бытовых диалогах; на пробе 110 правок, неожиданных нет. **Телефон:** словарь не прогонялся; интерфейс проверен в 0.3.11, код интерфейса не менялся.

## 2026-11-07 (вечер) — 0.3.11: словарь терминов проверен на телефоне, прогон 3 на main

- **Что нового в коде:** только версия (0.3.11-contest, versionCode 14); код = main bfeaf87 (словарь терминов хакатона, PR #37).
- **Телефонный прогон 3** (main bfeaf87, QA-сборки `.realtime`/`.solhigh`, SHA-256 сверены): 16 PASS / 2 FAIL, метрики идентичны прогону 2 (live syn3 3/52, syn4 14/76, veche-2 15/137, veche-3 16/123, aba 1/17; импорт aba 1/17, syn3 3/52, syn4 13/76) — словарь метрики не испортил. Два FAIL — стенд: (1) lifecycle — HONOR заморозил `.solhigh`, сторож в прогоне не покрывал lifecycle; (2) `foregroundMicrophoneScreenOff` прошёл на телефоне, но результат не дошёл до хоста («Failure reporting to instrumentation watcher»).
- **Дозапуск обоих (телефон, те же APK):** lifecycle, все 3 теста, со сторожем заморозки — **PASS** (112 с; сторож поймал 2 заморозки, 16:43 и 16:44, и вернул приложение); `foregroundMicrophoneScreenOff` — **PASS** (OK (1 test), logcat `run finished: 1 tests, 0 failed`). Раньше на 0.3.10: микрофон-lifecycle PASS после подъёма громкости медиа до 9/15 (при 0 микрофон слышал тишину), screen-off PASS. `run_suite3.ps1` теперь держит сторожа и на lifecycle.
- **Словарь на телефоне** (`.solhigh`, импорт `termprobe-all.wav`, 25 фраз gTTS, 02:16, один голос): кнопка «Исправить термины (7)»; окно «Написание терминов» показало Твел→ТВЭЛ, твел→ТВЭЛ, Магаты→МАГАТЭ, Хокатон→Хакатон, Киум→КИУМ, диарезации→диаризации (6 строк видно без прокрутки при счётчике 7; седьмая не просматривалась); «Применить» → текст «компания ТВЭЛ», «Каждый ТВЭЛ», «МАГАТЭ», метка «правка», кнопка «Термины исправлены (7)»; «Вернуть исходный текст (правок: 7)» → исходное «Твел/твел/Магаты», кнопка снова «Исправить термины (7)». Словарь исправляет только то, что есть в нём: «ВВЭР-1200» распознано как «V 200», «РБМК-1000» как «РБМК нар» — не исправлено. Скриншоты и тексты: `evidence/device-suite-20261107/run3-main/terms/`.
- **Заметки по стенду:** импорт через системный выбор файла на HONOR требует лицо/пароль владельца (приложение «Файлы»); `adb input text` теряет символы — вводить по одному.
- Сырьё: `evidence/device-suite-20261107/run3-main/`.

## 2026-11-07 — 0.3.10: страховка прогретого прохода C2, перекрытия, телефонный прогон

- **Ошибка 0.3.7–0.3.9 найдена на телефоне.** Прогон тестов на HONOR (код 0.3.9): живой `aba` (13 с, A-B-A) — 1 говорящий, cpWER 9/17. На ПК: одиночный проход C2 + постобработка даёт A-B-A, прогретый второй проход отдаёт второй голос первому (`aba`, `abab`). Ломались и импорт, и живая финализация.
- **Исправление** `NemotronDiarizer.chooseWarm`: прогретый проход берётся, только если не теряет говорящих. ПК: dev 4,14 % без изменений, test 4,96 → 5,01 % (1 откат), число говорящих 91 → 94 %; `aba`/`abab` 1 → 2; остальные 11 фикстур без изменений; живая финализация == импорт на 13 записях. `tools/c2pp/warm_guard.py`, `evidence/c2-postprocess-20261106/warm-guard.json`, раздел в [C2_POSTPROCESS_2026-11-06.md](C2_POSTPROCESS_2026-11-06.md).
- **Перекрытия:** вместо «Не определён» — «Говорящий 1 + Говорящий 2» (UI, поиск, TXT, SRT); JSON: `speaker_id` остаётся `null`, добавлен `overlap_speaker_ids`. Сохранённые стенограммы читают новое поле. Core: 16 групп + новый тест PASS.
- **Тест паритета** (ветка `test/device-suite`): живая финализация должна совпадать с импортом файла (warm + постобработка) — PASS на телефоне.
- **Телефонный прогон 1** (код 0.3.9): 16 PASS / 2 FAIL. Импорт файлов упал по таймауту, потому что HONOR заморозил процессы `.solhigh` (cgroup freezer, 20+ мин без CPU); screen-off тест — стенд не выключал экран. Оба — проблемы стенда, но импорт на этом коде на телефоне не подтверждён. Сырьё: `evidence/device-suite-20261107/run1-0.3.9/`.
- **Телефонный прогон 2** (0.3.10): 16 PASS / 1 FAIL. Живой `aba` 2/2 говорящих, cpWER 1/17 — исправление подтверждено; импорт файлов PASS на всех фикстурах. FAIL — lifecycle-тест (заморозка процессов HONOR, 707 с; на 0.3.9 проходил), при тихом перезапуске оба подтеста без звука PASS; подтест с динамиком ночью не запускался (на 0.3.9 PASS). Screen-off тест не запускался по просьбе владельца. Сырьё: `evidence/device-suite-20261107/run2-0.3.10/`.
- README переписан под текущее состояние (было 0.3.3).
- **Эмуляторный CI снова зелёный** (API 34/35, впервые с 05.11): `tools/run_android_ui.py` переписан под текущий интерфейс (запись с отказом/разрешением, поворот, HOME, выключение экрана, «Распознать» → экран стенограммы, импорт через системный выбор файла, отмена и сохранение TXT/JSON/SRT, удаление стенограммы без удаления экспортов, отзыв разрешения во время записи); `run_kit_install_check.py` — под текущие сообщения; `verify_transcript_exports.py` понимает «Говорящий 1 + Говорящий 2». Исправлены гонки стенда: поле поиска стенограммы принималось за поле имени файла, пустой дамп uiautomator во время анимации, тап по ящику выбора файла во время анимации. API 33 — таймаут загрузки эмулятора раннера.

## 2026-11-06/07 — 0.3.4–0.3.9 (кратко)

- 0.3.4–0.3.6: собраны без `-PasrA3=true` → приложение ждёт CTC-модель, которой нет в APK. **Неисправны**, в описаниях релизов предупреждение. Правильные флаги — `tools/build_product_apk.sh`.
- 0.3.7: постобработка C2 (гистерезис, расширение, мин. длительности; ноутбук Рузанны) + прогретый второй проход. ПК, 35 отложенных записей: DER 8,59 → 5,80 → 4,96 %, путаница 1,25 → 0,87 %. [C2_POSTPROCESS_2026-11-06.md](C2_POSTPROCESS_2026-11-06.md). (Прогретый проход на коротких диалогах терял говорящего — исправлено в 0.3.10.)
- 0.3.8: живая расшифровка в основном приложении; финализация после «Стоп» = тот же C2, что при импорте (ПК, 4 записи).
- 0.3.9: задержка живого режима на HONOR p50/p95 3,3/6,3 → 1,4/2,9 с, первая фраза 0,6 с. [LIVE_LATENCY_2026-11-07.md](LIVE_LATENCY_2026-11-07.md).
- PR #33: инструментальные тесты эмуляторного CI починены; workflow красный из-за устаревшего `tools/run_android_ui.py`.

## 2026-11-06 — отдельный QA на физическом HONOR

- В текущем repo, ветка `qa/honor-acceptance-20261106`, локальный код-коммит
  `c05127c366511ad50fa2d41f8cbf4c9c83021a08`; без нового worktree/push/merge.
  Выборочно проверены и перенесены QA/C2 safety fixes из `4214d104`.
- **PASS**: 16 core groups, app + AndroidTest build; реальный HONOR ARM64:
  исходные `OK (3 tests)` и расширенные `OK (4 tests)`. 2/3/4 speakers,
  A-B-A, licensed acted DEV, silence/corrupt inputs, 15 TXT/JSON/SRT exports,
  C2 replacement при активном 120 s worker без удаления прежней generation,
  worker death/cancel/recovery, настоящий микрофон 19.940 s + 1.940 s.
  Акустический публичный probe MIC→C2→A3: 4 контрольных слова / 3 segments.
- Stable `ru.neurostenographer.app` 0.3.3-contest сохранён; before/after APK SHA
  совпал. Обновлены только `.solhigh` и `.solhigh.test`, подписи/installed hashes
  проверены; uninstall/data clear/settings changes не выполнялись.
- Наибольший sampled total PSS 1071503 KiB (instrumentation suite, не release
  benchmark), worker отдельно 387062 KiB; 36→38 °C при питании. В собранных
  QA PID logs нет FATAL/ANR; intentional worker SIGKILL учтён отдельно.
- **NOT_READY для полной приёмки**: системный picker закрыт Huawei App Lock,
  пароль не обходился; UI SAF import/export **NOT_RUN**. Human-gold accuracy
  **NOT_SCORED**; Unknown в noise и acted DEV не скрыт за общим speaker-count
  PASS. Screen-off, новая длинная full-pipeline запись и 16 KiB device **NOT_RUN**.
  Новый CI **NOT_RUN** без push. Raw evidence/APK/audio сохранены только в `.local`.
- [Полный отчёт с hashes, ошибками ранних проверок и командами](HONOR_ACCEPTANCE_2026-11-06.md),
  [публичный агрегат](evidence/honor-acceptance-20261106/summary.json).
## 2026-11-05 — отдельный realtime prototype, NOT_READY

- Ветка `feature/realtime-honor-20261105`, отдельный пакет `.realtime`; основной APK и `.c2candidate` не заменялись, их SHA-256 до/после совпали.
- Реализованы независимый WAV/ring capture, Silero VAD, постоянный A3, stateful C2 FAST/FALLBACK, bounded ASR-priority worker, честная отложенная атрибуция, восстановление WAV и явный batch fallback. Финальные core/debug/instrumentation/lint и realtime-disabled product build PASS.
- HONOR, одна и та же синтетика 33,5 с, проверенный pacing: compute RTF 0,674 FAST / 0,488 FALLBACK; WER 3/52 в обоих; FAST выделил 2/3 голоса, FALLBACK 3/3 с неизвестными словами, строгая cpWER NOT_SCORED. Отдельные первые зависания и UiAutomation crash сохранены как проблемы, не скрыты.
- Windows native C2: точная offline parity; ускоренные 20/60 мин с bounded cache и causal reads PASS, **не Android и не ASR**. Физический mic/HOME/screen-off сохранил 19,94 с, но общий тест FAIL из-за UiAutomation; исправленный harness ещё не установлен.
- После screen-off HONOR защищён PIN; следующая установка требует обычной разблокировки владельцем. Финальный APK собран, но на нём телефонные проверки NOT_RUN. Подробные команды, хэши, логи, измерения и дальнейшие шаги: [REALTIME_HONOR_2026-11-05.md](REALTIME_HONOR_2026-11-05.md).

## 2026-11-05 — 0.3.2 и 0.3.3 в main

- PR #24 (0.3.2, merge `53455c3`): окна ASR по сплошной речи вместо нарезки на каждой смене говорящего; слова по говорящим по меткам токенов A3 (`TokenWords` + `TranscriptFusion.attributeWords`); имя экспорта больше не режется на точке в «нояб.». 29 дорожек, парный bootstrap: WER 379 → 304 из 1812 (ДИ −6,4…−2,1 п.п.), cpWER-U 448 → 431 (−2,1…+0,1). HONOR: проверки UI и экспорта пройдены, 20 мин RTF 0,45. Детали: [ASR_WORD_ATTRIBUTION_2026-11-05.md](ASR_WORD_ATTRIBUTION_2026-11-05.md).
- PR #25 (0.3.3, versionCode 6, merge `043f9a8`): обратимый словарь терминов B0. DEV WER 6,96 → 6,47 %, HOLDOUT без изменений (0 правок), 0 ложных предложений на 29 диалогах. HONOR: применение, сохранение после перезапуска, экспорт, откат проверены; `syn3-clean` WER 3/52, cpWER 3/52. Детали: [TERM_DICTIONARY_B0_2026-11-05.md](TERM_DICTIONARY_B0_2026-11-05.md).
- Ревью кода 0.3.1 → 0.3.3 (05.11, ночь): блокирующих багов не найдено. Мелочи на будущее: свой термин с пунктуацией в поле «Как распознано» (например «C++») молча не находит совпадений; отдельный токен-тире A3 приклеивается к предыдущему слову без пробела; метка «правка» ставится и на правку, которая перестала совпадать с текстом.
- Не сделано: повторная запись через микрофон на 0.3.2+ (нужен владелец), issue #5 (натуральная речь с разметкой), 16 КБ страницы для `libonnxruntime4j_jni.so` (решается в C++-ветке Сани).

## 2026-11-02 — documentation check against code

- Docs and two user messages still described the old 120-second and 24 MB limits,
  threshold 0.9 and the old integration branch. Corrected to match `PcmWav` and
  `AudioSnapshots`: 20 minutes, about 230 MB, 0.8, `feature/long-recordings`.
- All stress runs failed before the emulator started: `long-recording.yml` did not
  pass `GH_TOKEN` to provisioning (gh exit 4). Fixed; the workflow has not run since,
  so 20-minute memory and speed remain unmeasured.
- Open, seen in code and not changed:
  - recording stops when the app leaves the foreground (`MainActivity.onStop`);
  - the 60-second decode deadline may reject long compressed files;
  - the transcript screen text still says fragments up to 20 s, replies now reach 60 s.
- 2026-11-02 evening (code after 0dab286): the stress workflow, Real offline Russian ASR
  and Android build all succeeded at 0dab286 (runs 41354324447, 41354324445, 41354327796,
  as reported by the owner). The `long-recording-evidence` artifact has NOT been read:
  the stored `gh` token became invalid (HTTP 401), and artifact download needs
  authentication even on a public repo. Duration, PSS and RTF from that run are
  therefore unrecorded here. A green run is emulator evidence only, not a phone result.
- Added `DecodeBudget`: the decoding deadline is now half the declared duration, between
  60 s and 10 min (5 min if unknown), instead of a fixed 60 s. Core test added; 16 core
  groups PASS with a local Kotlin compiler. Android code changes (`AudioImport.kt`,
  hint text in `MainActivity.kt`) are not yet compiled or run in CI. Real decode time of
  a 20-minute MP3 on a phone is unmeasured.
- Recording still stops when the app is backgrounded. Fixing it needs a foreground
  service with the microphone type, `FOREGROUND_SERVICE_MICROPHONE` and notification
  permission, and the existing UI test expects HOME to stop recording; both change
  together and need a CI run, so it is not done yet.
- `gh` re-authorized; `7f3b601` pushed. Artifact `long-recording-evidence` of run
  [41354324447](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41354324447)
  (commit 0dab286, GitHub x86_64 emulator, looped public fixtures, scope
  `stress_looped_public_fixtures_not_accuracy`) was read:

  | Measure | Value |
  | --- | --- |
  | audio | 1 200 000 ms (20 min) |
  | diarization | 162.6 s, real-time factor 0.135 |
  | ASR | 65.9 s, RTF 0.055 |
  | total | 228.4 s, RTF 0.19 |
  | peak PSS, app process | 440 MiB |
  | peak PSS, `:diarization` worker | 435 MiB |
  | output | 304 turns, 304 windows, 110 replies, 8 speakers |

  Limits: the speaker count of 8 comes from looped fixtures and says nothing about
  accuracy; the two PSS peaks are per process, their sum was not measured at one instant;
  a x86_64 emulator on a CI host is far faster than a mid-range ARM phone, so RTF on a
  phone is unknown and must be measured.
- Recording in the background (commits 91c53cf, c94b750, 7ce4a00): new `RecordingService`
  (foreground service, type `microphone`; permissions `FOREGROUND_SERVICE`,
  `FOREGROUND_SERVICE_MICROPHONE`, optional `POST_NOTIFICATIONS`). The view model starts it
  with the recording and stops it when the recording ends; `MainActivity.onStop` stops
  the recording only if the service is not active. CI found a real bug on the way: a stop
  racing with the service start crashed the process
  (`ForegroundServiceDidNotStartInTimeException`); the service now finishes such a stop
  itself after entering the foreground. The emulator UI flow now checks that after HOME
  the service is `isForeground=true`, that recording continues, that "Остановить запись"
  finalizes the WAV and that the service ends with it. Run
  [41430825756](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41430825756)
  (Real offline Russian ASR, API 33 x86_64 emulator) PASS; Android build
  [41430834487](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41430834487)
  PASS. Not verified: a physical phone, a locked screen, OEM battery killers, a recording
  of tens of minutes in the background, API 34+ behaviour.
- Synced to `ffdcabc` (fast-forward, PR #12 documents merged). Review comment on PR #9
  raised two valid points on `RecordingService`, now addressed in code: the notification
  said "stop" but only opens the app (copy corrected), and a refused foreground entry was
  silent (the view model now warns after 3 s when the service is not active; `onStop`
  already stops and saves the recording in that case). Still untested: API 34/35, immediate
  HOME before the service starts, locked screen. Added
  [PHONE_ACCEPTANCE.md](PHONE_ACCEPTANCE.md): the exact procedure and report for the
  physical ARM64 run (status NOT_RUN).
- Commit `c947597` (all runs PASS, API 33 x86_64 emulator): Real offline Russian ASR
  [41511089594](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41511089594),
  stress [41511089611](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41511089611),
  Android build [41511098421](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41511098421).
  Stress artifact read: diarization 237.1 s (RTF 0.198), ASR 93.1 s (RTF 0.078), peak PSS
  app 612 MiB, worker 435 MiB, same 304 turns / 110 replies / 8 speakers. Versus run
  41354324447: both times about 1.4x slower, app PSS +172 MiB. Not explained: the
  slowdown looks like runner variance, the memory rise coincides with the foreground
  service and the new code and is not yet attributed. Single run each, no repeat.
- Blocked: the re-issued `gh` OAuth token has scopes gist, read:org, repo, without
  `workflow`, so GitHub refuses pushes that change `.github/workflows/`. Prepared
  locally in branch `ci-api-matrix-pending`: an API 33/34/35 matrix for the ASR and UI
  workflow. Needs `gh auth refresh -h github.com -s workflow` by the owner.
- Android API matrix (workflow now pushed after the owner added the `workflow` scope):
  Real offline Russian ASR on emulators API 33, 34 and 35 (x86_64, default image) all PASS at
  `38c1b0d`, run
  [41519033079](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41519033079),
  including the UI flow with HOME during recording and the foreground service check; Android
  build [41519036174](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41519036174)
  PASS. Two test-side findings on the way, no product change: Android 14+ throws
  `ZipException` itself for a `../` ZIP entry (the model import still rejects it; the test now
  accepts both exceptions), and the API 35 emulator showed a system launcher ANR dialog over
  the app (the UI script now sets `hide_error_dialogs`). Stress run
  [41517372792](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41517372792)
  (commit `5f10e5d`, API 33): diarization 265.7 s, ASR 96.3 s, total 361.9 s (RTF 0.30), peak
  PSS app 612 MiB, worker 454 MiB. The app peak is now stable near 612 MiB in two runs,
  versus 440 MiB before the background-recording change, so the +172 MiB is real, not noise;
  cause not yet isolated (candidates: the service, keeping the screen on, measurement
  timing). Emulator only; locked screen, OEM battery limits and a physical phone remain
  NOT_RUN.
- **2026-11-03 — memory/speed analysis, recording lifecycle, false-positive guard.**
  *Memory.* The "growth from 440 to 612 MiB" was a measurement artefact, not a regression
  and not a leak. Seven runs of the same 20-minute test on different commits (service
  present or absent) gave 439/440 or 610–628 MiB. The time series shows the app's native
  heap at 454–472 MiB in the first sample of the ASR phase and a steady ~260 MiB after it:
  the peak is the model load (`OfflineRecognizer` construction). A 2-second sampler hit it
  in some runs and missed it in others. With 0.5-second sampling (`47ee932`) all three
  runs report 611–613 MiB with the peak 0–2 s after ASR start, fast or slow runner. So the
  honest app peak is **about 612 MiB** (earlier 440 MiB figures understated it); steady ASR
  state is 415–440 MiB with a bounded sawtooth, no upward trend. Diarization worker peak
  447–455 MiB; app and worker peaks are in different phases (diarization ends before ASR
  starts), their sum at one instant was not measured.
  *Speed.* Same code, same API 33 emulator: diarization 151–270 s, ASR 61–97 s across runs
  (runner variance of about 1.8x), so the earlier 1.4x "slowdown" is not attributable to
  code. Host CPU flags are not visible inside the emulator (`Android virtual processor`).

  | Run (API 33, x86_64) | commit | diarization | ASR | RTF total | app peak | worker peak |
  | --- | --- | --- | --- | --- | --- | --- |
  | [41354324447](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41354324447) | 0dab286 | 162.6 s | 65.9 s | 0.19 | 440 MiB (2 s sampling, missed load peak) | 435 MiB |
  | [41427928254](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41427928254) | 7f3b601 | 144.0 s | 60.9 s | 0.17 | 439 MiB (same) | 446 MiB |
  | [41517372792](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41517372792) | 5f10e5d | 265.7 s | 96.3 s | 0.30 | 612 MiB | 454 MiB |
  | [41527295772](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41527295772) | 47ee932 | 238 s | 93 s | 0.28 | 613 MiB (0.5 s) | 455 MiB |
  | [41527295883](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41527295883) | 47ee932 | 156 s | 61 s | 0.18 | 611 MiB (0.5 s) | 455 MiB |
  | [41527302740](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41527302740) | 47ee932 | 244 s | 93 s | 0.28 | 613 MiB (0.5 s) | 447 MiB |

  All: 20 minutes of looped public fixtures (`stress_looped_public_fixtures_not_accuracy`),
  synthetic PCM through `IsolatedDiarization` and `OfflineAsr`, **no microphone**. Not
  measured: any ARM64 device, thermal state. Reducing the 612 MiB load peak was not
  attempted (it needs a different loading mode of the runtime; no evidence yet that it
  matters on the target phone).

  *Recording lifecycle (emulator, real `AudioRecord` through `RecordingService`, separate
  from the PCM stress test).* The UI flow (`tools/run_android_ui.py`) now: grants the
  microphone, rotates, presses HOME, checks `isForeground=true`, turns the screen off for 8 s,
  wakes it, returns, stops, and compares the WAV length with wall time. Run
  [41527368727](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41527368727)
  at `1fada6c`: API 33, 34 and 35 all PASS; the WAV was 26.1/26.7/25.7 s for 28.7/29.6/28.6 s
  of wall time (gap only dialogs and finalization, no multi-second hole from HOME or
  screen-off). The emulator microphone delivers silence, so this proves continuity, not
  speech capture. A secure lock screen with a PIN, OEM battery policies and a physical
  microphone are NOT_RUN.
  *False-positive guard.* `hide_error_dialogs` could hide an ANR of our own app, so the UI
  flow now scans logcat and DropBox for ANR, Java/native crashes, memory kills and
  foreground-service start failure of `ru.neurostenographer.app` and `:diarization`
  (`tools/app_failure_detector.py`, 12 unit tests including foreign ANR, similar package
  name, deliberate permission-revocation kill, DropBox entries before the run). Foreign
  ANRs (launcher) are ignored. It has passed on API 33–35 in the run above; it has not yet
  been shown to catch a real injected failure on a device (only on authored logs).
  *Go / no-go.* Emulator pipeline: GO (import, record, background/screen-off, offline
  Russian ASR, speakers, TXT/JSON/SRT, no network permission; API 33–35). Telling anyone the
  app works on a phone: NO-GO until `PHONE_ACCEPTANCE.md` is executed on ARM64. Public
  APK release: NO-GO (licence/notices review still open).
- **2026-11-03 — offline kit, no-picker model install, UI status, final CI at `516000f`.**
  Added: model install from the app's own external folder (`adb push`, strict SHA-256
  importers, free-space check, named error, rejected ZIP kept and the previous model
  untouched); `tools/offline_kit.py` (assemble and verify the kit: APK + `gigaam-v3.zip` +
  `diarization.zip`, `SHA256SUMS.txt`, `KIT_MANIFEST.json`, rejects a different runtime or
  tampered/truncated files); `tools/phone_kit.py` (`check`, `install`, `monitor`, `scan`,
  `exports` over adb; exit 2 = NOT_RUN without a device); owner-triggered
  `build-apk-kit.yml` (one-day artifact, deleted by `fetch-apk`; not run by me because the
  artifact of a public repository is visible while it exists); UI: status, errors and
  progress moved to the top, recording timer with an honest background hint, model
  readiness hints. Docs: [OFFLINE_KIT.md](OFFLINE_KIT.md), [PHONE_ACCEPTANCE.md](PHONE_ACCEPTANCE.md).
  *Final CI at `516000f` (code; `d3e63c6` is docs only, its build also PASS):*

  | Check | Result | Link |
  | --- | --- | --- |
  | Android build, lint, core tests | PASS | [41536700135](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41536700135) |
  | Real offline Russian ASR, API 33 / 34 / 35 (x86_64) incl. `KitInstallTest` (2 tests) and UI flow | PASS x3 | [41536695619](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41536695619) |
  | UI flow: timer visible, HOME, screen off, WAV continuity (30.1/33.9/30.0 s of 32.7/36.6/32.9 s), no app/worker ANR/crash/kill | PASS x3 | same run |
  | 20-minute stress (API 33): diarization 141 s, ASR 58 s, RTF 0.17, app peak 607 MiB at ASR start, worker 447 MiB | PASS | [41536695421](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41536695421) |
  | Python tool tests (`test_phone_kit`, `test_app_failure_detector`, ...) | PASS | in the build and ASR runs |

  *Identities.* APK (debug, both ABIs, built in that run): 50 989 367 bytes, SHA-256
  `8e8d9babfd306002dddec842be8c9bfceaa04522e0e97d38696710cbac76ba2f`; version `0.1.0-alpha`
  (code 1). sherpa-onnx no-TTS runtime AAR `771fda6a4abf845a6f84f48e05e887fdf159671beb88cbc9aae327806511c1c8`
  (matches the packaged natives; ELF machine 183 = arm64 for the arm64-v8a libraries).
  GigaAM v3 CTC INT8 model SHA-256 `f86ebfa0429ced91be6054fc344827e9c6c2572f3c318416cd974b06f66437ec`
  (HF revision `32a4c7cc…fbec`); diarization: segmentation `220ad67c…1079` (revision `9403a690…`),
  ERes2Net `1a331345…5e4b`. The ZIP files themselves are not byte-reproducible (timestamps);
  the kit records their SHA-256 at assembly time and the app checks every file inside.
  The APK differs per build (debug signing key), so its hash is per build.
  *Blockers before a demo on a phone:* (1) no APK in hand: the owner must run
  `build-apk-kit.yml` (or install the SDK locally); (2) no adb and no phone on this PC:
  every ARM64 item is NOT_RUN (real Russian speech from 2 and 3–4 speakers, A–B–A, noise,
  background/lock-screen on a real device, 20-minute recording, MP3 import timing,
  airplane mode, thermals, real memory/RTF); (3) public APK/weights remain NO-GO
  (distribution/notices review); (4) the emulator microphone is silent, so no spoken
  recording was ever transcribed through `RecordingService` yet. *Go/no-go:* emulator
  pipeline GO; kit and tooling ready; phone demo NO-GO until PHONE_ACCEPTANCE is executed.
- **2026-11-03 (later) — kit install proven end to end; local APK; decisions.** Owner
  decisions recorded: licences no longer block work (notices stay), GitHub Actions is the
  main build environment, no public APK with weights. The repository-local toolchain
  (`.local/build-tools` JDK 17 and Gradle 8.9, `.local/android-sdk` 35) works, so the earlier
  statement that no JDK/Gradle/SDK existed on this PC was wrong; adb is still absent.
  *Local build* (`tools/build_local_apk.py`, 2 min): core tests PASS, APK 50 989 367 bytes
  (same size as the CI build, different debug-key hash `4cc085cb…5be4`), `check_apk.py`
  runtime digest and native bytes MATCH. *Kit assembled* at `.local/kit` (git-ignored; not
  uploaded): `gigaam-v3.zip` 224 723 056 B sha256 `ec90b0cc…f350`, `diarization.zip`
  45 599 554 B `5979f150…1a2f`, `SHA256SUMS.txt`, `KIT_MANIFEST.json`, `phone_kit.py`;
  `offline_kit.py verify` OK.
  *New regression found and fixed:* the collector shell-script test failed after the kit step
  was added to `run_android_inference.sh` (CI 41539483669/41539489279 red, no emulator
  reached); the step is now covered by the collector tests, including "never runs after an
  earlier failure" because it wipes app data.
  *End-to-end kit install on clean emulators* (`tools/run_kit_install_check.py`, run
  [41539803654](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41539803654),
  API 33/34/35 all PASS): clean app shows the missing-model hint; a corrupt `gigaam-v3.zip`
  pushed with `adb push` is rejected by name and kept; the real ZIPs install both models,
  are deleted, and the hint disappears. That also shows `adb push` into
  `Android/data/<pkg>/files/kit` works on Android 13, 14 and 15 emulators. The same run keeps
  the 16-check UI flow green (timer, HOME, screen off, WAV continuity, no app/worker
  ANR/crash/kill). Build runs [41539715602](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41539715602)
  and [41539808229](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41539808229) PASS.
  Application code is unchanged since `516000f` (later commits are tests, tools, docs), so
  its stress run [41536695421](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41536695421)
  stays valid. Still NOT_RUN: every physical ARM64 item; a spoken recording through the
  microphone (the emulator microphone is silent).
- **2026-11-03 (adb found).** adb 36.0.0 exists on this PC inside another program's Python
  environment (`adbutils` package binary); no device is connected. `phone_kit.py` now finds
  adb itself (`--adb`, `ADB_PATH`, PATH, Android SDK folders, the `adbutils` package, copies in
  per-user Python environments) without changing PATH, works with plain Python 3.8+, and falls
  back to `/sdcard/Download` plus on-screen instructions if a phone refuses writes to
  `Android/data`. 22 tests (adb discovery with fakes, install flow, tampered kit never touches
  the phone, wrong ABI refused, push fallback). The assembled kit was run from a clean folder
  outside the repository: `check`, `install` and `scan` all end as NOT_RUN (exit 2) with no
  device, after `install` verified SHA256SUMS. Earlier statements in this file that adb/JDK/
  Gradle/SDK were absent are superseded: JDK/Gradle/SDK live in `.local`, adb in the extension
  environment above. Documentation was brought up to date (README, README.ru, OFFLINE_KIT,
  PHONE_ACCEPTANCE, AUDIO_IMPORT decode budget) and [DEMO_READINESS.md](DEMO_READINESS.md)
  separates tested steps from NOT_RUN. A physical phone is still needed for every ARM64 item.
- **2026-11-03 (device re-check, no phone).** `adb kill-server`/`start-server`, `adb devices -l`
  (empty), `adb mdns services` (empty) and a Windows PnP listing: the only USB devices are a
  webcam with microphone (VID 1BCF) and a keyboard/mouse (VID 09DA); no Android, ADB, MTP or
  WPD device, so the phone is not reaching the PC at all (charge-only cable, USB mode, or not
  plugged in), not merely unauthorized. `phone_kit.py` got `wait` (polls adb, distinguishes no
  device / unauthorized / offline / several, prints the concrete action, then runs `check`) and
  the same explanations in every command; 24 tests PASS. ARM64 acceptance remains NOT_RUN.
- **2026-11-03 (phone seen by Windows; emulator bug).** An HONOR 10X Lite (DNN-LX9,
  VID_12D1 PID_107E) is now visible to Windows (composite, MTP, mass storage). The "HDB
  Interface" Code 28 reported by the owner's diagnostics is gone: official Huawei drivers
  `hw_goadb.inf` (2016-07-11) and `hw_gohdb.inf` (2015-12-28), signed by "Microsoft Windows
  Hardware Compatibility Publisher", are installed, the HDB node (subclass 0x48) is OK with
  WinUSB. No driver was installed by me. `adb devices -l` is still empty for the phone: the
  phone exposes MTP, mass storage and HDB but **no ADB interface (subclass 0x42)**, which
  appears only with USB debugging on. Bug found by the owner's diagnostics and fixed
  (`c01e54f`): `phone_kit.py` reported an `emulator-5564 offline` entry as a phone to
  reconnect. Emulators are now never candidates (not by serial pattern, not via `--serial`,
  not by `ro.kernel.qemu`/`ro.hardware` in `check`/`install`), they are named separately in
  the diagnostics; 8 regression tests (32 total) PASS. Physical acceptance: still NOT_RUN,
  waiting for USB debugging on the phone. Instructions: PHONE_ACCEPTANCE.md, "Драйвер Windows".
- **2026-11-03 — FIRST PHYSICAL RESULTS: HONOR 10X Lite (DNN-LX9), Android 10 (API 29,
  Magic UI 3.1.1), arm64-v8a, 3.6 GB RAM, USB cable, charging, Wi-Fi ON.** Evidence:
  [docs/evidence/physical-honor-dnn-lx9-2026-11-03/](evidence/physical-honor-dnn-lx9-2026-11-03/)
  (exports, scores, memory/battery series; no private audio: public acted clips only).
  *Setup.* Official Huawei drivers (`hw_goadb`/`hw_gohdb`, Microsoft WHCP-signed) were already
  installed; the owner enabled USB debugging, accepted the RSA prompt, the HONOR install
  confirmation and the Files-app biometric lock. `phone_kit.py check` PASS (not an emulator,
  arm64-v8a, SDK 29, 31.9 GB free). *Bug found only on this phone and fixed (`1a8d6ac`):* the
  adb-pushed model kit was not seen because on this phone `getExternalFilesDir` is the SD card
  while `adb push` writes internal storage; the app now scans all external files dirs
  (`getExternalFilesDirs`). After the fix the app installed both models itself ("Комплект
  установлен, SHA-256 проверен"); SHA-256 of the installed files read on the phone match the
  pinned values (`model.int8.onnx` 224 721 476 B `f86ebfa0…37ec`, `segmentation.onnx`
  `220ad67c…1079`, `embedding.onnx` `1a331345…5e4b`). Requested permissions on the device:
  RECORD_AUDIO, FOREGROUND_SERVICE(+MICROPHONE), POST_NOTIFICATIONS, **no INTERNET**.
  *Import → process → speakers → timecodes → export, through the real UI and the system
  document picker, on the phone:*

  | Clip (public, acted, Russian) | Audio | Speakers found | WER | cpWER | Turn order |
  | --- | --- | --- | --- | --- | --- |
  | D/M/D `aba.wav` (development probe) | 19.7 s | 2 | 1/41 (2.44%) | 1/41 (2.44%) | A-B-A correct, D→Speaker 1, M→Speaker 2 |
  | M-D-M-D holdout `aba.wav` | 42.2 s | 2 | 2/92 (2.17%) | 2/92 (2.17%) | M-D-M-D correct |

  TXT, JSON and SRT were saved through the system save dialog and pulled; the exports pass
  `verify_transcript_exports` (consistent, SRT/JSON/TXT agree); the JSON records the no-TTS
  runtime SHA-256 `771fda6a…c1c8`. Identical WER to the x86_64 emulator, as expected for the
  same model. DER: `NOT_SCORED`.
  *Speed and memory on the phone (monitor `dumpsys meminfo` every second ran during both, which
  itself loads the CPU; phone charging):*

  | Clip | model load | diarization | ASR | total | RTF | app PSS peak | worker PSS peak | battery |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | 19.7 s | 5.5 s | 26.4 s | 8.6 s | 40.6 s | 2.07 | 588 MiB | 235 MiB | 41→42 °C |
  | 42.2 s | 8.5 s | 95.9 s | 27.9 s | 132.2 s | 3.13 | 750 MiB | 308 MiB | 41→45 °C |

  **Finding:** the phone is 2–3x slower than real time end to end (emulator runners: 0.17–0.30),
  diarization dominates. A 20-minute recording would take on the order of 40–60 minutes here;
  for a demo keep recordings to a few minutes. Not yet separated from the monitor's overhead.
  *Still NOT_RUN on the phone:* airplane mode, speech through the microphone from 2–4 live
  speakers (needs the owner's voices), noise and interruptions, HOME/lock-screen recording,
  20-minute recording and long MP3/WAV import, permission denial, worker kill, low storage.
- **2026-11-03 (later) — inference threads and a privacy slip.** The phone has 8 cores
  (4 fast Cortex-A73 + 4 slow A53); the app used a fixed 2 ONNX Runtime threads. Measured on
  the phone, no monitor running, same APK otherwise (`InferenceThreads`, cap 4):

  | Clip | threads | diarization | ASR | model load | total | RTF |
  | --- | --- | --- | --- | --- | --- | --- |
  | 19.7 s | 2 (with monitor) | 26.4 s | 8.6 s | 5.5 s | 40.6 s | 2.07 |
  | 19.7 s | 4 | 17.8 s / 17.5 s (two runs) | 5.3 s | 5.4 s / 5.1 s | 28.5 s / 27.9 s | 1.45 / 1.42 |
  | 42.2 s | 2 (with monitor) | 95.9 s | 27.9 s | 8.5 s | 132.2 s | 3.13 |
  | 42.2 s | 4 | 63.5 s | 16.2 s | 6.3 s | 86.0 s | 2.04 |
  | 42.2 s | 8 | 101.4 s | 24.7 s | 8.3 s | 134.4 s | 3.18 |

  Four threads is the best of the three; eight is slower than two (the slow cores hold the
  work back). The first rows include the monitor's overhead, so part of the gain is not due to
  threads; the 4-thread rows were repeated without it. Output unchanged (same fragment and
  speaker counts; WER not re-scored for these runs). Emulators have 2 cores and keep 2.
  Still slower than real time: a 20-minute recording would take roughly 25–40 minutes on this
  phone. *Privacy slip, mine:* commit `df1a439` accidentally added `tools/device-evidence/phone-ui/`
  (screenshots and UI dumps of the phone). The XML dumps contain only public clip text and my
  test folder, but four screenshots show names of folders/files in the owner's personal
  Downloads. Removed from the branch and git-ignored in the next commit; they remain in the
  history of `df1a439` on the public remote until the history is rewritten (a force-push, which
  I did not do): owner's decision. The helper now writes to `.local/phone-ui-private/`.
- **2026-11-03 (night) — physical phone, real microphone, background and live dialogue.**
  Same HONOR DNN-LX9 (Android 10, arm64-v8a), APK `1a8d6ac`+ (4 inference threads). Evidence in
  [docs/evidence/physical-honor-dnn-lx9-2026-11-03/](evidence/physical-honor-dnn-lx9-2026-11-03/).
  *Recording through the real microphone and `RecordingService`:* microphone permission granted
  with `pm grant` (own debug app), recording started from the UI, timer and notification visible;
  `dumpsys` showed `isForeground=true` with the same process id after HOME (25 s) and with the
  screen off on the lock screen (about 6 minutes in total); the WAV grew at 31–32 kB/s
  (real time) while locked. After the owner unlocked, the recording was stopped from the UI:
  17 093 804 bytes = 534 s against about 535 s of wall time (timer 08:31 at 22:14:48), so no gap
  through HOME and the locked screen; the service ended with the recording. Not tested: OEM
  battery limits over a long time (about 9 minutes only), a recording of 20 minutes.
  *Processing that 8 m 54 s recording on the phone* (content unknown: room microphone, nobody
  scripted it; it stays on the phone): model load 8.9 s, diarization 494 s, ASR 104 s, total 607 s
  (RTF 1.14), 62 fragments and **17 speaker clusters**: do not read this as quality, but it shows
  that noise or unclear audio can produce many clusters (a risk to explain in a demo). Monitor
  during it: app PSS peak 567 MiB, worker 398 MiB, battery 42→47 °C while charging over USB,
  83→82 %. *Live read-aloud dialogue, two people, scripted*
  ([script](../tools/fixtures/live-dialogue-script-ru.json), 83 words, 43.7 s of audio):
  7 segments, speakers alternate A-B-A-B-A-B (A→Speaker 1, B→Speaker 2; the first A turn was
  split in two segments of the same speaker). WER = cpWER **4/84 = 4.76%** against the script as
  actually spoken (the reader reported adding the word "да" to turn 5, our mistake, not the
  recognizer's; this correction came from the reader, not from the recognizer output), and 5/83 =
  6.02% against the original script; all 4 remaining errors are word substitutions by the
  recognizer ("жарили"→"жарити", "немного"→"много", "прочитаю её"→"прочитай ее", "я"→"и").
  DER: `NOT_SCORED`. Airplane mode during this run: the owner was asked to enable it but did not
  say so and I could not verify it afterwards, so the run counts as **not verified offline**
  (the app has no INTERNET permission, checked on the device). Monitor tool now writes
  incrementally and survives unplugging (34 tests PASS).
  *Remaining NOT_RUN on the phone:* verified airplane-mode run, 3–4 speakers, noise and
  interruptions, 20-minute recording and long MP3/WAV import, permission denial, worker kill,
  low storage.
- **2026-11-03 (late) — airplane mode confirmed; 3–4 speakers and noise without recruiting
  people.** The owner stated that airplane mode **was on** during the live dialogue (reported by
  the owner; not independently verifiable afterwards), so that run counts as offline by the
  owner's report. The four recognizer errors of that run, in full: жарили→жарити, я→и,
  прочитаю→прочитай, немного→много (two of them, "я→и" and "прочитаю→прочитай", are easy to miss
  on screen). For 3–4 speakers the project's own handoff pointed to the open, MIT-licensed
  Russian dataset `ivkond/synthetic-speech-diarization-ru` (revision `3fa8404c…`, 2000 synthetic
  TTS dialogues with per-speaker text and times). Three tracks of shard 0 were rewritten as
  16-bit WAV (hashes: `syn3-clean` `7b5d5f9c…`, `syn3-brown` `942bfdf4…`, `syn4-noise`
  `93964807…`; audio not committed) and pushed to the phone, then processed through the same
  UI path (import → recognize → JSON export) by `tools/phone_run_clip.py` and scored by
  `tools/score_clip_run.py`. Synthetic voices and file import, **not** natural speech and not the
  acoustic path (no loudspeaker, no room): evidence in
  [synthetic-3-4-speakers/](evidence/physical-honor-dnn-lx9-2026-11-03/synthetic-3-4-speakers/).

  | Track (ref speakers, condition) | Audio | App speakers | Segments | WER | cpWER | Total time (RTF) |
  | --- | --- | --- | --- | --- | --- | --- | 
  | `syn3-clean` (3, clean) | 33.5 s | **4** | 7 | 4/52 (7.7%) | 18/52 (34.6%) | 51.2 s (1.53) |
  | `syn3-brown` (3, brown noise 16.8 dB) | 37.8 s | 3 (+2 segments left unknown) | 9 | 5/37 (13.5%) | `NOT_SCORED` (unattributed words) | 52.7 s (1.39) |
  | `syn4-noise` (4, crowd noise 23.7 dB) | 57.3 s | **5** | 12 | 11/76 (14.5%) | 33/76 (43.4%) | 95.4 s (1.66) |

  Reading: ASR errors stay moderate (8–15% on synthetic TTS with noise), but the speaker count
  is one too high in two of three tracks, which is what drives the cpWER; the noisy 3-speaker
  track got the right count and honestly marked two uncertain segments as unknown. DER
  `NOT_SCORED` (the export has no raw speech turns). With only three tracks this is a warning
  about over-splitting at threshold 0.8, not a measurement of accuracy.
- Next: physical ARM64 run (pick a phone from the team), a demo APK that needs no
  manual model ZIPs, GigaAM v3 e2e RNN-T for punctuation, Nemotron 3 versus pyannote,
  then VoxLock on overlap regions only. Details in issues #7 and #10.

## 2026-10-31 — bounded Binder-death fallback for repeated diarization

- Previously failed Android full threshold sweep 41128549290:
  DiarizationUnavailable on previous private worker exit, preserved.
- Code commit 5c2dae0: the previously linked remote Binder is now checked
  with two independent death observations: callback via linkToDeath() or
  isBinderAlive()==false. Both identify the exact bound remote endpoint.
  Cleanup waits up to 5 seconds and subsequent processing up to 15 seconds;
  a still-alive/unknown worker blocks. No guessed PID, kill, blind retry,
  model weights or clustering threshold changed.
- Two complete Android multi-worker development sweeps PASS:
  https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41154762491
  https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41155171064
  Independent artifact recheck: each Android JUnit 1/1 pass, 0 failures;
  three-clip D-M-D voice recurrence PASS, WER/cpWER 1/41.
  The old 0.9 comparator still collapses voices.
- Independently checked production-only disjoint four-clip holdout PASS:
  https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41155174621
  JUnit 1/1 pass; M-D-M-D recurrence PASS, WER/cpWER 2/92, no parameter
  sweep; DER NOT_SCORED (no independent ground-truth speech boundaries).
  Offline Russian ASR/instrumentation
  https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41154762511
  PASS, both Android APK build jobs 41154762500 and 41154766825 PASS.
  All six runs are exactly at code SHA 5c2dae0; 44 local Python methods PASS.
- Exact original WAV hash, invocation per run, reference/hypothesis JSON
  SHA-256, independently recalculated scores and actual Android JUnit reports
  verified. Machine-readable report:
  docs/evidence/lifecycle-binder-recovery-20261031.json.
- These are three successful sessions and do not prove that an intermittent
  worker lifecycle error cannot return. No physical ARM64, real noisy
  conversations, overlap/DER acceptance, phone performance or complete
  redistribution review. Public APK upload stays disabled, PR #6 draft,
  contest verdict NOT_READY.

## Disjoint acted holdout — first measured production-only Android result

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
  The first independent-from-development-clips Android x86_64/API 33 run
  41127309893 at 423eed6 **PASS**: WER 2/92 = 2.17%, cpWER 2/92 =
  2.17%, 4/4 M-D-M-D speaker recurrence and all six same/different
  source-clip pair checks PASS. Inference 16,596 ms on 42,237 ms recording
  (emulator RTF 0.393). DER NOT_SCORED, as no boundary reference exists.
  Independently downloaded evidence was checked against both JSON hashes,
  invocation ID, locked audio hash, no sweep, and JUnit (1 test, 0 failures).
  Run: https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41127309893
  Saved machine-readable result: docs/evidence/holdout-first-run-20261030.json.
  A separate previous development sweep 41127281473 FAILED on
  unconfirmed Binder death of the previous worker, known intermittent
  lifecycle risk; do not relabel this old failure as a PASS. The production-only
  holdout used one worker request and completed normally.
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


## 2026-11-12: TitaNet rejection diagnosis on PC

- Reproduced initial 14/60 accepted; longer two-excerpt evidence (16 s per half, same .84 threshold) admitted 28/60. Contiguous-only gave 6/60; 80 ms boundary trimming gave 16/60.
- Other 66 cached files: 33/81 to 73/81. Actual cached C2 turns, 15 files: 12/30 to 26/30. No observed accepted-profile pairwise false accepts; not a population safety or global-link recall result.
- Corrected compact initial pair count from 83 to 88; original detailed scorer already had 88.
- Four extraction regressions pass. No product/default/thermal changes. Candidate needs full global-policy replay and Android cost validation.
- See docs/TITANET_REJECTION_DIAGNOSIS_2026-11-12.md and docs/evidence/titanet-excerpt-length-20261112.json.
- Full host global-policy replay on C2: longer evidence yields 7/7 correct admitted returning probes (baseline zero admitted returning probes), no false links/mixes/collisions observed. Android cost remains unverified.

## 2026-11-12: Longer experimental profiles validated on Android emulator

- Two disjoint samples now allow16s each; ordinary global speakerbook remains OFF and identity thresholds/physical thermal guards unchanged. Host replay mirrors400 frames/sample; historical diagnostic current mode stays200 frames.
- All4 emulator cases passed in run43178565587 at ea5095b. Long20m40s:268331ms,252 segments,5 profiled blocks,21 unknown segments, full coverage.
- Paired warmed native benchmark on identical60s/C2 turns:683.844ms to861.335ms median (+25.95%, ~177ms),2 accepted profiles with either budget. This is TitaNet-only emulator cost, not HONOR performance.
- Initial Linux scorer failed from a slice typo; fixed and covered by fifth selector regression. Windows actualC2 replay26/30 admitted and7/7 correct returning links. Host-only workflow rerun avoids repeating unchanged Android jobs.
- Evidence: docs/evidence/titanet16-android-validation-20261112.json. No natural-conversation safety/physical endurance claim.

## 2026-11-12: Human actor/style verification, keep global linking disabled

- Dialogs:129 new selected utterances,112 available/17 missing at pinned revision;35 actor/style groups,3 actors,12 styles,711.395s input. OpenRAIL license attached.
- Native TitaNet:8s cap4/35 admitted versus16s14/35. Candidate11 admitted returns:8 correct links,3 false splits,0 observed false links/mixes;65 correlated negative pairs. Four insufficient groups.
- Acted studio utterances regrouped by actor/style, not spontaneous C2/DER evidence. Veche forbids voice profiling/re-identification; DAI is access-gated; commercial cards provide no free audio. No access request or third-party contact performed.
- Decision: keep ordinary global speakerbook OFF. Eligible natural-conversation data and physical endurance remain open.
- See docs/SPEAKER_LINK_ACCEPTANCE_2026-11-12.md. Eleven existing guards and result accounting passed. No app, threshold or thermal changes.

## 2026-11-12: Three-model frozen-policy comparison

- Compared pinned TitaNet Small/Large and bilingual CAM++ Advanced on identical16s-capped profiles and unchanged .84/.07 gates. All native models completed with no Android/phone work.
- Dialogs admission14/13/12; correct admitted returns8/11,9/10,5/9. Oracle bookmix admission28/30/31; actual C2 admission26/28/28. No observed wrong links/mixed global IDs. Correlated, admission-dependent trials are not population safety.
- Identical4.527s warm control median56.2/161.4/66.9ms; ONNX40.3/101.4/28.3MB. Large has no compelling mobile benefit; CAM++ gains bookmix coverage but loses style robustness under existing policy. No independently calibrated optimum claimed.
- Decision: retain Small, ordinary global linking OFF. Metrics/licenses/source pins and reproduction: docs/SPEAKER_MODEL_COMPARISON_2026-11-12.md. No audio/weights/embeddings committed.
- Archived41-utterance Dialogs preview comparisons found: the preceding seven-original-file exclusion did not establish an untouched utterance holdout. Clarification recorded in acceptance report.

## 2026-11-12: Dual-anchor return-only verification implemented

- Experimental Small path now retains paired temporal evidence. New enrollment still needs .84 mutual agreement; disagreeing pairs can only reuse the same earlier ID after both independent anchor/centroid .84 similarity and .07 margin checks. No rescue enrollment or centroid adaptation. Ordinary flag stays OFF.
- IPCv2 requires both192D arrays and independently bounded3..16s durations; unknown/corrupt optional identity is dropped without discarding valid ASR/diarization.
- Host assignments14->15/35 Dialogs and28->31/60 oracle bookmix; actual C2 remains26/30. Correct admitted returns8/11->9/12,6/6->9/9,7/7 unchanged. No observed wrong links/mixed IDs; not population safety.
-1702 constructed disagreeing speaker-switch pairs:0 wrong rescues (810 pairs have both sources enrolled). Kotlin/Python parity:72 identical assignments across47 blocks; private vectors deleted.
- All20 core groups and local experimental app/test APK builds pass. Android end-to-end verification pending. See docs/DUAL_ANCHOR_VERIFICATION_2026-11-12.md.

- Final Android evidence: all4 emulator cases PASS on29ada9d in run43254970270; IPCv2 repeat/negative/absent-model controls and cleanup verified. Long20m40s:370038ms,252 segments,21 unknown,5 profiled blocks, time/end coverage pass. Uncontrolled separate-runner timing, not HONOR performance.
- Linux host baseline and16 Python guard/policy tests PASS; normal Android/core build PASS. Android rescue-quality recall is not independently scored; host/Kotlin gains remain limited. Ordinary feature stays OFF. Metadata: docs/evidence/dual-anchor-20261112/android.json.
