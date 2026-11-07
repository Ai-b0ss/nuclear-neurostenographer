# Issue 10: sherpa-onnx UVR BSS — isolated negative control

**Дата:** 07.11.2026. **Технический статус:** `PASS`. **Решение:** `HOST_NEGATIVE_CONTROL_PASS__A3_QUALITY_NOT_EVALUATED`.

Реализован отдельный host preflight/adapter: проверенный UVR ONNX → штатный `sherpa_onnx.OfflineSourceSeparation` → две дорожки `vocals.wav` и `accompaniment.wav` → подписанный хэшами `tracks.json` для последующего отдельного запуска A3. Код находится только в `tools/bss_sherpa/`; `app/`, `core/` и pinned production runtime не изменены. Commit/push/PR не выполнялись.

## Границы результата

- В проверенном дереве sherpa-onnx есть source separation для **UVR и Spleeter**, но нет SepFormer или MossFormer2. Здесь не заявляется их поддержка.
- `UVR-MDX-NET-Voc_FT` — модель домена **музыка/пение**, а не разделение пересекающихся собеседников. `vocals` может содержать несколько человек сразу; `accompaniment` не является дорожкой второго говорящего. Это negative control, а не speaker separation.
- Smoke на синтетических тонах подтверждает только загрузку графа, вызов API и контракт WAV/manifest. Он **не измеряет** качество русской речи, overlap, WER, DER или работу на HONOR.
- Общие real DataHive fragments и эталоны ещё не готовы. Поэтому DataHive/A3/HONOR имеют статус `NOT_RUN`, метрики равны `null`; никаких численных WER/HONOR нет.
- Host smoke использует отдельный `sherpa-onnx 1.12.26`, потому что пакет `1.12.20` недоступен на PyPI. Production `1.12.20` не вызывался и не заменялся. Перенос результата на Android не доказан.

## Закреплённые источники и лицензии

Полная машинная запись: `tools/bss_sherpa/upstream-lock.json`, SHA-256 `fe8f747e45f13cfdd2754b9cd4dd2d469e0f504ef01247be03fcf8868060181f`.

