# Handoff — новая сессия Claude Sonnet 5.5 (04.11.2026)

**Назначение:** полное поручение в НОВЫЙ чат Claude Code. Это не подтверждение запуска агента. Текущий чат Claude Desktop занимается очисткой компьютера; его не останавливать и не переключать. Работать независимо.

## Сначала прочесть первоисточники

Репозиторий: `Ai-b0ss/nuclear-neurostenographer` (**private**), активная интеграция `integration/c2-honor-20261104`, [PR #16](https://github.com/Ai-b0ss/nuclear-neurostenographer/pull/16) в `main` — Draft, **не сливать без владельца**.

- [KNOWLEDGE_BASE](KNOWLEDGE_BASE.md), [RESEARCH_COVERAGE_AUDIT](RESEARCH_COVERAGE_AUDIT_2026-11-04.md), [RESEARCH_PROGRAM](RESEARCH_PROGRAM.md), [DECISION_REGISTER](DECISION_REGISTER.md).
- [ASR_MODEL_HANDOFF](ASR_MODEL_HANDOFF_2026-11-04.md), [ASR_COMPARISON](ASR_COMPARISON_2026-11-04.md), [JOINT_A_C_EVALUATION](JOINT_A_C_EVALUATION_2026-11-03.md).
- [REPOSITORY_AUDIT](REPOSITORY_AUDIT_2026-11-04.md), [RELEASE_READINESS](RELEASE_READINESS_2026-11-04.md), [ACCEPTANCE](ACCEPTANCE_2026-11-04.md), [DISTILLATION_GATE](DISTILLATION_GATE_2026-11-03.md).
- [HUME_AUDIO_DECISIONS](HUME_AUDIO_DECISIONS_2026-11-04.md) — отдельное направление P2, НЕ ASR.
- [PR #17](https://github.com/Ai-b0ss/nuclear-neurostenographer/pull/17): продуктовая концепция и локальная история, [PR #18](https://github.com/Ai-b0ss/nuclear-neurostenographer/pull/18): контекстное ASR, словари, hotwords, rescoring. Оба отдельные Draft, не считаются реализованными.
- Issues [#2](https://github.com/Ai-b0ss/nuclear-neurostenographer/issues/2), [#3](https://github.com/Ai-b0ss/nuclear-neurostenographer/issues/3), [#4](https://github.com/Ai-b0ss/nuclear-neurostenographer/issues/4), [#5](https://github.com/Ai-b0ss/nuclear-neurostenographer/issues/5), [#7](https://github.com/Ai-b0ss/nuclear-neurostenographer/issues/7), [#10](https://github.com/Ai-b0ss/nuclear-neurostenographer/issues/10), комментарии и review к PR #6, #9, #11, #13, #14, #15, #16.

## Основная задача: проверяемые испытания моделей

- Базовый A0: **GigaAM v3 CTC INT8**, в офлайн Android + Nemotron C2.
- Последовательно протестировать 4 альтернативы: **GigaAM v3 RNNT**, **v3 e2e CTC**, **v3 e2e RNNT**, **Multilingual CTC 220M**.
- Отдельно исследовать **MOSS Transcribe-Diarize 0.9B** (единая ASR+diarization архитектура) против связки GigaAM+Nemotron; **VibeVoice-ASR-Streaming 1.5B** — вторичный кандидат по ресурсам.
- Коллизия нумерации! В старом `RESEARCH_PROGRAM` A1–A4 обозначали другие модели. Для новых запусков использовать `ASR-20261104-v2` + полные `canonical_model_id`, ревизии, контрольные суммы.
- Сопоставимые по SHA WAV, отдельные DEV/HOLDOUT, реальные русские диалоги с ручной разметкой по возможности; WER/CER, нормализация и пунктуация отдельно, строгая cpWER/DER только при достаточной разметке, speaker recurrence A–B–A, overlap, unknown, шум, отказ, hallucination, память, RTF, нагрев.
- Отдельно проверить повторяющиеся слова на границе окон/QuietCuts; не исправлять недоказанным слепым дедупом. Desktop RTF не сравнивать непосредственно с ARM64.
- Не использовать псевдоразметку VAD как human ground truth; не исключать FAIL/timeout/OOM из отчётов.

## Важные инженерные замечания

- В PR #9 возможна гонка startForegroundService/микрофона на Android API 34/35. Не объявлять отсутствие crash на HONOR Android 10 доказательством безопасности старших API.
- В истории Git PR #9 могут оставаться XML-дампы телефона, хотя в актуальном HEAD их нет. Не публиковать личные данные и не переписывать историю самовольно.
- Native alignment 16 KB требует отдельной проверки; CI debug не сертифицирует production C2.
- Signed RC1 на HONOR работает офлайн, 2/3-speaker и TXT/JSON/SRT проверены. 20 минут аудио: wall RTF около 0.57, память около 650 MiB, батарея нагрелась до 49°C. Критерий RTF≤0.5 НЕ пройден. Реальная независимая DER/сохранение стенограммы после рестарта/повторяемость/fallback на release не закрыты.
- Hume Audio Decision API — ограниченные решения по звуку, преимущественно облако, нет подтверждённой локальной Android модели, не включать в ASR и не запускать.
- До утверждения правила дистрибуции не удалять лицензии сторонних весов и runtime только потому, что GitHub приватный.

## Режим выполнения и защита параллельной работы

1. **СЕЙЧАС**: читать документы, PR/Issues и локальную среду; подготовить inventory и benchmark-план. Не скачивать большие модели, не устанавливать Torch, не запускать GPU/долгие телефонные тесты, пока другая сессия Claude очищает ПК. Не трогать VPN и другие приложения, не удалять файлы.
2. Учитывать, что старый каталог `K:\nn-product-c2` может быть уже удалён; проверять рабочий путь перед использованием. Локальный репозиторий вероятно `C:\Users\user\Documents\nuclear-neurostenographer`, сейчас `feature/long-recordings`. Не править эту ветку без проверки состояния. Материалы также временно скопированы в `C:\Users\user\Documents\Neurostenography-Handoff-20261104`.
3. **ПОСЛЕ подтверждённого завершения очистки и освобождения места**: отдельная R&D-ветка/worktree, модели по одной, фиксированные версии, тесты и реальные метрики. Без платных API, без изменения RC1, без автоматического merge в main.
4. Точно обновлять to-do после каждого подтверждённого этапа, не ставить одновременно «выполнено» для всего списка.
5. Итог: воспроизводимые скрипты, CSV/JSON, табличное сравнение A0–A4 + MOSS (раздельные метрики ASR и joint), негативные кейсы и GO/NO-GO с практической ценой Android-порта; отдельный R&D PR после фактических экспериментов.

**На момент создания файла:** новая сессия Claude Code ещё не запущена и этот текст не отправлен в Claude автоматически. Не вводить пользователя в заблуждение насчёт отправки или выполнения.
