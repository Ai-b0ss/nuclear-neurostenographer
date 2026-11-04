# Аудит исследовательского охвата, 04.11.2026

**Назначение:** единая карта идей, экспериментов, нерешённых гипотез и источников, без подмены статуса «задумано» статусом «работает». Изучены дерево интеграционной ветки (502 файла, включая документы и evidence), критичные исследовательские документы, 7 обычных Issues и актуальные 11 PR (включая #17 и #18). Это **не** построчная верификация всего исторического `PROGRESS.md` и не запуск новых моделей.

## Сохранённые направления и реальное состояние

| Трек | Что именно существует | Чего всё ещё нет / источники |
|---|---|---|
| **CORE + A0 + C2** | Signed RC1 на HONOR, полностью офлайн; GigaAM CTC INT8 + Nemotron 3 C2, резервная C0; запись, импорт, TXT/JSON/SRT; 20 мин RTF≈0,57, температура батареи до 49°C | Повторяемость, полноценный fallback на signed build, 2–4 естественных голоса с ручной DER, история стенограмм. [Актуальная приёмка](RELEASE_READINESS_2026-11-04.md) |
| **A — GigaAM** | A0 CTC INT8 — baseline; четыре кандидата: v3 RNNT, v3 e2e CTC, v3 e2e RNNT и multilingual CTC 220M **NOT_RUN** | [Поручение Sonnet](ASR_MODEL_HANDOFF_2026-11-04.md); одинаковые WAV, окна и независимые эталоны нужны до вывода о победителе |
| **Другие ASR** | Whisper v3 Turbo Q5 — ограниченный PC-контроль трёх WAV; Nemotron ASR 0.6B, Parakeet, whisper.cpp и др. — кандидаты | [Контроль Whisper](ASR_COMPARISON_2026-11-04.md), [гипотеза teacher](DISTILLATION_GATE_2026-11-03.md). Секунды ПК ≠ Android RTF |
| **C — говорящие** | C0 pyannote+ERes2Net, C1 FP32 и C2 INT8; сравнительные исследования и реальные короткие прогоны HONOR | Нет строгой самостоятельной оценки DER на настоящем русском совещании; overlap, unknown, A–B–A и длинные записи не все закрыты. [C0/C1 v2](DIARIZATION_C0_C1_V2.md), [Issue #7](https://github.com/Ai-b0ss/nuclear-neurostenographer/issues/7) |
| **J — совместная A+C** | MOSS-Transcribe-Diarize 0.9B, VibeVoice-ASR-Streaming 1.5B, VibeVoice BitNet — описаны | **NOT_RUN** на едином русском корпусе. [План сравнения](JOINT_A_C_EVALUATION_2026-11-03.md), [PR #14](https://github.com/Ai-b0ss/nuclear-neurostenographer/pull/14) |
| **O — наложения речи** | VoxLock (target-speaker suppression), DiCoP (conditioned ASR), audio.cpp (альтернативный inference/runtime), upstream sherpa-onnx, LiteRT — зафиксированы | **RESEARCH_ONLY**; не путать separation с восстановлением слов. [Issue #10](https://github.com/Ai-b0ss/nuclear-neurostenographer/issues/10) |
| **B — контекст** | Словарь B0, RNNT hotwords B1, rescoring B2, повтор ASR B3, маленький текстовый корректор B4 — гипотезы | **NOT_RUN**; [новый PR #18](https://github.com/Ai-b0ss/nuclear-neurostenographer/pull/18) содержит `CONTEXTUAL_ASR_DECISION_2026-11-04.md`, **не слит в интеграцию**; CTC+greedy не поддерживает RNNT-hotwords автоматически |
| **Продукт / D** | Идея raw ASR + обратимые правки + audio-linked review + speaker correction + локальная история + опциональные ответы на вопросы по содержанию | **Частично реализовано/гипотеза**; [PR #17](https://github.com/Ai-b0ss/nuclear-neurostenographer/pull/17) содержит `PRODUCT_VISION_2026-11-04.md`, **не слит**; D не подтверждён организаторами как P0 |
| **T — обучение** | Nemotron Transcribe 30B, REAP/pruning русского, Granary-v2, дистилляция teacher→student — сохранённые гипотезы | **NOT_RUN**, сначала Gate 0: учитель лучше baseline на независимой русской речи? [Отдельный документ](DISTILLATION_GATE_2026-11-03.md) |
| **U — анализ самого звука** | Hume Audio Decisions — проверены официальные свойства облачного API; больше, чем эмоции, но ограниченные ответы | **NOT_TESTED**, нет проверенного офлайн Android-порта или ASR. [Заметка](HUME_AUDIO_DECISIONS_2026-11-04.md), необязательная P2 |
| **Методика** | scorer, manifests, CI synthetic gates, C2 измерения | Отсутствует достаточный независимый естественный русский корпус с человеческими speaker+word labels; `NOT_SCORED` нельзя менять на ноль. [Issue #5](https://github.com/Ai-b0ss/nuclear-neurostenographer/issues/5), [сравнения](MODEL_COMPARISON.md) |

## Потери согласованности, требующие исправления

1. **Одинаковый код A1–A4 означает РАЗНЫЕ модели.** В историческом [RESEARCH_PROGRAM](RESEARCH_PROGRAM.md): A1=e2e RNNT, A2=multilingual 220M, A3=Whisper, A4=Nemotron ASR 0.6B. В новом [ASR_MODEL_HANDOFF](ASR_MODEL_HANDOFF_2026-11-04.md): A1=v3 RNNT, A2=v3 e2e CTC, A3=v3 e2e RNNT, A4=multilingual CTC 220M. Историю **не переписывать**. Новым испытаниям назначить явно `ASR-20261104-v2` плюс `canonical_model_id`/revision/checksum.
2. **Устаревшее представление о baseline.** [PROJECT_CHARTER](PROJECT_CHARTER.md), [DECISION_REGISTER](DECISION_REGISTER.md) и ранний [PROGRESS](PROGRESS.md) датированы 2–3 ноября: там C0 может называться стандартным и ARM64 `NOT_RUN`. Для текущего подписанного RC1 ориентир — [RELEASE_READINESS](RELEASE_READINESS_2026-11-04.md): C2 успешно на HONOR с ограничениями. Старые сведения оставить датированными, не стирать результаты и ошибки.
3. **PR #17/#18 действительно добавили новое содержание, не вошедшее в PR #16** (оба Draft, base=integration). Не закрывать как superseded и не считать функции внедрёнными, пока решения не рассмотрены.
4. **Метрики нельзя переносить между разными схемами.** В контроле Whisper использован цельный WAV, в GigaAM — окна QuietCuts. Синтетический A–B–A и VAD-псевдоразметка DER не подтверждают работу на естественном совещании. Для DER — независимые интервалы, collar и overlap; для cpWER — неизвестных говорящих не исключать молча.
5. **Продуктовое качество отличается от ASR WER.** Не забывать отмену, восстановление после сбоя, стабильное сохранение/экспорт, приватность, редактирование говорящих, долгие записи (1 час был исходной амбицией, не утверждённым Hex требованием), энергопотребление и воспроизводимые источники метрик.
6. **История Git может содержать чувствительное.** XML-дампы UI телефона удалены из актуального дерева, но остаются в прошлых коммитах PR #9. Отдельная оценка приватности до исторического merge в `main`; не публиковать исходные частные аудиозаписи, API-ключи или материалы личных переписок.
7. **Лицензии моделей, датасетов и runtime различны.** Упоминание ссылки и наличие приватного репозитория не означают разрешение на распространение весов. Нельзя объявлять вопросы закрытыми без review.
8. **Hume — P2, не A/C/J.** Это облачный audio decision API; не конкурент ASR и не обязательное конкурсное условие. Разграничение [здесь](HUME_AUDIO_DECISIONS_2026-11-04.md).

## Единый словарь новых моделей: схема ASR-20261104-v2

| Код | canonical_model_id | Измерения |
| --- | --- | --- |
| A0 | `gigaam-v3-ctc-int8` | baseline, MEASURED (ограниченная выборка) |
| A1 | `gigaam-v3-rnnt` | NOT_RUN |
| A2 | `gigaam-v3-e2e-ctc` | NOT_RUN |
| A3 | `gigaam-v3-e2e-rnnt` | NOT_RUN |
| A4 | `gigaam-multilingual-ctc-220m` | NOT_RUN |
| J1 | `moss-transcribe-diarize-0.9b` | NOT_RUN |
| J2 | `vibevoice-asr-streaming-1.5b` | NOT_RUN |

В каждом новом результате: исходный WAV и reference SHA-256, модель и revision SHA, параметры/окна ASR, декодер, корпус DEV vs HOLDOUT, WER/CER, speaker attribution, DER только при валидном эталоне, латентность/RTF, память/температура, негативные кейсы, результат PASS/FAIL/NOT_RUN. Нельзя тюнить по HOLDOUT, игнорировать падения и запускать тяжёлую задачу на заполненном диске.

**Принцип:** найденные пробелы должны стать явно видимыми гипотезами или задачами, а не стираться из отчётов. Этот аудит не меняет main, PR, Issues, текущий Claude и не запускает модели.