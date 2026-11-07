# VoxLock на реальных DataHive overlap-фрагментах с ручным enrollment

**Статус: `NOT_RUN`.** Общие реальные фрагменты DataHive и независимая ручная
разметка слов/говорящих пока недоступны и размечаются. Поэтому здесь нет WER,
RTF, PSS или вывода о качестве. Старый synthetic baseline не повторялся и его
числа не переносились. Аудио, веса и приватный текст в Git не добавляются.

> Самый прагматичный шаг — после готовности общей разметки прогнать VoxLock на
> тех же реальных DataHive overlap-фрагментах, что и общий A3+C2 baseline, с
> обязательным ручным enrollment и без automatic enrollment fallback.

## Что подготовлено

- `manual_manifest.py` проверяет входной manifest, WAV и reference, SHA-256,
  ровно два разных ручных enrollment по 48 000 samples (3 с, mono PCM16, 16 kHz)
  на каждый фрагмент. Требуются `kind=REAL_DATAHIVE_MANUAL_OVERLAP` и
  `enrollment_mode=manual`; synthetic, automatic, неполный, тихий, клиппованный,
  короткий или одинаковый для двух голосов enrollment отклоняется. Паддинг,
  обрезка до 3 с и автоматический выбор интервала отсутствуют.
- `run_manual.py` выполняет C2 и baseline A3 на исходном WAV, затем оба
  VoxLock target и тот же A3 на каждом extracted WAV. Слова вне C2-overlap
  сохраняются из baseline; recovered words остаются `speaker_id=null` и
  `attribution_reliable=false`. Отсутствие enrollment не превращается в
  baseline fallback: вход отклоняется до inference.
- `manual_metrics.py` считает лексические совпадения только внутри ручной
  reference-разметки overlap. `recovered_correct_words` — изменение числа
  одно-ко-одному сопоставленных правильных слов candidate относительно baseline
  с допуском midpoint ±250 мс; значение может быть отрицательным. Speaker identity
  при этом не присваивается и не считается подтверждённой.
- `export_manual.py` обновляет `score.json` и hash-only `fixture-manifest.json`
  после завершённого host run. Пути, reference text, transcripts и PCM не
  экспортируются. HONOR остаётся `NOT_RUN`, пока не выполнен отдельный real-data
  device protocol.

Перенесённый `run_phone.py` жёстко связан со старым synthetic fixture, поэтому
его нельзя использовать как HONOR-доказательство этого эксперимента. Здесь нет
команды, которая незаметно подменила бы real fragments старыми synthetic данными.

## Входной контракт

Все относительные пути разрешаются от каталога исходного manifest. Reference
должен быть привязан к точному `audio_sha256` и `audio_duration_ms`, содержать
`text_segments` с одним нормализованным словом на interval и независимую ручную
`diarization` с хотя бы одним перекрытием. Пример ниже описывает только структуру;
это не fixture и не результат.

```json
{
  "schema_version": 1,
  "kind": "REAL_DATAHIVE_MANUAL_OVERLAP",
  "enrollment_mode": "manual",
  "cases": [
    {
      "id": "datahive-overlap-001",
      "audio_path": "fragment.wav",
      "audio_sha256": "<sha256>",
      "reference_path": "reference.json",
      "reference_sha256": "<sha256>",
      "enrollments": [
        {"speaker_id": "caller", "selection": "manual", "wav_path": "enroll-caller.wav", "sha256": "<sha256>"},
        {"speaker_id": "callee", "selection": "manual", "wav_path": "enroll-callee.wav", "sha256": "<sha256>"}
      ]
    }
  ]
}
```

## Команды после готовности общего baseline

Запускать из корня этой research-ветки. Пути к приватным данным и моделям задаются
локально. Первые две команды нужны только если pinned harness ещё не подготовлен;
`--harness` должен указывать на уже проверенный harness либо параметр опускается
для получения зафиксированных зависимостей по правилам исходного harness.

```powershell
$Py = 'python'
$Java = 'C:/path/to/java17/bin/java.exe'
$A3 = 'C:/secure/models/a3-opsetfix'
$C2 = 'C:/secure/models/nemotron'
$Shared = 'C:/secure/shared-datahive-overlap'

& $Py -B tools/overlap_research/provision.py --harness C:/secure/verified-harness
& $Py -B tools/overlap_research/build_host.py --java $Java
& $Py -B tools/overlap_research/manual_manifest.py `
  --manifest "$Shared/manual-manifest.json" `
  --out .local/issue10/manual-real
& $Py -B tools/overlap_research/run_manual.py `
  --fixtures .local/issue10/manual-real/manifest.json `
  --java $Java --a3 $A3 --c2 $C2 `
  --out .local/issue10/manual-host
& $Py -B tools/overlap_research/export_manual.py `
  --fixtures .local/issue10/manual-real/manifest.json `
  --run .local/issue10/manual-host/summary.json `
  --score-output docs/evidence/issue10-tse-voxlock-manual/score.json `
  --fixture-output docs/evidence/issue10-tse-voxlock-manual/fixture-manifest.json
```

`run.log` после прогона нужно заменить фактическим статусом и командами/ошибками,
не добавляя transcript или participant text. `decision` exporter намеренно
оставляет `RESEARCH_ONLY_MANUAL_REVIEW_REQUIRED`: интеграция не следует из одного
host-прогона автоматически.

## Проверки без моделей и real fixtures

```powershell
python -B tools/overlap_research/test_manual.py
python -B tools/overlap_research/test_overlap.py
```

Обе команды прошли: 6 + 6 unit tests. Это структурные тесты адаптера, метрик и
защитных отказов, а не VoxLock inference и не evidence качества.
