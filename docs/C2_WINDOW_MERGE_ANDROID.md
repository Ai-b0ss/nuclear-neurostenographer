# C2 ASR window merge on Android 16

After the measured 150 ms C2 boundary padding, `C2WindowMerge` joins two adjacent ASR windows only when their gap is at most 400 ms, the joined span is at most 20 seconds, and both windows and the complete joined span are at least 90% covered by the same eligible speaker. Any competing speaker or ineligible turn prevents the join. C2 diarization turns and DER are unchanged; this changes the GigaAM input windows and their coarse attribution. The exported speaker provenance includes `window-merge400`.

The fixed policy was chosen on the existing 10-file Russian regression set. On the Android 16 API 36 16 KiB page emulator configured with 4 GiB RAM, C2 + 150 ms padding gave WER **45/525**, strict cpWER **76/380**, and summed ASR model load + decode **15.24 s**. With the 400 ms merge, these became **40/525**, **71/380**, and **14.76 s**. Every case kept its cpWER scoring status; no individual file worsened in WER or cpWER. These times are paired emulator measurements, not HONOR/Kirin timings.

Before testing the selected 400 ms policy on new audio, four additional three-voice acted compositions were frozen from previously unused clips in the pinned [Dialogs Russian test split](https://huggingface.co/datasets/langswap/dialogs-ru-emotional-conversations). `tools/fixtures/dialogs-ru-window-merge-holdout-lock.json` records source revision, selection ranks, source clip/WAV/reference SHA-256 and excludes prior fixture clips. The audio and reference texts remain ignored under `.local`. Source scripts are not manually re-audited; these are composed clips, not a natural conversation or DER reference.

| Held-out four files, 158 words | Current padded C2 | With 400 ms merge |
| --- | ---: | ---: |
| WER | 3/158 | 2/158 |
| Strict cpWER | 45/158 | 44/158 |
| ASR windows | 30 | 13 |
| Summed ASR load + decode | 5.30 s | 5.24 s |

The held-out gain is small but consistent, with no file-level regression in this set. This does not establish that all real meetings improve, that the scripts perfectly match spoken words, or that the phone meets a speed target. The change was promoted to the C2 product path; C0 and the manually supplied speaker-count path are unaffected. The full ViewModel path is checked by `C2PaddingFlowTest`.

Reproduction: run `python tools/nemotron/provision_window_merge_holdout.py` after obtaining the pinned source metadata/license. The script verifies the committed lock and provisions ignored WAV/reference files. Run the opt-in Android `C2WindowMergeProbeTest` with `-PnemotronPrototype=true -PnativeAsrCandidate=true -PdiarThresholdProbe=true`, and pass instrumentation argument `caseSet=holdout` for the frozen new files. Pull `files/c2-window-merge-holdout-evidence.json` before uninstall and score it with `python tools/nemotron/score_window_merge_holdout.py EVIDENCE.json`. The development run uses default `caseSet` and `tools/nemotron/score_c2_padding_asr.py`.
