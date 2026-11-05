# HONOR ARM64 — фактическая приёмка 6 ноября 2026

**DEVICE PIPELINE PASS; полная запрошенная приёмка НЕ завершена.**
Реальные A3+C2, микрофон, экспорты и lifecycle выполнены на HONOR DNN-LX9 /
Android 10 / ARM64. UI file picker защищён Huawei App Lock и требует обычной
аутентификации владельца. Пароль не вводился, защита не обходилась.

Код: `c05127c366511ad50fa2d41f8cbf4c9c83021a08`, ветка
`qa/honor-acceptance-20261106`, исходный main `a10dd395`.
[Машинный агрегат с измерениями](evidence/honor-acceptance-20261106/summary.json).

## Сохранность и установка

Git был чистым; текущих Gradle/ADB install и других агентов сессии не обнаружено.
Работа выполнена в существующем репозитории, без нового worktree, `codex exec`,
push, merge, платных сервисов или установки нового SDK.

Stable `ru.neurostenographer.app` **не заменялся**, uninstall/clear data не было.
Версия остаётся `0.3.3-contest`, versionCode 6. SHA фактического APK до, в середине
и после испытаний: `5ba1f0c5545f48f21a3eb1dcd9da869c5a234c0e2c8395d3fb610019754d3bb0`.
Приватное хранилище stable не читалось: это не побайтовый аудит пользовательских данных.

После просмотра diff из `4214d1044c7ce2939068ed27dfeebaa722f5b8bc` перенесены
только отдельный QA package, C2 generation retention, speaker-count assertions
и GigaAM MIT notice. VoxLock/fusion и остальные research-инструменты не перенесены.
Добавлены реальные lifecycle/acoustic tests и helper pinned fixtures.

Старый `.solhigh` имел иной hash при том же versionCode. APK извлечён и проверен
`apksigner`; сертификат совпал с обновлением и AndroidTest:
`a2e6ab1bec795c358c94a51561c64322e2f8cf705da533051e52c9dd3294052c`.
Выполнен update с сохранением данных: уникальный staging-файл → phone SHA →
один `pm install -r -t` с лимитом 1200 s → `pm path`, metadata и installed SHA.
Прежняя uncertain installation не повторялась вслепую. Расширенный AndroidTest
ждал обычных кнопок «ПРОДОЛЖИТЬ» и «УСТАНОВИТЬ» в Package Installer; перед
подтверждением проверено точное имя `.solhigh.test`. Настройки безопасности,
сети и системная громкость не менялись.

| Артефакт | SHA-256 |
|---|---|
| Установленный app QA, 367953218 bytes | `01edec85369562f786c62ea5964ddf08f0fd48bda2c5b876f2764625a1bbe42a` |
| Первый AndroidTest, 3 теста | `8d7893811301ab1e61e80b2fc49269653bc3f15632381cfa3e44191ebc3c3fb2` |
| Расширенный установленный AndroidTest | `1671f34c936fdf811c09ee9539932ab9fb3a576b88a2403f110fb41bf5e92ebb` |
| App APK из текущего repo | `fb79aa976a8ad61bc530a5abdbbf716f276b946ef662e28841e75bf441593dc0` |

Два app APK имеют **одинаковые имена и SHA всех ZIP entries**: DEX, manifest,
ресурсы, модели, лицензии и JNI. Полные SHA контейнеров после incremental
packaging различаются; побайтовая воспроизводимость APK НЕ подтверждена.
Строгая локальная проверка полного SHA завершилась ошибкой; затем независимо
сопоставлены все entries. На телефоне оставлен проверенный `01edec85…`.
AndroidTest имеет 215111460 bytes при небольшом текущем наборе entries:
incremental ZIP сохранил свободное место после прежних assets. Он не предназначен
для публикации. QA sourceSets теперь берёт отдельную `.local/solHighTestAssets`.

## Исполненные gates

