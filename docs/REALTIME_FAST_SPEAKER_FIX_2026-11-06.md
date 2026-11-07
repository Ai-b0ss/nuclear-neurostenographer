# FAST C2: диагноз и NO-GO, 06.11.2026

**NO-GO FAST. Исправление качества не доказано; производственный код и параметры не изменены.**
Оставлены воспроизводимый native regression gate, трассировка и тесты границ.
Безусловный автоматический FALLBACK **отклонён**: на сохранённом ABA он теряет
второй голос. Это нарушает условие «не ухудшать продукт». Существующая адаптация
по нагрузке оставлена как была; новый режим под названием FAST не создан.

Исходная ревизия `58188d4`, ветка `feature/realtime-honor-20261105`.
Перед изменениями проверены status и процессы: только чужой untracked
`CODEX_REALTIME_PHONE_TASK_20261105.md`, активных Gradle/inference задач не было.
AGENTS.md в worktree и родительской цепочке не найден. Новых агентов/worktree нет.
Чужой файл не редактировался, его SHA-256:
`9a1b45aaf810da3760972bf31981e42b475fb5d21b9bd98ceb86c1b53328598d`.

## Что установлено

На неизменном syn3-clean Windows ORT 1.17.1 воспроизводит **2/3 и DER 57,210%**.
Повтор после добавления подробной трассировки дал побайтно те же TSV для всех
пяти конфигураций и исходного batch. Reference применяется только отдельным
scorer после inference; модель не получает число голосов, эталон или remap.

[FAST trace](evidence/realtime-fast-fix-20261106/syn3-traced/fast-trace.tsv):
на вызове 5 context=180 encoder frames, исторический slot 2 имеет **589**
положительных 10-мс строк, но новых фиксируемых строк slot 2 — **0**.
Модель пересматривает историю: 1512 бинарных решений отличаются от уже выданных.
На вызове 6 этот slot снова исчезает из истории, на 7 возвращается.
То есть это не просто пропущенная неизменная метка, которую можно безопасно дописать.

`NemotronStreaming.step` сохраняет только диапазон
`context*8 .. (context+count)*8`; переоценённые logits истории отбрасываются.
`RealtimeTranscript` затем замораживает атрибуцию фразы за committed boundary +650 мс.
Наблюдаемый механизм потери — **ранняя необратимая фиксация нестабильных speaker slots
короткого окна**. Внутреннюю причину нестабильности нейросети этот опыт не доказывает.
Простой пересмотр старых raw turns без изменения frontier стенограммы тоже недостаточен.

В этом FAST-прогоне cache не сжимается: 419 encoder frames всего, единственный
FIFO pop=222, cache=222 <264. Состояние не сбрасывается; right-context действительно
подаётся (408 mel frames = (45+6)*8), и будущий PCM не читается. Поэтому reset cache,
потеря PCM или компрессия cache не объясняют именно этот воспроизведённый случай.
Kotlin FIFO/update соответствует сохранённому pinned `diarize.py`, revision
`4a911fc3ca821b76a99fffd5ce5135bd1efca540`; сеть для исследования не использовалась.

Две однофакторные диагностические проверки, без перебора параметров:
возврат right=40 из batch при chunk=45 и chunk=120 из FALLBACK при right=6.
Обе возвращают 3 голоса на syn3, но первая ломает ABA, а вторая требует уже
10,096 с входа. Это не доказанный минимальный ремонт исходного FAST.
Безопасное продолжение потребует отдельного протокола provisional/final меток,
устойчивости IDs и ограниченного пересмотра истории, включая cache compression,
отмену и EOF. Такой протокол здесь не объявляется реализованным.

## До/после и ограничения метрик

DER — тот же scorer, широкие TTS-интервалы, collar ±250 мс, overlap учитывается.
Это **не human-labeled gold**. Число кластеров само по себе не доказывает правильность
идентичности голосов. ABA — сохранённая производная синтетика, не независимая речь.

| Host C2, fixture | FAST до → после диагностики: голоса; DER | FALLBACK: голоса; DER | 45/right40: голоса; DER | 120/right6: голоса; DER | Batch: голоса; DER |
|---|---|---|---|---|---|
| syn3-clean, 33,507 с | **2 → 2; 57,210 → 57,210%** | 3; 43,972% | 3; 46,561% | 3; 44,041% | 3; 31,947% |
| ABA, 12,950 с | 2; 52,854% (код неизменён) | **1; 54,161%** | **1; 53,849%** | 2; 41,508% | 2; 45,176% |
| syn4-noise, 57,324 с | 4; 40,959% (код неизменён) | 4; 40,922% | 4; 40,924% | 4; 40,943% | 4; 40,744% |

| syn3, Windows, C2-only | Compute RTF | CPU, с | Минимальный вход до первого вызова, с |
|---|---:|---:|---:|
| FAST, первый → повтор с трассировкой | 0,08258 → 0,07998 | 11,093 → 11,046 | 4,096 |
| FALLBACK | 0,03987 | 5,109 | 10,656 |
| 45/right40 | 0,08891 | 11,875 | 6,816 |
| 120/right6 | 0,03790 | 5,046 | 10,096 |

