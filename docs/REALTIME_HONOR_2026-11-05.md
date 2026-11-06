# Realtime на HONOR: эксперимент, 05.11.2026

**Вердикт: NOT_READY.** Отдельный рабочий прототип реализован, собран и частично проверен на HONOR. Конкурсная версия не заменялась. Продвигать realtime в основной режим нельзя: короткие чанки ухудшили диаризацию; окончательный APK после исправлений ещё не установлен из-за защищённого PIN экрана.

Ветка: `feature/realtime-honor-20261105`, исходная ревизия `a10dd39`. Все изменения — в этом worktree. Чужие worktree и процессы не изменялись. Push, PR, merge и публикации не выполнялись.

## Артефакты и воспроизведение

- Финальный подписанный debug APK: `app/build/outputs/apk/debug/app-debug.apk`, пакет **`ru.neurostenographer.app.realtime`**, отдельный debug-сертификат. SHA-256: **`6e0730f5ca891d42f787b561ceac328fcf6f3a27c71ccf9cad46ff79a86e6231`**, 368 745 173 байт. Модели внутри, INTERNET отсутствует. [Проверка APK](evidence/realtime-honor-20261105/final-apk.json), [сертификат](evidence/realtime-honor-20261105/final-apk-signature.txt).
- APK, на котором получены последние телефонные цифры: **`7a9ff20a809311061b92429c767dda969b87fc114cf32f42cee7539d301d85f3`**. [Фактически установленные байты](evidence/realtime-honor-20261105/app-apk.json). Исправления после этого APK проверены сборкой/ядром; телефонный результат на них не переносится автоматически.
- [Сводные измерения](evidence/realtime-honor-20261105/summary.json), [последняя сборка](evidence/realtime-honor-20261105/final-build.txt), [хэши исходников](evidence/realtime-honor-20261105/source-manifest.json).

Команды из корня worktree, PowerShell. `$adb` — путь к уже установленному официальному `adb.exe`, `$serial` — серийный номер именно разрешённого HONOR; в публикуемых материалах он скрыт.

```powershell
python -X utf8 tools/realtime/diagnose.py --adb $adb --serial $serial --out .local/baseline-refresh.json
python -X utf8 tools/realtime/provision_vad.py
python -X utf8 tools/realtime/build.py :core:runCoreTests :app:assembleDebug :app:assembleDebugAndroidTest :app:lintDebug
python -X utf8 tools/realtime/inspect_apk.py
python -X utf8 tools/realtime/make_fixtures.py
# Следующие две команды — после обычной разблокировки телефона владельцем:
python -X utf8 tools/realtime/phone.py --adb $adb --serial $serial install
python -X utf8 tools/realtime/phone.py --adb $adb --serial $serial fixtures
python -X utf8 tools/realtime/phone.py --adb $adb --serial $serial run --label syn3-fast300-final-r1 --clip syn3-clean --pause 300
python -X utf8 tools/realtime/phone.py --adb $adb --serial $serial run --label syn3-fast500-final-r1 --clip syn3-clean
python -X utf8 tools/realtime/phone.py --adb $adb --serial $serial run --label syn3-fallback500-final-r1 --clip syn3-clean --fallback
python -X utf8 tools/realtime/phone.py --adb $adb --serial $serial run --label mic20min-final-r1 --method foregroundMicrophoneScreenOff --mic-seconds 1200 --timeout-seconds 1320
```

Каждый запуск требует новое `--label`, прежние evidence не перезаписываются. Доступны методы `c2OfflineParity`, `damagedC2KeepsAsrAlive`, `cancellationRecoveryAndRestart`, `microphoneCaptureOnlyAndRestart`; дорожки `single`, `aba`, `syn3-clean`, `syn3-brown`, `syn4-noise`, `overlap`, `silence`. Производные probes создаются только из уже имеющейся MIT-синтетики, с сохранёнными рецептами/ссылками/хэшами в [fixture-references](evidence/realtime-honor-20261105/fixture-references). Их подготовка не означает выполнения на телефоне.