| Gate | Результат и граница |
|---|---|
| Core + app + AndroidTest build | **PASS**, 16 core groups; финальный build 73 tasks / 39 s. Первый полный 6m44s, промежуточный 1m28s |
| Исходная instrumentation | **PASS**, `OK (3 tests)`, 70.659 s: pipeline/exports, corrupt C2 replacement, denied mic/malformed inputs |
| Расширенная instrumentation | **PASS**, `OK (4 tests)`, 148.557 s; ровно четыре success status, нет failure/abort markers |
| 2/3/4 speakers, A-B-A | **PASS** на синтетических DEV fixtures; последовательность `Speaker 1 → Speaker 2 → Speaker 1` |
| Лицензированный acted DEV | **PASS** для выполнения pipeline, двух speaker IDs, bounds и exports; не human gold |
| Тишина | **PASS**, 8 s, 0 speakers / 0 segments, ASR не запускался |
| Corrupt/empty/truncated/over-duration WAV | **PASS**, предыдущий выбранный файл сохранён |
| JSON/TXT/SRT | **PASS**, реальные prepareExport/finishExport и Android ContentResolver с file URI, 15 exports, UTF-8/truncation/text/ID/intervals. Четыре непустых набора дополнительно сверены независимым Python reader |
| Замена C2 во время inference | **PASS**, 120 s PCM / 45 turns, worker активен после публикации новой generation, старый model hash сохранён, исходный worker завершился с speech turns |
| Worker death/cancel/recovery | **PASS**, намеренный SIGKILL только QA worker; caller жив, отмена освобождает worker, повторная C2-тишина пуста, staged PCM очищен |
| Микрофон/reopen | **PASS**, реальные PCM16 mono 16 kHz WAV: 19.940 s и 1.940 s |
| Публичный acoustic probe | **PASS**, MediaPlayer внутри QA → динамик/MIC → C2 → A3: 3 segments, 4 известных контрольных слова; это не WER естественного разговора |
| UI recording/background/stop | **PASS для capture**, обычный permission dialog, HOME и возврат: WAV 73.700 s / 16 kHz успешно обработан. Речь с динамиков Windows не дошла, результат 0 segments; это НЕ acoustic speech PASS |
| Полностью локальный runtime | **PASS**, фактический APK без INTERNET; read-only airplane=1, Wi-Fi=0; offline assets/pinned JNI |
| Crash/ANR наблюдение | **PASS в собранной области**, 11 PID-filtered logs без FATAL/ANR markers, QA отсутствует в lastANR snapshot; intentional SIGKILL учтён отдельно |
| UI SAF import/export | **NOT_RUN / BLOCKED**, Huawei App Lock; File URI tests не заменяют UI picker |
| Screen-off / новый длительный full pipeline | **NOT_RUN**, 120 s выше — отдельный C2 lifecycle test |
| Независимый human WER/cpWER/DER | **NOT_SCORED**, новой человеческой разметки нет |
| 16 KiB device | **NOT_RUN**, HONOR имеет страницы 4096 bytes; известный ORT-Java ELF alignment дефект не исправлен |
| CI нового коммита | **NOT_RUN**, push не разрешён; исторический [main CI 41942088669](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41942088669) |

Первый сборщик crash-логов завершился ошибкой: Android 10 отверг `logcat --uid`.
JUnit-вывод сохранён; последующий сбор использовал поддерживаемый `--pid`.
Ограниченный набор PID и lastANR snapshot не доказывают отсутствие всех сбоев
на устройстве во все моменты времени.

## Измерения

| Файл | Audio / wall, ms | Speakers | WER DEV | Строгий cpWER |
|---|---:|---:|---:|---:|
| Synthetic A-B-A | 12950 / 14049 | 2 | 5.88% | 5.88% |
| Synthetic 3 clean | 33507 / 19351 | 3 | 5.77% | 5.77% |
| Synthetic 4 noise | 57324 / 26257 | 4 | 15.79% | NOT_SCORED: Unknown |
| Silence | 8000 / 5316 | 0 | не определён | не определён |
| Acted DEV | 19655 / 14469 | 2 | 0% | NOT_SCORED: Unknown |