| Компонент | Закреплённый источник | SHA-256 / лицензия |
|---|---|---|
| Host runtime | [k2-fsa/sherpa-onnx v1.12.26](https://github.com/k2-fsa/sherpa-onnx/tree/174f8684fa9a0e188ba9b9f3ac04b17cfd44379b), commit `174f8684fa9a0e188ba9b9f3ac04b17cfd44379b` | Apache-2.0; LICENSE `cfc7749b…3d30` |
| Официальный UVR API example | `python-api-examples/offline-source-separation-uvr.py` в том же commit | `38a9bae1…04be` |
| Windows host wheel | `sherpa_onnx-1.12.26-cp311-cp311-win_amd64.whl` | `15b14d51…97cf` |
| Обязательный native core | `sherpa_onnx_core-1.12.26-py3-none-win_amd64.whl` | `509ec6f8…17be` |
| NumPy host wheel | `numpy-1.26.4-cp311-cp311-win_amd64.whl` | `cd25bcec…cb2` |
| ONNX | [sherpa-onnx source-separation-models/UVR-MDX-NET-Voc_FT.onnx](https://github.com/k2-fsa/sherpa-onnx/releases/download/source-separation-models/UVR-MDX-NET-Voc_FT.onnx), 66 762 795 bytes | `e411182ce2c53541fefdcc99a8f46f2fe03978eb22038b9497c1d9d95a00fad4` |
| Исходные UVR weights | [TRvlvr/model_repo](https://github.com/TRvlvr/model_repo/releases/tag/all_public_uvr_models), конвертация описана в `scripts/uvr_mdx/` pinned sherpa source | Отдельные weights не включены в репозиторий |
| UVR upstream/notice | [Anjok07/ultimatevocalremovergui](https://github.com/Anjok07/ultimatevocalremovergui/tree/a5f88453bfb2b38b05a965bcf67727243e0cbf19), commit `a5f88453bfb2b38b05a965bcf67727243e0cbf19` | MIT; README `393f5bc0…3834`; требуется credit UVR и разработчикам |

ONNX и WAV лежат только в игнорируемом `.local/bss-sherpa/`; `*.onnx` и `*.wav` также исключены корневым `.gitignore`. В commit не попали ни веса, ни аудио.

## Запуск

```bash
python -m venv .local/bss-sherpa/venv
.local/bss-sherpa/venv/Scripts/python.exe -m pip install -r tools/bss_sherpa/requirements-host.txt
.local/bss-sherpa/venv/Scripts/python.exe -I tools/bss_sherpa/run.py fetch --model .local/bss-sherpa/UVR-MDX-NET-Voc_FT.onnx
.local/bss-sherpa/venv/Scripts/python.exe -I tools/bss_sherpa/run.py preflight --model .local/bss-sherpa/UVR-MDX-NET-Voc_FT.onnx
.local/bss-sherpa/venv/Scripts/python.exe -I tools/bss_sherpa/run.py make-fixture --output .local/bss-sherpa/smoke-input.wav
.local/bss-sherpa/venv/Scripts/python.exe -I tools/bss_sherpa/run.py separate --model .local/bss-sherpa/UVR-MDX-NET-Voc_FT.onnx --input .local/bss-sherpa/smoke-input.wav --output .local/bss-sherpa/smoke-tracks --threads 2
.local/bss-sherpa/venv/Scripts/python.exe -I tools/bss_sherpa/run.py validate --tracks .local/bss-sherpa/smoke-tracks
```

На Unix-подобном host вместо `venv/Scripts/python.exe` используется `venv/bin/python`. Вход: непустой несжатый PCM16 WAV, 44 100 Гц, mono или stereo; mono дублируется в stereo. Выход: два PCM16 stereo WAV по 44 100 Гц с числом frames исходника. Другие форматы сознательно отклоняются, скрытого resample нет.

Preflight fail-closed: размер и SHA-256 модели проверяются до импорта native runtime; затем сверяются версии `numpy`, `sherpa-onnx`, `sherpa-onnx-core` и наличие UVR API. Выход создаётся во временной соседней папке и атомарно переименовывается только после валидации. Существующие model/output не перезаписываются. Валидатор отклоняет подмену файлов, небезопасные пути, другую модель, разную длину stems и любые неподтверждённые A3/WER/HONOR-поля.

Для кириллического пути Windows native API получает существующий ASCII short path; байты исходной модели предварительно проверяются. Отдельно зафиксировано, что пропуск обязательного `sherpa-onnx-core` приводил к native access violation; теперь такое окружение не проходит preflight.

## Фактический smoke

Одна секунда детерминированных числовых тонов, не речь. Вход SHA-256 `ea1ec37e…0941`; два выхода по 44 100 frames, оба PCM16 stereo. `vocals.wav` SHA-256 `7ef1ca68…0100`, `accompaniment.wav` SHA-256 `d546a3ae…74e0`. Повторный `validate` — `PASS`.

Время `process` на этом Windows AMD64 host при 2 threads составило 10,840022 с для 1 с аудио (RTF 10,840022). Это единичный synthetic host факт, не benchmark русского корпуса и не оценка HONOR. Подробности и исправленные ошибки запуска: `run.log`; точные fixture hashes: `fixture-manifest.json`; статусы: `score.json`.

## Что разрешено для следующего A3

Когда появятся общие real DataHive fragments и references, нужен один протокол на одних и тех же исходниках: raw mixture baseline → A3 и отдельно каждый UVR stem → A3, с сохранением исходных текстов и speaker attribution. Нельзя присваивать stems именам людей без независимой проверки. До такого прогона решение о пользе/вреде для Russian overlap и Android/HONOR не принимается.

## Общая schema evidence

`score.json` и `fixture-manifest.json` используют `schema_version = issue10-bss-sherpa/v1`, поля `issue`, `status`, `decision`. Статус `PASS` относится только к перечисленным техническим проверкам; `NOT_RUN` означает отсутствие измерения, `FAIL` — провал, `BLOCKED` — невозможность запуска. Значение `decision` не заменяет quality decision: оно в `score.json.quality_decision` сейчас `NOT_RUN/null`.