```powershell
python -X utf8 tools/realtime/host.py
python -X utf8 tools/realtime/analyze.py
# Регрессия продукта, realtime выключен; этот unsigned APK НЕ устанавливать:
python -X utf8 tools/realtime/build.py --variant product :app:assembleRelease :app:lintRelease
```

Сборщик использует существующий JDK 17 / Gradle 8.9 / SDK 35, копию кэша внутри worktree, offline Gradle и собственный debug-ключ. Производственный signing key не читается. Штатные подтверждения установщика HONOR нажимаются только для проверенного пакета/названия приложения; настройка неизвестных источников, защитные механизмы и PIN не обходятся.

## Что реализовано

- `-Prealtime=true -PasrA3=true -PnemotronProduct=true`: отдельный package, экран и foreground service. Старые импорт, batch ASR/C2, история и экспорт доступны в том же тестовом приложении; без флага realtime продуктовый манифест не содержит новый экран/service.
- `AudioRecord` 16 кГц, mono PCM16, чтения до 512 отсчётов / 32 мс. Поток захвата пишет WAV и lock-free ring на 60 с, не вызывает модели. При отставании inference читает сохранённый PCM с диска; аудио из-за переполнения ring не теряется. Максимум нового захвата — 60 минут; старый batch-импорт ограничен прежними 20 минутами.
- WAV сохраняется отдельно от стенограммы. Существующий файл нельзя нечаянно открыть на перезапись. Незавершённый PCM остаётся для восстановления заголовка после гибели процесса; автоматическое возобновление inference после рестарта не заявляется. Восстановленный/завершённый WAV до 20 минут можно явно передать в прежний batch-режим.
- Silero VAD через реальный sherpa-onnx, 512 отсчётов; паузы 300/500 мс при одинаковом лимите фразы 15 с, тихий forced cut по `QuietCuts`. Один финальный ASR decode на фразу, без секундных partials. A3 recognizer живёт всю сессию; streams освобождаются после каждого decode.
- C2 получает только захваченный акустический префикс, включая 256 отсчётов правого контекста STFT. EOF-padding разрешён только в конце. FAST: `chunk=45/right=6`, FALLBACK: `120/13`; общий FIFO 264, update 222, speaker cache 264. Переключение сохраняет кэш и IDs сессии. Исходный offline `340/40/40/300` сохранён.
- Один inference worker, очередь до трёх фраз, ASR выше C2. Отставание >5 с/тепловая нагрузка переводят C2 в FALLBACK с гистерезисом. Android 10 использует thermal status API 29 и температуру батареи, без API 30 thermal headroom.
- Новый текст сначала имеет неизвестного говорящего; после C2 обновляется по токенам A3 через `TranscriptFusion`, с честными overlap/unknown. Прошлая атрибуция замораживается за завершённой границей, чтобы часовая история не переразмечалась квадратично на каждом шаге. При недоступности C2 ASR продолжает без новых speaker claims.
- Foreground lifetime/wakelock отделены от Activity; предусмотрены HOME/поворот/выключенный экран, отмена, ошибки AudioRecord и системное silencing. Эти пути имеют разный объём реальной проверки, см. ниже.

## Проверено на настоящем HONOR

[Первичная read-only диагностика](evidence/realtime-honor-20261105/baseline.json): DNN-LX9, Android 10/API 29, ARM64, страницы 4096, ~32 ГБ свободно, батарея 100%, 35 °C. Авиарежим 1, Wi-Fi 0, Bluetooth 1 — уже такие; настройки связи не менялись. Активной записи, C2 worker или чужой сборки перед началом не обнаружено.

На одной и той же `syn3-clean`, 33,507 с, SHA `7b5d5f9c…c4ce9`, реальные модели на телефоне, подача PCM в темпе записи, **не микрофон и не естественная встреча**:

