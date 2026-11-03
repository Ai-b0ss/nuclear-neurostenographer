# Nemotron 3 Diarization INT8 (C2) на Android: прототип и решение

**Дата:** 3 ноября 2026. **Ветка:** `research/nemotron-android-20261103`. Конкурсная сборка не менялась: C2 собирается только с `-PnemotronPrototype=true`, а C0 остаётся по умолчанию.

## Вердикт

| Решение | Статус | Основание |
|---|---|---|
| Отдельный PR интеграции C2 за флагом, с fallback на C0 | **GO** | Полный путь WAV → `:diarization` → интервалы → ASR → TXT/SRT/JSON работает на эмуляторе. Качество совпадает с host-эталоном. Сбой модели не мешает C0 |
| C2 по умолчанию в конкурсном APK | **NO-GO** | Физический ARM64 не проверен. JNI-библиотека ONNX Runtime Java выровнена на 4 КБ. Человеческого эталона натуральной речи нет |
| Приёмка C2 на телефоне ARM64 | **GO как следующий шаг** | Те же тесты и тот же APK, что на эмуляторе. Критерии ниже |
| LiteRT вместо ORT | **NO-GO для этого проекта сейчас** | Работает и даёт то же качество, но на эмуляторе занимает примерно вдвое больше памяти. Модели FP16 весят 201 МБ, это второй рантайм |

## Что именно проверено

### Android x86_64 эмулятор, API 33. Не телефон

