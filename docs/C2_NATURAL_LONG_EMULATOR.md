# Twenty-minute natural Russian call on Android 16 emulator

The opt-in long test uses the first 1200 seconds of `preview/ru_000010.mp3` from the pinned [DataHive multilingual conversations sample](https://huggingface.co/datasets/datahiveai/multilingual-conversations-sample), revision `1120cd7533b16ba8dd7a7c07e6d316b74b60f72a`, CC BY 4.0. `tools/nemotron/provision_natural_long_android.py` verifies the source MP3 SHA-256 `5561f59008a6df48f705217cccd0b7609a97dc22560d6d8a5698c368f5338415` and the bitexact 16 kHz mono WAV SHA-256 `e9933e55693151a6f2c5d0f34188348d62053b66a70d9dad0dd25ffd3a408df5`. Audio remains ignored in `.local`. The dataset provides no transcripts; this is a throughput, memory, and completion check, **not** a WER/cpWER/DER benchmark.

Earlier `.local/androidTestAssets/nemotron-bench/long-ru_000010.wav` was a 1190-second repetition of a short holdout for cancellation testing. It is not the natural DataHive call. Its preliminary run is excluded from the natural-call result below.

Both tests ran on `honor10x_lite_api36_16k`: Android API 36, x86_64, 4 GiB RAM, 16 KiB pages. `C2LongAsrProbeTest` ran C2 once, then A0 GigaAM CTC with the current 150 ms turn padding first without and then with the product's conservative 400 ms same-speaker window merge. The paired test saves no audio or transcript text in its evidence file.

| Scope | Without merge | With merge |
| --- | ---: | ---: |
| ASR input windows | 544 | 429 |
| ASR wall time | 24.918 s | 23.481 s |
| App PSS sample peak during ASR | 635,297 KiB | 670,056 KiB |
| Transcript segments / assigned speaker | 314 / 208 | 314 / 208 |

C2 worker wall time was 20.664 s; its simultaneous app-plus-worker PSS sample peaked at 607,429 KiB. The ASR wall reduction is 1.437 s (5.8%) in this sequential emulator run. Run-order/allocator effects make the PSS difference unsuitable as a causal memory claim. The two transcript text SHA-256 values differ, and no independent reference can say which text is better. Segment count is not an accuracy metric; 106 segments remain without a reliable speaker ID.

`C2LongProductFlowTest` then exercised the real `TranscriptionViewModel` import, C2+A0 inference, and TXT/JSON export twice. Both runs completed: import **0.796–0.824 s**, through export **45.228–46.192 s** (wall RTF **0.0377–0.0385**), app PSS sample peaks **687,922–711,900 KiB**, 314 transcript segments, 208 with a speaker ID, and nonempty exports. The second run saved a transcript-text SHA-256 matching the direct `merge400` inference exactly; raw text is not committed. The timer starts after model installation and after the test copied the source asset to a local file; it includes the application's import and model verification. Product peak samples cover the app process, not the isolated worker. The direct paired test above separately samples the simultaneous app-plus-worker PSS during C2.

This proves a 20-minute input completes through the current product logic on this emulator. It does not prove speed, thermal behaviour, memory, or recognition accuracy on the Kirin 710A HONOR. The product test used a debug build; the release APK is unsigned and was not installed for this run. A human-audited natural transcript and speaker reference are still needed before claiming natural-call WER, cpWER, or DER improvement.

Reproduction: run `python tools/nemotron/provision_natural_long_android.py`, build opt-in instrumentation with `-PnemotronPrototype=true -PnativeAsrCandidate=true -PdiarThresholdProbe=true`, then run `C2LongAsrProbeTest` and `C2LongProductFlowTest` on the 4 GiB API 36 16 KiB AVD. Pull `files/c2-natural-long-asr-evidence.json` and `files/c2-natural-long-product-evidence.json` from the debug app before uninstalling it. Run `python tools/nemotron/score_natural_long_android.py PAIRED.json PRODUCT.json` to verify WAV identity, product/direct text parity, and timings without inventing accuracy scores.