| Измерение | FAST 4,1 с, пауза 500 мс | FALLBACK 10,6 с, пауза 500 мс |
|---|---:|---:|
| Instrumentation / точность сохранённого PCM / pacing | PASS / exact / valid | PASS / exact / valid |
| Загрузка моделей, с | 9,681 | 6,933 |
| ASR / C2 / VAD, с | 6,320 / 14,992 / 1,255 | 6,557 / 7,527 / 2,251 |
| **Compute RTF**, без загрузки и ожидания входа | **0,674** | **0,488** |
| От начала capture до завершения, с | 39,003 | 37,069 |
| Конец окна ASR → готовый текст, p50 / p95, с; 8 фраз | 3,458 / 7,795 | 1,416 / 4,838 |
| CPU процесса, с; загрузка моделей включена | 97,301 | 67,977 |
| Максимум снятых срезов PSS, МиБ; не гарантированный абсолютный пик | 1061,1 | 920,9 |
| Температура батареи во время прогона, °C | 36…36 | 36…37 |
| WER | 3/52 = 5,77% | 3/52 = 5,77% |
| Говорящие в тексте / эталон | **2 / 3 — регрессия** | 3 / 3 |
| Строгая cpWER | NOT_SCORED: есть неизвестные слова | NOT_SCORED: есть неизвестные слова |

Latency измерена от конца **входного окна фразы**, с его padding, а не от вручную размеченного акустического конца речи. Включает стартовую загрузку моделей; UI-render latency отдельно не инструментирована. CPU seconds — накопленное время всех потоков, не процент одного ядра. Телефон на зарядке: энергетическую эффективность по заряду не выводим. Это по одному пригодному прогону, не оценка устойчивого распределения.

Доказательства: [FAST](evidence/realtime-honor-20261105/syn3-fast500-r3-foreground), [FALLBACK](evidence/realtime-honor-20261105/syn3-fallback500-r1). Независимая проверка согласованности реальных JSON/TXT/SRT — PASS. Слова не подставлялись из reference в приложение.

RAW C2 позволяет отдельно посчитать DER против **широких исходных TTS-интервалов**: 57,14% FAST и 44,07% FALLBACK, collar ±250 мс, overlap учитывается. В них около 9 с пропусков относительно широких интервалов, включающих паузы; это не DER по человеческой разметке. На том же эталоне host offline C2 — 31,95%, host FAST — 57,21%, FALLBACK — 43,97%. Даже с этим ограничением качество коротких чанков не оправдывает замену batch.

### Сохранённые проблемы испытаний

- [Первый запуск](evidence/realtime-honor-20261105/syn3-fast500-r1) завершил inference и проверку PCM, но wall 283,737 с / compute RTF 4,90. Pacing не инструментирован; `dumpsys meminfo` зависал и вызывал GC, приложение сначала было невидимым, затем выведено на экран вручную. Такой прогон не считается realtime PASS и не используется в сравнительной таблице.
- [Повтор с kernel PSS, без видимого Activity с начала](evidence/realtime-honor-20261105/syn3-fast500-r2-kernel-monitor) — **FAIL: Producer stuck**. Последний checkpoint CANCELLED, загрузка 194 с. С foreground Activity и проверкой pacing получен нормальный третий запуск. Причины GC/OEM scheduling не разделены полностью; одна замена измерителя проблему не решила. В финальном harness дополнительно удерживается собственный foreground service, но эта правка на телефоне ещё NOT_RUN.
- [Микрофон, HOME и экран off, 20 с](evidence/realtime-honor-20261105/mic-screenoff-20s-r1): service реально был foreground, сохранено **319 040 отсчётов / 19,940 с**, 638 124 байта, hardware frame position тоже 319 040, max read gap 143 мс. Аудио не распознавалось и не выгружалось. **Весь тест FAIL**: Magic UI отключил UiAutomation, и AndroidJUnitRunner упал в `finally`/`finish`. Метаданные capture PASS не подменяют этот FAIL. Harness исправлен: HOME/off/wake выполняет внешний ADB, а не UiAutomation внутри теста. Исправление на телефоне ещё NOT_RUN.
- Экран восстановлен в awake, но защищённый keyguard теперь `secure=true/showing=true`. Обычная разблокировка владельцем нужна для следующего штатного подтверждения установки. PIN не запрашивался, root/bootloader/защита не менялись. Запрос владельцу отправлен; к моменту checkpoint ответ не получен.