| Прогон | SHA | Что показал |
|---|---|---|
| [41539745232](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41539745232) | `c7f8ed1` | 32 запуска C0 и C2 на 13 записях без сбоев. Это единственный полный набор интервалов, разобранный в [android-emulator-41539745232.json](evidence/nemotron-android/android-emulator-41539745232.json) |
| [41542902800](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41542902800) | `437e285` | JUnit `sameRecordingsThroughBothBackends` и `damagedModelFailsAndC0StillWorks` PASS. Обычная сборка без флага: `OfflineDiarizationTest` 7/7 PASS. **Файл интервалов этого прогона потерян:** его перезаписал сборщик после регрессионного прогона, в файле осталось `run-as: unknown package`. Время и память видны только из логов, поэтому оценку качества этот прогон не заменяет |
| [41542902879](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41542902879) | `437e285` | LiteRT-проба на тех же 13 записях, 13/13 OK, CPU XNNPACK. GPU на эмуляторе не используется, NPU не загружен. Разбор: [litert-emulator-41542902879.json](evidence/nemotron-android/litert-emulator-41542902879.json) |
| [41674924388](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41674924388) | `f8c6f19` | Evidence сохранён. Интервалы C0 и C2 совпали с 41539745232 до байта по итоговому DER. **Тест отмены упал из-за ошибки самого теста:** внешний `withTimeoutOrNull` `IsolatedDiarization` превращает в «Превышено время диаризации». Это уже существующее поведение и для C0. Регрессия обычной сборки не запустилась из-за этого падения |
| [41678965845](https://github.com/Ai-b0ss/nuclear-neurostenographer/actions/runs/41678965845) | `a129a80` | **Итоговый прогон.** `NemotronBenchmarkTest` 3/3 PASS: одинаковые записи, повреждённая модель с fallback на C0, отмена C2 через `Job.cancel` (после неё C0 и C2 снова OK, воркер PID 3083). Обычная сборка: `OfflineDiarizationTest` 7/7 PASS. Хеши 13/13. [android-emulator-41678965845.json](evidence/nemotron-android/android-emulator-41678965845.json) |

Хеши всех 13 записей совпали с замороженным манифестом ПК во всех прогонах: 13/13 `match`, копии в [ci/](evidence/nemotron-android/ci). DER C0 16,67% и C2 12,23% одинаковы в трёх независимых прогонах с сохранёнными интервалами. Повторы детерминированы: `acted-dmd` ×3 и `rubook-rec_0416-white0db` ×2 дали побайтно одинаковые интервалы для C0 и для C2.

Код прототипа (`app/src/nemotron`, `core`, `app/src/main`) между `c7f8ed1` и `437e285` не менялся. Изменились только тесты, скрипты и проверки: `git diff --stat c7f8ed1 437e285`.

### На ПК

| Проверка | Результат |
|---|---|
| Kotlin-перенос (мел, кэш спикеров, цикл) на ORT 1.17.1 против Python-эталона на ORT 1.31.1, 87 записей | DER 7,45% против 7,37%. Побайтно совпало 6 файлов; наибольшее расхождение между ними 5,8% DER на одном файле. [kotlin-host-parity.json](evidence/nemotron-android/kotlin-host-parity.json) |
| Kotlin-мел против `preprocessor_core.onnx` | Наибольшая разница 5,9·10⁻⁴ в лог-домене, средняя 1,2·10⁻⁶ |
| Эмулятор против host C2 на тех же 13 файлах | Наибольшая разница интервалов 2,6% DER, на `ru_000001` |
| C0, C1, C2 на 87 записях | [Версия 2 доказательств](https://github.com/Ai-b0ss/nuclear-neurostenographer/blob/research/diarization-c0-c1-20261102/docs/DIARIZATION_C0_C1_V2.md), PR #13 |

## Итоговая таблица

**Ручного эталона нет: DER по человеческой разметке `NOT_SCORED`.** Все DER ниже посчитаны против автоматических или синтетических эталонов, collar ±250 мс, перекрытия учитываются.

| Показатель | C0 | C1 fp32 (ПК, Python) | C2 INT8 (Android) | LiteRT FP16 (Android, проба) |
|---|---|---|---|---|
| DER, человеческий эталон | NOT_SCORED | NOT_SCORED | NOT_SCORED | NOT_SCORED |
| DER, звонки DataHive, эталон от VAD, 20 файлов, ПК | 28,82 | 6,38 | 6,33 | — |
| DER, ru-book 2/3/4 спикера, ПК | 13,94 / 20,65 / 20,67 | 8,21 / 4,70 / 9,04 | 8,28 / 4,95 / 8,81 | — |
| DER, 9 файлов эмулятора | 16,67 | — | 12,23 | 12,30 |
| Точное число спикеров без подсказки, ПК: звонки, 2 спикера | 0/20 | 18/20 | 18/20 | — |
| То же, ru-book 2 / 3 / 4 спикера | 11/19, 9/19, 7/11 | 18/19, 17/19, 10/11 | 18/19, 17/19, 10/11 | — |
| 20 минут естественного звонка, найдено спикеров (в разговоре 2) | 47 | — | 2 | 2 |
| A-B-A актёрская | PASS | PASS | PASS | — |
| cpWER, GigaAM, синтетика ivkond 2/3/4 спикера, ПК | 52,35 / 30,34 / 42,27 | 41,78 / 10,11 / 8,76 | 42,11 / 10,11 / 9,28 | — |
| cpWER, естественная речь | NOT_SCORED | NOT_SCORED | NOT_SCORED | NOT_SCORED |
| Тишина и белый шум, ложная речь | 0 с | 0 с | 0 с | 0 с |
| 20 минут, эмулятор: полное время с запуском воркера, 3 прогона | 288,5–321,3 с (RTF 0,24–0,27) | — | 91,8–93,6 с (RTF 0,076–0,078) | 120 с (RTF 0,100), 1 прогон |
| 20 минут: пик суммарного PSS приложения и воркера, 4 прогона | 627–640 МиБ | — | 544–551 МиБ | 1332 МиБ, один процесс |
| Холодная загрузка модели в воркере | 424–483 мс | — | 512–625 мс | 570 мс, один раз |
| Размер моделей | 46 МБ | 398 МБ | 104 МБ | 201 МБ |
| Прирост APK | — | — | +3,7 МБ (50,99 → 54,68 МБ) | +11,8 МБ AAR без моделей |
| Сбои | 0 из 64 запусков | 0 | 0 из 64 запусков, плюс отмена и повреждённая модель | 0 из 13 |
| Лицензия модели | MIT / Apache-2.0 | OpenMDW-1.1 | OpenMDW-1.1 | OpenMDW-1.1 |

Пики PSS у C0 и C2 сняты одной и той же обвязкой теста. Процесс приложения включает тестовые данные, поэтому абсолютные значения выше, чем в реальном приложении. LiteRT запущен в процессе теста, а не в `:diarization`, поэтому его память сравнивается только грубо.

## Проблемы, найденные по ходу

| Проблема | Статус |
|---|---|
| ONNX Runtime 1.17.1 из приложения не читает экспорт: IR 10 | Обойдено: в копии модели изменён один байт версии IR, хеш закреплён. Веса и операторы не менялись |
| `preprocessor_core.onnx` падает на 1.17.1 на STFT | Обойдено: мел-спектрограмма считается в Kotlin, `NemotronMel` |
| `libonnxruntime4j_jni.so` из `onnxruntime-android:1.17.1` выровнена на 4 КБ | **Открыто.** Остальные библиотеки приложения выровнены на 16 КБ. На телефонах с 16 КБ страницами библиотека может не загрузиться; это не проверено. Путь: проверить `getconf PAGE_SIZE` на телефонах команды, либо собрать свой JNI к уже упакованному `libonnxruntime.so` |
| Перезапись evidence в прогоне 41542902800 | Исправлено в `f8c6f19`, файл сохраняется только если это корректный JSON |
| Отмена C2 и повторный запуск воркера | PASS в 41678965845 |
| Внешний `withTimeout` вокруг `IsolatedDiarization` выдаётся как «Превышено время диаризации» | Найдено тестом. Это код C0 из рабочей ветки, его я не менял. Приложение отменяет через `Job.cancel` и не затронуто |
| `ru_000001`: C2 49% DER, 3–4 кластера при 2 спикерах | **Причина не установлена.** По интервалам C2 делит речь принимающего на два кластера и смешивает её с речью звонящего. Совпадает у Python, Kotlin и LiteRT, значит это свойство модели, а не переноса |
| `rubook-rec_0416-white0db`: C2 31,3% DER против 12,6% у C0 | При шуме 0 дБ C2 хуже на этом файле. По всей группе шума 0 дБ C2 лучше, но CI разности включает 0 |

## Ручная проверка

Комплект готов, разметки нет. `tools/diar_bench/manual_review.py` (PR #13) создаёт для 6 заранее выбранных звонков, включая `ru_000001`, стерео-WAV и метки Audacity из VAD. Проверяющий слушает каждый канал отдельно и исправляет метки. `score` считает DER только по полностью размеченным файлам и пишет `HUMAN_REVIEWED_INTERVALS` отдельно от VAD. Аудио и метки остаются на машине проверяющего.

## Что нужно для GO на телефоне

1. Установить APK с `-PnemotronPrototype=true` и модели на ARM64-телефон.
2. Записать `getconf PAGE_SIZE`.
3. Прогнать тот же `NemotronBenchmarkTest` в авиарежиме. Критерии GO:
   - 5 из 5 прогонов без сбоев, включая 20-минутный файл;
   - DER на этих 13 файлах не хуже эмулятора больше чем на 1 п.п.;
   - устойчивый RTF C2 ≤0,5;
   - суммарный PSS не выше C0 больше чем на 100 МиБ;
   - обычная сборка проходит `OfflineDiarizationTest`.
4. Провести ручную проверку DataHive хотя бы на 3 звонках и записать отдельно от VAD.
5. Сделать 20-минутную запись с микрофона на телефоне и диаризовать её через C0 и C2.

## Не проверено

- **Физический ARM64.**
- **Естественная речь 2–4 человек с ручным эталоном.** В DataHive только по двое, эталон от VAD.
- **20-минутная запись с реального микрофона.**
- Загрузка `libonnxruntime4j_jni.so` на устройстве с 16 КБ страницами.
- Нагрев и батарея.
- LiteRT на GPU и в процессе `:diarization`.

## Не относится к C2

MOSS-Transcribe-Diarize, VibeVoice и дистилляция teacher→student — отдельные будущие эксперименты. Решения по ним описаны в [JOINT_A_C_EVALUATION_2026-11-03](https://github.com/Ai-b0ss/nuclear-neurostenographer/blob/docs/knowledge-consolidation-20261103/docs/JOINT_A_C_EVALUATION_2026-11-03.md) и [DISTILLATION_GATE_2026-11-03](https://github.com/Ai-b0ss/nuclear-neurostenographer/blob/docs/knowledge-consolidation-20261103/docs/DISTILLATION_GATE_2026-11-03.md). Результаты C2 о них ничего не говорят.

## Воспроизведение

```bash
python tools/provision_nemotron.py --test-assets
```

```bash
python tools/nemotron/run_host_parity.py --root ROOT --java JAVA17 --evidence docs/evidence/nemotron-android --manifest docs/evidence/diarization-c0-c1-v2/corpus-manifest.json --python-results ROOT/results-v2/C2
```

```bash
python tools/nemotron/score_android.py --evidence-json nemotron-evidence.json --corpus ROOT/data/corpus --manifest docs/evidence/diarization-c0-c1-v2/corpus-manifest.json --host-results ROOT/results-v2 --out report.json
```

Эмуляторный прогон: workflow `nemotron-android.yml`, LiteRT: `nemotron-litert-probe.yml`. Оба запускаются push в ветку `research/nemotron-android-**` или вручную.

**Лицензии:** модель OpenMDW-1.1 (NVIDIA), сторонний ONNX-экспорт и `diarize.py` (Joost Helfers, OpenMDW-1.1, перенос на Kotlin отмечен в заголовке `NemotronDiarizer.kt`). Мел-фильтры и окно взяты из LiteRT-репозитория (OpenMDW-1.1). LICENSE и NOTICE входят в ZIP модели и в ассеты прототипа. ONNX Runtime — MIT. `check_prototype_apk.py` проверяет, что нет INTERNET, следов espeak/TTS и упакованных аудио или моделей.
