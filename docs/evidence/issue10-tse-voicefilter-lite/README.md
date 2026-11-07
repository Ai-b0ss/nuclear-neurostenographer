# Issue 10: VoiceFilter-Lite TSE research adapter

## Статус и границы

Добавлен изолированный **offline research adapter** `manual 3 s enrollment → enhanced WAV` для последующего общего A3 harness. Это **independent implementation** исследовательской обвязки на NumPy/SciPy/ONNX Runtime, а не официальный inference CLI upstream и не интеграция в production `app/core`. Обучение не запускалось. A3/C2 не изменялись.

Общие реальные фрагменты ещё не размечены. Поэтому Russian DataHive WER, recovered correct, unknown, общий A3 RTF, HONOR и PSS имеют статус `NOT_RUN`. Численный synthetic smoke подтверждает только исполняемость pinned ONNX и формирование WAV, но не качество разделения речи.

## Provenance и фактический размер

- Upstream: `https://github.com/linsanzhu/open-voicefilter-lite.git`.
- Полный pin: `bfb557cb27f4ccd5ed8860a107aba9a0345d27ae`.
- Лицензия: Apache-2.0; pinned `LICENSE` скачивается вместе с моделями.
- `voicefilter_lite.int8.onnx`: **6 827 972 байта**, SHA-256 `9c7a3b9a585b79cf6c976b5fdf0a38de7437074a839e9ea95a70057632b464b7`.
- `embedder.int8.onnx`: **12 199 675 байт**, SHA-256 `c4d17ba220a33d7f27866c78f573372f4ae2dd57b405cdacdaf4483ecc374812`.

Это фактические размеры двух bundled ONNX из указанного commit. Утверждение upstream о цели **2.2 MB** не описывает суммарный или фактический размер этих артефактов. ONNX, WAV, venv и upstream checkout находятся только под `.local/` и не коммитятся.

## Provision и preflight

Из корня worktree:

```bash
python tools/voicefilter_lite/provision.py --install-deps
.local/voicefilter-lite/venv/Scripts/python.exe \
  tools/voicefilter_lite/preflight.py
```

`provision.py` скачивает только файлы по полному commit URL из `raw.githubusercontent.com`, проверяет размер и SHA-256 до атомарной замены и сохраняет `.local/voicefilter-lite/provenance.json`. `--install-deps` создаёт изолированный `.local/voicefilter-lite/venv` и устанавливает точные версии из `tools/voicefilter_lite/requirements.txt`. Для уже скачанного upstream можно использовать `--source-dir PATH`; его `HEAD` обязан совпасть с pin.

Preflight повторно проверяет хеши/размеры, версии `numpy==2.2.6`, `scipy==1.15.3`, `onnxruntime==1.23.2`, metadata и IO обоих ONNX, CPU provider. Фактический preflight этого прогона: `OK`.

## Inference CLI

```bash
.local/voicefilter-lite/venv/Scripts/python.exe tools/voicefilter_lite/infer.py \
  --enrollment enrollment.wav \
  --input mixture.wav \
  --output enhanced.wav \
  --report enhanced-report.json
```

Поведение:

- принимаются несжатые PCM WAV 8/16/24/32 bit, mono/stereo; вход при необходимости ресемплируется в 16 kHz;
- enrollment обязан содержать не меньше 3,000 с и не быть цифровой тишиной; используются ровно первые 48 000 сэмплов после ресемплинга;
- mixture должен содержать не меньше 10 мс; стандартный предел длительности — 600 с;
- выход всегда 16 kHz mono PCM16, длина совпадает с обработанным входом; последний неполный hop дополняется нулями только на время вычисления и затем обрезается;
- повреждённые/пустые/нефинитные данные, неверные модели и попытка перезаписать вход отклоняются; WAV пишется атомарно;
- модельный state создаётся заново для каждого CLI-запуска. Адаптер не является streaming/production компонентом приложения.

## Фактический synthetic smoke

Сгенерированы численные PCM16 сигналы без речи и без внешних аудиоданных: 3,000 с enrollment (220/440 Hz) и 1,000 с mixture (220/440/330/997 Hz). Команда inference завершилась со статусом `OK`.

| Проверка | Фактический результат |
|---|---:|
| Output | 16 kHz, mono, PCM16 |
| Длительность / frames | 1,000 с / 16 000 |
| Output RMS | 0,052904223389990054 |
| Peak до scaling / scale | 0,1599317491054535 / 1,0 |
| Output SHA-256 | `35e600825d67aeed820be6ae86c2def2ff7b375f1196170224a6b439c9fd9168` |
| Model load | 0,3625872 с |
| Inference / RTF | 0,3539063 с / 0,3539063 |
| Полный wall / RTF | 0,7316070 с / 0,7316070 |

Замеры относятся к одному 1-секундному synthetic файлу на Windows host, CPU, один thread. Они не являются общим A3 benchmark и не переносятся на HONOR. PSS не измерялся (`NOT_RUN`). Хеши fixture и командная история находятся в `fixture-manifest.json` и `run.log`.

## Tests и решение

```bash
.local/voicefilter-lite/venv/Scripts/python.exe \
  -m unittest discover -s tools/voicefilter_lite -p 'test_*.py' -v
```

Фактически: **11 tests, OK**. Покрыты pin/size, PCM/stereo/resample, ошибочный WAV и duration limit, 3-секундный enrollment и silence, минимальная длина mixture, d-vector windows, mel orientation/left context, атомарный WAV, model integrity и сохранение предыдущего файла при failed provision.

`score.json` использует общие поля `baseline/candidate WER`, `recovered_correct`, `unknown`, `rtf_status`, `pss_status`, `decision`. Для отсутствующих общих данных установлено `NOT_RUN`; synthetic RTF вынесен отдельно и не подменяет A3. Текущее решение: **NOT_RUN / качество и переносимость ещё не оценены**, а не GO/NO-GO по речи.