Host RTF — ускоренный replay C2 с mel/cache/диагностикой, без загрузки модели,
ASR и VAD; CPU — сумма процессорного времени потоков. Окно ожидания входа вычислено
из canStep, это не измеренная задержка UI/слов. PSS на Windows неприменим;
Android PSS/CPU/RTF и latency после исправления **NOT_RUN**, исправления нет.
Время — отдельные прогоны, не распределение; дополнительная трассировка влияет на cost.

Физический HONOR: только **архивные** single-trial цифры
[исходного отчёта](REALTIME_HONOR_2026-11-05.md): FAST 2/3, DER 57,14%, compute RTF
0,674, CPU 97,301 с, sampled PSS 1061,1 МиБ; FALLBACK 3/3, DER 44,07%, RTF 0,488,
CPU 67,977 с, PSS 920,9 МиБ. Новый телефонный прогон **NOT_RUN**: безопасного
кандидата нет, переустановка не нужна. Только read-only keyguard query, без UI,
разблокировки или обхода защиты; его неоднозначные поля не объявляются BLOCKED-тестом.
Микрофон, личная речь, stable package/data не затрагивались.

## Воспроизведение

Из текущего worktree, существующие JDK17/Gradle8.9/SDK35/ORT; без скачиваний.
Каждый `--out` должен быть новым: host.py теперь отказывается перезаписывать evidence.

```powershell
$fixtures = 'C:/Users/user/Documents/nuclear-neurostenographer/.local/synthetic-ru'
python -X utf8 tools/realtime/host.py --diagnostic --out .local/fast-fix-replay
python -X utf8 tools/realtime/score_host.py .local/fast-fix-replay "$fixtures/syn3-clean.reference.json"
# Ожидается exit 1: FAST speaker_count_gate=FAIL, это видимая регрессия.
python -X utf8 tools/realtime/host.py --diagnostic --fixture .local/realtime-fixtures/aba.wav --out .local/fast-fix-aba-replay
python -X utf8 tools/realtime/score_host.py .local/fast-fix-aba-replay docs/evidence/realtime-honor-20261105/fixture-references/aba.reference.json
python -X utf8 tools/realtime/host.py --diagnostic --fixture "$fixtures/syn4-noise.wav" --out .local/fast-fix-syn4-replay
python -X utf8 tools/realtime/score_host.py .local/fast-fix-syn4-replay "$fixtures/syn4-noise.reference.json"
python -X utf8 tools/realtime/build.py :core:runCoreTests :app:compileDebugKotlin :app:compileDebugAndroidTestKotlin :app:lintDebug
python -X utf8 -m unittest discover -s tools -p test_score_transcript.py
```

Исходные результаты: [syn3](evidence/realtime-fast-fix-20261106/syn3-baseline/scores.json),
[ABA](evidence/realtime-fast-fix-20261106/aba-baseline/scores.json),
[syn4](evidence/realtime-fast-fix-20261106/syn4-baseline/scores.json),
[повтор syn3](evidence/realtime-fast-fix-20261106/syn3-traced/scores.json).
`status=PASS` в старом формате native harness означает только выполненные assertions;
качество оценивается отдельно в `scores.json`, поле `speaker_count_gate`.

## Проверки и артефакты

- **FAIL**: регрессия качества FAST на неизменном syn3; безопасное исправление не найдено.
- **FAIL**: right40 и безусловный FALLBACK как универсальная замена — ABA 1/2.
- **PASS**: native OFFLINE точно совпал с исходным batch на всех трёх fixtures;
  повтор syn3 совпал по всем TSV. Production C2/streaming/scheduler не изменены.
- **PASS**: Kotlin core (16 групп, включая новые boundary tests), Android debug
  и instrumentation compile, lint (0 ошибок, 1 прежнее UsableSpace warning).
  [build.txt](evidence/realtime-fast-fix-20261106/build.txt),
  [lint](evidence/realtime-fast-fix-20261106/lint-debug.txt).
- **PASS**: 12 тестов scorer; [лог](evidence/realtime-fast-fix-20261106/scorer-tests.txt).
- Authored boundary tests проверяют exact mel slices, causal reads, идентичность
  FIFO embeddings через переключение FAST→FALLBACK, EOF с неполным sample/frame,
  отсутствие повторов выходных кадров, unknown и overlap. Существующие тесты
  проверяют побитовое сохранение PCM/disk recovery и длительные потоки.
- **NOT_RUN**: новая физическая приёмка HONOR, реальные встречи, полный новый
  ASR+C2 paced replay, human-gold DER. Не заменяются host результатами.

SHA-256 входа syn3:
`7b5d5f9c8d5a984d193c2a0e31afe5dc6e3c1fb068d9499d552f104c0a6c4ce9`.
SHA-256 модели:
`c465504c2f3a29242e1b3d894187ae5962be7320bed71a2ae203950285ee6025`.
ORT jar:
`a4e57e18a04b6c1b5b0e2885af1d8557873d4ca04bfcebf79743966c4c8eb20f`.
Все входные/source pins сохранены в `inputs.json` каждого прогона;
хэши TSV — в scores.json; итоговые файлы — в
[artifact-manifest.json](evidence/realtime-fast-fix-20261106/artifact-manifest.json).
Существующий APK `6e0730f5ca891d42f787b561ceac328fcf6f3a27c71ccf9cad46ff79a86e6231`
не пересобирался и не устанавливался. Push/PR/merge отсутствуют.
