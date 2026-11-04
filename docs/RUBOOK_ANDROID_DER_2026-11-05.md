# Independent Russian RTTM check on Android 16

The [ru-book-mix-10h dataset](https://huggingface.co/datasets/mexus/ru-book-mix-10h) provides generator RTTM with known speech and overlap boundaries under CC-BY-4.0. Four development IDs were fixed before the first run. Four more IDs were fixed after observing the development padding sweep but before their own inference and before the final production choice. The eight 60-second files include two each with 1, 2, 3 and 4 speakers. They are synthetic audiobook mixtures, not natural meetings. Source revision, split, IDs, WAV and reference hashes are frozen in `tools/fixtures/rubook-android-lock.json`; the WAVs, RTTM-derived references and device results stay ignored in `.local`.

On `honor10x_lite_api36_16k` (Android API 36, 4 GiB RAM, 16 KiB pages, x86_64), `RubookDerProbeTest` ran the same files through the current C0 and C2 isolated workers. `tools/nemotron/score_rubook_android.py` checked each WAV/reference digest and scored raw turns with 250 ms collar, overlap included, optimal speaker-label mapping. No reference transcript is available, so WER and cpWER are unscored.

| Development file | Speakers | C0 DER | C2 DER | C0 / C2 model load + infer |
| --- | ---: | ---: | ---: | ---: |
| `rec_0000` | 1 | 29.78% | 5.69% | 7.78 / 1.14 s |
| `rec_0055` | 2 | 23.66% | 3.29% | 7.15 / 1.11 s |
| `rec_0275` | 3 | 27.13% | 8.96% | 6.51 / 1.28 s |
| `rec_0437` | 4 | 32.27% | 13.69% | 6.53 / 1.12 s |
| **Pooled** | **count correct: 2/4 vs 4/4** | **28.17%** | **7.90%** | **27.97 / 4.65 s** |

The separate four-file holdout gave C0 DER **14.75%** and C2 DER **3.14%**. Extending each C2 turn by 150 ms at both ends, clipped to the recording, reduced C2 DER from **7.90% to 3.67%** on development and **3.14% to 0.79%** on holdout. Padding is pure interval postprocessing; it needs no extra model inference. A 200 ms candidate reduced holdout DER further to 0.51%, but failed the attribution check below.

`C2PaddingAsrProbeTest` then compared base and padded turns plus ASR windows on the separate frozen 10-file Russian text set (525 reference words). This set had been used for earlier ASR research, so it is a regression set rather than a pristine blind holdout for padding. With 150 ms, WER improved **48/525 to 45/525**; strictly scored cpWER stayed **76/380** on the same cases. Summed ASR model load + decode rose **14.44 to 15.08 s** in the paired emulator run. At 200 ms WER fell to 43/525, but one previously scored recording acquired unattributed words, so its cpWER became unscorable. The 150 ms value was promoted to the C2 product path; exported provenance now includes `boundary-pad150`. C0 and user-supplied speaker-count paths remain as before.

The paired result supports the existing choice of C2 in the C2 product variant, and the 150 ms postprocessing gives a measured gain on these fixtures. It does not establish phone speed or natural-meeting quality. Model timings came from sequential C0-then-C2 runs, so cache and run-order effects are possible. They exclude IPC, audio import, export and the app UI. A physical phone was not connected. The branch keeps C0 as fallback if C2 cannot load.

To reproduce locally, download `manifest.jsonl` and shards 0000–0002 from the pinned dataset revision into `.local/ru-book-mix`, run `python tools/nemotron/provision_rubook_android.py`, then run the opt-in instrumentation class `ru.neurostenographer.app.RubookDerProbeTest` with `-PnemotronPrototype=true -PnativeAsrCandidate=true -PdiarThresholdProbe=true`. Run with `-e caseSet holdout` for the held-out set. Pull `files/rubook-development-evidence.json` or `files/rubook-holdout-evidence.json` from the debug app before uninstalling it and run `python tools/nemotron/score_rubook_android.py EVIDENCE.json --split development|holdout`. The independent text probe is `C2PaddingAsrProbeTest`; score its evidence with `tools/nemotron/score_c2_padding_asr.py`.
