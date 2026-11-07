# Issue #10: AMV-STT OverlapResolver

## Решение

**NO-GO для утверждения о восстановлении перекрытой речи (WER recovery).** Проверенный `uno-km/amv-stt` `OverlapResolver` не является сепаратором и не выдаёт очищенные дорожки. Адаптер остаётся изолированным исследовательским инструментом в `tools/tsvad_amv_stt`; `app/` и `core/` не изменены.

## Зафиксированный источник и лицензия

- Репозиторий: <https://github.com/uno-km/amv-stt>.
- Commit: `b063c273749b72002e7d498a2eb9a8e07e11721b`.
- Исходник: `amv_stt/diarization/overlap_resolver.py`, SHA-256 `743ff0398943645336ef634c81e23def0ded6a91c815169a120563e7fb89b517`.
- Корневой `LICENSE`: Apache-2.0, SHA-256 `a6cba85bc92e0cff7a450b1d873c0eaa2e9fc96bf472df0247a26bec77bf3ff9`.
- В заголовке самого исходника указано `Apache-2.0 OR Commercial-License`; это сохранено в `upstream/provenance.json` и не заменено более широкой трактовкой лицензии.

Побайтово сохранённые исходник и лицензия находятся в `tools/tsvad_amv_stt/upstream/`. `verify_upstream()` проверяет их SHA-256 перед вызовом resolver.

## Что делает исходный алгоритм

`OverlapResolver` строит центроиды voiceprint по исходным интервалам, сканирует длинные интервалы скользящим окном и сравнивает CAM++-embedding с профилями через cosine similarity. Пики другого говорящего порогами превращаются в sub-segment, после чего исходный интервал разрезается.

Несмотря на названия TS-VAD и multi-label trajectory, `resolve_overlaps()` возвращает только `List[(start, end, speaker_id)]`. При вставке interjection он **заменяет участок dominant speaker**, а не сохраняет два одновременно активных говорящих. Он не вызывает separator, не возвращает waveform и не восстанавливает слова. Адаптер не создаёт fake clean tracks и не выполняет destructive zero-mask ASR.

## Реализованные интерфейсы

- `adapter.py`: преобразование общих интервалов `{start_ms, end_ms, speaker_id}` в секунды AMV-STT и обратно; вызов resolver; неизменность входного document и samples.
- `evaluate.py`: сравнение baseline/candidate с общей ручной разметкой. Используются точные границы интервалов, без дискретизации ошибки по кадрам.
- Activity-метрики: miss/false alarm и error rate для union speech, recall/precision для overlap, а также per-speaker activity с буквальным совпадением speaker ID.
- `tools/test_tsvad_amv_stt.py`: fake extractor, fake trajectory, converter, проверка pin/hash и CLI evaluator.

Evaluator требует `annotation_source`, явно содержащий `manual`, и общие поля `audio_duration_ms` и `diarization`. Запуск:

```bash
PYTHONPATH=tools python -m tsvad_amv_stt.evaluate \
  --reference common-manual-reference.json \
  --baseline baseline.json \
  --candidate resolved.json \
  --output score.json
```

`reference_sha256` в отчёте evaluator — SHA-256 канонического JSON (`sort_keys=True`, компактные separators), а не исходного текстового файла.

## Статус измерений

| Метрика | Статус | Причина |
|---|---|---|
| Activity против common manual reference | `NOT_RUN` | Общая ручная разметка отсутствует в этом worktree; synthetic unit fixtures не считаются оценкой качества |
| WER recovery | `NOT_RUN` | Нет separator, восстановленных дорожек и paired ASR run |
| RTF на HONOR | `NOT_RUN` | Нет Android runner для этого адаптера |
| Peak PSS на HONOR | `NOT_RUN` | Нет Android runner для этого адаптера |

`score.json` использует общие поля `status`, `value`, `unit` и `reason`; отсутствующие измерения не заменяются нулями или upstream-показателями.

## Ограничения

- Fake extractor/trajectory проверяют только контракт converter/adapter/evaluator, а не точность CAM++ или качество на русской речи.
- Activity-метрики оценивают временную активность, а не WER, cpWER или восстановление слов.
- Изменение intervals само по себе не доказывает улучшение ASR и не создаёт одновременные независимые дорожки.
- Для recovery claim нужны независимый separator, общая manual reference, paired ASR evaluation и физический HONOR run с RTF/PSS.

## Проверка

`python -m unittest tools.test_tsvad_amv_stt -v`: **10 тестов, OK**. Подробности команд записаны в `run.log`; состав fixtures — в `fixture-manifest.json`.