Scorer: NFKC/lowercase/ё→е/Unicode words, без разворачивания цифр. Это известные
development probes, не независимый holdout и не общая точность. Наличие N IDs
не доказывает правильную атрибуцию всех слов. Unknown остаётся Unknown; DER
не считается из ASR fragment boundaries.
Источники: [synthetic dataset pin](https://huggingface.co/datasets/ivkond/synthetic-speech-diarization-ru/tree/3fa8404cfde61d2e3a3369000ce771747821e844),
[acted DEV pin](https://huggingface.co/datasets/langswap/dialogs-ru-emotional-conversations/blob/a74ff44d8d27ca3d21098ea3ed4d31a32923fbdd/test.csv).
Синтетика — MIT по dataset card; acted — Dialogs OpenRAIL, полная копия условий
в существующем локальном benchmark kit. Аудио не добавлено в Git.

Наибольшие внешние наблюдения: app **1071503 KiB**, worker **387062 KiB**;
максимальная сумма одного раунда **1071503 KiB**, не сумма отдельных максимумов.
61 раунд / интервал 2 s; разница чтений в пиковом раунде 470 ms. Есть также
250-ms sampler основного процесса. Это fixture suite с instrumentation и
повторными загрузками, не изолированный release benchmark; пики между samples
не исключены. Батарея 100→100% при питании, температура 36→38 °C.
Thermal stress и расход батареи не измерялись.

## Воспроизведение

`python -X utf8 tools/prepare_honor_acceptance.py` (также проверен с `-O`)
сверяет пять pinned hashes и готовит fixtures из существующих публичных
`.local/synthetic-ru` и лицензированного `.local/dialogue-benchmark`.
Downloads и приватные записи helper не использует. С существующими
JDK 17 / Gradle 8.9 / SDK 35, pinned no-TTS runtime и product assets:

```powershell
gradle --offline --no-daemon --max-workers=2 `
  -PsolHighAcceptance=true -PasrA3=true -PnemotronProduct=true `
  -PlocalDebugStore=<workspace-owned-debug-key> `
  :core:runCoreTests :app:assembleDebug :app:assembleDebugAndroidTest
# Только после package/signature/SHA audit и однозначной установки:
adb -s $serial shell am instrument -w -r -e class `
  ru.neurostenographer.app.SolHighAcceptanceTest `
  ru.neurostenographer.app.solhigh.test/androidx.test.runner.AndroidJUnitRunner
# Сначала отрицательный mic test выше, затем обычный UI mic grant, затем:
adb -s $serial shell am instrument -w -r -e class `
  'ru.neurostenographer.app.SolHighAcceptanceTest#fixturePipelineAndExports,ru.neurostenographer.app.HonorLifecycleAcceptanceTest' `
  ru.neurostenographer.app.solhigh.test/androidx.test.runner.AndroidJUnitRunner
```

Первый класс требует denied mic. После разрешения микрофона он не является
безусловно повторяемым: не сбрасывать разрешение/данные ради зелёного теста.
Пять fixtures должны быть подготовлены до первого запуска; первоначальный
архивный 3-test APK содержал четыре fixtures, расширенный — пять.

Exact commands, start/end/status, install reconciliation, APK copies,
source/model/JNI/DEX hashes, PSS, exports и logs находятся в ignored
`.local/honor-acceptance-20261106/`. Ошибки ранних проверок сохранены.
Микрофонные записи остаются приватными в QA package. Raw audio/transcripts/logs,
serial, debug keys и APK не входят в публичный агрегат.

Следующий блокер — обычная аутентификация владельца в App Lock для проверки
системного file picker. Естественная речь с ручной разметкой, новая длинная
запись и 16 KiB runtime остаются отдельными gates. Автоматического GC старых
C2 generations пока нет: прежний model сохраняется ради in-flight worker.
