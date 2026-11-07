# Issue 10: research preflight DiCoP для TS-ASR

## Решение

**REJECT для хакатона; research only.** Inference не запускался, WER/cpWER/tcpWER/DER и прогон на HONOR имеют статус `NOT_RUN`. Причина: **отсутствует checkpoint с доказанным качеством на русской речи** (`missing Russian-proven checkpoint`). Общие C2 turns/reference fragments также ещё не подготовлены, поэтому `fixture-manifest.json` не объявляет ни одного готового case.

Это не отрицательный результат модели: числовых измерений нет. Проверены только воспроизводимый контракт официального inference и конвертация существующего формата C2.

## Зафиксированные источники и модель

Upstream: [BUTSpeechFIT/DiCoP](https://github.com/BUTSpeechFIT/DiCoP), commit **`b9ccee411877f5e8da42e56ed27e693829f80ce1`**. Контракт проверен по [`infer.py`](https://github.com/BUTSpeechFIT/DiCoP/blob/b9ccee411877f5e8da42e56ed27e693829f80ce1/infer.py), [`utils/audio.py`](https://github.com/BUTSpeechFIT/DiCoP/blob/b9ccee411877f5e8da42e56ed27e693829f80ce1/utils/audio.py), [`utils/rttm.py`](https://github.com/BUTSpeechFIT/DiCoP/blob/b9ccee411877f5e8da42e56ed27e693829f80ce1/utils/rttm.py) и [README](https://github.com/BUTSpeechFIT/DiCoP/blob/b9ccee411877f5e8da42e56ed27e693829f80ce1/README.md) именно этого commit.

Опубликованный [BUT-FIT/DiCoP_v0.1](https://huggingface.co/BUT-FIT/DiCoP_v0.1) построен на **`nvidia/parakeet-tdt-0.6b-v2`**, содержит 618M параметров и в model card обозначен как `language: en`. Это **не Russian Parakeet-TDT-0.6b-v3**. Модель не скачивалась, обучение и fine-tuning не выполнялись. Любой language-mismatch output нельзя выдавать за Russian quality evidence; опубликованные английские результаты AMI/NOTSOFAR/LibriMix не переносятся на C2.

## Что реализовано

- `tools/dicop/preflight.py` — беззагрузочная проверка локального checkout: точный commit, неизменённые inference-файлы, Python и видимость зависимостей. Официальный English checkpoint блокируется для Russian evidence; Parakeet v3 отклоняется как несоответствующая база. Сам факт наличия локального файла качество на русском не доказывает.
- `tools/dicop/convert_c2.py` — конвертер oracle reference (`{case}.ref.json#diarization`) или C2 turns (`{case}.tsv`) в RTTM и flat audio layout для официального `infer.py`.
- `tools/dicop/test_dicop.py` — unit-тесты escaping, интервалов, детерминированного порядка, C2 unknown turns, layout и language/base-model gate.
- `metrics.schema.json` — общая JSON Schema для числовых метрик и запусков по платформам. `SCORED` требует число; `NOT_RUN`, `NOT_SCORED`, `FAILED` требуют причину и запрещают подмену её нулевым результатом.

Код конвертации использует только Python stdlib и не импортирует NeMo, PyTorch или модель.

## Контракт данных DiCoP

Официальный вызов принимает `--rttm`, `--audio-dir`, `--output` и `--checkpoint`, а выдаёт STM. Для каждого session поле 2 RTTM должно совпадать с basename аудио. Конвертер создаёт:

```text
OUTPUT/
├── audio/{session}.wav
├── rttm/{session}.rttm
└── fixture-manifest.json
```

Это первый и приоритетный вариант поиска `resolve_audio_path`: `audio-dir/{session}.wav`. WAV проверяется как 16 kHz mono PCM16; SHA-256 и длительность должны совпасть с frozen C2 manifest/reference. RTTM использует секунды и хранит **duration**, а не end:

```text
SPEAKER session 1 1.250 2.500 <NA> <NA> speaker <NA> <NA>
```

Интервалы исходника имеют вид `[start_ms, end_ms)`. Отрицательные, нулевые, выходящие за аудио и нецелые границы отклоняются. Порядок строк: `(start_ms, end_ms, speaker_id)`. Session и speaker кодируются UTF-8 percent-encoding вне `[A-Za-z0-9_.~-]`, поэтому пробелы, переводы строк, `%`, `/` и Unicode не ломают whitespace-формат. Для C2 cluster `N` становится speaker `hN`; unknown cluster `-1` не может задать target speaker, исключается и считается в `unknown_turns_excluded`.

## Команды после появления общих fragments

Preflight ничего не скачивает и возвращает код 2, пока Russian inference заблокирован:

```bash
python tools/dicop/preflight.py \
  --upstream /path/to/DiCoP \
  --output preflight.json
```

Oracle reference:

```bash
python tools/dicop/convert_c2.py \
  --manifest docs/evidence/c2-same-tracks/manifest.json \
  --corpus ROOT/data/same \
  --mode reference \
  --output ROOT/dicop/reference
```

C2 turns:

```bash
python tools/dicop/convert_c2.py \
  --manifest docs/evidence/c2-same-tracks/manifest.json \
  --corpus ROOT/data/same \
  --mode c2 \
  --turns ROOT/results-same/C2 \
  --output ROOT/dicop/c2
```

Только после появления отдельно проверенного Russian-proven checkpoint можно заполнять команду официального `infer.py`; текущий evidence не разрешает и не выполняет такой запуск. Подстановка `BUT-FIT/DiCoP_v0.1` для русского корпуса запрещена условием исследования.

## Проверка и артефакты

```bash
python -m unittest -v tools/dicop/test_dicop.py
```

- `score.json` — общий статус, метрики `NOT_RUN`, HONOR `NOT_RUN`, `REJECT`.
- `fixture-manifest.json` — пустой список cases и ожидаемый layout; готовые fragments не выдумываются.
- `run.log` — фактически выполненные проверки и их результаты.
- `metrics.schema.json` — общая схема evidence-метрик.