## Проверено на ПК — отдельно от телефона

- Финальная сборка APK + instrumentation + lint + `runCoreTests`: **PASS**, lint 0 ошибок / 1 прежнее предупреждение UsableSpace. [Лог](evidence/realtime-honor-20261105/final-build.txt).
- Продукт A3+C2 с realtime **выключенным**: `assembleRelease lintRelease` **PASS**, unsigned APK не устанавливался. [Лог](evidence/realtime-honor-20261105/product-regression-build.txt), [манифест](evidence/realtime-honor-20261105/product-regression-apk.json).
- Реальный journal: >70 с PCM, вытеснение начала из 60-секундного ring, чтение с диска, побитовое сохранение порядка/числа отсчётов, отказ перезаписать существующий WAV, восстановление незавершённого файла — PASS.
- Ядро: 20/60-минутные потоки с паузами 300/500, короткая речь/тишина/EOF, лимит фраз, bounded queue, backpressure, cache pressure, overlap/unknown, часовая ограниченная активная атрибуция — PASS. Это authored tests, не качество живой речи.
- **Настоящий C2 через ORT 1.17.1 на Windows**, [host-native-c2](evidence/realtime-honor-20261105/host-native-c2): исходный offline и новый OFFLINE config совпали по canonical turns точно. FAST/FALLBACK работают на тех же байтах модели/PCM. 20 мин ускоренного зацикленного synthetic input, FAST → FALLBACK после трёх вызовов: 127 calls, max context 525, 78,618 с вычислений. 60 мин FALLBACK: 376 calls, max context 528, 253,772 с вычислений. В обоих три кластера и ноль чтений будущего контекста. ASR/микрофона/Android в этих длинных испытаниях нет.

## Сохранность и границы готовности

Защищённые APK до/после одинаковы: основной `5ba1f0c5545f48f21a3eb1dcd9da869c5a234c0e2c8395d3fb610019754d3bb0`, `.c2candidate` `fbe7f3cc2642519c5afe6ad1be39e4c593b816d7f342a2c8b9e04641fed667a8`. [Повторная инвентаризация](evidence/realtime-honor-20261105/preservation.json) содержит также список моделей внутри установленных APK; проверенный экспериментальный APK сохранён локально как `.local/tested-phone-v5.apk`. Команд clear/uninstall/update для защищённых пакетов не было. Приватные sessions этих приложений не читались и побайтно не сравнивались; изоляция обеспечена отдельным applicationId. Собственные захваты тестового приложения оставлены на телефоне, аудио в Git отсутствует.

Realtime native работает в одном процессе с захватом: обычные ошибки C2 дают unknown fallback, но hard native crash не изолирован отдельным процессом. Восстановление WAV сохраняет записанные байты, а не обещает восстановить несчитанный аппаратный буфер. Старый batch с изолированным worker сохранён.

**NOT_RUN / ещё требуется:** повторить финальный APK после разблокировки; 300 против 500 мс на одинаковых условиях; 0/1/2/4 голоса и authored overlap на телефоне; C2 damaged-load/отмена/restart и offline parity на телефоне; новое screen-off испытание; настоящие 10/20/30/60 минут с полным A3+C2 scheduler и мониторингом; реальное OS audio interruption и процесс-death recovery; естественные русские 2–4 голоса с независимой ручной разметкой; длительные нагрев/энергия и OEM policy. Подготовленные тесты или успешная компиляция не повышают эти пункты до PASS. API/устройства с 16-КБ страницами остаются отдельным прежним ограничением ORT Java.

Все inference офлайн, платных API/услуг нет. Финальный статус — безопасный checkpoint для продолжения, **не конкурсная приёмка realtime**.
