# Протокол проверки C2 на физическом ARM64

**Статус: NOT_RUN.** Тест на телефоне не проводился. Кандидат: POCO M4 Pro 5G Сергея. Ни согласие владельца, ни готовность телефона пока не подтверждены. HONOR 10X Lite занят основной сборкой, запускать на нём этот протокол нельзя.

## До начала

1. Владелец телефона согласен. Он знает, что прототип ставится под тем же именем пакета `ru.neurostenographer.app`. Если основное приложение уже установлено, прототип заменит его вместе с данными. Скрипт останавливается в этом случае, если не задано `ALLOW_REPLACE=1`.
2. Телефон заряжен не меньше чем на 50%, лежит без чехла при комнатной температуре.
3. На телефоне включён **авиарежим**. Скрипт его проверяет, но сам не включает.
4. Подключён ровно этот телефон. Скрипт работает только с устройством из `ANDROID_SERIAL` и сверяет модель.
5. На компьютере установлены JDK 17, Gradle 8.9, Android SDK 35, Python 3.11+, ffmpeg и около 3 ГБ свободного места.

## Шаги

Все команды запускаются из корня ветки `research/nemotron-android-20261103`.

Подготовка моделей и записей; это те же файлы, что в CI, хеши проверяются:

```bash
python3 tools/provision_asr.py --test-assets
```

```bash
python3 tools/provision_diarization.py --test-assets
```

```bash
python3 tools/provision_nemotron.py --test-assets
```

```bash
python3 tools/nemotron/fetch_corpus_sources.py --data .local/bench
```

```bash
python3 tools/provision_dialogue_benchmark.py --suite development
```

```bash
python3 tools/diar_bench/build_corpus.py --data .local/bench --evidence .local/bench/evidence --acted .local/dialogue-benchmark
```

```bash
ffmpeg -v error -y -t 1200 -i .local/bench/raw/datahive/ru_000010.mp3 -ar 16000 -ac 1 -bitexact -c:a pcm_s16le .local/bench/long-ru_000010.wav
```

```bash
python3 tools/nemotron/prepare_android_corpus.py --corpus .local/bench/corpus --manifest docs/evidence/diarization-c0-c1-v2/corpus-manifest.json --long-wav .local/bench/long-ru_000010.wav --long-manifest docs/evidence/diarization-c0-c1-v2/long-manifest.json --assets .local/androidTestAssets --report device-evidence/corpus
```

Прогон: серийный номер взять из `adb devices`, модель из `adb shell getprop ro.product.model`.

```bash
ANDROID_SERIAL=SERIAL EXPECTED_MODEL="MODEL" bash tools/phone_c2/run_c2_phone.sh
```

Скрипт выполняет:
- тесты прототипа (`-PnemotronPrototype=true`): 13 записей через C0 и C2, повреждённую модель с откатом на C0, отмену C2;
- регрессию C0 в обычной сборке (`OfflineDiarizationTest`).

Он сохраняет только модель, ABI, SoC, версию Android, размер страницы и объём памяти. Батарея и температура записываются до и после. Серийный номер и IMEI не сохраняются.

Оценка и решение:

```bash
python3 tools/nemotron/score_android.py --evidence-json EVIDENCE_DIR/nemotron-evidence.json --corpus .local/bench/corpus --manifest docs/evidence/diarization-c0-c1-v2/corpus-manifest.json --host-results NONE --out EVIDENCE_DIR/score.json
```

```bash
python3 tools/phone_c2/check_phone_gate.py --evidence EVIDENCE_DIR --scored EVIDENCE_DIR/score.json --reference docs/evidence/nemotron-android/android-emulator-41678965845.json
```

`--host-results NONE`: на телефоне сравнение идёт с эмулятором через `--reference`, а не с ПК.

## Критерии GO

Для GO должны пройти все пункты. Любой `NOT_RUN` оставляет итог `NOT_RUN`, любой `FAIL` даёт `NO-GO`.

| Критерий | Порог |
|---|---|
| Физическое устройство | ABI `arm64-v8a` |
| Тесты прототипа | 3/3: одинаковые записи, повреждённая модель с откатом на C0, отмена |
| Обычная сборка | `OfflineDiarizationTest` 7/7 |
| Сбои | 0 |
| Качество C2 | Объединённый DER не хуже эмулятора (12,23%) больше чем на 1 п.п.; по каждому файлу не дальше 3% DER от эмулятора |
| Скорость C2 | 20 минут: полное время не больше 0,5 от длительности (RTF ≤0,5) |
| Память C2 | 20 минут: пик суммарного PSS приложения и воркера не выше C0 больше чем на 100 МиБ |
| Повторяемость | Повторы `acted-dmd` и `rubook-rec_0416-white0db` побайтно одинаковы |

Проверка логики решения: `tools/phone_c2/test_check_phone_gate.py`, 5 тестов.

Отдельно записать `page_size` из `device.json`. При 16384 загрузка `libonnxruntime4j_jni.so`, выровненной на 4 КБ, — главный риск. Сбой загрузки будет виден в `related-log.txt` как `dlopen` или `UnsatisfiedLink` и даст FAIL.

## Чего этот протокол не покрывает

- DER по ручной разметке: инструмент `tools/diar_bench/manual_review.py`, PR #13.
- Естественную речь 3–4 человек.
- Реальную 20-минутную запись с микрофона.
- Нагрев за несколько прогонов подряд.

Итог `GO` разрешает только PR интеграции C2 за флагом, с откатом на C0. Он не разрешает замену C0 в конкурсной сборке.
