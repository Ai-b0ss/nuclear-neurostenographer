# RuDevices conversational ASR probe (2026-11-05)

[SOVA RuDevices](https://github.com/sovaai/sova-dataset) is manually annotated
Russian live speech captured on nonprofessional devices. The authors did not
define an official train/test partition. This probe uses every one of the 47
records in the small tail shard of the third-party
[`Sh1man/rudevices` mirror](https://huggingface.co/datasets/Sh1man/rudevices),
revision `3d5a8ee75616a47d339c9c9a7f84fc75c0e93d43`, path
`rudevices_audio_records/test/test-00001.tar`, archive SHA-256
`4a37760aba6ec72d55d0911bd2941510ef3fbdf368bfed012ba42debb2a1cfcc`.
The committed lock records every source ID, WAV hash, and reference hash; the
5.9 MB source archive, WAVs, text, and raw Android evidence stay ignored in
`.local`. Total audio is 178.8 s and there are 389 reference words.

All heads ran on the same Android 16 API 36 x86_64, 4 GiB, 16 KiB page emulator.
Each run used C2 turns and the product's 150 ms boundary padding and 400 ms
same-speaker ASR window merge. A0 is the current GigaAM v3 CTC INT8; A3 is
GigaAM v3 RNN-T INT8 with two ASR threads; multilingual CTC is the 220M INT8
candidate. The three heads use the same native C++ sherpa C API. All 47 cases
had decoded windows. The A0 repetitions in the two paired runs agreed exactly
on total WER and differed by only 0.3 s in summed wall time.

| Head | WER errors / words | WER | Sum ASR wall time |
| --- | ---: | ---: | ---: |
| A0 CTC, product | 56 / 389 | 14.40% | 55.218 s (A3 pair) |
| A3 RNN-T | 52 / 389 | 13.37% | 57.292 s |
| Multilingual CTC | 68 / 389 | 17.48% | 56.133 s |

A3 improved six clips, worsened two, and tied 39 against A0. Its four-error
gain costs 3.8% more ASR wall time on this emulator. Multilingual CTC worsened
the total by twelve errors, so it remains rejected. Across this shard, the
earlier Golos farfield sample, and the prior 14 mixed/acted cases, A0 has
109/1252 WER errors and A3 has 104/1252. That pooled figure combines different
domains and is **not** a deployment metric. A3 remains a candidate; a five-word
pooled gain does not yet justify changing the roughly 225 MB product model.

These are short single-speaker fragments cut from live speech, not full
conversations. The archive has no verified speaker/timing annotations, so
cpWER/DER and conversation-level speaker consistency are not scored. The mirror
split is not guaranteed independent of model training. x86_64 emulator wall
time does not measure Kirin 710A speed. The next meaningful promotion gate is
a disjoint set of longer natural Russian conversations with independently
checked words and speaker turns, plus ARM64 performance evidence.

To reproduce: download the pinned shard to `.local/rudevices-test-tail.tar`,
run `python tools/nemotron/provision_rudevices_android.py` to verify the lock,
build opt-in instrumentation with `-PnemotronPrototype=true
-PnativeAsrCandidate=true -PasrHeadProbe=true`, and run
`AsrHeadProbeTest#compareAsrHeads` with `suite=rudevices-tail`, `backends=c2`,
`c2ProductPolicy=true`, and either `heads=a0,a3` plus `rnntThreads=2` or
`heads=a0,mctc`. The test verifies candidate model hashes. Pull
`files/asr-head-product-rudevices-tail-evidence.json` after each run and score
it with `python tools/nemotron/score_golos_farfield_android.py EVIDENCE.json`.
